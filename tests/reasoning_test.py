"""engine/reasoning.py — the advisory thinking step. No network: get/post are fakes."""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine import reasoning as R  # noqa: E402

NOW = datetime(2026, 10, 19, 21, 0, tzinfo=UTC)
PICKS = {"date": "2026-10-19", "generated_at": "g1", "singles": [
    {"fixture": "A v B", "market": "SB:10||Home or Away", "pick": "A or B", "price": 1.3, "chance": 0.8},
    {"fixture": "C v D", "market": "SB:18|total=4.5|Under 4.5", "pick": "Under 4.5", "price": 1.2, "chance": 0.82}]}


class Resp:
    def __init__(self, body):
        self.body = body

    def raise_for_status(self):
        pass

    def json(self):
        return self.body


def get(url, **kw):
    return Resp({"data": [{"id": "models/gemini-9.0-flash-lite-preview"}, {"id": "models/gemini-2.5-flash-lite"},
                          {"id": "models/gemini-3.0-flash-lite"}, {"id": "models/gemini-3.0-flash"},
                          {"id": "models/text-embedding-004"}]})


def post_ok(url, json=None, **kw):
    import json as j
    assert json["model"] == "gemini-3.0-flash-lite", json["model"]
    ans = {"picks": [{"id": 0, "verdict": "veto", "ai_chance": 0.6, "confidence": 0.7, "reasons": "x"},
                     {"id": 1, "verdict": "BACK", "ai_chance": 0.85, "confidence": 0.6, "reasons": "y"}]}
    return Resp({"choices": [{"message": {"content": "```json\n" + j.dumps(ans) + "\n```"}}]})


def test_reason_picks_newest_stable_flash_lite_and_cleans_answers():
    doc = R.reason(PICKS, key="k", get=get, post=post_ok, now=NOW)
    assert doc["model"] == "gemini-3.0-flash-lite"
    assert [p["verdict"] for p in doc["picks"]] == ["veto", "back"]
    assert doc["advisory"] is True and doc["note"] is None


def test_no_key_or_failure_reads_pending():
    doc = R.reason(PICKS, key="", get=get, post=post_ok, now=NOW)
    assert all(p["verdict"] == "PENDING" for p in doc["picks"]) and "PENDING" in doc["note"]

    def boom(*a, **k):
        raise ConnectionError("down")
    doc = R.reason(PICKS, key="k", get=get, post=boom, now=NOW)
    assert all(p["verdict"] == "PENDING" for p in doc["picks"]) and "ConnectionError" in doc["note"]


def test_malformed_answer_is_pending():
    def post_bad(url, **kw):
        return Resp({"choices": [{"message": {"content": json.dumps(
            {"picks": [{"id": 0, "verdict": "maybe", "ai_chance": 2, "confidence": 0.5}]})}}]})
    doc = R.reason(PICKS, key="k", get=get, post=post_bad, now=NOW)
    assert [p["verdict"] for p in doc["picks"]] == ["PENDING", "PENDING"]


def test_record_scores_verdicts_against_results():
    with tempfile.TemporaryDirectory() as d:
        out, led = Path(d) / "r", Path(d) / "p"
        out.mkdir(), led.mkdir()
        doc = R.reason(PICKS, key="k", get=get, post=post_ok, now=NOW)
        (out / "reasoning_2026-10-19.json").write_text(json.dumps(doc))
        graded = {**PICKS, "singles": [{**PICKS["singles"][0], "result": "lost"},
                                       {**PICKS["singles"][1], "result": "won"}]}
        (led / "picks_2026-10-19.json").write_text(json.dumps(graded))
        rec = R.record(out, led)
        assert rec["graded"] == 2
        assert rec["by_verdict"]["veto"]["won"] == 0 and rec["by_verdict"]["back"]["won"] == 1
        assert "veto 0/1" in R.summary_line(rec)


def test_records_are_spelled_out_with_a_weak_flag():
    assert R._say_fw({"n": 20, "hit": 0.6, "need": 0.78, "pl": -5.0}).endswith("WEAK")
    assert R._say_fw({"n": 20, "hit": 0.8, "need": 0.78, "pl": 1.0}).endswith("OK")
    assert R._say_mb({"bets": 37, "won": 27, "expected_wins": 30.5, "mean_clv": -0.0016}).endswith("WEAK")
    assert "no Matchbook" in R._say_mb(None)


def test_it_never_touches_the_picks_file():
    import inspect
    src = inspect.getsource(R)
    assert ".write_text" not in src and "open(" not in src      # the engine only reads; the runner writes output/ and memory/


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("reasoning_test OK")
