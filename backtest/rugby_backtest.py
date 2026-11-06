"""
RUGBY walk-forward backtest (framework#344, multi-sport rollout; shadow from 2026-11-05, live 2026-11-12).

The multi-sport board rates rugby with the shared win-probability Elo (engine/multisport.py: K 24, start 1500,
MIN_GAMES rated games). This study replays every Premiership, URC, Top 14 and Champions Cup game ESPN lists
(free, final scores only) in date order, one rating pool for all four (Champions Cup links the leagues):

  - every setting tried is counted (K x home advantage); the best is chosen on the FIRST years and reported on
    the LATER years only (no peeking);
  - accuracy: Brier and hit rate of the Elo vs a "home side wins as often as it did in the tuning years" baseline;
  - draws (rare) are scored 0.5 for the Elo update and skipped for Brier.

No free historical rugby CLOSING odds exist, so this measures accuracy, not return. Return and closing-line
value come from the shadow board's own graded record. Record only: nothing here changes a stake, a bar,
a threshold or the live switch.

  python backtest/rugby_backtest.py      writes backtest/RUGBY_STUDY.md
"""
from __future__ import annotations

import itertools
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "backtest" / "RUGBY_STUDY.md"
LEAGUES = {"267979": "Premiership", "270557": "URC", "270559": "Top 14", "271937": "Champions Cup"}
YEARS = tuple(range(2014, 2026))
TUNE_YEARS = (2014, 2019)             # chosen here; 2020 onward is the held-out test
MIN_GAMES, ELO_START = 8, 1500.0
KS = (16.0, 24.0, 32.0)               # 24 = the live board's ELO_K
HOME = (0.0, 40.0, 70.0)              # the live board uses 0 (no home edge)
API = "https://site.api.espn.com/apis/site/v2/sports/rugby/{lg}/scoreboard?dates={y}&limit=1000"


def fetch_year(lg: str, y: int) -> list[dict]:
    req = urllib.request.Request(API.format(lg=lg, y=y), headers={"User-Agent": "olp-xdv-backtest"})
    with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310 (fixed https URL)
        return json.load(r).get("events", [])


def parse(events: list[dict], league: str) -> list[dict]:
    out = []
    for e in events:
        try:
            comp = e["competitions"][0]
            if not e["status"]["type"]["completed"]:
                continue
            side = {c["homeAway"]: c for c in comp["competitors"]}
            hs, as_ = float(side["home"]["score"]), float(side["away"]["score"])
            out.append({"day": e["date"][:10], "league": league, "home": side["home"]["team"]["displayName"],
                        "away": side["away"]["team"]["displayName"], "hs": hs, "as": as_})
        except (KeyError, ValueError, TypeError, IndexError):
            continue
    return out


def load(fetch=fetch_year) -> list[dict]:
    games, seen = [], set()
    for lg, name in LEAGUES.items():
        for y in YEARS:
            try:
                evs = fetch(lg, y)
            except Exception as ex:  # a year that will not load is PENDING, never invented
                print(f"{name} {y}: not loaded ({type(ex).__name__})")
                continue
            for g in parse(evs, name):
                key = (g["day"], g["home"], g["away"])
                if key not in seen:
                    seen.add(key)
                    games.append(g)
    games.sort(key=lambda g: (g["day"], g["home"]))
    for g in games:
        g["year"] = int(g["day"][:4])
        g["y"] = 0.5 if g["hs"] == g["as"] else float(g["hs"] > g["as"])
    return games


def replay(games: list[dict], k: float, home: float) -> list[float | None]:
    """Elo chance of a home win BEFORE each game (None while a side has < MIN_GAMES games), then learn."""
    r, n, out = {}, {}, []
    for g in games:
        h, a = g["home"], g["away"]
        rh, ra = r.get(h, ELO_START), r.get(a, ELO_START)
        e = 1 / (1 + 10 ** ((ra - rh - home) / 400))
        out.append(e if n.get(h, 0) >= MIN_GAMES and n.get(a, 0) >= MIN_GAMES else None)
        r[h], r[a] = rh + k * (g["y"] - e), ra - k * (g["y"] - e)
        n[h], n[a] = n.get(h, 0) + 1, n.get(a, 0) + 1
    return out


