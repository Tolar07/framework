"""BTTS STUDY (2026-10-05): does the model's both-teams-to-score chance land?

Walk-forward, same leagues and seasons as selection_study.py (model fitted only
on matches before each 14-day block). football-data has no BTTS prices, so
this measures calibration and the fair odds needed, not profit. Results:
backtest/BTTS_STUDY.md. Run: python backtest/btts_study.py
"""
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))
from collections import defaultdict
from datetime import date, timedelta
from backtest.clv_backtest import BacktestConfig, get_model, refit_cut_dates
from backtest.selection_study import GROUPS
from data.football_data_source import load_league
from engine.dixon_coles import predict

cfg = BacktestConfig(leagues=(), carry_in_season="", test_season="", refit_every_days=14)
rows = []   # (league, season, p_btts, landed, p_o15, o15, p_o25, o25)
for carry_s, test_s, leagues in GROUPS:
    for lg in leagues:
        try:
            carry, _ = load_league(lg, carry_s); test, _ = load_league(lg, test_s)
        except Exception as e:
            print("skip", lg, test_s, e); continue
        hist = sorted(carry + test, key=lambda r: r.date); test = sorted(test, key=lambda r: r.date)
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
                t = m.fthg + m.ftag
                rows.append((lg, test_s, p.p_btts_yes, m.fthg > 0 and m.ftag > 0,
                             p.p_over_15, t >= 2, p.p_over_25, t >= 3))
        print("done", lg, test_s, flush=True)

def table(name, idx_p, idx_y):
    print(f"\n{name}: {len(rows)} matches, landed {sum(r[idx_y] for r in rows)/len(rows):.1%} overall")
    print(" model says   matches  landed   fair odds needed")
    for lo, hi in ((0, .4), (.4, .5), (.5, .55), (.55, .6), (.6, .65), (.65, .7), (.7, 1.01)):
        g = [r for r in rows if lo <= r[idx_p] < hi]
        if not g: continue
        hit = sum(r[idx_y] for r in g) / len(g)
        se = (hit * (1 - hit) / len(g)) ** .5
        print(f" {lo:.0%}-{min(hi,1):.0%}   {len(g):7d}  {hit:6.1%} ±{se:.1%}   {1/hit:.2f}")
table("BTTS yes", 2, 3); table("Over 1.5", 4, 5); table("Over 2.5", 6, 7)
by = defaultdict(lambda: [0, 0])
for r in rows:
    if r[2] >= .6: by[r[0]][0] += 1; by[r[0]][1] += r[3]
print("\nBTTS where the model says 60%+, by league:")
for lg, (n, w) in sorted(by.items(), key=lambda x: -x[1][0]): print(f"  {lg}: {n} matches, landed {w/n:.0%}")
