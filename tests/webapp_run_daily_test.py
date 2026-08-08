"""run_daily integration — the board JSON must be written next to the .txt,
and web=False must skip it. Network is stubbed so the test is fast and
deterministic."""
import sys
import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import run_daily
from output.produce_bet import BoardFixture
from verification.id403 import verify, SourcedDatum

tmp = Path(tempfile.mkdtemp(prefix="olp_webapp_runn_"))
boards = tmp / "boards"
brain_path = tmp / "brain" / "olp.db"


def _fake_scan(lg, season, **kw):
    return ([BoardFixture(
        fixture="Bristol City v Walsall (EFL Cup)", probs=None,
        verification=verify([SourcedDatum(domain="thesportsdb.com",
                                          value="x", url="https://x",
                                          structured=True)]),
        softness_tier="D",
        rejection_reason="NO DATA — PENDING: test")], [])


from brain.store import Brain

with patch.object(run_daily, "BOARD_DIR", boards), \
     patch.object(run_daily, "Brain",
                  lambda *a, **k: Brain(brain_path)), \
     patch.object(run_daily, "grade_open_legs",
                  lambda *a, **k: ("", [])), \
     patch.object(run_daily.orchestrator, "scan_one_league", _fake_scan), \
     patch.object(run_daily, "_predictions_from_board", lambda *a, **k: 0):
    # --- 1. web=True writes the JSON next to the txt -------------------------
    boards.mkdir(parents=True, exist_ok=True)
    out = run_daily.run(send=False, web=True, leagues=["EFL Cup"])
    txt = boards / f"board_{date.today().isoformat()}.txt"
    jsn = boards / f"board_{date.today().isoformat()}.json"
    assert txt.exists(), "txt board must still be written"
    assert jsn.exists(), "web=True must write the board JSON"
    from webapp import schema
    payload = schema.read_payload(jsn)
    assert payload["n_leagues"] == 1
    assert payload["board"][0]["fixture"] == "Bristol City v Walsall (EFL Cup)"
    assert payload["board"][0]["probs"] is None
    assert "TODAY'S PICKS" in payload["recommendation"]
    print("1. web=True writes a readable board JSON: OK")

    # --- 2. web=False skips the JSON, keeps the txt --------------------------
    txt.unlink(); jsn.unlink()
    run_daily.run(send=False, web=False, leagues=["EFL Cup"])
    assert txt.exists()
    assert not jsn.exists(), "web=False must not write the JSON"
    print("2. web=False skips the JSON: OK")

    # --- 3. the run still returns a RunResult (nothing regressed) ------------
    assert out.full and out.telegram_text
    print("3. RunResult intact: OK")

print("\n[OK] ALL WEBAPP RUN_DAILY TESTS PASSED")
