"""Board JSON schema tests — the dashboard's data contract.

The schema is what the local server AND the hosted export both read, so it
must be lossless over BoardFixture and honest about missing/newer data
(HR35: a missing board is FileNotFoundError, a newer schema is refused)."""
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.dixon_coles import FixtureProbabilities
from output.produce_bet import BoardFixture
from verification.id403 import verify, SourcedDatum
from webapp import schema

tmp = Path(tempfile.mkdtemp(prefix="olp_webapp_schema_"))


def _rated() -> BoardFixture:
    return BoardFixture(
        fixture="Fenerbahce v Sturm Graz (Champions League)",
        probs=FixtureProbabilities("Fenerbahce", "Sturm Graz",
                                   lambda_home=1.8, lambda_away=0.9,
                                   p_home=0.56, p_draw=0.24, p_away=0.20,
                                   p_over_15=0.71, p_over_25=0.45,
                                   p_over_35=0.22, p_btts_yes=0.55,
                                   modal_scoreline=(1, 0)),
        verification=verify([SourcedDatum(domain="thesportsdb.com",
                                          value="Fenerbahce v Sturm Graz",
                                          url="https://www.thesportsdb.com",
                                          structured=True)]),
        softness_tier="D",
        on_deploy_shortlist=False,
        mes_trigger_price=None,
        best_market="Fenerbahce to win",
        best_price=1.91,
        best_bookmaker="bet365",
        best_n_books=3,
        best_mes_ev=0.0696,
        best_model_prob=0.56,
        cal_adjustment=None,
        kickoff_date="2026-08-11",
        elo_probs=(0.52, 0.27, 0.21),
        xg_probs=None,
        engine_divergence=None,
        rejection_reason=None)


def _unrated() -> BoardFixture:
    return BoardFixture(
        fixture="Bristol City v Walsall (EFL Cup)",
        probs=None,
        verification=verify([SourcedDatum(domain="thesportsdb.com",
                                          value="Bristol City v Walsall",
                                          url="https://www.thesportsdb.com",
                                          structured=True)]),
        softness_tier="D",
        rejection_reason="NO DATA — PENDING: no fitted history for this league")


# --- 1. fixture_to_dict is lossless over a rated fixture ----------------------
d = schema.fixture_to_dict(_rated())
for key in ("fixture", "probs", "softness_tier", "on_deploy_shortlist",
            "best_market", "best_price", "best_bookmaker", "best_n_books",
            "best_mes_ev", "best_model_prob", "kickoff_date", "elo_probs",
            "verification"):
    assert key in d, f"missing {key}"
assert d["probs"]["p_home"] == 0.56 and d["probs"]["p_btts_yes"] == 0.55
assert d["elo_probs"] == [0.52, 0.27, 0.21]   # tuple -> list
assert d["verification"]["tier"]
print("1. rated fixture serialized losslessly: OK")

# --- 2. unrated fixture keeps the honest reason, probs None -------------------
d = schema.fixture_to_dict(_unrated())
assert d["probs"] is None
assert "NO DATA — PENDING" in d["rejection_reason"]
print("2. unrated fixture: probs None + honest reason: OK")

# --- 3. payload round-trips through disk -------------------------------------
payload = schema.build_payload(
    date="2026-08-11", phase="PHASE 2 — PAPER", leagues_scanned=["EFL Cup"],
    board=[_rated(), _unrated()], data_flags=["⚠ EFL Cup: no history"],
    gate={"legs_with_clv": 0, "gate_requirement": 30},
    telemetry={"clv_capture_rate": None, "days_to_gate": None},
    calibration_count=0, mean_clv=None,
    recommendation="⭐ TODAY'S PICKS\nNO DATA — no eligible pick today.")
p = tmp / "board_2026-08-11.json"
schema.write_payload(payload, p)
back = schema.read_payload(p)
assert back["schema_version"] == 1
assert back["n_leagues"] == 1 and back["board"][0]["fixture"] == "Fenerbahce v Sturm Graz (Champions League)"
assert len(back["board"]) == 2 and back["board"][1]["probs"] is None
print("3. payload written + read back faithfully: OK")

# --- 4. missing file -> FileNotFoundError (never a guess) ---------------------
try:
    schema.read_payload(tmp / "board_1999-01-01.json")
    raise SystemExit("missing board must raise FileNotFoundError")
except FileNotFoundError:
    pass
print("4. missing board is FileNotFoundError: OK")

# --- 5. a NEWER schema is refused, not adapted (HR35) -------------------------
p.write_text(json.dumps({"schema_version": 99, "board": []}),
             encoding="utf-8")
try:
    schema.read_payload(p)
    raise SystemExit("newer schema must be refused")
except ValueError as e:
    assert "newer" in str(e)
print("5. newer schema refused, never adapted: OK")

