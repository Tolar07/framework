"""engine/multisport_reasoning.py (framework#353): every rollout sport's picks are scouted and judged like
football's and the NBA's, ADVISORY and recorded only, and scored against results. Offline: Gemini is stubbed."""
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from engine import multisport_reasoning as MR  # noqa: E402
from engine import scout as SC  # noqa: E402


class Resp:
    def __init__(self, body, code=200):
        self._b, self.status_code = body, code

    def json(self):
        return self._b

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


def fake_get(*a, **k):
    return Resp({"models": [{"name": "models/gemini-3.5-flash"}], "data": [{"id": "gemini-3.5-flash"}]})


PROMPTS: list = []


def fake_post(url, **k):
    text = (k.get("json") or {}).get("contents", [{}])[0].get("parts", [{}])[0].get("text", "") \
        if "generateContent" in url else (k.get("json") or {}).get("messages", [{}])[0].get("content", "")
    PROMPTS.append(text)
    if "FIXTURES:" in text:
        body = {"fixtures": [{"id": 0, "direction": "home", "confidence": 0.62, "finding": "starting goalie confirmed",
                              "sources": ["https://example.com/news"],
                              "absences": [{"player": "Some Goalie", "team": "away", "role": "goalie", "status": "out"}]}]}
    else:
        body = {"picks": [{"id": 0, "verdict": "lower", "ai_chance": 0.55, "confidence": 0.5, "reasons": "backup in net"}]}
    return Resp({"candidates": [{"content": {"parts": [{"text": json.dumps(body)}]}}]})


def ih_board(result=None, pick_result=None):
    return {"date": "2026-11-12", "sport": "ice_hockey", "games": {
        "g1": {"comp": "NHL", "home": "Florida Panthers", "away": "Washington Capitals", "ko": "2026-11-12T00:00:00Z",
               "matchbook": True, "sides": {}, "result": result},
        "g2": {"comp": "SRL League", "country": "Simulated Reality", "home": "A (Srl)", "away": "B (Srl)",
               "ko": "2026-11-12T01:00:00Z", "matchbook": True, "sides": {}, "result": None}},
        "picks": [{"sb_event_id": "g1", "home": "Florida Panthers", "away": "Washington Capitals", "comp": "NHL",
                   "ko": "2026-11-12T00:00:00Z", "sport": "ice_hockey", "pick": "Florida Panthers",
                   "key": "H:406||Home", "price": 1.9, "fair": 0.56, "value": 0.064, "source": "matchbook",
                   "chance": 0.56, "code": "ABC", "result": pick_result, "clv_fair": 0.02 if pick_result else None}]}


# every rollout sport is covered, each with its own team news in the scout's question
assert set(MR.SPORTS) == set(SC.MS_SPORTS) and len(MR.SPORTS) == 10
for s in MR.SPORTS:
    assert s in MR.NEWS and MR.NEWS[s] in MR.scout_prompt(s) and "PICKS:" in MR.prompt_for(s)
assert "STARTING GOALIE" in MR.scout_prompt("ice_hockey") and "STARTING PITCHER" in MR.scout_prompt("baseball")
assert "QUARTERBACK" in MR.scout_prompt("american_football") and "PLAYING XI" in MR.scout_prompt("cricket")
assert "TEAM SHEETS" in MR.scout_prompt("rugby") and "WITHDRAWALS" in MR.scout_prompt("tennis")
assert "does not set a stake" in MR.prompt_for("tennis"), "advisory: the prompt never says the verdict stakes"
assert MR.split("H:406||Home") == ("406", "", "Home") and MR.split("tennis:202|setnr=1|Away") == ("202", "setnr=1", "Away")

with tempfile.TemporaryDirectory() as t:
    out, ms, ih = Path(t, "reasoning"), Path(t, "multisport"), Path(t, "ice_hockey")
    ih.mkdir()
    (ih / "ih_2026-11-12.json").write_text(json.dumps(ih_board()), encoding="utf-8")
    (ms / "tennis").mkdir(parents=True)
    (ms / "tennis" / "ms_2026-11-12.json").write_text(json.dumps({"date": "2026-11-12", "games": {}, "picks": []}))
    kw = {"key": "k", "keys": {"gemini": "k"}, "get": fake_get, "post": fake_post, "sleep": lambda s: None}
    lines = MR.run(["2026-11-12"], out_dir=out, ms_dir=ms, ih_dir=ih, **kw)
    assert any(x.startswith("ice_hockey 2026-11-12: 1 picks, 1 judged now") for x in lines), lines
    assert any(x.startswith("tennis 2026-11-12: no picks") for x in lines), lines
    sdoc = json.loads((out / "scout_ms_ice_hockey_2026-11-12.json").read_text(encoding="utf-8"))
    assert sdoc["recorded_only"] and sdoc["sport"] == "ice_hockey"
    assert [f["fixture"] for f in sdoc["fixtures"]] == ["Florida Panthers v Washington Capitals"], "simulated games skipped"
    assert sdoc["fixtures"][0]["absences"][0]["role"] == "goalie"
    rdoc = json.loads((out / "reasoning_ms_ice_hockey_2026-11-12.json").read_text(encoding="utf-8"))
    p = rdoc["picks"][0]
    assert rdoc["advisory"] and p["verdict"] == "lower" and p["stake_factor"] == 1.0, "advisory: never sizes a stake"
    assert p["market_chance"] == 0.56 and p["anchored_chance"] == 0.55
    assert any("starting goalie confirmed" in x for x in PROMPTS if "PICKS:" in x), "the scout's finding is in the context"
    n = len(PROMPTS)
    MR.run(["2026-11-12"], out_dir=out, ms_dir=ms, ih_dir=ih, **kw)
    assert len(PROMPTS) == n, "a judged pick and a scouted fixture are not asked again"

    # no key: PENDING, never a made-up verdict (HR35)
    d2, _ = MR.reason_day("ice_hockey", "2026-11-12", ih_board(), None, Path(t, "r2"), key="", ms_dir=ms, ih_dir=ih)
    assert d2["picks"][0]["verdict"] == "PENDING" and d2["note"].startswith("NO DATA")

    # graded: the verdict is scored, the scout call too (Florida won 3-2)
    (ih / "ih_2026-11-12.json").write_text(json.dumps(ih_board({"final": [3, 2], "reg": [2, 2]}, "won")), encoding="utf-8")
    rec = MR.record(out, ms, ih)
    s = rec["sports"]["ice_hockey"]
    assert s["graded"] == 1 and s["by_verdict"]["lower"] == {"n": 1, "won": 1, "flat_return": 0.9, "close_value": 0.02}
    assert s["brier"]["n"] == 1 and rec["advisory"]
    assert MR.summary_line(rec).startswith("Multi-sport reasoning (advisory, recorded): ice_hockey lower 1/1")
    old_ih = MR.IH_DIR
    MR.IH_DIR = ih
    try:
        assert SC.ms_results("ice_hockey", "2026-11-12") == {"Florida Panthers v Washington Capitals": "1-0"}
        srec = Path(t, "scout_record.json")
        assert SC.grade(out, Path(t, "none"), srec) == 1, "the multi-sport scout call is graded like football's"
        assert SC.load_record(srec)["history"][0]["won"] is True
    finally:
        MR.IH_DIR = old_ih

# kill switch
os.environ["MS_REASONING"] = "0"
assert MR.run(["2026-11-12"])[0].startswith("multi-sport reasoning: switched off")
os.environ.pop("MS_REASONING")

if __name__ == "__main__":
    print("multisport_reasoning_test: OK")
