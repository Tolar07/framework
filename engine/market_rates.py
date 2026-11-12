"""
MARKET RATES - one model for every side of every market in every sport we cover (Architect 2026-11-12: "run this
model for all the markets ... in all the sports we are covering"). RECORD / PAPER ONLY: nothing here picks for a
bot, stakes or blocks.

It is the lower-league value idea (framework #584) made sport- and market-free: every market is a set of yes/no
sides (the Football-Markets-Catalogue rule), so for each side the model asks how often THIS side has happened

  - in the league, so far (needs MIN_LEAGUE priced games of that side),
  - in the home team's home games and the away team's away games, so far,

and blends them:  p = (SHRINK x league rate + home team's hits + away team's hits) / (SHRINK + their games).
A side's value at a price is p x price - 1. Walk-forward only: a game is rated from games that kicked off before it.

Keys: football keeps the ladder's exact key (its lines are fixed: "SB:18|total=2.5|Over 2.5"); every other sport's
numbers are folded ("total=#"), because their lines move game to game, so a side means "over the posted line".

Sources (both already graded by the framework):
  football, basketball   the SportyBet universe sweep (data/universe/graded_*.jsonl.gz; engine/universe.all_records)
  10 other sports        the multi-sport boards (output/multisport/<sport>/ms_*.json) and the ice hockey board
                         (output/ice_hockey/ih_*.json): every side SportyBet listed, first and last price, won 0/1.
Study: backtest/market_rates_study.py (re-run daily by monitor/stats_lists_run.py as the archive grows; its report
goes to the private data repo). best_side() is the pick a paper board would make: the study grades it walk-forward.
"""
from __future__ import annotations

import gzip
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UNIVERSE = ROOT / "data" / "universe"
MULTISPORT = ROOT / "output" / "multisport"
HOCKEY = ROOT / "output" / "ice_hockey"
SHRINK = 10.0
MIN_LEAGUE = 20
MIN_TEAM = 3
PRICE_MIN, PRICE_MAX = 1.20, 5.00
_NUM = re.compile(r"-?\d+(?:\.\d+)?")


def norm_key(sport: str, key: str) -> str:
    if sport == "football":
        return key
    return _NUM.sub("#", key)


def family(sport: str, key: str) -> str:
    """The market a side belongs to (for the report): football 'SB:18|total=2.5', others 'total' / '186|' ..."""
    k = norm_key(sport, key)
    return k.rsplit("|", 1)[0] if "|" in k else k


def _devig(key: str, sides: dict[str, float]) -> float | None:
    grp = key.rsplit("|", 1)[0]
    group = [v for k, v in sides.items() if k.rsplit("|", 1)[0] == grp and v and v > 1]
    if len(group) != 2 or not sides.get(key):
        return None                               # only clean two-way markets are de-margined here
    return (1 / sides[key]) / sum(1 / v for v in group)


def games_universe(folder: Path = UNIVERSE) -> list[dict]:
    """Graded football and basketball games: every settled side at SportyBet's last price."""
    from engine import universe as uv
    out, seen = [], set()
    for f in sorted(Path(folder).glob("graded_*.jsonl.gz")):
        with gzip.open(f, "rt", encoding="utf-8") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if r.get("id") in seen or r.get("sport") not in ("football", "basketball"):
                    continue
                seen.add(r.get("id"))
                which = "last" if r.get("last") else "first"
                sides = [(x["key"], x["won"], x["price"], x.get("fair")) for x in uv.all_records(r, which)]
                if sides:
                    out.append({"sport": r["sport"], "id": r["id"], "league": f"{r.get('country', '')}: {r.get('comp', '')}",
                                "ko": r.get("ko") or "", "home": r.get("home"), "away": r.get("away"), "sides": sides})
    return out


def _doc_games(sport: str, doc: dict) -> list[dict]:
    out = []
    for gid, g in (doc.get("games") or {}).items():
        priced = {k: ((s.get("last") or s.get("first") or {}).get("price")) for k, s in (g.get("sides") or {}).items()}
        priced = {k: v for k, v in priced.items() if v}
        sides = [(k, s["won"], priced[k], _devig(k, priced)) for k, s in (g.get("sides") or {}).items()
                 if s.get("won") is not None and k in priced]
        if sides:
            out.append({"sport": sport, "id": gid, "league": f"{g.get('country', '')}: {g.get('comp', '')}",
                        "ko": g.get("ko") or "", "home": g.get("home"), "away": g.get("away"), "sides": sides})
    return out


def games_boards(ms_dir: Path = MULTISPORT, ih_dir: Path = HOCKEY) -> list[dict]:
    """Graded games of the multi-sport and ice hockey boards (every side SportyBet listed)."""
    out, seen = [], set()
    files = [(d.name, f) for d in sorted(Path(ms_dir).glob("*")) if d.is_dir() for f in sorted(d.glob("ms_*.json"))]
    files += [("ice_hockey", f) for f in sorted(Path(ih_dir).glob("ih_*.json"))]
    for sport, f in files:
        try:
            doc = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for g in _doc_games(sport, doc):
            if (sport, g["id"]) not in seen:
                seen.add((sport, g["id"]))
                out.append(g)
    return out


def all_games() -> list[dict]:
    games = games_universe() + games_boards()
    games.sort(key=lambda g: g["ko"])
    return games


class Rates:
    """Running counts of every side: per league, per team at home / away."""

    def __init__(self):
        self.lg: dict[tuple, list] = {}
        self.tm: dict[tuple, list] = {}

    def add(self, g: dict) -> None:
        sp, lg = g["sport"], g["league"]
        for key, won, _price, _fair in g["sides"]:
            nk = norm_key(sp, key)
            for k, d in (((sp, lg, nk), self.lg), ((sp, lg, g["home"], "h", nk), self.tm),
                         ((sp, lg, g["away"], "a", nk), self.tm)):
                c = d.setdefault(k, [0, 0])
                c[0] += 1
                c[1] += won

    def predict(self, sport: str, league: str, home: str, away: str, key: str) -> dict | None:
        nk = norm_key(sport, key)
        n_l, w_l = self.lg.get((sport, league, nk), (0, 0))
        if n_l < MIN_LEAGUE:
            return None
        rate = (w_l + 1) / (n_l + 2)
        n_h, w_h = self.tm.get((sport, league, home, "h", nk), (0, 0))
        n_a, w_a = self.tm.get((sport, league, away, "a", nk), (0, 0))
        p = (SHRINK * rate + w_h + w_a) / (SHRINK + n_h + n_a)
        return {"p": p, "league_rate": rate, "league_n": n_l, "home_n": n_h, "away_n": n_a,
                "teams": n_h >= MIN_TEAM and n_a >= MIN_TEAM}


def best_side(rates: Rates, g: dict, sides: list[tuple[str, float]]) -> dict | None:
    """The side with the largest value at its price (both teams known, price in range), if above zero."""
    best = None
    for key, price in sides:
        if not price or not (PRICE_MIN <= price <= PRICE_MAX):
            continue
        m = rates.predict(g["sport"], g["league"], g["home"], g["away"], key)
        if not m or not m["teams"]:
            continue
        ev = m["p"] * price - 1
        if ev > 0 and (best is None or ev > best["value"]):
            best = {"key": key, "price": price, "model_p": round(m["p"], 4), "fair_odds": round(1 / m["p"], 2),
                    "value": round(ev, 4), "league_rate": round(m["league_rate"], 4), "league_n": m["league_n"],
                    "home_n": m["home_n"], "away_n": m["away_n"]}
    return best
