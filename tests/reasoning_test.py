"""engine/reasoning.py — the thinking step (its verdict scales the stake since 2026-10-23). No network: get/post are fakes."""
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
    assert doc["advisory"] is True and doc["note"] is None      # verdict stakes off: it acts on nothing
    assert doc["acts_on"].startswith("nothing")
    assert [p["stake_factor"] for p in doc["picks"]] == [1.0, 1.0]   # verdict stakes off (Architect 02-11)
    assert [p["advised_stake_factor"] for p in doc["picks"]] == [0.5, 1.0]   # what the verdict advised, recorded


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


# ── NBA (Architect 2026-10-20: "the Gemini reasoning, build the NBA") ─────────
NBA_BOARD = {"date": "2026-10-21", "generated_at": "n1", "picks": [
    {"home": "Detroit Pistons", "away": "Boston Celtics", "tip": "2026-10-20T19:00:00+00:00", "market_id": "68",
     "specifier": "total=114.5", "outcome": "Under 114.5", "pick": "1st half Under 114.5 points", "price": 1.95,
     "chance": 0.6095, "ev": 0.1884, "stage": "regular", "sharp": {"total": 221.5}, "result": None}],
    "picks_dropped": [
    {"home": "New York Knicks", "away": "Philadelphia 76ers", "tip": "2026-10-20T23:00:00+00:00",
     "market_id": "219", "specifier": "", "outcome": "Away", "pick": "76ers to win", "price": 2.53,
     "chance": 0.40, "ev": 0.012, "stage": "regular", "result": None}]}


def test_nba_board_is_reasoned_with_its_own_prompt_and_families():
    seen = {}

    def post(url, json=None, **kw):
        import json as j
        seen.setdefault("prompt", json["messages"][0]["content"])   # the verdict's, not the panel's (later)
        ans = {"picks": [{"id": 0, "verdict": "back", "ai_chance": 0.6, "confidence": 0.5, "reasons": "a"},
                         {"id": 1, "verdict": "lower", "ai_chance": 0.38, "confidence": 0.5, "reasons": "b"}]}
        return Resp({"choices": [{"message": {"content": j.dumps(ans)}}]})
    with tempfile.TemporaryDirectory() as d:
        doc = R.reason_nba(NBA_BOARD, key="k", get=get, post=post, now=NOW, ledger_dir=Path(d))
    assert doc["sport"] == "nba" and [p["verdict"] for p in doc["picks"]] == ["back", "lower"]
    assert doc["picks"][0]["market"] == "NBA:68|total=114.5|Under 114.5"
    assert doc["picks"][0]["fixture"] == "Detroit Pistons v Boston Celtics"
    assert "NBA betting model" in seen["prompt"] and "football" not in seen["prompt"].split("PICKS:")[0]
    assert '"market_family": "NBA 1st half total"' in seen["prompt"] and "value_pts" in seen["prompt"]
    assert R.nba_family("219") == "NBA winner" and R.nba_family("999") == "NBA other"


def test_nba_record_scores_verdicts_and_keeps_football_apart():
    with tempfile.TemporaryDirectory() as d:
        out, led = Path(d) / "out", Path(d) / "led"
        out.mkdir()
        led.mkdir()
        board = json.loads(json.dumps(NBA_BOARD))
        board["picks"][0].update(result="won", close_value=0.05)
        board["picks_dropped"][0].update(result="lost")
        (led / "nba_2026-10-21.json").write_text(json.dumps(board))
        (out / "reasoning_nba_2026-10-21.json").write_text(json.dumps({"date": "2026-10-21", "picks": [
            {"fixture": "Detroit Pistons v Boston Celtics", "market": "NBA:68|total=114.5|Under 114.5", "verdict": "back"},
            {"fixture": "New York Knicks v Philadelphia 76ers", "market": "NBA:219||Away", "verdict": "lower"}]}))
        rec = R.record(out, led)
    assert rec["graded"] == 0, "NBA verdicts never enter the football record"
    nb = rec["nba"]["by_verdict"]
    assert rec["nba"]["graded"] == 2 and nb["back"] == {"n": 1, "won": 1, "flat_return": 0.95, "close_value": 0.05}
    assert nb["lower"]["won"] == 0 and nb["veto"] == {"n": 0}
    assert "NBA (2 graded)" in R.summary_line(rec)
    with tempfile.TemporaryDirectory() as d:
        b = json.loads(json.dumps(NBA_BOARD))
        b["picks"][0].update(result="won")
        (Path(d) / "nba_2026-10-21.json").write_text(json.dumps(b))
        assert R.nba_records(Path(d)) == {"NBA 1st half total": {"n": 1, "won": 1, "flat_return": 0.95,
                                                                  "close_value": None}}



