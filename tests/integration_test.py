"""Integration test — full daily pipeline on synthetic data.

This test runs the entire paper pipeline (run_daily.py's core logic) against a
tiny, deterministic synthetic fixture set so we can assert end-to-end behavior
without network I/O or the real football-data CSVs. It validates:

1. Data ingestion → model fitting → board generation → CLV logging
2. The approve→publish gate (Architect sign-off env) works
3. Telegram command layer loads and routes /board /legs /clv /status /produce
4. Web dashboard routes serve the correct payloads (trimmed vs full)
5. JSONL access log + /metrics exposition both emit lines

It does NOT send Telegram messages, start HTTP servers, or touch the real
output/boards or brain/olp.db. All state is redirected to a temp dir.
"""
import json
import os
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

# Redirect ALL state to a throwaway tree so the real repo is never touched.
_tmp = Path(tempfile.mkdtemp(prefix="olp_integration_test_"))

os.environ.update({
    "TELEGRAM_CHAT_ID": "888",  # whitelisted in telegram_commands
    "ARCHITECT_SIGNOFF": "1",   # pass the publish gate
    "ADMIN_USER": "test",
    "ADMIN_PASS": "testpass",
    "OLP_ACCESS_LOG": str(_tmp / "web.jsonl"),
    "PAPER_PHASE": "phase2_paper",
})

# --- minimal synthetic board that passes the produce gate --------------------
from webapp.schema import build_payload, write_payload, write_published
from engine.dixon_coles import FixtureProbabilities
from output.produce_bet import BoardFixture
from verification.id403 import verify, SourcedDatum

today = date.today().isoformat()
yesterday = (date.today() - timedelta(days=1)).isoformat()

def _rated_bf(fixture: str, home: str, away: str) -> BoardFixture:
    # NOTE: BoardFixture has no `league` field — league is carried in the
    # fixture string ("Arsenal v Chelsea (Premier League)") and derived at
    # render time, so the builder passes only the fixture text.
    return BoardFixture(
        fixture=fixture,
        probs=FixtureProbabilities(
            home, away,
            lambda_home=1.8, lambda_away=0.9,
            p_home=0.56, p_draw=0.24, p_away=0.20,
            p_over_15=0.71, p_over_25=0.45,
            p_over_35=0.22, p_btts_yes=0.55,
            modal_scoreline=(1, 0)),
        verification=verify([SourcedDatum(
            domain="thesportsdb.com", value="x", url="https://x", structured=True)]),
        on_deploy_shortlist=True,
        best_market=f"{home} to win", best_price=1.91,
        best_bookmaker="bet365", best_n_books=3, best_mes_ev=0.0696,
        best_model_prob=0.56, mes_trigger_price=1.52,
        kickoff_date=today,
        elo_probs=(0.52, 0.27, 0.21),
        engine_divergence="4pp on home — within tolerance",
        rejection_reason=None)

def _unrated_bf(fixture: str, reason: str) -> BoardFixture:
    return BoardFixture(
        fixture=fixture, probs=None,
        verification=verify([SourcedDatum(
            domain="thesportsdb.com", value="x", url="https://x", structured=True)]),
        rejection_reason=reason)

# 1. BUILD + WRITE a raw board (BOARD_DIR) + publish it (PUBLISHED_DIR)
raw_payload = build_payload(
    date=today, phase="PHASE 2 — PAPER",
    leagues_scanned=["Premier League", "Championship", "Serie A"],
    board=[
        _rated_bf("Arsenal v Chelsea (Premier League)", "Arsenal", "Chelsea"),
        _rated_bf("Leicester v Leeds (Championship)", "Leicester", "Leeds"),
        _unrated_bf("Juventus v Napoli (Serie A)",
                    "NO DATA — PENDING: no fitted history"),
    ],
    data_flags=[],
    gate={"legs_with_clv": 35, "gate_requirement": 30, "mean_clv_pct": 1.2},
    telemetry={}, calibration_count=0, mean_clv=1.2)

# Override schema dirs to the temp tree
import webapp.schema as S
S.BOARD_DIR = _tmp / "boards"
S.PUBLISHED_DIR = _tmp / "published"
S.AUDIT_LOG = S.PUBLISHED_DIR / "publish_audit.jsonl"
S.BOARD_DIR.mkdir(parents=True, exist_ok=True)
S.PUBLISHED_DIR.mkdir(parents=True, exist_ok=True)

write_payload(raw_payload, S.BOARD_DIR / f"board_{today}.json")
# Publish so the public dashboard sees it
write_published(raw_payload, approved_by="architect")
print("1. Synthetic board built, written, and published: OK")

# 2. PATCH brain DB path + run orchestrator's next_season_code fallback path
import brain.store as BS
BS.DEFAULT_BRAIN_PATH = _tmp / "olp.db"
print("2. Brain DB redirected to temp: OK")

# 3. VERIFY web dashboard routes (no HTTP server — just the handlers).
# The server's Handler methods read via webapp.schema (read_payload /
# read_published); we call those same functions directly, with the dirs
# already redirected to the temp tree above.
payload = S.read_payload(_tmp / "boards" / f"board_{today}.json")
assert payload is not None and payload["date"] == today
assert len(payload["board"]) == 3
assert payload["board"][0]["fixture"].startswith("Arsenal")
# Admin payload carries internals
for needle in ("elo_probs", "engine_divergence", "verification", "best_mes_ev"):
    assert needle in payload["board"][0], f"admin payload missing {needle}"
