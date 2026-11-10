"""engine/reasoning.py world basketball / NCAA twin (framework#392). No network: get/post are fakes."""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine import reasoning as R  # noqa: E402

NOW = datetime(2026, 11, 10, 21, 0, tzinfo=UTC)
BOARD = {"date": "2026-11-11", "generated_at": "n=2", "picks": [
    {"home": "Duke", "away": "Kansas", "comp": "NCAA", "pick": "Over 150.5", "price": 1.9, "chance": 0.55,
     "value": 0.045, "market_id": "225", "specifier": "total=150.5", "outcome": "Over", "tip": "2026-11-11T00:00Z",
     "result": "won", "close_value": 0.02},
    {"home": "Real", "away": "Barca", "comp": "EuroLeague", "pick": "Real", "price": 2.0, "chance": 0.53,
     "value": 0.06, "market_id": "219", "specifier": "", "outcome": "Home", "tip": "2026-11-11T19:00Z",
     "result": "lost"}]}


class Resp:
    def __init__(self, body):
        self.body = body

    def raise_for_status(self):
        pass

    def json(self):
        return self.body


def get(url, **kw):
    return Resp({"data": [{"id": "models/gemini-3.0-flash-lite"}]})


def post_ok(url, json=None, **kw):
    import json as j
    ans = {"picks": [{"id": 0, "verdict": "veto", "ai_chance": 0.5, "confidence": 0.7, "reasons": "x"},
                     {"id": 1, "verdict": "back", "ai_chance": 0.55, "confidence": 0.6, "reasons": "y"}]}
    return Resp({"choices": [{"message": {"content": j.dumps(ans)}}]})


def test_reason_wb_is_record_only_and_keyed():
    with tempfile.TemporaryDirectory() as d:
        doc = R.reason_wb(BOARD, key="k", get=get, post=post_ok, now=NOW, wb_dir=Path(d))
    assert doc["sport"] == "world_basketball" and doc["advisory"] is True
    assert [p["verdict"] for p in doc["picks"]] == ["veto", "back"]
    assert [p["stake_factor"] for p in doc["picks"]] == [1.0, 1.0]       # a veto never changes a stake here
    assert doc["picks"][0]["market"] == "WB:225|total=150.5|Over" and doc["picks"][0]["fixture"] == "Duke v Kansas"


def test_no_key_reads_pending():
    with tempfile.TemporaryDirectory() as d:
        doc = R.reason_wb(BOARD, key="", get=get, post=post_ok, now=NOW, wb_dir=Path(d))
    assert all(p["verdict"] == "PENDING" for p in doc["picks"]) and "PENDING" in doc["note"]


def test_context_uses_graded_record_and_pending_without_one():
    with tempfile.TemporaryDirectory() as d:
        assert "TOO FEW" in R.wb_context(BOARD["picks"], Path(d))[0]["framework_record_in_family"]
        (Path(d) / "wb_2026-11-11.json").write_text(json.dumps(BOARD))
        rec = R.wb_records(Path(d))
        assert rec["basketball total"]["n"] == 1 and rec["basketball winner"]["won"] == 0
        assert R.wb_context(BOARD["picks"], Path(d))[0]["value_pts"] == 4.5


def test_record_wb_scores_verdicts():
    with tempfile.TemporaryDirectory() as d:
        out, wb = Path(d) / "r", Path(d) / "w"
        out.mkdir(), wb.mkdir()
        doc = R.reason_wb(BOARD, key="k", get=get, post=post_ok, now=NOW, wb_dir=wb)
        (out / "reasoning_wb_2026-11-11.json").write_text(json.dumps(doc))
        (wb / "wb_2026-11-11.json").write_text(json.dumps(BOARD))
        rec = R.record_wb(out, wb)
        assert rec["graded"] == 2
        assert rec["by_verdict"]["veto"]["won"] == 1 and rec["by_verdict"]["back"]["won"] == 0
        assert rec["by_verdict"]["veto"]["close_value"] == 0.02


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f()
    print("reasoning_wb_test ok")