def evaluate(games, probs, years, base=0.5) -> dict:
    n = hits = 0
    b = b0 = 0.0
    for g, p in zip(games, probs):
        if p is None or g["y"] == 0.5 or not (years[0] <= g["year"] <= years[1]):
            continue
        n += 1
        b += (p - g["y"]) ** 2
        b0 += (base - g["y"]) ** 2
        hits += (p > 0.5) == (g["y"] == 1.0)
    return {"n": n, "brier": b / n if n else None, "base": b0 / n if n else None, "hit": hits / n if n else None}


def run(games: list[dict]) -> str:
    last = max(g["year"] for g in games)
    test = (TUNE_YEARS[1] + 1, last)
    tune_g = [g for g in games if TUNE_YEARS[0] <= g["year"] <= TUNE_YEARS[1] and g["y"] != 0.5]
    base = sum(g["y"] for g in tune_g) / len(tune_g) if tune_g else 0.5
    cache = {(k, h): replay(games, k, h) for k, h in itertools.product(KS, HOME)}
    tries = len(cache)
    tuned = {kh: evaluate(games, p, TUNE_YEARS) for kh, p in cache.items()}
    ok = {kh: t for kh, t in tuned.items() if t["n"] >= 100}
    best = min(ok, key=lambda kh: ok[kh]["brier"]) if ok else None
    live = evaluate(games, cache[(24.0, 0.0)], test, base)
    held = evaluate(games, cache[best], test, base) if best else None
    league_n = {nm: sum(1 for g in games if g["league"] == nm) for nm in LEAGUES.values()}
    home_rate = sum(g["y"] == 1.0 for g in games) / len(games)

    def line(name, r):
        if not r["n"]:
            return f"| {name} | 0 | PENDING | PENDING | PENDING |"
        return f"| {name} | {r['n']} | {r['brier']:.4f} | {r['base']:.4f} | {r['hit']:.1%} |"

    made = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    L = ["# Rugby walk-forward backtest", "",
         f"Made {made} by `backtest/rugby_backtest.py` (framework#344). {len(games)} games "
         f"({', '.join(f'{k} {v}' for k, v in league_n.items())}), final scores only (ESPN). Settings tried: "
         f"**{tries}** (K x home edge); chosen on {TUNE_YEARS[0]}-{TUNE_YEARS[1]}, reported on "
         f"**{test[0]}-{test[1]} only**. Home sides won {home_rate:.1%} of all games.", "",
         f"| Rule (held-out years) | Games rated | Brier | Brier flat home-edge baseline ({base:.1%}) | Winner hit rate |",
         "|---|---|---|---|---|",
         line("Live board: Elo K24, no home edge", live)]
    if held:
        L.append(line(f"Best on tuning years: K{best[0]:.0f}, home +{best[1]:.0f}", held))
    L += ["", "## Reading", ""]
    if live["n"]:
        beat = live["brier"] < live["base"]
        L.append(f"- Live-board Elo Brier {live['brier']:.4f} vs baseline {live['base']:.4f}: "
                 + ("the Elo carries information beyond the home edge." if beat else
                    "the Elo does NOT beat a flat home edge here; lean on the exchange price."))
    if held and live["n"] and best[1] > 0:
        L.append(f"- Tuning picked a home edge of {best[1]:.0f} Elo points; the live board uses none. "
                 f"Held-out Brier {held['brier']:.4f} vs {live['brier']:.4f} for the live setting.")
    L += [f"- {tries} settings tried; the held-out line is the honest one.",
          "- No free historical closing odds, so no return figure: return and CLV come from the shadow record.",
          "- Record only: nothing here changes a stake, a bar or the live switch."]
    return "\n".join(L) + "\n"


def main() -> int:
    games = load()
    if len(games) < 1000:
        print(f"only {len(games)} games read: NO DATA - PENDING")
        return 1
    text = run(games)
    OUT.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