def _graded_dir(d):
    """One reasoned day: A v B vetoed and WON (a mistake), C v D backed and won."""
    out, led = Path(d) / "out", Path(d) / "led"
    out.mkdir()
    led.mkdir()
    doc = {"date": "2026-10-19", "picks": [
        {"fixture": "A v B", "market": "SB:10||Home or Away", "pick": "A or B", "price": 1.3, "verdict": "veto",
         "model_chance": 0.8, "ai_chance": 0.6, "reasons": "rotation feared"},
        {"fixture": "C v D", "market": "SB:18|total=4.5|Under 4.5", "pick": "Under 4.5", "price": 1.2,
         "verdict": "back", "model_chance": 0.82, "ai_chance": 0.85, "reasons": "both sides tight"}]}
    (out / "reasoning_2026-10-19.json").write_text(json.dumps(doc))
    p = json.loads(json.dumps(PICKS))
    for s in p["singles"]:
        s["result"] = "won"
    (led / "picks_2026-10-19.json").write_text(json.dumps(p))
    return out, led


def test_teaching_shows_record_evidence_and_lessons_never_single_results():
    with tempfile.TemporaryDirectory() as d:
        out, led = _graded_dir(d)
        les = Path(d) / "lessons.json"
        les.write_text(json.dumps({"football": {"lessons": ["veto only on a confirmed absence"]}}))
        t = R.teaching("football", out, led, les)
        assert "2 graded verdicts" in t and "veto: 1/1 won" in t
        # a veto that won is ONE result, not a mistake: no single game is shown, and the text says so
        assert "YOUR RECENT MISTAKES" not in t and "rotation feared" not in t and "-> it WON" not in t
        assert "WHERE YOUR RECORD DIFFERS FROM THE CHANCES" in t and "nowhere yet" in t
        assert "veto only on a confirmed absence" in t


def _rows(n, verdict, chance, won, market="SB:10||Home or Away"):
    return [dict(verdict=verdict, model_chance=chance, ai_chance=chance, won=i < won, market=market, price=1.3,
                 date="2026-10-19", fixture=f"F{i}", pick="p", reasons="") for i in range(n)]


def test_evidence_needs_twenty_verdicts_and_two_standard_errors():
    # 25 vetoes at 50%: 24 won. Expected 12.5, sd 2.5 -> z = +4.6: evidence that these vetoes find no losers
    ev = R.evidence(_rows(25, "veto", 0.5, 24))
    assert {e["group"] for e in ev} == {"verdict veto", "family Double chance", "family Double chance x verdict veto"}
    assert ev[0]["n"] == 25 and ev[0]["won"] == 24 and ev[0]["z"] > 4
    assert "won MORE often than their chances said" in R.say_evidence(ev)[0]
    assert R.evidence(_rows(19, "veto", 0.5, 19)) == []                 # too few, however lopsided
    assert R.evidence(_rows(100, "back", 0.75, 74)) == []               # 74/100 at 75%: exactly what was said
    assert R.evidence(_rows(100, "back", 0.75, 60))[0]["z"] < -2        # 60/100 at 75%: over-rated


