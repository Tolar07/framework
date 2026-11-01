"""engine/fact_sheet.py — step 2 of the bot-training plan (2026-11-01). Recorded only."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine import fact_sheet as FS  # noqa: E402

KEYS = {"gemini": "g", "nvidia": "n", "openrouter": "o"}
FREE = {"data": [{"id": "google/gemma-4-31b-it:free", "pricing": {"prompt": "0", "completion": "0"}}]}
SINGLE = {"fixture": "Ajax v PSV", "home": "Ajax", "away": "PSV", "league": "Eredivisie",
          "kickoff_utc": "2026-11-02T13:30:00Z", "market": "SB:1||Home", "pick": "Ajax to win", "price": "2.10"}


class Resp:
    def __init__(self, body, status=200):
        self.body, self.status_code = body, status

    def json(self):
        return self.body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def get(url, **kw):
    return Resp(FREE) if "openrouter" in url else Resp({"data": [{"id": "gemini-3.5-flash-lite"}]})


def poster(gem: dict, readers: dict, gem_status=200):
    """Gemini (search) answers `gem` for fixture 0; each reader answers its dict."""
    sent = []

    def post(url, json=None, **kw):
        if ":generateContent" in url:
            sent.append("gemini")
            if gem_status != 200:
                return Resp({}, gem_status)
            text = __import__("json").dumps({"fixtures": [{"id": 0, "evidence": "BBC: Ajax miss 3 starters.", **gem}]})
            return Resp({"candidates": [{"content": {"parts": [{"text": text}]}}]})
        name = "openrouter" if "openrouter" in url else "nvidia"
        sent.append(name)
        assert "BBC: Ajax miss 3 starters." in json["messages"][0]["content"]   # readers see the evidence
        body = __import__("json").dumps({"fixtures": [{"id": 0, **readers[name]}]})
        return Resp({"choices": [{"message": {"content": body}}]})
    post.sent = sent
    return post


def test_a_fact_counts_only_when_two_members_agree():
    post = poster({"key_absences_home": 3, "derby": True, "motivation_away": "high"},
                  {"nvidia": {"key_absences_home": 2, "derby": False, "motivation_away": "high"},
                   "openrouter": {"key_absences_home": None, "derby": False, "motivation_away": None}})
    doc = FS.build({"date": "2026-11-02", "generated_at": "x", "singles": [dict(SINGLE)]},
                   keys=KEYS, get=get, post=post)
    f = doc["fixtures"][0]
    assert f["agreed"]["key_absences_home"] in (2, 3)        # within 1 of each other: agreed
    assert f["agreed"]["derby"] is False                     # two said no
    assert f["agreed"]["motivation_away"] == "high"
    assert "rest_days_home" not in f["agreed"]               # nobody knew: stays unknown
    facts = {x["fact"]: x for x in doc["picks"][0]["facts"]}
    assert facts["key_absences"]["direction"] == -1          # Ajax's absences hurt an Ajax pick
    assert facts["motivation_high"]["direction"] == -1       # a motivated opponent hurts it too
    assert doc["recorded_only"] is True


def test_one_model_alone_is_never_used():
    post = poster({"rotation_home": True}, {"nvidia": {"rotation_home": None}, "openrouter": {"rotation_home": None}})
    doc = FS.build({"date": "d", "singles": [dict(SINGLE)]}, keys=KEYS, get=get, post=post)
    assert doc["fixtures"][0]["agreed"] == {}
    assert doc["picks"][0]["facts"] == []


def test_no_gemini_evidence_means_no_readers_and_nothing_agreed():
    post = poster({}, {}, gem_status=500)
    doc = FS.build({"date": "d", "singles": [dict(SINGLE)]}, keys=KEYS, get=get, post=post)
    assert post.sent.count("nvidia") == 0 and post.sent.count("openrouter") == 0
    assert doc["fixtures"][0]["evidence"] == "PENDING"
    assert doc["fields_agreed"] == 0


def test_clean_and_agree():
    assert FS.clean("rest_days_home", "4") == 4
    assert FS.clean("rest_days_home", "unknown") is None
    assert FS.clean("derby", "yes") is True
    assert FS.clean("motivation_home", "VERY") is None
    assert FS.agree("rest_days_home", [3, 4, None]) == (3, 2) or FS.agree("rest_days_home", [3, 4, None])[1] == 2
    assert FS.agree("rest_days_home", [3, 7, None])[0] is None
    assert FS.agree("referee", ["M. Oliver", "m. oliver", None])[0] == "M. Oliver"


def test_study_sets_facts_against_the_market():
    tmp = Path(tempfile.mkdtemp())
    out, led = tmp / "facts", tmp / "picks"
    out.mkdir()
    led.mkdir()
    picks = [{"fixture": f"T{i} v U{i}", "market": "SB:1||Home", "facts": [
        {"fact": "key_absences", "side": "home", "direction": -1, "size": 0.6}]} for i in range(4)]
    (out / "facts_2026-11-01.json").write_text(json.dumps({"date": "2026-11-01", "picks": picks}))
    singles = [{"fixture": f"T{i} v U{i}", "market": "SB:1||Home", "price": "2.0",
                "result": "won" if i == 0 else "lost"} for i in range(4)]
    (led / "picks_2026-11-01.json").write_text(json.dumps({"singles": singles}))
    rec = FS.study(out, led)
    cell = rec["facts"]["key_absences (-)"]
    assert rec["graded_picks"] == 4 and cell["n"] == 4
    assert cell["won_rate"] == 0.25 and cell["market_rate"] == 0.5 and cell["residual"] == -0.25
    assert cell["trusted"] is False
    assert "key_absences (-)" in FS.summary_line(rec)


def main() -> None:
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("fact_sheet_test OK")


if __name__ == "__main__":
    main()
