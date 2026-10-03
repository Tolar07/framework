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
from webapp import schema

tmp = Path(tempfile.mkdtemp(prefix="olp_webapp_runn_"))
boards = tmp / "boards"
brain_path = tmp / "brain" / "olp.db"


def _fake_scan(lg, season, **kw):
    # Real scanned fixtures carry a kickoff date (the source's fixture date);
    # strict single-day production keeps ONLY fixtures on the board date, so the
    # stub must be dated today or it is honestly refused (HR35).
    return ([BoardFixture(
        fixture="Bristol City v Walsall (EFL Cup)", probs=None,
        verification=verify([SourcedDatum(domain="thesportsdb.com",
                                          value="x", url="https://x",
                                          structured=True)]),
        kickoff_date=date.today().isoformat(),
        rejection_reason="NO DATA — PENDING: test")], [])


from brain.store import Brain

with patch.object(run_daily, "BOARD_DIR", boards), \
     patch.object(run_daily, "Brain",
                  lambda *a, **k: Brain(brain_path)), \
     patch.object(run_daily, "grade_open_legs",
                  lambda *a, **k: ("", [])), \
     patch.object(run_daily.orchestrator, "scan_one_league", _fake_scan), \
     patch.object(run_daily, "_predictions_from_board", lambda *a, **k: 0), \
     patch.object(schema, "FEED_AUDIT", boards / "feed_audit.jsonl"):
    # --- 1. web=True writes the JSON next to the txt -------------------------
    boards.mkdir(parents=True, exist_ok=True)
    out = run_daily.run(send=False, web=True, leagues=["EFL Cup"])
    txt = boards / f"board_{date.today().isoformat()}.txt"
    jsn = boards / f"board_{date.today().isoformat()}.json"
    assert txt.exists(), "txt board must still be written"
    assert jsn.exists(), "web=True must write the board JSON"
    payload = schema.read_payload(jsn)
    assert payload["n_leagues"] == 1
    assert payload["board"][0]["fixture"] == "Bristol City v Walsall (EFL Cup)"
    assert payload["board"][0]["probs"] is None
    # ⭐ TODAY'S PICKS parlay was REPLACED by the Acca A production block
    # (Architect 2026-08-10) — the recommendation is now empty.
    assert payload["recommendation"] == ""
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

    # --- 4. web=True persists the byte-faithful Telegram feed + audit ---------
    feed = boards / f"telegram_{date.today().isoformat()}.txt"
    assert feed.exists(), "web=True must persist telegram_<date>.txt"
    assert out.telegram_text in feed.read_text(encoding="utf-8"), \
        "feed file must carry the Telegram body (one render, two outlets)"
    audit = boards / "feed_audit.jsonl"
    assert audit.exists(), "feed audit must be stamped"
    line = audit.read_text(encoding="utf-8").strip().splitlines()[-1]
    import json as _json
    entry = _json.loads(line)
    assert entry["date"] == date.today().isoformat()
    assert "gate" in entry and "legs_with_clv" in entry["gate"]
    print("4. web=True writes telegram_<date>.txt + feed_audit.jsonl: OK")

    # --- 5. CODES-FIX: a booking-skip run PRESERVES a captured codes file -----
    import run_daily as rd
    codes = boards / f"acca_{date.today().isoformat()}_codes.json"
    codes.write_text('{"results": [{"label": "Acca A", "code": "M5LMFE"}]}',
                     encoding="utf-8")
    # Simulate a later MANUAL regen run that skips booking (web=False, codes off)
    run_daily.run(send=False, web=False, leagues=["EFL Cup"],
                  booking_codes=False)
    assert codes.exists(), "a good capture must survive a booking-skip regen"
    saved = codes.read_text(encoding="utf-8")
    assert "M5LMFE" in saved, "captured code must be intact after a skip run"
    print("5. CODES-FIX: a booking-skip run preserves a captured codes file: OK")

print("\n[OK] ALL WEBAPP RUN_DAILY TESTS PASSED")