# --- 6. trim_payload: the client-safe boundary (Architect order 2026-08-07) ---
full = schema.build_payload(
    date="2026-08-11", phase="PHASE 2 — PAPER", leagues_scanned=["Champions League"],
    board=[_rated(), _unrated()], data_flags=["⚠ flag"], gate={"legs_with_clv": 0},
    telemetry={}, calibration_count=0, mean_clv=None)
trimmed = schema.trim_payload(full)
for key in ("data_flags", "gate", "telemetry", "calibration_count", "mean_clv",
            "recommendation"):
    assert key not in trimmed, f"trim kept admin field {key}"
t0, t1 = trimmed["board"]
assert t0["fixture"].startswith("Fenerbahce")
assert t0["on_deploy_shortlist"] is False
assert t0["best_market"] == "Fenerbahce to win"
assert t0["best_model_prob"] == 0.56
assert t0["mes_trigger_price"] is None
for k in ("elo_probs", "xg_probs", "market_probs", "engine_divergence",
          "consensus", "engine_picks", "consensus_pick", "verification",
          "cal_adjustment", "best_mes_ev", "best_price", "best_bookmaker",
          "best_n_books", "softness_tier", "model_engine", "kickoff_date"):
    assert k not in t0, f"trim kept internal {k}"
assert set(t0["probs"]) == schema.CLIENT_PROBS_KEYS
assert "lambda_home" not in t0["probs"] and "modal_scoreline" not in t0["probs"]
assert t1["probs"] is None and "NO DATA" in t1["rejection_reason"]
# never mutates the source payload
assert "elo_probs" in full["board"][0] and "verification" in full["board"][0]
assert "data_flags" in full and full["board"][0]["probs"]["lambda_home"] == 1.8
print("6. trim_payload keeps predictions, drops internals, never mutates: OK")

# --- 7. check_client_publish_gate: hard blocks until Phase 3 gate met ----------
import os
os.environ["ARCHITECT_SIGNOFF"] = "0"  # ensure sign-off is off

# 7a: insufficient legs with CLV
payload_few = schema.build_payload(
    date="2026-08-11", phase="PHASE 2 — PAPER", leagues_scanned=["Test"],
    board=[_rated()], data_flags=[], gate={"legs_with_clv": 5, "gate_requirement": 30, "mean_clv_pct": 2.5},
    telemetry={}, calibration_count=0, mean_clv=2.5)
try:
    schema.check_client_publish_gate(payload_few)
    raise SystemExit("should raise with 5 legs")
except schema.ClientPublishGateError as e:
    assert "5/30" in str(e)
print("7a. gate blocks with <30 legs: OK")

# 7b: enough legs but negative mean CLV
payload_neg = schema.build_payload(
    date="2026-08-11", phase="PHASE 2 — PAPER", leagues_scanned=["Test"],
    board=[_rated()], data_flags=[], gate={"legs_with_clv": 35, "gate_requirement": 30, "mean_clv_pct": -1.2},
    telemetry={}, calibration_count=0, mean_clv=-1.2)
try:
    schema.check_client_publish_gate(payload_neg)
    raise SystemExit("should raise with negative mean CLV")
except schema.ClientPublishGateError as e:
    assert "negative" in str(e).lower() or "positive" in str(e).lower()
print("7b. gate blocks with negative mean CLV: OK")

# 7c: gate met but no Architect sign-off
payload_gate_met = schema.build_payload(
    date="2026-08-11", phase="PHASE 2 — PAPER", leagues_scanned=["Test"],
    board=[_rated()], data_flags=[], gate={"legs_with_clv": 35, "gate_requirement": 30, "mean_clv_pct": 1.5},
    telemetry={}, calibration_count=0, mean_clv=1.5)
try:
    schema.check_client_publish_gate(payload_gate_met, require_architect_signoff=True)
    raise SystemExit("should raise without sign-off")
except schema.ClientPublishGateError as e:
    assert "sign-off" in str(e).lower() or "architect" in str(e).lower()
print("7c. gate blocks without Architect sign-off: OK")

# 7d: all requirements met -> passes
os.environ["ARCHITECT_SIGNOFF"] = "1"
schema.check_client_publish_gate(payload_gate_met, require_architect_signoff=True)
print("7d. gate passes when all requirements met: OK")

# Clean up
os.environ.pop("ARCHITECT_SIGNOFF", None)

# --- 8. write_published enforces the gate ---------------------------------------
from pathlib import Path
import tempfile
with tempfile.TemporaryDirectory() as td:
    pub_dir = Path(td) / "published"
    with patch.object(schema, "PUBLISHED_DIR", pub_dir):
        schema.AUDIT_LOG = pub_dir / "publish_audit.jsonl"
        # Gate not met -> write_published raises
        try:
            schema.write_published(payload_few, approved_by="test")
            raise SystemExit("write_published should raise when gate not met")
        except schema.ClientPublishGateError:
            pass
        print("8. write_published enforces gate: OK")

print("\n[OK] ALL WEBAPP SCHEMA TESTS PASSED")
