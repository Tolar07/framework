"""
BASEBALL walk-forward backtest vs the closing moneyline (framework#352, multi-sport rollout; record-only).

Source: ESPN's public MLB scoreboard (every finished regular-season and play-off game, 2019-2025) and, per game,
ESPN's odds record (the pre-game bookmakers' moneylines; the CLOSE where ESPN keeps one, else the last pre-game line;
the median over the bookmakers is used, live-odds lines and projections left out). The free archive that went back to
2010 (sportsbookreviewsonline.com) refuses scripts, so it is not used. Every game is replayed in date order:

  - team Elo (K x home edge x pull back to the start between seasons), each setting tried is counted, then the same
    Elo blended with the de-vigged closing moneyline (market weight);
  - the best setting is chosen on the FIRST seasons (2019-2022) and reported on the LATER seasons (2023-2025) only;
  - judged by Brier / log loss against the de-vigged close (the "source of truth"), then a flat-stake test: back a
    side when the model beats the de-vigged close by an edge bar, (a) at the closing bookmaker price (margin in) and
    (b) at the fair close less 2% commission on winnings (an exchange-like price, the bots' venue).

Sides are visitor (a) and home (b) as ESPN lists them, never winner-first. A game without both closing prices is
skipped, never filled (HR35); a season that will not load reads PENDING, never invented (HR59). Record only: nothing
here changes a stake, a bar, a threshold or the live switch.

  python backtest/baseball_backtest.py      writes backtest/BASEBALL_STUDY.md
"""
from __future__ import annotations

import itertools
import json
import statistics
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import results_walkforward as wf  # noqa: E402
from backtest.tennis_backtest import blend, devig, num  # noqa: E402

OUT = ROOT / "backtest" / "BASEBALL_STUDY.md"
CACHE = ROOT / "backtest" / "cache" / "espn_mlb"
BOARD = "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard?dates={d}"
ODDS = "https://sports.core.api.espn.com/v2/sports/baseball/leagues/mlb/events/{e}/competitions/{e}/odds"
UA = "Mozilla/5.0 (olp-xdv record-only backtest; github.com/Tolar07/framework)"
SKIP_PROVIDERS = ("live", "consensus", "numberfire", "teamrankings")
SEASONS = tuple(range(2019, 2026))
TUNE = (2019, 2022)                      # chosen here; 2023 onward is the held-out test
KS = (4.0, 8.0, 12.0)
HOME = (0.0, 24.0)                       # Elo points for the home side
CARRY = (1.0, 0.67)                      # share of a rating kept into the next season
MKT_W = (0.0, 0.25, 0.5)
EDGES = (0.03, 0.05)
MIN_GAMES = 10
COMMISSION = 0.02


def american(x) -> float | None:
    """US moneyline -> decimal price (None when missing or not a number)."""
    v = num(x)
    if v is None or abs(v) < 100:
        return None
    return 1 + v / 100 if v > 0 else 1 + 100 / -v


def _get(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": UA})  # noqa: S310 (fixed https URL)
    with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310 (fixed https ESPN host)
        return json.loads(r.read())


def cached(name: str, url: str, get=None):
    """One ESPN answer, kept in backtest/cache/ (not committed) so a re-run does not fetch it again."""
    f = CACHE / name
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    for wait in (0, 2, 10):
        time.sleep(wait)
        try:
            d = (get or _get)(url)
            break
        except Exception:  # noqa: BLE001 — retried, then PENDING
            d = None
    if d is None:
        return None
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(d), encoding="utf-8")
    return d


def games_of_day(board: dict) -> list[dict]:
    """Finished regular-season and play-off games of one ESPN scoreboard (spring training left out)."""
    out = []
    for e in (board or {}).get("events") or []:
        if (e.get("season") or {}).get("type") not in (2, 3):
            continue
        c = (e.get("competitions") or [{}])[0]
        if not ((c.get("status") or e.get("status") or {}).get("type") or {}).get("completed"):
            continue
        side = {t.get("homeAway"): t for t in c.get("competitors") or []}
        h, a = side.get("home"), side.get("away")
        if not h or not a:
            continue
        sh, sa = num(h.get("score")), num(a.get("score"))
        if sh is None or sa is None or sh == sa:
            continue
        out.append({"id": str(e["id"]), "key": e.get("date", "")[:16], "season": int((e.get("season") or {})["year"]),
                    "a": (a.get("team") or {}).get("abbreviation", ""), "b": (h.get("team") or {}).get("abbreviation", ""),
                    "y": 1.0 if sa > sh else 0.0, "neutral": bool(c.get("neutralSite"))})
    return out


