"""CLV-gated recalibration tests.

The engine's EV probabilities are nudged ONLY by markets with enough settled
leg CLV evidence (MIN_LEGS), the adjustment is bounded (MAX_ADJUSTMENT), and
the ledger keeps the RAW model probability (no feedback loop). With no
evidence — the current state — the engine is entirely inert."""
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from engine import recalibration as recal
from brain.store import Brain

_tmp = Path(tempfile.mkdtemp(prefix="olp_xdv_recal_test_"))

# --- 1. inert with no evidence ----------------------------------------------
assert recal.adjustments_for([]) == {}, "no legs -> no adjustments, inert"
assert recal.apply(0.55, None) == 0.55, "no delta -> no-op"
print("1. inert with no evidence: OK")

# --- 2. below the evidence gate -> no adjustment ------------------------------
rows = [{"market": "1X2_HOME", "n": 5, "mean_clv_pct": 0.05,
         "mean_hit": 0.7, "mean_model_prob": 0.5}]
assert recal.adjustments_for(rows) == {}, "5 legs < MIN_LEGS -> no adjustment"
print("2. below MIN_LEGS gate -> inert: OK")

# --- 3. evidence above the gate -> bounded, correct direction -----------------
good = [{"market": "1X2_AWAY", "n": 20, "mean_clv_pct": 0.03,
         "mean_hit": 0.62, "mean_model_prob": 0.50}]
cal = recal.adjustments_for(good)
assert "1X2_AWAY" in cal and cal["1X2_AWAY"] > 0, \
    "beating the close + over-hitting -> positive adjustment"
assert cal["1X2_AWAY"] <= recal.MAX_ADJUSTMENT, "must be bounded"
assert abs(recal.apply(0.50, cal["1X2_AWAY"]) - 0.50) <= recal.MAX_ADJUSTMENT + 1e-9
print(f"3. positive evidence -> +{cal['1X2_AWAY']:.3f}, bounded: OK")

bad = [{"market": "OVER_2_5", "n": 25, "mean_clv_pct": -0.04,
        "mean_hit": 0.45, "mean_model_prob": 0.58}]
cal_b = recal.adjustments_for(bad)
assert "OVER_2_5" in cal_b and cal_b["OVER_2_5"] < 0, \
    "losing to the close + over-predicting -> negative adjustment"
print(f"4. negative evidence -> {cal_b['OVER_2_5']:.3f}, deflates: OK")

# --- 5. extreme evidence is still bounded (can't manufacture an edge) ---------
extreme = [{"market": "1X2_HOME", "n": 200, "mean_clv_pct": 0.5,
            "mean_hit": 1.0, "mean_model_prob": 0.1}]
ce = recal.adjustments_for(extreme)
assert abs(ce["1X2_HOME"]) <= recal.MAX_ADJUSTMENT + 1e-9, \
    "even absurd evidence cannot exceed MAX_ADJUSTMENT"
assert 0.02 <= recal.apply(0.5, ce["1X2_HOME"]) <= 0.98
print("5. bounded under extreme evidence: OK")

# --- 6. brain calibration_by_market + schema v2 migration ---------------------
b = Brain(_tmp / "c1.db")
from brain.store import SCHEMA_VERSION
assert b.schema_version == SCHEMA_VERSION, "schema must migrate to SCHEMA_VERSION"
# seed a market with 15 settled, CLV-logged legs
from clv.clv_logger import CLVLog
log = CLVLog(path=_tmp / "clv.json")
legs = []
for i in range(15):
    leg = log.log_entry(league="Eredivisie", fixture=f"H{i} v A{i}",
                        market="1X2_HOME", model_prob=0.5, entry_odds=2.0)
    log.log_close(leg.leg_id, closing_odds=1.8)
    log.log_result(leg.leg_id, ft_result="1-0", hit=(i % 2 == 0))  # settle
b.sync_legs([_tmp / "clv.json"])
rows = b.calibration_by_market()
assert any(r["market"] == "1X2_HOME" and r["n"] == 15 for r in rows), \
    "calibration_by_market must return the settled legs with CLV"
print("6. brain calibration query + schema v2 migration: OK")

# --- 7. the priced prediction row carries cal_adjustment ----------------------
from output.produce_bet import BoardFixture
bf = BoardFixture(fixture="H v A", probs=None, verification=None,
                  cal_adjustment=0.012)
assert bf.cal_adjustment == 0.012
print("7. BoardFixture.cal_adjustment field: OK")

print("\n✅ ALL RECALIBRATION TESTS PASSED")
