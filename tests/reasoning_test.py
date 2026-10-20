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


def test_record_scores_clv_per_verdict_even_before_the_result():
    with tempfile.TemporaryDirectory() as d:
        out, led = Path(d) / "r", Path(d) / "p"
        out.mkdir(), led.mkdir()
        doc = R.reason(PICKS, key="k", get=get, post=post_ok, now=NOW)
        (out / "reasoning_2026-10-19.json").write_text(json.dumps(doc))
        closed = {**PICKS, "singles": [{**PICKS["singles"][0], "clv": -2.5},
                                       {**PICKS["singles"][1], "clv": 4.0}]}
        (led / "picks_2026-10-19.json").write_text(json.dumps(closed))
        rec = R.record(out, led)
        assert rec["graded"] == 0
        assert rec["by_verdict"]["back"]["mean_clv"] == 4.0 and rec["by_verdict"]["back"]["beat_close"] == 1
        assert rec["by_verdict"]["veto"]["mean_clv"] == -2.5 and rec["by_verdict"]["veto"]["beat_close"] == 0
        assert "CLV back +4.00% (beat 1/1)" in R.summary_line(rec)


def test_records_are_plain_verdicts_and_break_even_is_given():
    assert R.say_framework({"n": 169, "hit": 0.781, "need": 0.803, "pl": -4.82}).startswith("LOSING")
    assert R.say_framework({"n": 3, "hit": 0, "need": 0.8, "pl": -3}).startswith("TOO FEW")
    assert R.say_framework(None).startswith("TOO FEW")
    assert R.say_matchbook({"bets": 12, "won": 10, "expected_wins": 9.1, "mean_clv": 0.01}).startswith("WINNING")
    assert R.say_matchbook({"bets": 1, "won": 0, "expected_wins": 0.35}).startswith("TOO FEW")
    row = R.context(PICKS["singles"])[0]
    assert row["break_even_chance"] == round(1 / 1.3, 4) and row["model_edge_pts"] == 3.1


def test_busy_server_is_retried():
    calls = []

    class Busy(Resp):
        status_code = 503

        def raise_for_status(self):
            raise RuntimeError("503")

    def post(url, json=None, **kw):
        calls.append(1)
        return Busy({}) if len(calls) < 2 else post_ok(url, json=json, **kw)

    got = R._ask(post, "k", "gemini-3.0-flash-lite", R.context(PICKS["singles"]), sleep=lambda s: None)
    assert len(calls) == 2 and got[0]["verdict"] == "veto"


def test_tradable_pool_legs_get_verdicts_too():
    doc = {**PICKS, "rated": [{"fixture": "A v B", "pool": [["SB:10||Home or Away", 0.8], ["SB:1||Home", 0.9]]},
                              {"fixture": "E v F", "pool": [["SB:18|total=3.5|Under 3.5", 0.85],
                                                            ["SB:1||Home", 0.6]]}]}
    legs = R.pool_legs(doc)
    assert [(x["fixture"], x["pick"]) for x in legs] == [("A v B", "Home"), ("E v F", "Under 3.5")]
    out = R.reason(doc, key="", now=NOW)
    assert len(out["picks"]) == 4 and [p["pool"] for p in out["picks"]] == [False, False, True, True]


def test_it_never_touches_the_picks_file():
    import inspect
    src = inspect.getsource(R)
    assert ".write_text" not in src and "open(" not in src      # the engine only reads; the runner writes output/ and memory/


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("reasoning_test OK")
