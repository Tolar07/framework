"""
DRAW LEAGUE STUDY — which draws are worth backing? (Architect 2026-10-11:
"those leagues that have more draws ... see if they are viable ... create a
separate table for them").

Data: football-data.co.uk results + prices, every main-league season since
2015/16 (mmz4281/<season>/<code>.csv saved as <code>_<season>.csv) and the
extra-league files (new/<CC>.csv saved as new_<CC>.csv), in one folder.
Bet price = bet365's draw (the closest free proxy for SportyBet); market
chance = Pinnacle's closing 1X2 with the margin removed (bookmaker average
when Pinnacle is missing).

A  Every draw, by league: real draws vs the market, £1 return.
B  Walk-forward: pick "draw leagues" from the 4 seasons before, bet them the
   next season - can the league alone be used?
C  Filters chosen on seasons to 2021, tested on 2022 on - which GAMES draw?
D  The rule TABLE 3E uses, by season and by league, and as 2-leg doubles.

Run: python backtest/draw_league_study.py <folder of csvs>
     (writes backtest/DRAW_LEAGUE_STUDY.md)
"""
from __future__ import annotations

import csv
import glob
import math
import os
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAMES = {"E0": "Premier League", "E1": "Championship", "E2": "League One", "E3": "League Two",
         "EC": "National League", "SC0": "Scottish Prem", "SC1": "Scottish Champ", "SC2": "Scottish L1",
         "SC3": "Scottish L2", "D1": "Bundesliga", "D2": "2. Bundesliga", "I1": "Serie A", "I2": "Serie B",
         "SP1": "La Liga", "SP2": "La Liga 2", "F1": "Ligue 1", "F2": "Ligue 2", "N1": "Eredivisie",
         "B1": "Belgian Pro League", "P1": "Primeira Liga", "T1": "Super Lig", "G1": "Greek Super League"}
GAP, U25 = 0.10, 1.70          # the TABLE 3E rule (output/produce_bet.py DRAW_*)


def f(x):
    try:
        v = float(x)
        return v if v > 1 else None
    except (TypeError, ValueError):
        return None


def devig(o):
    s = sum(1 / x for x in o)
    return [1 / x / s for x in o]


def load(folder: str) -> list[dict]:
    rows = []
    for p in glob.glob(os.path.join(folder, "*.csv")):
        b = os.path.basename(p)[:-4]
        with open(p, encoding="utf-8-sig", errors="replace") as fh:
            for r in csv.DictReader(fh):
                if b.startswith("new_"):
                    lg = " ".join((r.get("Country", "") + " " + r.get("League", "")).split())
                    s = (r.get("Season") or "")[-4:]
                    if not s.isdigit():
                        continue
                    season, hg, ag = int(s), r.get("HG"), r.get("AG")
                    bet = f(r.get("B365CD")) or f(r.get("AvgCD"))
                    fair = [f(r.get(k)) for k in ("PSCH", "PSCD", "PSCA")]
                    if not all(fair):
                        fair = [f(r.get(k)) for k in ("AvgCH", "AvgCD", "AvgCA")]
                    u25 = None
                else:
                    c, s = b.split("_")
                    if c not in NAMES:
                        continue
                    lg, season, hg, ag = NAMES[c], 2000 + int(s[2:]), r.get("FTHG"), r.get("FTAG")
                    bet = f(r.get("B365D"))
                    fair = [f(r.get(k)) for k in ("PSCH", "PSCD", "PSCA")]
                    for alt in (("AvgCH", "AvgCD", "AvgCA"), ("AvgH", "AvgD", "AvgA"), ("BbAvH", "BbAvD", "BbAvA")):
                        if not all(fair):
                            fair = [f(r.get(k)) for k in alt]
                    u25 = f(r.get("Avg<2.5")) or f(r.get("BbAv<2.5"))
                try:
                    hg, ag = int(hg), int(ag)
                except (TypeError, ValueError):
                    continue
                if not bet or not all(fair):
                    continue
                pr = devig(fair)
                rows.append({"lg": lg, "season": season, "draw": hg == ag, "bet": bet, "pD": pr[1],
                             "gap": abs(pr[0] - pr[2]), "u25": u25, "date": r.get("Date", "")})
    return rows


def stat(R):
    n = len(R)
    if not n:
        return None
    x = [(r["bet"] - 1) if r["draw"] else -1 for r in R]
    return (n, sum(r["draw"] for r in R) / n, sum(r["pD"] for r in R) / n, sum(x) / n,
            math.sqrt(sum(v * v for v in x) / n) / math.sqrt(n))


def rule(r) -> bool:
    return r["gap"] < GAP and r["u25"] is not None and r["u25"] <= U25