def close_prices(odds: dict) -> tuple[float, float] | None:
    """(visitor, home) closing decimal prices: the median over the pre-game bookmakers ESPN keeps (live-odds lines,
    projections and the consensus figure left out). The 'close' line where ESPN has one, else the last line."""
    va, vh = [], []
    for it in (odds or {}).get("items") or []:
        name = str((it.get("provider") or {}).get("name", ""))
        if any(x in name.lower() for x in SKIP_PROVIDERS):
            continue
        ao, ho = it.get("awayTeamOdds") or {}, it.get("homeTeamOdds") or {}

        def last(o):
            c = ((o.get("close") or {}).get("moneyLine") or {}).get("american")
            return american(c if c not in (None, "") else o.get("moneyLine"))
        pa, ph = last(ao), last(ho)
        if pa and ph and 1 / pa + 1 / ph < 1.15:          # a two-way book; anything wider is not a pre-game price
            va.append(pa)
            vh.append(ph)
    if not va:
        return None
    return statistics.median(va), statistics.median(vh)


def load(get=None, seasons=SEASONS) -> tuple[list[dict], list[str]]:
    """All finished games with a closing price, in date order (+ notes on what did not load)."""
    notes: list[str] = []
    games: list[dict] = []
    for s in seasons:
        day, end = date(s, 3, 15), date(s, 11, 10)
        found = priced = 0
        todo = []
        while day <= end:
            d = day.strftime("%Y%m%d")
            b = cached(f"sb_{d}.json", BOARD.format(d=d), get)
            for g in games_of_day(b) if b else []:
                if g["season"] == s:
                    todo.append(g)
            day += timedelta(days=1)
        with ThreadPoolExecutor(max_workers=4) as pool:
            got = list(pool.map(lambda g: cached(f"odds_{g['id']}.json", ODDS.format(e=g["id"]), get), todo))
        for g, o in zip(todo, got, strict=True):
            found += 1
            cp = close_prices(o) if o else None
            if cp:
                g["pa"], g["pb"] = cp
                games.append(g)
                priced += 1
        if found == 0:
            notes.append(f"{s}: no games loaded - PENDING")
        elif priced < found:
            notes.append(f"{s}: {found - priced} of {found} games without a closing price (skipped)")
    games.sort(key=lambda g: (g["key"], g["a"], g["b"]))
    for g in games:
        g["mkt"] = devig(g["pa"], g["pb"])
    return games, notes


def _as_home(games: list[dict]) -> list[dict]:
    """The replay's `home` flag is for side a; here side b is at home, so flip sides for the replay."""
    return [{"key": g["key"], "season": g["season"], "a": g["b"], "b": g["a"], "home": not g["neutral"],
             "y": 1.0 - g["y"]} for g in games]


def probs_for(games: list[dict], k: float, home: float, carry: float) -> list[float | None]:
    """Chance that the visitor (side a) wins, before each game."""
    hp = wf.replay(_as_home(games), k, MIN_GAMES, home, carry)
    return [None if p is None else 1 - p for p in hp]


def evaluate(games, probs, seasons, mw=0.0) -> dict:
    rows, mrows = [], []
    for g, p in zip(games, probs, strict=True):
        if p is None or not (seasons[0] <= g["season"] <= seasons[1]):
            continue
        rows.append((blend(p, g["mkt"], mw), g["y"]))
        mrows.append((g["mkt"], g["y"]))
    r = wf.score(rows)
    r["mkt_ll"], r["mkt_brier"], r["mkt_hit"] = (wf.score(mrows)[x] for x in ("ll", "brier", "hit"))
    return r


def bets(games, probs, seasons, mw, edge) -> dict:
    """Flat 1-unit bets where model chance - de-vigged close >= edge: at the bookmaker close, and at the fair close
    less commission on winnings."""
    n = 0
    book = fair = 0.0
    for g, p in zip(games, probs, strict=True):
        if p is None or not (seasons[0] <= g["season"] <= seasons[1]):
            continue
        q = blend(p, g["mkt"], mw)
        for sp, sm, price, won in ((q, g["mkt"], g["pa"], g["y"] == 1.0), (1 - q, 1 - g["mkt"], g["pb"], g["y"] == 0.0)):
            if sp - sm >= edge:
                n += 1
                book += (price - 1) if won else -1.0
                fair += (1 / sm - 1) * (1 - COMMISSION) if won else -1.0
    return {"n": n, "book": book / n if n else None, "fair": fair / n if n else None}