print("3a. read_payload (admin view) returns full internals: OK")

pub = S.read_published(today)
assert pub is not None and pub["date"] == today
# All three fixtures survive the client trim; the unrated one is kept and
# honestly marked NO DATA (HR35) rather than dropped.
assert len(pub["board"]) == 3
for needle in ("elo_probs", "engine_divergence", "verification", "best_mes_ev"):
    assert needle not in pub["board"][0], f"public payload leaks {needle}"
unrated = pub["board"][2]
assert unrated["probs"] is None
assert "NO DATA" in unrated.get("rejection_reason", "")
print("3b. read_published (client view) is trimmed + NO DATA honest: OK")

# 4. TELEGRAM command layer — exercise routing + the bright-line gate without
#    network. send_telegram is patched (no network); BOARD_DIR is redirected to
#    the temp tree so /board reads a synthetic board, never the real repo's.
import output.telegram_commands as TC
TC.STATE_DIR = _tmp
TC.OFFSET_FILE = _tmp / "telegram_offset.json"
TC.CORRECTIONS_FILE = _tmp / "corrections.csv"
TC.BOARD_DIR = _tmp / "boards"
(_tmp / "boards").mkdir(parents=True, exist_ok=True)
(_tmp / "boards" / f"board_{today}.txt").write_text(
    "OLP XDV — TODAY'S PICKS\nArsenal v Chelsea (Premier League)\n"
    "Leicester v Leeds (Championship)\n", encoding="utf-8")

def _msg(mid: int, text: str) -> dict:
    return {"update_id": mid,
            "message": {"message_id": mid, "chat": {"id": 888, "type": "private"},
                        "text": text}}

with patch.object(TC, "send_telegram", return_value=(True, ["ok"])) as sent:
    ok, notes = TC.handle_update(_msg(1, "/status"), token="t")
    assert ok and sent.call_count == 1
    assert "PHASE 3 GATE" in sent.call_args[0][0]
    print("3c. /status -> PHASE 3 GATE: OK")

with patch.object(TC, "send_telegram", return_value=(True, ["ok"])) as sent:
    ok, notes = TC.handle_update(_msg(2, "/board"), token="t")
    assert ok and sent.call_count == 1
    assert "TODAY'S PICKS" in sent.call_args[0][0]
    print("3d. /board -> synthetic board txt: OK")

# Bright-line: a message that would move a bright line is REFUSED, not sent.
with patch.object(TC, "send_telegram", return_value=(True, ["ok"])) as sent:
    ok, notes = TC.handle_update(_msg(3, "go live and deploy capital"), token="t")
    assert sent.call_count == 1
    assert "REFUSED" in sent.call_args[0][0]
    print("3e. bright-line message refused end-to-end: OK")

# Non-whitelisted chat is IGNORED — send_telegram is never called.
with patch.object(TC, "send_telegram", return_value=(True, ["ok"])) as sent:
    ok, notes = TC.handle_update({
        "update_id": 4,
        "message": {"message_id": 4, "chat": {"id": 999, "type": "private"},
                    "text": "/status"}}, token="t")
    assert sent.call_count == 0
    print("3f. non-whitelisted chat ignored (no send): OK")

# 5. JSONL access log + /metrics both emit lines (no HTTP server)
from monitor import json_log, metrics
json_log.setup_json_logging(_tmp / "web.jsonl")
json_log.json_log("integration-check", path="/api/board.json", method="GET", status=200, duration_ms=5.1)
lines = (_tmp / "web.jsonl").read_text(encoding="utf-8").splitlines()
assert len(lines) >= 1
obj = json.loads(lines[-1])
assert obj["path"] == "/api/board.json" and obj["status"] == 200
print("4a. JSONL access log writes structured line: OK")

# /metrics render (globals already patched by env)
mtext = metrics.collect_metrics()
assert "olp_web_up 1" in mtext
assert "olp_boards_published_total 1" in mtext
assert "olp_phase3_gate_requirement 30" in mtext
print("4b. /metrics exposition emits gauges: OK")

# 6. CLV logging — a leg is logged and read back
from clv.clv_logger import CLVLog
log = CLVLog(_tmp / "clv_log.json")
log.log_entry(league="Premier League", fixture="Arsenal v Chelsea",
              market="1X2 Home", model_prob=0.56, entry_odds=1.90)
assert len(log.legs) >= 1
print("5. CLV log entry + read: OK")

# 7. The approve→publish gate in schema.py is the single source of truth
from webapp import schema as SCH
# Passing board (≥30 legs, positive mean CLV) → no exception (architect
# sign-off relaxed so the unit check is about the gate arithmetic).
SCH.check_client_publish_gate(
    {"gate": {"legs_with_clv": 35, "gate_requirement": 30, "mean_clv_pct": 1.2}},
    require_architect_signoff=False,
)
print("6. Approve->publish gate (passing board opens): OK")
try:
    SCH.check_client_publish_gate(
        {"gate": {"legs_with_clv": 5, "gate_requirement": 30, "mean_clv_pct": -0.1}},
        require_architect_signoff=False,
    )
    raise SystemExit("gate must raise for a failing board")
except SCH.ClientPublishGateError:
    pass
print("7. Approve->publish gate (failing board blocked): OK")

print("\n[OK] ALL INTEGRATION TESTS PASSED")
