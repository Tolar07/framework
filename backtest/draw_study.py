"""
DRAW STUDY — do team profiles predict draws beyond the market?
(Architect 2026-10-04: draws sank the no-draw "X or Y" picks.)

Clubs: every cached football-data league, seasons 23/24, 24/25, 25/26.
The market's draw chance = Pinnacle closing 1X2 with the margin removed
(the sharpest free estimate). The profile's draw tendency = the two teams'
draw share over their last 20 games BEFORE the match (no look-ahead).

Q1  Bucketed by (profile tendency - market), is the real draw rate above
    the market's when the profiles say "draw-prone"?
Q2  Fit pD' = pD + k x (tendency - league mean) on 23/24+24/25, test the
    Brier score of the draw / no-draw call on 25/26.
Q3  Same with bet365's OPENING price (what we bet into), since the closing
    price already knows more than we do at 10pm.

Run: python backtest/draw_study.py  (writes backtest/DRAW_STUDY.md)
"""
from __future__ import annotations

import csv
import glob
import os
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine.profiles import ProfileBook, club_rows, match_profile  # noqa: E402

TRAIN, TEST = ("2324", "2425"), ("2526",)


def f(x):
    try:
        v = float(x)
        return v if v > 1 else None
    except (TypeError, ValueError):
        return None


def devig(*o):
    s = sum(1 / x for x in o)
    return [1 / x / s for x in o]


def load():
    by_league = defaultdict(list)
    for p in glob.glob(os.path.join(ROOT, "data", "cache", "*.csv")):
        name = os.path.basename(p)[:-4]
        season = name[-4:]
        if not season.isdigit():
            continue
        by_league[name[:-5]].append((season, p))
    data = []
    for league, files in by_league.items():
        book = ProfileBook(club_rows([p for _, p in sorted(files)]))
        for season, p in files:
            if season not in TRAIN + TEST:
                continue
            with open(p, encoding="utf-8-sig", errors="replace") as fh:
                for r in csv.DictReader(fh):
                    try:
                        hg, ag = int(r["FTHG"]), int(r["FTAG"])
                    except (KeyError, TypeError, ValueError):
                        continue
                    psc = [f(r.get(k)) for k in ("PSCH", "PSCD", "PSCA")]
                    bo = [f(r.get(k)) for k in ("B365H", "B365D", "B365A")]
                    if not all(psc) or not all(bo):
                        continue
                    d = r.get("Date", "")
                    dd, mm, yy = d.split("/")
                    yy = ("20" + yy) if len(yy) == 2 else yy
                    iso = f"{yy}-{mm.zfill(2)}-{dd.zfill(2)}"
                    mp = match_profile(book, r["HomeTeam"], r["AwayTeam"], before=iso)
                    if mp.draw_tendency is None:
                        continue
                    data.append({"season": season, "league": league.replace("_", " "),
                                 "pD_close": devig(*psc)[1], "pD_open": devig(*bo)[1],
                                 "tend": mp.draw_tendency, "draw": int(hg == ag)})
    return data


def brier(rows, key, k=0.0, mean_t=0.0):
    tot = 0.0
    for r in rows:
        p = min(max(r[key] + k * (r["tend"] - mean_t), 0.01), 0.99)
        tot += (p - r["draw"]) ** 2
    return tot / len(rows)


def main():
    data = load()
    tr = [r for r in data if r["season"] in TRAIN]
    te = [r for r in data if r["season"] in TEST]
    mean_t = sum(r["tend"] for r in tr) / len(tr)
    L = ["# DRAW STUDY — do team profiles predict draws beyond the market?", "",
         f"Matches with a profile for both teams and Pinnacle + bet365 prices: "
         f"{len(data)} (learn {len(tr)}, test {len(te)})", ""]

    L += ["## Q1 · Real draw rate vs the market, by profile signal (all seasons)",
          "| profile tendency − market (close) | n | market says | real draws |",
          "|---|---|---|---|"]
    buckets = [(-1, -0.05), (-0.05, 0.0), (0.0, 0.05), (0.05, 0.10), (0.10, 1)]
    for lo, hi in buckets:
        xs = [r for r in data if lo <= r["tend"] - r["pD_close"] < hi]
        if xs:
            L.append(f"| {lo:+.2f} to {hi:+.2f} | {len(xs)} | "
                     f"{100 * sum(r['pD_close'] for r in xs) / len(xs):.1f}% | "
                     f"{100 * sum(r['draw'] for r in xs) / len(xs):.1f}% |")
    L.append("")

    for key, label in (("pD_close", "Pinnacle closing"), ("pD_open", "bet365 opening")):
        best_k, best_b = 0.0, brier(tr, key)
        for k in [x / 100 for x in range(0, 61, 5)]:
            b = brier(tr, key, k, mean_t)
            if b < best_b - 1e-6:
                best_k, best_b = k, b
        base_te, adj_te = brier(te, key), brier(te, key, best_k, mean_t)
        L += [f"## {'Q2' if key == 'pD_close' else 'Q3'} · {label}: add the profile signal?",
              f"- best weight learned on 23/24+24/25: k = {best_k:.2f}",
              f"- test 25/26 Brier (draw / no draw): market alone {base_te:.5f} · "
              f"market + profile {adj_te:.5f} "
              f"({'better' if adj_te < base_te - 1e-5 else 'no better'})", ""]
    L += ["## Q4 · By league: are draws under-priced (real − market, Pinnacle close)?",
          "| League | learn n | learn real−market | test n | test real−market |",
          "|---|---|---|---|---|"]
    lg = defaultdict(list)
    for r in data:
        lg[r["league"]].append(r)
    steady = []
    for name in sorted(lg):
        a = [r for r in lg[name] if r["season"] in TRAIN]
        b = [r for r in lg[name] if r["season"] in TEST]
        if len(a) < 150 or len(b) < 80:
            continue
        da = sum(r["draw"] - r["pD_close"] for r in a) / len(a)
        db = sum(r["draw"] - r["pD_close"] for r in b) / len(b)
        L.append(f"| {name} | {len(a)} | {da*100:+.1f} pts | {len(b)} | {db*100:+.1f} pts |")
        if da > 0.02 and db > 0.02:
            steady.append(name)
    tot = sum(r["draw"] - r["pD_close"] for r in data) / len(data)
    L += ["", f"All leagues: real draws {tot*100:+.1f} pts vs the closing price. "
          f"Leagues under-pricing draws by 2+ pts in BOTH periods: {', '.join(steady) or 'none'}.", ""]
    open(os.path.join(ROOT, "backtest", "DRAW_STUDY.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
