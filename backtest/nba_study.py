"""
NBA STUDY — can the football framework's method work on the NBA?
(Architect 2026-10-06: "look at basketball NBA ... see if we can adapt the framework")

Data: ESPN (free, keyless) — every regular-season game 2022-23 .. 2025-26 with
the closing ESPN BET line (moneyline, spread, total). data/nba_source.py.

Model: NBA Elo (FiveThirtyEight's published method): K 20, margin-of-victory
multiplier, home advantage, 25% regression to the mean between seasons.
2022-23 only warms the ratings up; 2023-24 learns the settings; 2024-25 and
2025-26 are the test (never seen while choosing anything).

Q1  Is the model any good next to the closing moneyline? (Brier, log loss)
Q2  The football recipe — chance = market + w x (model - market) — what w?
Q3  The football pick rule: a side priced 1.20-2.00 with a chance of 75%+.
    How often does it win, and what does it return at the closing price?
Q4  3-leg accas of those picks (order 40): hit rate and return.
Q5  Totals: how far does the final total land from the closing line? That
    sets the fair price of every line on SportyBet's points ladder.

Run: python backtest/nba_study.py   (writes backtest/NBA_STUDY.md)
"""
from __future__ import annotations

import math
import os
import random
import statistics as st
import sys
from collections import defaultdict
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from data import nba_source as ns  # noqa: E402

SEASONS = {2023: (date(2022, 10, 18), date(2023, 4, 9)),
           2024: (date(2023, 10, 24), date(2024, 4, 14)),
           2025: (date(2024, 10, 22), date(2025, 4, 13)),
           2026: (date(2025, 10, 21), date(2026, 4, 12))}
LEARN, TEST = (2024,), (2025, 2026)
BAND = (1.20, 2.00)
MIN_CHANCE = 0.75


class Elo:
    def __init__(self, k=20.0, hca=100.0, carry=0.75, mean=1505.0):
        self.k, self.hca, self.carry, self.mean = k, hca, carry, mean
        self.r: dict[str, float] = defaultdict(lambda: mean)
        self.season = None

    def p_home(self, h, a) -> float:
        return 1 / (1 + 10 ** (-(self.r[h] - self.r[a] + self.hca) / 400))

    def new_season(self, s):
        if self.season is not None and s != self.season:
            for t in list(self.r):
                self.r[t] = self.carry * self.r[t] + (1 - self.carry) * self.mean
        self.season = s

    def update(self, g):
        p = self.p_home(g.home, g.away)
        win = 1.0 if g.hs > g.as_ else 0.0
        mov = abs(g.hs - g.as_)
        diff = (self.r[g.home] + self.hca - self.r[g.away]) * (1 if win else -1)
        mult = ((mov + 3) ** 0.8) / (7.5 + 0.006 * diff)
        d = self.k * mult * (win - p)
        self.r[g.home] += d
        self.r[g.away] -= d


def devig(a, b):
    s = 1 / a + 1 / b
    return (1 / a) / s


def run_elo(games, **kw):
    """[(game, model p_home)] for every game, predicted BEFORE it is played."""
    m, out = Elo(**kw), []
    for g in games:
        m.new_season(g.season)
        out.append((g, m.p_home(g.home, g.away)))
        m.update(g)
    return out


def scores(rows):
    b = ll = 0.0
    for p, y in rows:
        b += (p - y) ** 2
        ll -= math.log(max(p if y else 1 - p, 1e-9))
    return b / len(rows), ll / len(rows)


