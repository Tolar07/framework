"""SHRINK STUDY (2026-10-05): does pulling team ratings toward the league
average (dixon_coles.fit ridge=) predict better, especially for promoted clubs
and early-season matches? Walk-forward like production: fit on last season +
this season up to the cut, 240-day half-life, refit every 14 days. Scored on
1X2 log loss and Brier. Results: backtest/SHRINK_STUDY.md.
Run: python backtest/shrink_study.py <ridge> <out.json>
"""
import json
import math
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest.clv_backtest import refit_cut_dates  # noqa: E402
from backtest.selection_study import GROUPS  # noqa: E402
from data.football_data_source import load_league  # noqa: E402
from engine.dixon_coles import fit, predict  # noqa: E402

ridge = float(sys.argv[1])
rows = []
for carry_s, test_s, leagues in GROUPS:
    for lg in leagues:
        try:
            carry, _ = load_league(lg, carry_s)
            test, _ = load_league(lg, test_s)
        except Exception:
            continue
        test = sorted(test, key=lambda r: r.date)
        carry_teams = {r.home_team for r in carry} | {r.away_team for r in carry}
        for cut in refit_cut_dates([r.date for r in test], 14):
            end = (date.fromisoformat(cut) + timedelta(days=14)).isoformat()
            block = [r for r in test if cut <= r.date < end]
            window = carry + [r for r in test if r.date < cut]
            if not block or len(window) < 50:
                continue
            try:
                model = fit(window, half_life_days=240, ref_date=cut, ridge=ridge)
            except Exception:
                continue
            played = {}
            for r in window:
                for t in (r.home_team, r.away_team):
                    played[t] = played.get(t, 0) + 1
            for m in block:
                p = predict(model, m.home_team, m.away_team)
                if p is None:
                    continue
                y = 0 if m.fthg > m.ftag else 1 if m.fthg == m.ftag else 2
                q = (p.p_home, p.p_draw, p.p_away)
                new = (m.home_team not in carry_teams) or (m.away_team not in carry_teams)
                rows.append([lg, test_s, cut, new, min(played.get(m.home_team, 0), played.get(m.away_team, 0)),
                             -math.log(max(q[y], 1e-9)), sum((q[k] - (k == y)) ** 2 for k in range(3))])
        print("done", lg, test_s, flush=True)
json.dump(rows, open(sys.argv[2], "w"))