def test_pool_and_value_verdicts_are_graded_too():
    with tempfile.TemporaryDirectory() as d:
        out, led = Path(d) / "out", Path(d) / "led"
        out.mkdir()
        led.mkdir()
        doc = {"date": "2026-10-19", "picks": [
            {"fixture": "A v B", "market": "SB:10||Home or Away", "pick": "A or B", "price": 1.3, "verdict": "back",
             "model_chance": 0.8, "ai_chance": 0.8},
            {"fixture": "P v Q", "market": "SB:18|total=4.5|Under 4.5", "pick": "Under 4.5", "price": None,
             "verdict": "veto", "model_chance": 0.85, "ai_chance": 0.7, "pool": True},
            {"fixture": "E v F", "market": "SB:1||Home", "pick": "E to win", "price": 1.9, "verdict": "lower",
             "model_chance": 0.6, "ai_chance": 0.55, "code": "VAL111"}]}
        (out / "reasoning_2026-10-19.json").write_text(json.dumps(doc))
        ledger = {"date": "2026-10-19", "singles": [dict(PICKS["singles"][0], result="lost", ft="1-1")],
                  "rated": [{"fixture": "P v Q", "ft": "2-1", "pool": [["SB:18|total=4.5|Under 4.5", 0.85]]},
                            {"fixture": "X v Y", "pool": [["SB:1||Home", 0.9]]}],                    # not played yet
                  "value": [{"code": "VAL111", "alt_legs": [{"fixture": "E v F", "market": "SB:1||Home",
                                                              "price": 1.9, "result": "won", "ft": "2-0"}]}]}
        (led / "picks_2026-10-19.json").write_text(json.dumps(ledger))
        rows = R.graded_verdicts("football", out, led)
        assert [(r["fixture"], r["won"]) for r in rows] == [("A v B", False), ("P v Q", True), ("E v F", True)]
        rec = R.record(out, led, Path(d) / "rec.json")
        assert rec["graded"] == 3
        # the pool leg has no price: its win is in the count and the Brier score, never in the flat return
        assert rec["by_verdict"]["veto"] == {"n": 1, "won": 1, "hit": 1.0, "priced": 0, "flat_return": 0.0,
                                             "model_said": 0.85, "ai_said": 0.7}
        assert rec["by_verdict"]["lower"]["flat_return"] == 0.9 and rec["brier"]["n"] == 3


class Refused(Resp):
    def __init__(self, code, status, message):
        super().__init__({"error": {"code": code, "status": status, "message": message}})
        self.status_code = code

    def raise_for_status(self):
        raise RuntimeError(f"{self.status_code}")


def test_no_search_call_says_so_and_a_dead_model_is_not_tried_again():
    R.DEAD_MODELS.clear()

    def get_pro(url, **kw):
        return Resp({"data": [{"id": "models/gemini-3.0-pro"}, {"id": "models/gemini-3.0-flash-lite"}]})
    seen, prompts = [], []

    def post(url, json=None, **kw):
        import json as j
        model = (json or {}).get("model") or url.split("/models/")[1].split(":")[0]
        seen.append((model, ":generateContent" in url))
        if "pro" in model:
            return Refused(404, "NOT_FOUND", "models/gemini-3.0-pro is not found for API version v1beta")
        if ":generateContent" in url:
            return Refused(429, "RESOURCE_EXHAUSTED", "Quota exceeded for metric: search_grounding, limit: 0")
        if "reasoning step of a football betting model" in json["messages"][0]["content"]:
            prompts.append(json["messages"][0]["content"])     # the verdict call (the panel asks through post too)
        ans = {"picks": [{"id": "0", "verdict": "back", "ai_chance": 0.8, "confidence": 0.3, "reasons": "x"}]}
        return Resp({"choices": [{"message": {"content": j.dumps(ans)}}]})
    old = R.BATCH
    R.BATCH = 1                                   # two batches, so the second one shows what was remembered
    try:
        doc = R.reason(PICKS, key="k", get=get_pro, post=post, now=NOW)
    finally:
        R.BATCH = old
    # batch 1: the dead model is asked once (no second, search-less try on it); the next model's search is refused
    # with Google's own reason, and it answers without search. Batch 2: the dead model is skipped.
    assert seen[:3] == [("gemini-3.0-pro", True), ("gemini-3.0-flash-lite", True), ("gemini-3.0-flash-lite", False)]
    assert ("gemini-3.0-pro", True) not in seen[3:] and ("gemini-3.0-pro", False) not in seen
    assert doc["model"] == "gemini-3.0-flash-lite" and doc["search"]["dead_models"] == ["gemini-3.0-pro"]
    assert doc["search"]["queries"] == 0 and "limit: 0" in doc["search"]["errors"][0]
    assert doc["picks"][0]["verdict"] == "back"             # the id came back as "0": still matched
    # the model is never told to search, or to name what it found, in a call that cannot search
    assert prompts and all("NO WEB SEARCH IN THIS CALL" in t and "SEARCH FIRST" not in t for t in prompts)
    assert all("sets no stake" in t and "now sets the stake" not in t for t in prompts)
    assert "SEARCH FIRST" in R._effective(R.PROMPT, True)
    R.DEAD_MODELS.clear()


