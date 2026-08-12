"""Board JSON schema tests — the dashboard's data contract.

The schema is what the local server AND the hosted export both read, so it
must be lossless over BoardFixture and honest about missing/newer data
(HR35: a missing board is FileNotFoundError, a newer schema is refused)."""
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

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
        rejection_reason="NO DATA — PENDING: no fitted history for this league")


# --- 1. fixture_to_dict is lossless over a rated fixture ----------------------
d = schema.fixture_to_dict(_rated())
for key in ("fixture", "probs", "on_deploy_shortlist",
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
          "best_n_books", "model_engine"):
    assert k not in t0, f"trim kept internal {k}"
# kickoff_date is a factual match datum (not a model internal) and stays —
# the client renders the today-only call from it (standing rule 2026-08-09).
assert t0["kickoff_date"] == "2026-08-11"
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

# --- 9. build_feed_payload: the Telegram board, lean + honest ----------------
os.environ["ARCHITECT_SIGNOFF"] = "1"   # override active → feed shows it
feed_src = schema.build_payload(
    date="2026-08-11", phase="PHASE 2 — PAPER", leagues_scanned=["Champions League"],
    board=[_rated(), _unrated()], data_flags=["⚠ EFL Cup: no history"],
    gate={"legs_with_clv": 12, "gate_requirement": 30, "mean_clv_pct": -1.631},
    telemetry={}, calibration_count=3, mean_clv=-1.631,
    yesterday_graded=[{
        "fixture": "Fenerbahce v Sturm Graz",
        "league": "Champions League",
        "outcome": "HOME",
        "engines": {
            "dc": {"1X2_HOME": {"prob": 0.56, "hit": True}},
            "elo": {"1X2_HOME": {"prob": 0.52, "hit": False}},
            "xg": {"1X2_DRAW": {"prob": 0.30, "hit": True}},
        },
    }],
    rolling_7d={
        "engines": {
            "dc": {"predictions": 20, "settled": 10, "hit_rate": 0.5},
            "elo": {"predictions": 8, "settled": 4, "hit_rate": 0.25},
            "xg": {"predictions": 0, "settled": 0, "hit_rate": None},
        },
        "legs_logged": 40, "legs_with_clv": 12, "avg_clv_pct": -1.631,
        "gate": {"legs_with_clv": 12, "gate_requirement": 30, "gate_met": False},
    })
feed = schema.build_feed_payload(feed_src)

# honest gate/edge fields added back (the Telegram message carries them)
assert feed["data_flags"] == ["⚠ EFL Cup: no history"]
assert feed["calibration_count"] == 3 and feed["mean_clv"] == -1.631
gs = feed["gate_state"]
assert gs["legs_with_clv"] == 12 and gs["gate_requirement"] == 30
assert gs["mean_clv_pct"] == -1.631
assert gs["gate_met"] is False and gs["override"] is True
assert gs["architect_signed_off"] is True
# still the data-leak boundary: no internals at top level or per fixture
for k in ("gate", "telemetry", "elo_probs", "xg_probs", "market_probs",
          "consensus", "engine_picks", "verification", "best_mes_ev"):
    assert k not in feed, f"feed leaked internal {k}"
for k in ("elo_probs", "xg_probs", "market_probs", "engine_picks",
          "consensus_pick", "verification", "best_mes_ev"):
    assert k not in feed["board"][0], f"feed board leaked {k}"
# yesterday-graded is lean: hit marks only, never the per-engine probs
yg = feed["yesterday_graded"]
assert yg[0]["fixture"] == "Fenerbahce v Sturm Graz"
assert yg[0]["engines_hit"] == {"dc": True, "elo": False, "xg": True}
assert "engines" not in yg[0] and "prob" not in yg[0]
# rolling is lean: hit rates + legs/CLV, no prediction volumes
r7 = feed["rolling_7d"]
assert r7["engines"] == {"dc": {"hit_rate": 0.5}, "elo": {"hit_rate": 0.25}}
assert "xg" not in r7["engines"]      # no settled predictions → not shown
assert r7["legs_logged"] == 40 and r7["avg_clv_pct"] == -1.631
assert r7["gate"]["legs_with_clv"] == 12
# never mutates the source payload
assert "elo_probs" in feed_src["board"][0]
assert "prob" in feed_src["yesterday_graded"][0]["engines"]["dc"]["1X2_HOME"]
assert "predictions" in feed_src["rolling_7d"]["engines"]["dc"]
os.environ.pop("ARCHITECT_SIGNOFF", None)
print("9. build_feed_payload: lean Telegram board, honest fields, no internals: OK")

# --- 10. read_feed / list_board_dates read the RAW board, never published ----
with patch.object(schema, "BOARD_DIR", tmp):
    p = tmp / "board_2026-08-11.json"
    schema.write_payload(feed_src, p)
    f2 = schema.read_feed("2026-08-11")
    assert f2["date"] == "2026-08-11"
    assert f2["gate_state"]["legs_with_clv"] == 12
    assert "elo_probs" not in f2["board"][0]
    assert schema.list_board_dates() == ["2026-08-11"]
    try:
        schema.read_feed("1999-01-01")
        raise SystemExit("missing feed board must raise FileNotFoundError")
    except FileNotFoundError:
        pass
print("10. read_feed + list_board_dates: raw board feed, HR35 on missing: OK")

# --- 11. stamp_feed_audit: the feed's never-silent gate record ----------------
with patch.object(schema, "FEED_AUDIT", tmp / "feed_audit.jsonl"):
    os.environ["ARCHITECT_SIGNOFF"] = "1"
    schema.stamp_feed_audit("2026-08-11", feed_src)
    lines = (tmp / "feed_audit.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["date"] == "2026-08-11"
    assert entry["gate"]["override"] is True
    assert entry["gate"]["architect_signed_off"] is True
    assert entry["gate"]["mean_clv_pct"] == -1.631
    os.environ.pop("ARCHITECT_SIGNOFF", None)
# best-effort: a stamp into an unwritable path never raises
bad_path = MagicMock()
bad_path.parent.mkdir.side_effect = OSError
with patch.object(schema, "FEED_AUDIT", bad_path):
    schema.stamp_feed_audit("2026-08-12", feed_src)
print("11. stamp_feed_audit records gate numbers, never raises on failure: OK")

print("\n[OK] ALL WEBAPP SCHEMA TESTS PASSED")
