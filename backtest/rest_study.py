"""REST STUDY (2026-10-05): do rest days or fixture congestion predict results the
model misses? Walk-forward, same leagues/seasons as selection_study.py. Results:
backtest/REST_STUDY.md. Run: python backtest/rest_study.py <out.json>
"""
import sys, json
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))
from datetime import date, timedelta
from backtest.clv_backtest import BacktestConfig, get_model, refit_cut_dates
from backtest.selection_study import GROUPS
from data.football_data_source import load_league
from engine.dixon_coles import predict
cfg = BacktestConfig(leagues=(), carry_in_season="", test_season="", refit_every_days=14)
rows = []
for carry_s, test_s, leagues in GROUPS:
    for lg in leagues:
        try:
            carry, _ = load_league(lg, carry_s); test, _ = load_league(lg, test_s)
        except Exception as e:
            continue
        hist = sorted(carry + test, key=lambda r: r.date); test = sorted(test, key=lambda r: r.date)
        last = {}; recent = {}
        prev = {}
        for r in hist:   # rest = days since each team's previous league match
            for t in (r.home_team, r.away_team):
                prev[(r.date, r.home_team, r.away_team, t)] = last.get(t)
                last[t] = r.date
            for t in (r.home_team, r.away_team):
                recent.setdefault(t, []).append(r.date)
        def games_in(t, d, days):
            d0 = (date.fromisoformat(d) - timedelta(days=days)).isoformat()
            return sum(1 for x in recent.get(t, []) if d0 <= x < d)
        warm = None
        for cut in refit_cut_dates([r.date for r in test], 14):
            end = (date.fromisoformat(cut) + timedelta(days=14)).isoformat()
            block = [r for r in test if cut <= r.date < end]
            if not block: continue
            model, _ = get_model(lg, cut, hist, cfg, warm)
            if model is None: continue
            warm = getattr(model, "warm_seed", None) or warm
            for m in block:
                p = predict(model, m.home_team, m.away_team)
                if p is None: continue
                ph = prev.get((m.date, m.home_team, m.away_team, m.home_team))
                pa = prev.get((m.date, m.home_team, m.away_team, m.away_team))
                if not ph or not pa: continue
                rh = (date.fromisoformat(m.date) - date.fromisoformat(ph)).days
                ra = (date.fromisoformat(m.date) - date.fromisoformat(pa)).days
                rows.append([lg, m.date, rh, ra, games_in(m.home_team, m.date, 14), games_in(m.away_team, m.date, 14),
                             p.p_home, p.p_draw, p.p_away, m.fthg, m.ftag])
json.dump(rows, open(sys.argv[1], "w"))
print(len(rows))