def test_reflect_rewrites_lessons_once_a_day_and_keeps_old_ones_on_failure():
    with tempfile.TemporaryDirectory() as d:
        out, led = _graded_dir(d)
        les = Path(d) / "lessons.json"

        def post_les(url, json=None, **kw):
            import json as j
            return Resp({"choices": [{"message": {"content": j.dumps(
                {"lessons": ["only veto on a confirmed absence"], "summary": "vetoes on rumour won"})}}]})
        # two graded verdicts are no evidence: the old lessons are cleared WITHOUT asking a model for rules
        les.write_text(json.dumps({"football": {"lessons": ["a rule from one game"], "date": "2026-10-01"}}))

        def never(*a, **k):
            raise AssertionError("no evidence, so no model call")
        got = R.reflect("football", key="k", get=get, post=never, now=NOW, out_dir=out, ledger_dir=led,
                        lessons_path=les)
        assert got["lessons"] == [] and got["graded"] == 2 and got["evidence"] == [] and "nothing to learn" in got["summary"]
        # with a group the record supports, the model writes the lessons and is shown the evidence
        asked = []

        def post_ev(url, json=None, **kw):
            asked.append(json["messages"][0]["content"])
            return post_les(url, json=json, **kw)
        orig = R.evidence
        R.evidence = lambda rows, sport="football": [{"group": "verdict veto", "n": 25, "won": 24, "expected": 12.5, "z": 4.6}]
        try:
            got = R.reflect("football", key="k", get=get, post=post_ev, now=NOW, out_dir=out, ledger_dir=led,
                            lessons_path=les)
        finally:
            R.evidence = orig
        assert got["lessons"] == ["only veto on a confirmed absence"] and got["graded"] == 2
        assert "verdict veto: 24/25 won against 12.5 expected" in asked[0]
        les.write_text(json.dumps({"football": got}))                   # the runner saves it
        assert R.reflect("football", key="k", get=get, post=post_les, now=NOW, out_dir=out, ledger_dir=led,
                         lessons_path=les) is None                       # once a day

        def boom(*a, **k):
            raise ConnectionError("down")
        les2 = Path(d) / "l2.json"
        les2.write_text(json.dumps({"football": {"lessons": ["old"], "date": "2026-10-01", "graded": 1}}))
        R.evidence = lambda rows, sport="football": [{"group": "verdict veto", "n": 25, "won": 24, "expected": 12.5, "z": 4.6}]
        try:
            assert R.reflect("football", key="k", get=get, post=boom, now=NOW, out_dir=out, ledger_dir=led,
                             lessons_path=les2) is None                  # failed: nothing to save, old ones stay
        finally:
            R.evidence = orig


def test_model_chain_strongest_first_and_falls_back():
    def get_pro(url, **kw):
        return Resp({"data": [{"id": "models/gemini-3.0-pro"}, {"id": "models/gemini-3.0-flash"},
                              {"id": "models/gemini-3.0-flash-lite"}]})
    assert R.model_chain(get_pro, "k") == ["gemini-3.0-pro", "gemini-3.0-flash", "gemini-3.0-flash-lite"]
    seen = []

    def post_quota(url, json=None, **kw):
        import json as j
        model = (json or {}).get("model") or url.split("/models/")[1].split(":")[0]
        seen.append(model)
        if "pro" in model:
            raise RuntimeError("429 quota")
        if ":generateContent" in url:                      # the grounded call answers like Gemini does
            ans = {"picks": [{"id": 0, "verdict": "lower", "ai_chance": 0.75, "confidence": 0.5, "reasons": "x"},
                             {"id": 1, "verdict": "back", "ai_chance": 0.85, "confidence": 0.6, "reasons": "y"}]}
            return Resp({"candidates": [{"content": {"parts": [{"text": "Found news.\n" + j.dumps(ans)}]}}]})
        raise AssertionError("the grounded call should have answered")
    doc = R.reason(PICKS, key="k", get=get_pro, post=post_quota, now=NOW)
    assert doc["model"] == "gemini-3.0-flash" and seen[0] == "gemini-3.0-pro"
    assert [p["stake_factor"] for p in doc["picks"]] == [1.0, 1.0]
    assert [p["advised_stake_factor"] for p in doc["picks"]] == [0.75, 1.0]


