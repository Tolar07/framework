"""
NATIONAL-TEAM STUDY — new national Elo vs the old UEFA Dixon-Coles fit.

Test set: competitive internationals between UEFA teams, 2024-01-01 to now
(Nations League, Euro and World Cup qualifiers, Euro finals). Neither model
sees a match before predicting it:
  * national Elo — ratings rolled forward match by match on ALL internationals
  * old model    — Dixon-Coles on UEFA home-venue matches since 2022 (what the
                   board used), refitted every quarter on data before the quarter
  * blend        — the average of the two scoreline grids
Scores: 1X2 Brier and log loss, and Brier for Over 2.5 and "no draw" (X or Y).

Run: python backtest/national_study.py  (writes backtest/NATIONAL_STUDY.md)
"""
from __future__ import annotations

import math
import os
import sys
from collections import defaultdict

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import national_elo as ne  # noqa: E402
from engine import dixon_coles as dc  # noqa: E402
from data.international_source import UEFA_MARKER_TOURNAMENTS, UEFA_MARKER_SINCE  # noqa: E402

TEST_FROM = "2024-01-01"
COMPETITIVE = ("UEFA Nations League", "UEFA Euro qualification", "UEFA Euro",
               "FIFA World Cup qualification")


class _R:  # MatchResult-like row for dc.fit
    def __init__(self, m):
        self.league, self.date, self.home_team, self.away_team = "INT", m.date, m.home, m.away
        self.fthg, self.ftag = m.hg, m.ag
        self.ftr = "H" if m.hg > m.ag else ("A" if m.ag > m.hg else "D")


def quarter(d: str) -> str:
    return f"{d[:4]}Q{(int(d[5:7]) - 1) // 3 + 1}"


def main():
    allm = ne.load()
    uefa = {t for m in allm if m.tournament in UEFA_MARKER_TOURNAMENTS and m.date >= UEFA_MARKER_SINCE
            for t in (m.home, m.away)}
    test = [m for m in allm if m.date >= TEST_FROM and m.tournament in COMPETITIVE
            and m.home in uefa and m.away in uefa]

    # rolling Elo
    elo, samples = ne.NationalElo(), []
    preds_elo = {}
    ti = {id(m) for m in test}
    for m in allm:
        if m.date >= "2005-01-01":
            samples.append((elo.gap(m.home, m.away, m.neutral), m.hg, m.ag))
        if id(m) in ti and elo.known(m.home) and elo.known(m.away):
            if not getattr(elo, "_goals_fit", False):
                elo.fit_goals(samples)
                elo._goals_fit = True
            lh, la = elo.lambdas(m.home, m.away, m.neutral)
            preds_elo[id(m)] = ne.score_matrix(lh, la)
        elo.update(m)

    # old model: quarterly DC refits
    preds_dc = {}
    by_q = defaultdict(list)
    for m in test:
        by_q[quarter(m.date)].append(m)
    for q, ms in sorted(by_q.items()):
        start = min(x.date for x in ms)
        train = [_R(x) for x in allm if "2022-01-01" <= x.date < start and not x.neutral
                 and x.home in uefa and x.away in uefa]
        model = dc.fit(train)
        for m in ms:
            p = dc.predict(model, m.home, m.away)
            if p is not None and p.matrix is not None:
                preds_dc[id(m)] = p.matrix

    both = [m for m in test if id(m) in preds_elo and id(m) in preds_dc]

    def scores(grid_of):
        b1 = ll = bo = bn = 0.0
        for m in both:
            g = grid_of(m)
            ph, pd, pa = float(np.tril(g, -1).sum()), float(np.trace(g)), float(np.triu(g, 1).sum())
            y = (m.hg > m.ag, m.hg == m.ag, m.hg < m.ag)
            b1 += sum((p - int(o)) ** 2 for p, o in zip((ph, pd, pa), y))
            ll += -math.log(max([ph, pd, pa][y.index(True)], 1e-9))
            tot = np.add.outer(np.arange(g.shape[0]), np.arange(g.shape[1]))
            po = float(g[tot > 2.5].sum())
            bo += (po - int(m.hg + m.ag > 2)) ** 2
            bn += ((1 - pd) - int(m.hg != m.ag)) ** 2
        n = len(both)
        return b1 / n, ll / n, bo / n, bn / n

    def pad(a, b):
        s = max(a.shape[0], b.shape[0])
        A, B = np.zeros((s, s)), np.zeros((s, s))
        A[:a.shape[0], :a.shape[1]] = a
        B[:b.shape[0], :b.shape[1]] = b
        return A, B

    rows = {"national Elo (new)": scores(lambda m: preds_elo[id(m)]),
            "UEFA Dixon-Coles (old)": scores(lambda m: preds_dc[id(m)]),
            "blend (average)": scores(lambda m: sum(pad(preds_elo[id(m)], preds_dc[id(m)])) / 2)}
    L = ["# NATIONAL-TEAM STUDY — new national Elo vs the old model", "",
         f"Test: {len(both)} competitive UEFA internationals since {TEST_FROM} "
         f"(Nations League, Euro + World Cup qualifiers, Euro finals); neither model "
         f"saw a match before predicting it. Lower is better.", "",
         "| Model | 1X2 Brier | 1X2 log loss | Over 2.5 Brier | 'no draw' Brier |",
         "|---|---|---|---|---|"]
    for k, (a, b, c, d) in rows.items():
        L.append(f"| {k} | {a:.4f} | {b:.4f} | {c:.4f} | {d:.4f} |")
    best = min(rows, key=lambda k: rows[k][1])
    L += ["", f"Best on log loss: **{best}**.", ""]
    open(os.path.join(ROOT, "backtest", "NATIONAL_STUDY.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
