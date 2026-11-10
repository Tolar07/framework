"""engine/wb_watch.py — record-only line watch for world basketball picks (framework#390)."""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine import wb_watch as ww  # noqa: E402

NOW = datetime(2026, 11, 5, 9, 0, tzinfo=UTC)
KO = NOW + timedelta(hours=5)
PICK = {"sb_event_id": "sr:1", "home": "Real Madrid", "away": "Olympiacos", "pick": "Real Madrid to win",
        "key": "B:219||Home", "price": 1.62, "fair": 0.66, "value": 0.07, "code": "ABC123",
        "source": "matchbook", "ko": KO.strftime("%Y-%m-%dT%H:%M:%SZ")}


def _row(price):
    return {"id": "sr:1", "sides": {"B:219||Home": price} if price else {}}


def test_quiet_when_value_holds():
    e: dict = {}
    assert ww.check(PICK, e, _row(1.62), 0.66, NOW) == []
    assert e["looks"][0]["value"] == round(1.62 * 0.66 - 1, 4) and e["star_out"].startswith("PENDING")


def test_value_gone_once():
    e: dict = {}
    out = ww.check(PICK, e, _row(1.45), 0.64, NOW)           # 1.45 x .64 - 1 < 0
    assert len(out) == 1 and "VALUE GONE" in out[0]
    assert ww.check(PICK, e, _row(1.45), 0.64, NOW) == []      # told once
    assert len(e["looks"]) == 2


def test_not_offered_and_line_moved():
    e: dict = {}
    assert "no longer offered" in ww.check(PICK, e, _row(None), 0.66, NOW)[0]
    e2: dict = {}
    assert "moved" in ww.check(PICK, e2, _row(1.62), 0.72, NOW)[0]


def test_missing_fair_is_pending_not_guessed():
    e: dict = {}
    assert ww.check(PICK, e, _row(1.62), None, NOW) == []
    assert e["looks"][0]["fair"] is None and e["looks"][0]["value"] is None


def test_update_writes_record_and_skips_started_games():
    with tempfile.TemporaryDirectory() as t:
        d = Path(t)
        day = KO.strftime("%Y-%m-%d")
        old = {**PICK, "sb_event_id": "sr:2", "ko": (NOW - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")}
        (d / f"wb_{day}.json").write_text(json.dumps({"date": day, "picks": [PICK, old]}), encoding="utf-8")
        ww.current_fair = lambda *a, **k: 0.64
        alerts = ww.update([_row(1.45), {**_row(1.45), "id": "sr:2"}], [], NOW, folder=d)
        assert len(alerts) == 1
        rec = json.loads((d / f"wb_watch_{day}.json").read_text(encoding="utf-8"))
        assert list(rec["picks"]) == ["sr:1"]