def test_value_singles_get_verdicts_with_their_code():
    doc = dict(PICKS, value=[{"name": "Value 1", "code": "VAL111", "alt_legs": [
        {"fixture": "E v F", "market": "SB:1||Home", "pick": "E to win", "price": 1.9, "chance": 0.6}]}])
    rows = R.value_legs(doc)
    assert [(r["fixture"], r["code"]) for r in rows] == [("E v F", "VAL111")]
    assert R.value_legs(dict(PICKS, value=[{"code": "X", "alt_legs": [PICKS["singles"][0]]}])) == []


def test_eval_summary_compares_chances_on_the_same_picks():
    rows = [dict(model_chance=0.8, ai_chance=0.8, market_chance=0.6, anchored_chance=0.65, won=False),
            dict(model_chance=0.5, ai_chance=0.5, market_chance=None, anchored_chance=None, won=True)]
    s = R.eval_summary(rows)
    assert s["n"] == 1 and s["model_chance"] == 0.64 and s["market_chance"] == 0.36
    assert R.eval_summary([])["model_chance"] is None


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("reasoning_test OK")


def test_market_chance_and_absences_reach_the_verdict():
    s = {**PICKS["singles"][0], "sharp_p": 0.7753, "missing": {"home": 0.4724, "away": 0.2512}}
    row = R.context([s])[0]
    assert row["market_chance"] == 0.7753
    assert row["missing_value_share"] == {"home": 0.47, "away": 0.25}
    assert R.context(PICKS["singles"])[0]["missing_value_share"] is None
    assert "market_chance" in R.PROMPT and "market_chance" in R.PROMPT_NBA


def test_anchored_chance_stays_within_the_band_of_the_market():
    assert R.anchored_chance(0.90, 0.70) == 0.75
    assert R.anchored_chance(0.40, 0.70) == 0.65
    assert R.anchored_chance(0.72, 0.70) == 0.72
    assert R.anchored_chance(0.72, None) == 0.72      # no market price: the AI's own
    assert R.anchored_chance(None, 0.70) is None


def test_a_changed_prompt_re_reasons_the_board():
    board = {"generated_at": "2026-10-27T18:00:00"}
    v = R.prompt_version(R.PROMPT)
    assert v != R.prompt_version(R.PROMPT_NBA)
    assert R.reasoned_already({"picks_generated_at": board["generated_at"], "prompt_version": v}, board)
    assert not R.reasoned_already({"picks_generated_at": board["generated_at"], "prompt_version": "old"}, board)
    assert R.reasoned_already({"picks_generated_at": board["generated_at"]}, board)       # older files
    assert not R.reasoned_already({"picks_generated_at": "other"}, board)
    assert R.reasoned_already({"picks_generated_at": board["generated_at"], "prompt_version":
                               R.prompt_version(R.PROMPT_NBA)}, board, R.PROMPT_NBA)


def test_verdict_stakes_off_by_default_and_architect_switch_restores(monkeypatch):
    import importlib
    monkeypatch.delenv("VERDICT_STAKES", raising=False)
    m = importlib.reload(R)
    assert set(m.STAKE_FACTOR.values()) == {1.0} and m.ADVISED_STAKE_FACTOR["veto"] == 0.5
    monkeypatch.setenv("VERDICT_STAKES", "1")
    m = importlib.reload(R)
    assert m.STAKE_FACTOR == m.ADVISED_STAKE_FACTOR
    monkeypatch.delenv("VERDICT_STAKES")
    importlib.reload(R)
