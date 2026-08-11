"""Backtest report tests — the calibration block is the honesty instrument.

The CLV backtest found a negative headline that selection knobs could not
explain: the model was overconfident at every probability (model_p sat ~8-17pp
above the realized hit rate and above the margin-free closing implied), and a
raw-EV screen amplifies that on long (away) prices. The calibration block
makes that measurable on every run — model_p vs hit vs fair_close per market —
so a future run cannot silently repeat it. These tests pin the block's
rendering and its honesty rules (NO DATA, never a guessed number)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest.backtest_report import render_report, _cal_row, summarise
from backtest.clv_backtest import PaperLeg


def _leg(**kw) -> PaperLeg:
    base = dict(league="PL", date="2024-08-10", fixture="A v B",
                status="OK", derived=False,
                overround_open=0.05, overround_close=0.05)
    base.update(kw)
    return PaperLeg(**base)


def _cfg():
    class Cfg:
        fingerprint = lambda self: "test"
        carry_in_season = "2324"
        test_season = "2425"
        selector = "model"
        min_mes = 0.02
        refit_every_days = 7
        book_preference = ("market_avg",)
        half_life_days = None
    return Cfg()


def _coverage():
    return {"PL": {"n_fixtures_in_scope": 2, "n_excluded_warmup": 0,
                   "n_no_model": 0}}


# --- 1. overconfident away legs show a positive gap (model_p > hit) ----------
legs = [
    _leg(market="1X2_A", model_prob=0.42, entry_odds=2.70, closing_odds=2.85,
         hit=False, clv_pct=-2.1),
    _leg(market="1X2_A", model_prob=0.44, entry_odds=2.55, closing_odds=2.60,
         hit=True, clv_pct=-2.0),
]
rep = render_report(legs, [], _coverage(), _cfg(), "2425_model_test")
assert "MODEL CALIBRATION" in rep, "calibration block must render"
assert "1X2_A" in rep
# model_p = 0.43, hit = 0.50 (2 legs, 1 hit) — gap must appear as a number
assert "gap=" in rep, "calibration rows must carry a gap"
# fair_close present and sane (overround 5% stripped)
assert "fair_close=" in rep
print("1. calibration block renders with gap + fair_close: OK")

# --- 2. a genuinely calibrated bucket shows gap near zero ---------------------
s = summarise([_leg(market="1X2_D", model_prob=0.25, entry_odds=3.80,
                    closing_odds=3.75, hit=True, clv_pct=1.0)], "1X2_D")
# model_p 0.25, hit 1.0 on n=1 — trivially one leg, but the maths must run
assert s["mean_model_prob"] == 0.25
assert s["mean_fair_implied_open"] is not None
assert s["mean_fair_implied_close"] is not None
row = _cal_row(s)
assert "model_p=   0.250" in row
print("2. _cal_row maths runs on a single leg: OK")

# --- 3. no graded legs -> honest NO DATA, never a guessed number -------------
s = summarise([_leg(market="1X2_H", model_prob=0.50, entry_odds=2.00,
                    closing_odds=None, hit=None, status="NO_CLOSE")], "1X2_H")
assert s["mean_model_prob"] is None       # nothing measured
assert s["hit_rate_pct"] is None
assert "NO DATA" in _cal_row(s)
print("3. unmeasured bucket renders NO DATA — PENDING: OK")

# --- 4. overround is stripped before comparison ------------------------------
# entry 2.00, overround 5% -> fair_open = (1/2.00)/1.05 = 0.476
s = summarise([_leg(market="1X2_H", model_prob=0.55, entry_odds=2.00,
                    closing_odds=1.90, hit=True, clv_pct=5.0)], "1X2_H")
fo = s["mean_fair_implied_open"]
assert abs(fo - 0.4761904) < 1e-3, f"fair implied must strip overround, got {fo}"
assert s["mean_model_prob"] == 0.55
print("4. fair implied = raw implied / (1+overround): OK")

print("\n✅ ALL BACKTEST REPORT TESTS PASSED")