def run(games: list[dict], notes: list[str] | None = None) -> str:
    last = max(g["season"] for g in games)
    test = (TUNE[1] + 1, last)
    elo = list(itertools.product(KS, HOME, CARRY))
    cache = {c: probs_for(games, *c) for c in elo}
    combos = [c + (w,) for c in elo for w in MKT_W]
    tries = len(combos) + len(EDGES) * 2
    tuned = {c: evaluate(games, cache[c[:3]], TUNE, c[3]) for c in combos}
    ok = {c: t for c, t in tuned.items() if t["n"] >= 1000}
    best_elo = min((c for c in ok if c[3] == 0.0), key=lambda c: ok[c]["ll"], default=None)
    best = min(ok, key=lambda c: ok[c]["ll"]) if ok else None
    re_ = evaluate(games, cache[best_elo[:3]], test, 0.0) if best_elo else None
    rb = evaluate(games, cache[best[:3]], test, best[3]) if best else None
    made = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    n_test = sum(1 for g in games if test[0] <= g["season"] <= test[1])

    def line(name, r):
        if not r or not r["n"]:
            return f"| {name} | 0 | PENDING | PENDING | PENDING | PENDING | PENDING |"
        return (f"| {name} | {r['n']} | {r['brier']:.4f} | {r['ll']:.4f} | {r['hit']:.1%} | {r['mkt_brier']:.4f} | "
                f"{r['mkt_ll']:.4f} |")

    def label(c):
        s = f"K{c[0]:g}, home +{c[1]:g}, carry {c[2]:.0%}"
        return s + (f", market weight {c[3]:.0%}" if len(c) > 3 else "")

    L = ["# Baseball (MLB) walk-forward backtest", "",
         f"Made {made} by `backtest/baseball_backtest.py` (framework#352). {len(games)} MLB games {SEASONS[0]}-{last} "
         f"with both closing moneylines (ESPN scoreboard + ESPN odds record, median pre-game bookmaker; fetched in this run, cached in `backtest/cache/espn_mlb/`). Tries counted: "
         f"**{tries}** (K x home edge x season carry x market weight, then the edge bars on two models); chosen on "
         f"{TUNE[0]}-{TUNE[1]}, reported on **{test[0]}-{test[1]} only** ({n_test} games).", ""]
    if notes:
        L += ["Not loaded: " + "; ".join(notes), ""]
    L += ["| Rule (held-out seasons) | Games | Brier | Log loss | Hit rate | Close Brier | Close log loss |",
          "|---|---|---|---|---|---|---|"]
    if best_elo:
        L.append(line(f"Best Elo alone on tuning seasons: {label(best_elo[:3])}", re_))
    if best:
        L.append(line(f"Best on tuning seasons: {label(best)}", rb))
    if rb and rb["n"]:
        L += ["", f"The closing favourite won {rb['mkt_hit']:.1%} of the same held-out games."]
    L += ["", "## Flat-stake test (model vs the de-vigged close)", "",
          "| Setting | Edge bar | Bets | ROI at the bookmaker close | ROI at fair close less 2% commission |",
          "|---|---|---|---|---|"]
    for name, c in (("Best Elo alone", best_elo), ("Best on tuning seasons", best)):
        if not c:
            continue
        for e in EDGES:
            r = bets(games, cache[c[:3]], test, c[3], e)
            L.append(f"| {name} | {e:.0%} | {r['n']} | {wf.fmt(r['book'], '+.1%')} | {wf.fmt(r['fair'], '+.1%')} |")
    L += ["", "## Reading", ""]
    if re_ and re_["n"]:
        L.append(f"- Elo alone log loss {re_['ll']:.4f} vs the close {re_['mkt_ll']:.4f}: "
                 + ("the Elo beats the closing price." if re_["ll"] < re_["mkt_ll"] else
                    "the closing price is the better chance; a team Elo (no pitchers) adds nothing on its own."))
    if rb and rb["n"]:
        L.append(f"- Market-anchored best setting log loss {rb['ll']:.4f} vs the close {rb['mkt_ll']:.4f}: "
                 + ("some information beyond the price held-out." if rb["ll"] < rb["mkt_ll"] - 0.0005 else
                    "no information beyond the price held-out: price baseball off the exchange."))
    L += [f"- {tries} tries made; the held-out lines are the honest ones, and any ROI above is one of them, not a "
          "result to bank.",
          "- A team Elo has no starting-pitcher input, which is where MLB prices move most; bookmaker closes carry a "
          "margin, the fair-close column takes it out and charges 2% commission instead.",
          "- Record only: nothing here changes a stake, a bar, a threshold or the live switch."]
    return "\n".join(L) + "\n"


def main() -> int:
    games, notes = load()
    if len(games) < 5000:
        print(f"only {len(games)} games read: NO DATA - PENDING ({'; '.join(notes)})")
        return 1
    text = run(games, notes)
    OUT.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
