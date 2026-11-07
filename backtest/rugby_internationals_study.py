"""
RUGBY internationals Elo study (framework#344, record-only).

The Rugby issue lists internationals in scope, but every rugby study so far rated clubs only. National teams play
~8-12 games a year, often on neutral grounds, so K (rating speed) and the home edge may differ from clubs. Here
Six Nations, Rugby Championship, World Cup and other Test matches (ESPN, free, final scores only) are replayed in
date order; K and home edge are chosen on 2014-2019 (every try counted) and reported on 2020+ only. Record only:
nothing here changes a stake, bar, threshold or live switch.

  python backtest/rugby_internationals_study.py      writes backtest/RUGBY_INTERNATIONALS_STUDY.md
"""
from __future__ import annotations

import itertools
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import rugby_backtest as rb  # noqa: E402

OUT = ROOT / "backtest" / "RUGBY_INTERNATIONALS_STUDY.md"
LEAGUES = {"180659": "Six Nations", "244293": "Rugby Championship", "164205": "Rugby World Cup",
           "289234": "Test Match"}
KS = (16.0, 24.0, 32.0, 48.0)
HOME = (0.0, 40.0, 70.0, 100.0)
MIN_N = 100


def load(fetch=rb.fetch_year) -> list[dict]:
    games, seen = [], set()
    for lg, name in LEAGUES.items():
        for y in rb.YEARS:
            try:
                evs = fetch(lg, y)
            except Exception as ex:  # a year that will not load is PENDING, never invented
                print(f"{name} {y}: not loaded ({type(ex).__name__})")
                continue
            for g in rb.parse(evs, name):
                key = (g["day"], frozenset((g["home"], g["away"])))
                if key not in seen:
                    seen.add(key)
                    games.append(g)
    games.sort(key=lambda g: (g["day"], g["home"]))
    for g in games:
        g["year"] = int(g["day"][:4])
        g["y"] = 0.5 if g["hs"] == g["as"] else float(g["hs"] > g["as"])
    return games


def run(games: list[dict]) -> str:
    last = max((g["year"] for g in games), default=rb.TUNE_YEARS[1])
    test = (rb.TUNE_YEARS[1] + 1, last)
    tune_g = [g for g in games if rb.TUNE_YEARS[0] <= g["year"] <= rb.TUNE_YEARS[1] and g["y"] != 0.5]
    base = sum(g["y"] for g in tune_g) / len(tune_g) if tune_g else 0.5
    cache = {(k, h): rb.replay(games, k, h) for k, h in itertools.product(KS, HOME)}
    tries = len(cache)
    tuned = {kh: rb.evaluate(games, p, rb.TUNE_YEARS) for kh, p in cache.items()}
    ok = {kh: t for kh, t in tuned.items() if t["n"] >= MIN_N}
    best = min(ok, key=lambda kh: ok[kh]["brier"]) if ok else None
    club = rb.evaluate(games, cache[(32.0, 70.0)], test, base)   # the club-tuned setting
    held = rb.evaluate(games, cache[best], test, base) if best else None
    made = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    n_by = {nm: sum(1 for g in games if g["league"] == nm) for nm in LEAGUES.values()}
    L = ["# Rugby internationals Elo study", "",
         f"Made {made} by `backtest/rugby_internationals_study.py` (framework#344). {len(games)} national-team games "
         f"({', '.join(f'{k} {v}' for k, v in n_by.items())}), final scores only (ESPN). Settings tried: **{tries}** "
         f"(K x home edge); chosen on {rb.TUNE_YEARS[0]}-{rb.TUNE_YEARS[1]}, reported on "
         f"**{test[0]}-{test[1]} only**.", "",
         f"| Rule (held-out years) | Games | Brier | Brier flat baseline ({base:.1%}) | Winner hit rate |",
         "|---|---|---|---|---|"]
    rows = [("Club setting: K32, home +70", club)]
    if held and best != (32.0, 70.0):
        rows.append((f"Best on tuning years: K{best[0]:.0f}, home +{best[1]:.0f}", held))
    for nm, r in rows:
        L.append(f"| {nm} | {r['n']} | {r['brier']:.4f} | {r['base']:.4f} | {r['hit']:.1%} |" if r["n"]
                 else f"| {nm} | 0 | PENDING | PENDING | PENDING |")
    L += ["", "## Reading", ""]
    if held and club["n"]:
        gain = club["brier"] - held["brier"]
        L.append(f"- Internationals pick K{best[0]:.0f}, home +{best[1]:.0f}; held-out Brier changed {gain:+.4f} vs the club "
                 "setting " + ("(a shadow candidate for national-team matches, to be confirmed on the shadow board)."
                               if gain > 0.0005 else "(no real help: the club setting is fine)."))
        L.append(f"- Elo vs flat home-edge baseline on held-out: {club['brier']:.4f} vs {club['base']:.4f} "
                 + ("(the Elo carries information)." if club["brier"] < club["base"] else "(no better than the baseline)."))
    else:
        L.append("- PENDING: too little tuning data.")
    L += [f"- {tries} settings tried; the held-out line is the honest one.",
          "- Record only: nothing here changes a stake, a bar or the live switch."]
    return "\n".join(L) + "\n"


def main() -> int:
    games = load()
    if len(games) < 500:
        print(f"only {len(games)} games read: NO DATA - PENDING")
        return 1
    text = run(games)
    OUT.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
