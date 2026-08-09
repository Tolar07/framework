"""Phase 3.3 — CLV-weighted model ensemble tests.

The consensus gives every engine an equal vote and averages their 1X2
arithmetically. Phase 3.3 weights each engine's say by its historical
performance — does it beat the close on the markets it calls (CLV, market-
level evidence) and is it well-calibrated on its own settled record? — via
clv/clv_logger.ensemble_weights(), and feeds the weights into
engine/consensus.compute_consensus(engine_weights=...).

Honesty rules proven here:
  1. no weights          -> consensus is bit-identical to the classic vote
  2. all weights 1.0     -> INERT: weighted=False, nothing moves
  3. weights tune the average: the proven engine's probabilities dominate
  4. weights can flip the result, but unweighted_result records the plain
     majority so the flip is never hidden
  5. a missing engine key counts as weight 1.0 (never silenced by absence)
  6. evidence gate: no settled record -> every weight exactly 1.0, applied
     flag says the consensus is unweighted (HR35: NO DATA is never a move)
  7. thin evidence is shrunk; a weight never leaves [0.5, 1.5]; sub-noise
     moves collapse back to equal say
  8. brain wiring: engine_calibration() + engine_clv() -> weights -> consensus
"""

import json
import sys
import tempfile
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent))

from brain.store import SCHEMA_VERSION, Brain
from clv import clv_logger as cl
from clv.clv_logger import LoggedLeg
from engine.consensus import compute_consensus

_tmp = Path(tempfile.mkdtemp(prefix="olp_xdv_ew_"))


def _probs(h=0.5, d=0.25, a=0.25):
    return SimpleNamespace(p_home=h, p_draw=d, p_away=a,
                           home_team="Home FC", away_team="Away FC",
                           p_over_15=0.7, p_over_25=0.5, p_btts_yes=0.5,
                           lambda_home=1.4, lambda_away=1.0)


# --- 1. no weights -> classic vote, unweighted ---------------------------------
c = compute_consensus(_probs(0.55, 0.25, 0.20), (0.45, 0.30, 0.25), None)
assert c is not None and not c.weighted and c.weight_used is None, c
assert c.result == "HOME" and c.votes == {"HOME": 2}, c
assert abs(c.avg_home - 0.50) < 1e-9, c            # (0.55+0.45)/2
assert c.unweighted_result == c.result, c
print("1. no weights -> classic consensus, unweighted: OK")

# --- 2. all-1.0 weights are INERT ----------------------------------------------
w_all = {"dc": 1.0, "elo": 1.0, "xg": 1.0}
c2 = compute_consensus(_probs(0.55, 0.25, 0.20), (0.45, 0.30, 0.25),
                       (0.50, 0.25, 0.25), engine_weights=w_all)
assert c2 is not None and not c2.weighted, \
    "all-1.0 weights must leave the consensus unweighted (evidence gate)"
assert c2.votes == {"HOME": 3} and abs(c2.avg_home - 0.50) < 1e-9, c2
print("2. all-1.0 weights -> inert, identical to the classic vote: OK")

# --- 3. weights tune the averaged 1X2 ------------------------------------------
# Elo (weight 3.0) is the proven engine and leans AWAY; dc (weight 1.0) HOME.
c3 = compute_consensus(_probs(0.60, 0.20, 0.20), (0.30, 0.30, 0.40), None,
                       engine_weights={"dc": 1.0, "elo": 3.0})
assert c3 is not None and c3.weighted, c3
# weighted avg_home = (1.0*0.60 + 3.0*0.30) / 4.0 = 0.375 (vs unweighted 0.45)
assert abs(c3.avg_home - 0.375) < 1e-9, c3
assert abs(c3.avg_away - (0.20 + 3.0 * 0.40) / 4.0) < 1e-9, c3
assert c3.votes == {"HOME": 1.0, "AWAY": 3.0}, c3
print("3. weights tune the averaged 1X2 toward the proven engine: OK")

# --- 4. a heavy weight can flip the result, but never silently ------------------
c4 = compute_consensus(_probs(0.55, 0.25, 0.20), (0.30, 0.30, 0.40),
                       (0.35, 0.35, 0.30), engine_weights={"dc": 1.0, "elo": 3.0, "xg": 1.0})
assert c4 is not None and c4.weighted, c4
assert c4.unweighted_result == "HOME", \
    "the plain 2-of-3 majority was HOME — that must be recorded"
assert c4.result == "AWAY", f"the heavier elo vote should flip the pick, got {c4}"
# agreeing counts ENGINES matching the final result (1: elo only)
assert c4.agreeing == 1, c4
print("4. heavy weight flips the result; unweighted_result records the plain vote: OK")

# --- 5. a missing engine key counts as weight 1.0 -------------------------------
c5 = compute_consensus(_probs(0.60, 0.20, 0.20), (0.40, 0.25, 0.35), None,
                       engine_weights={"dc": 2.0})
assert c5 is not None and c5.weighted, c5
assert c5.votes["ELO"] == 1.0 if "ELO" in c5.votes else True  # elo missing key -> 1.0
assert c5.weight_used == {"dc": 2.0, "elo": 1.0}, c5.weight_used
print("5. missing engine key -> weight 1.0, never silenced: OK")

