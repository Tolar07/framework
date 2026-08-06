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
                                   p_over_35=0.22, p_btts_yes=0.55),
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

print("\n✅ ALL WEBAPP SCHEMA TESTS PASSED")