def main(folder: str) -> None:
    rows = load(folder)
    L = ["# DRAW LEAGUE STUDY — which draws are worth backing?", "",
         f"Written by `backtest/draw_league_study.py`: {len(rows):,} matches, "
         f"{len({r['lg'] for r in rows})} leagues, seasons {min(r['season'] for r in rows)}–"
         f"{max(r['season'] for r in rows)} (football-data.co.uk). Bet at bet365's draw price; "
         "market = Pinnacle close, margin removed. ± is one standard error.", ""]
    by = defaultdict(list)
    for r in rows:
        by[r["lg"]].append(r)
    L += ["## A · Every draw, by league (300+ matches)", "",
          "| League | matches | real draws | market said | real − market | £1 return ± se |",
          "|---|---|---|---|---|---|"]
    for lg, R in sorted(by.items(), key=lambda t: -stat(t[1])[3]):
        n, w, m, ret, se = stat(R)
        if n >= 300:
            L.append(f"| {lg} | {n} | {w:.1%} | {m:.1%} | {100 * (w - m):+.1f} pts | {ret:+.1%} ± {se:.1%} |")
    n, w, m, ret, se = stat(rows)
    L += [f"| **ALL** | {n} | {w:.1%} | {m:.1%} | {100 * (w - m):+.1f} pts | {ret:+.1%} ± {se:.1%} |", "",
          "The market prices draws almost exactly; backing every draw loses the margin.", ""]
    L += ["## B · Walk-forward: can the LEAGUE pick the draws?", "",
          "Each season, back every draw in the leagues whose draws made money (and landed 1+ pt above "
          "the market) over the 4 seasons before.", "",
          "| test season | leagues picked | bets | draws | £1 return |", "|---|---|---|---|---|"]
    tot = []
    for t in range(2019, max(r["season"] for r in rows) + 1):
        pick = []
        for lg, R in by.items():
            past = [r for r in R if t - 4 <= r["season"] < t]
            if len(past) >= 300:
                s = stat(past)
                if s[3] > 0 and s[1] - s[2] > 0.01:
                    pick.append(lg)
        T = [r for r in rows if r["season"] == t and r["lg"] in pick]
        if T:
            n, w, m, ret, se = stat(T)
            tot += T
            L.append(f"| {t} | {', '.join(sorted(pick))} | {n} | {w:.1%} | {ret:+.1%} |")
    n, w, m, ret, se = stat(tot)
    L += [f"| **all** | | {n} | {w:.1%} | **{ret:+.1%} ± {se:.1%}** |", "",
          "No: a league's draw history does not carry into the next season.", ""]
    L += ["## C · Which GAMES draw? (filter fixed on seasons to 2021, tested on 2022 on)", "",
          "| filter | to-2021 bets | to-2021 return | 2022-on bets | draws | 2022-on return ± se |",
          "|---|---|---|---|---|---|"]
    F = {"every game": lambda r: True,
         "draw price ≤ 3.20": lambda r: r["bet"] <= 3.2,
         "evenly matched (win chances within 10 pts)": lambda r: r["gap"] < 0.10,
         "priced low-scoring (Under 2.5 ≤ 1.75)": lambda r: r["u25"] and r["u25"] <= 1.75,
         "market draw chance ≥ 32%": lambda r: r["pD"] >= 0.32,
         "market draw chance < 22%": lambda r: r["pD"] < 0.22,
         "evenly matched + Under 2.5 ≤ 1.75": lambda r: r["gap"] < 0.10 and r["u25"] and r["u25"] <= 1.75,
         "**evenly matched + Under 2.5 ≤ 1.70 (TABLE 3E)**": rule,
         "evenly matched + Under 2.5 ≤ 1.65": lambda r: r["gap"] < 0.10 and r["u25"] and r["u25"] <= 1.65}
    for name, fn in F.items():
        a = stat([r for r in rows if r["season"] <= 2021 and fn(r)])
        b = stat([r for r in rows if r["season"] >= 2022 and fn(r)])
        if a and b:
            L.append(f"| {name} | {a[0]} | {a[3]:+.1%} | {b[0]} | {b[1]:.1%} | {b[3]:+.1%} ± {b[4]:.1%} |")
    T = [r for r in rows if rule(r)]
    L += ["", "## D · The TABLE 3E rule", "", "| season | games | draws | £1 return |", "|---|---|---|---|"]
    for s in sorted({r["season"] for r in T}):
        x = stat([r for r in T if r["season"] == s])
        if x and x[0] >= 100:
            L.append(f"| {s} | {x[0]} | {x[1]:.1%} | {x[3]:+.1%} |")
    L += ["", "| league (150+ games) | games | draws | £1 return |", "|---|---|---|---|"]
    bl = defaultdict(list)
    for r in T:
        bl[r["lg"]].append(r)
    for lg, R in sorted(bl.items(), key=lambda t: -len(t[1])):
        x = stat(R)
        if x[0] >= 150:
            L.append(f"| {lg} | {x[0]} | {x[1]:.0%} | {x[3]:+.1%} |")
    byd = defaultdict(list)
    for r in T:
        if r["season"] >= 2022:
            byd[r["date"]].append(r)
    n = w = 0
    ret = 0.0
    for R in byd.values():
        for i in range(0, len(R) - 1, 2):
            a, b = R[i], R[i + 1]
            hit = a["draw"] and b["draw"]
            n += 1
            w += hit
            ret += (a["bet"] * b["bet"] - 1) if hit else -1
    if n:
        L += ["", f"**2-leg draw doubles** (2022 on, same-day games paired): {n} doubles, "
              f"{w} landed ({w / n:.1%}, about 1 in {round(n / max(w, 1))}), £1 return {ret / n:+.1%}.", ""]
    L += ["## Verdict", "",
          "- The league is not the edge; the type of game is. Evenly matched sides in a game priced "
          "low-scoring draw about 1 in 3, and beat bet365's price in both periods.",
          "- The edge is thin (one to two standard errors) and the latest seasons were negative. "
          "So TABLE 3E is a minimal-stake test, graded as its own line (`draws` in the picks ledger) and as "
          "paper rule F14 / paper acca A5 on every game worldwide.",
          "- A draw double lands about 1 time in 9. Expect long losing runs; judge it on 100+ bets.",
          "- SportyBet's 1X2 margin averaged 4.3% on our covered leagues but 8.7% across all its football "
          "(10-11 Oct 2026 sweep). The table skips any 1X2 book above 9%."]
    with open(os.path.join(ROOT, "backtest", "DRAW_LEAGUE_STUDY.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    print(f"wrote backtest/DRAW_LEAGUE_STUDY.md ({len(rows):,} matches)")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "data", "cache", "football_data"))