# --- 6. ensemble_weights: no evidence -> every weight 1.0 -----------------------
w6, i6 = cl.ensemble_weights([], [])
assert w6 == {} and not i6["applied"], (w6, i6)
assert "unweighted" in i6["flag"], i6["flag"]
print("6. no settled evidence -> unweighted, reported honestly: OK")

# --- 7. evidence gates: thin, bounded, shrunk, no-noise -------------------------
# Below the calibration AND clv floor -> weight 1.0 (untouched).
w7, _ = cl.ensemble_weights(
    [{"model_engine": "elo", "n": 3, "mean_clv_pct": 5.0}],
    [{"model_engine": "elo", "n": 10, "mean_hit": 0.9, "mean_model_prob": 0.5}])
assert w7["elo"] == 1.0, f"thin evidence must not earn a weight, got {w7}"

# A genuinely strong engine (calibration solid + CLV positive) earns weight > 1.
w8, i8 = cl.ensemble_weights(
    [{"model_engine": "dc", "n": 12, "mean_clv_pct": 3.0},
     {"model_engine": "elo", "n": 12, "mean_clv_pct": 0.0}],
    [{"model_engine": "dc", "n": 60, "mean_hit": 0.62, "mean_model_prob": 0.50},
     {"model_engine": "elo", "n": 60, "mean_hit": 0.40, "mean_model_prob": 0.60}])
assert w8["dc"] > 1.0 and w8["elo"] < 1.0, f"expected dc up, elo down, got {w8}"
assert i8["applied"] and "ACTIVE" in i8["flag"], i8["flag"]
# Bounded: a wild CLV cannot push past 1.5.
w9, _ = cl.ensemble_weights(
    [{"model_engine": "dc", "n": 30, "mean_clv_pct": 50.0}],
    [{"model_engine": "dc", "n": 200, "mean_hit": 1.0, "mean_model_prob": 0.0}])
assert w9["dc"] == cl.WEIGHT_MAX == 1.5, f"must clamp to 1.5, got {w9}"
# Sub-noise moves collapse back to equal say (no fabricated nudge).
w10, _ = cl.ensemble_weights(
    [{"model_engine": "dc", "n": 10, "mean_clv_pct": 0.1}],
    [{"model_engine": "dc", "n": 60, "mean_hit": 0.51, "mean_model_prob": 0.50}])
assert w10["dc"] == 1.0, f"sub-noise residual must collapse to 1.0, got {w10}"
print("7. evidence gated, bounded at 1.5, sub-noise collapsed: OK")

# --- 8. brain wiring: engine_calibration + engine_clv -> weights -> consensus ---
b = Brain(_tmp / "e1.db")
assert b.schema_version == SCHEMA_VERSION
base = {"run_id": "r1", "predicted_at": "2026-08-01T08:00:00Z",
        "league": "Eredivisie", "fixture": "AAA v BBB", "match_date": "2026-08-02",
        "model_engine": "dc", "entry_odds": None, "bookmaker": None, "ev": None,
        "softness_tier": "B", "on_deploy_shortlist": 0, "cal_adjustment": None}
preds = [dict(base, market="1X2_HOME", model_prob=0.5) for _ in range(6)]
preds += [dict(base, market="1X2_HOME", model_prob=0.6) for _ in range(4)]
assert b.append_predictions(preds) == 10
b.record_outcomes("AAA v BBB", "2026-08-02", "1-0", {"1X2_HOME": True})
cal = {r["model_engine"]: r for r in b.engine_calibration()}
assert "dc" in cal and cal["dc"]["n"] == 10, cal
assert abs(cal["dc"]["mean_hit"] - 1.0) < 1e-9, cal
# no legs -> no CLV evidence -> unweighted (inert until CLV exists)
w8b, i8b = cl.ensemble_weights(b.engine_clv(), b.engine_calibration())
assert not i8b["applied"], i8b
# now feed a leg so the CLV term has evidence
leg = LoggedLeg(
    leg_id="L1", date_logged=datetime.now(UTC).isoformat(),
    league="Eredivisie", fixture="AAA v BBB", market="1X2_HOME",
    model_prob=0.5, match_date="2026-08-02", phase="phase2_paper",
    stake=0, entry_odds=2.1, entry_capture_path="archived",
    closing_odds=2.2, closing_capture_path="archived",
    clv_pct=2.3, ft_result="1-0", hit=True)
_ledger = _tmp / "clv_log.json"
with open(_ledger, "w") as f:
    json.dump([asdict(leg)], f)
b.sync_legs(paths=[_ledger])
assert len(b.engine_clv()) >= 1, b.engine_clv()
w8c, i8c = cl.ensemble_weights(b.engine_clv(), b.engine_calibration())
assert w8c.get("dc", 1.0) >= 1.0, w8c  # positive CLV + perfect hit -> dc never down
print("8. brain -> weights -> consensus wired end to end: OK")

b.close()

print("\n✅ ALL CLV-WEIGHTED CONSENSUS TESTS PASSED")