def main():
    games = []
    for s, (a, b) in SEASONS.items():
        gs = [g for g in ns.season_games(a, b, with_odds=s != 2023) if g.stype == 2 and g.completed]
        print(f"season {s}: {len(gs)} games, {sum(1 for g in gs if g.ml_home)} with a closing line")
        games += gs
    games.sort(key=lambda g: (g.date, g.id))

    L = ["# NBA STUDY — can the football framework's method work on the NBA?", "",
         "Data: every NBA regular-season game 2022-23 to 2025-26 from ESPN, with the closing "
         "ESPN BET moneyline, spread and total. 2022-23 warms the ratings up, 2023-24 learns "
         "the settings, **2024-25 and 2025-26 are the test** (never used to choose anything).", ""]
    for s in SEASONS:
        n = sum(1 for g in games if g.season == s)
        k = sum(1 for g in games if g.season == s and g.ml_home and g.ml_away)
        L.append(f"- {s - 1}-{str(s)[2:]}: {n} games, {k} with a closing moneyline")
    L.append("")

    # --- settings learned on 2023-24 only ---
    best = None
    for hca in (40, 60, 80, 100):
        for k in (15, 20, 25):
            rows = [(p, int(g.hs > g.as_)) for g, p in run_elo(games, k=k, hca=hca) if g.season in LEARN]
            b, _ = scores(rows)
            if best is None or b < best[0]:
                best = (b, k, hca)
    _, K, HCA = best
    pred = run_elo(games, k=K, hca=HCA)
    priced = [(g, p, devig(g.ml_home, g.ml_away)) for g, p in pred
              if g.ml_home and g.ml_away and g.ml_home > 1 and g.ml_away > 1]
    learn = [x for x in priced if x[0].season in LEARN]
    test = [x for x in priced if x[0].season in TEST]

    # Q1
    L += ["## Q1 · The model next to the closing moneyline (test seasons)", "",
          f"Elo settings learned on 2023-24: K {K}, home advantage {HCA} Elo points.", "",
          "| Who predicts | Brier (lower = better) | log loss |", "|---|---|---|"]
    for name, f in (("Elo model alone", lambda x: x[1]), ("Closing line (margin removed)", lambda x: x[2])):
        b, ll = scores([(f(x), int(x[0].hs > x[0].as_)) for x in test])
        L.append(f"| {name} | {b:.4f} | {ll:.4f} |")
    L.append("")

    # Q2
    def blend(x, w):
        return x[2] + w * (x[1] - x[2])
    bw = min((w / 100 for w in range(0, 101, 5)),
             key=lambda w: scores([(blend(x, w), int(x[0].hs > x[0].as_)) for x in learn])[0])
    b0 = scores([(blend(x, 0.0), int(x[0].hs > x[0].as_)) for x in test])[0]
    bb = scores([(blend(x, bw), int(x[0].hs > x[0].as_)) for x in test])[0]
    b25 = scores([(blend(x, 0.25), int(x[0].hs > x[0].as_)) for x in test])[0]
    L += ["## Q2 · Football's recipe: chance = market + w × (model − market)", "",
          f"- best w on 2023-24: **{bw:.2f}**",
          f"- test Brier: market alone {b0:.4f} · w = 0.25 (football's) {b25:.4f} · "
          f"w = {bw:.2f} {bb:.4f}", ""]
    W = bw

    # Q3: football pick rule on moneylines
    def picks(rows, w, lo=BAND[0], hi=BAND[1], min_ch=MIN_CHANCE):
        out = []
        for x in rows:
            g = x[0]
            ch = blend(x, w)
            for side, c, price, won in (("home", ch, g.ml_home, g.hs > g.as_),
                                        ("away", 1 - ch, g.ml_away, g.as_ > g.hs)):
                if lo <= price <= hi and c >= min_ch:
                    out.append((g, side, c, price, won))
        return out

    def summary(ps):
        if not ps:
            return "none", 0.0
        n, w = len(ps), sum(1 for p in ps if p[4])
        ret = sum(p[3] for p in ps if p[4]) - n
        return f"{n} picks · won {w} ({100 * w / n:.1f}%) · avg chance {100 * st.mean(p[2] for p in ps):.1f}% · avg price {st.mean(p[3] for p in ps):.2f}", 100 * ret / n

    L += ["## Q3 · The football pick rule on NBA winners (price 1.20–2.00, chance 75%+)", "",
          "Returns are at ESPN BET's closing price. SportyBet's price for the same side is "
          "usually a little lower, so treat these as the best case.", "",
          "| Season | Picks | Return per £1 |", "|---|---|---|"]
    allp = []
    for s in TEST:
        ps = picks([x for x in test if x[0].season == s], W)
        allp += ps
        txt, roi = summary(ps)
        L.append(f"| {s - 1}-{str(s)[2:]} | {txt} | {roi:+.1f}% |")
    txt, roi = summary(allp)
    L += [f"| **both** | {txt} | **{roi:+.1f}%** |", ""]
    L += ["By price bracket (both test seasons):", "", "| Price | Picks | Return per £1 |", "|---|---|---|"]
    for lo, hi in ((1.20, 1.25), (1.25, 1.30), (1.30, 1.36), (1.36, 2.0)):
        ps = [p for p in allp if lo <= p[3] < hi]
        txt, r = summary(ps)
        L.append(f"| {lo:.2f}–{hi:.2f} | {txt} | {r:+.1f}% |")
    L.append("")
    mkt_only = []
    for s in TEST:
        mkt_only += picks([x for x in test if x[0].season == s], 0.0)
    txt0, roi0 = summary(mkt_only)
    L += [f"Same rule on the market's chance alone (no model): {txt0} · return {roi0:+.1f}%.", ""]

    # Q4: 3-leg accas
    by_day = defaultdict(list)
    for p in allp:
        by_day[p[0].date].append(p)
    n_acca = won_acca = 0
    ret = 0.0
    for d, ps in sorted(by_day.items()):
        ps = sorted(ps, key=lambda p: -p[2])
        for i in range(0, len(ps) - 2, 3):
            g = ps[i:i + 3]
            n_acca += 1
            if all(p[4] for p in g):
                won_acca += 1
                ret += math.prod(p[3] for p in g)
    L += ["## Q4 · 3-leg accas of those picks (order 40), same day, strongest first", ""]
    if n_acca:
        L += [f"{n_acca} accas · won {won_acca} ({100 * won_acca / n_acca:.1f}%) · "
              f"return per £1 {100 * (ret - n_acca) / n_acca:+.1f}%", ""]
    else:
        L += ["Not enough picks on one day to form an acca.", ""]

    # Q5: totals
    res = [(g.hs + g.as_) - g.total for g in games if g.season in TEST and g.total]
    sd = st.pstdev(res)
    L += ["## Q5 · Totals: where the final score lands against the closing line", "",
          f"{len(res)} test games. Final total minus the closing line: mean {st.mean(res):+.1f}, "
          f"spread (standard deviation) **{sd:.1f} points**.", "",
          "| Line vs closing total | Over landed | Fair price (Over) |", "|---|---|---|"]
    for k in (-12.5, -9.5, -6.5, -3.5, 0, 3.5, 6.5):
        hits = sum(1 for r in res if r > k)
        p = hits / len(res)
        L.append(f"| {k:+.1f} | {100 * p:.1f}% | {1 / p:.2f} |" if p else f"| {k:+.1f} | 0% | — |")
    L.append("")
    L += ["The fair price on any line of SportyBet's points ladder follows from this table: "
          "a pick there is only worth it when SportyBet pays MORE than the fair price.", ""]

    open(os.path.join(ROOT, "backtest", "NBA_STUDY.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    random.seed(0)
    main()
