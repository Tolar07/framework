"""SOT STUDY (2026-10-05): does a shots-on-target rating (engine/sot_model.py),
blended 50/50 with Dixon-Coles like Understat xG, predict better than
Dixon-Coles alone in leagues Understat doesn't cover? Walk-forward like
production (last season + this season to the cut, 240-day half-life, ridge 3,
refit every 14 days). Scored on 1X2 log loss and Over 2.5 Brier, per league.
Results: backtest/SOT_STUDY.md. Run: python backtest/sot_study.py
"""
import math
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest.clv_backtest import refit_cut_dates  # noqa: E402
from data.football_data_source import load_league  # noqa: E402
from engine import sot_model, xg_model  # noqa: E402
from engine.dixon_coles import fit, predict  # noqa: E402
from orchestrator import RECENCY_HALF_LIFE_DAYS, RIDGE  # noqa: E402

CACHE = sot_model.CACHE
PAIRS = [("2425", "2526", ["Championship", "Eredivisie", "Primeira Liga",
                           "Scottish Premiership", "Belgian Pro League"]),
         ("2526", "2627", ["Championship", "League One", "League Two", "National League",
                           "La Liga 2", "Serie B", "2. Bundesliga", "Ligue 2",
                           "Eredivisie", "Primeira Liga", "Scottish Premiership",
                           "Belgian Pro League", "Turkish Super Lig", "Greek Super League"])]


def score(q, y, over):
    p = (q.p_home, q.p_draw, q.p_away)
    return -math.log(max(p[y], 1e-9)), (q.p_over_25 - over) ** 2


def main():
    stats = defaultdict(lambda: [0, 0.0, 0.0, 0.0, 0.0])  # n, ll_dc, ll_blend, br_dc, br_blend
    for carry_s, test_s, leagues in PAIRS:
        for lg in leagues:
            try:
                carry, _ = load_league(lg, carry_s)
                test, _ = load_league(lg, test_s)
            except Exception:
                continue
            stem = lg.replace(" ", "_")
            rows = sot_model.rows_from_csv([CACHE / f"{stem}_{carry_s}.csv",
                                            CACHE / f"{stem}_{test_s}.csv"])
            if len(rows) < 100:
                print("no shots data:", lg, test_s, flush=True)
                continue
            test = sorted(test, key=lambda r: r.date)
            for cut in refit_cut_dates([r.date for r in test], 14):
                end = (date.fromisoformat(cut) + timedelta(days=14)).isoformat()
                block = [r for r in test if cut <= r.date < end]
                window = carry + [r for r in test if r.date < cut]
                if not block or len(window) < 50:
                    continue
                try:
                    model = fit(window, half_life_days=RECENCY_HALF_LIFE_DAYS, ref_date=cut,
                                ridge=RIDGE)
                except Exception:
                    continue
                sr = sot_model.ratings_from_rows(rows, cut)
                for m in block:
                    p = predict(model, m.home_team, m.away_team)
                    if p is None:
                        continue
                    xm = sr.matrix(m.home_team, m.away_team) if sr else None
                    if xm is None:
                        continue
                    b = xg_model.blend(p, xm)
                    y = 0 if m.fthg > m.ftag else 1 if m.fthg == m.ftag else 2
                    over = float(m.fthg + m.ftag > 2)
                    l1, b1 = score(p, y, over)
                    l2, b2 = score(b, y, over)
                    s = stats[f"{lg} {test_s}"]
                    for k, v in enumerate((1, l1, l2, b1, b2)):
                        s[k] += v
            print("done", lg, test_s, flush=True)
    tot = np.array([v for v in stats.values()]).sum(axis=0)
    print(f"\nALL: n={int(tot[0])} 1X2 log loss DC {tot[1]/tot[0]:.4f} blend {tot[2]/tot[0]:.4f} | "
          f"O2.5 Brier DC {tot[3]/tot[0]:.4f} blend {tot[4]/tot[0]:.4f}")
    by_lg = defaultdict(lambda: [0, 0.0, 0.0, 0.0, 0.0])
    for k, v in stats.items():
        lg = k.rsplit(" ", 1)[0]
        by_lg[lg] = [a + b for a, b in zip(by_lg[lg], v, strict=True)]
    for lg, v in sorted(by_lg.items()):
        n = v[0]
        print(f"{lg:22s} n={n:4d} ll DC {v[1]/n:.4f} blend {v[2]/n:.4f} ({(v[2]-v[1])/n:+.4f}) | "
              f"O2.5 Brier DC {v[3]/n:.4f} blend {v[4]/n:.4f} ({(v[4]-v[3])/n:+.4f})")


if __name__ == "__main__":
    main()
