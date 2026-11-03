"""engine/scout.py: recorded-only scout section. Offline: Gemini / NVIDIA / OpenRouter are stubbed."""
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from engine import scout as S  # noqa: E402
from engine import verdict_panel as VP  # noqa: E402


class R:
    def __init__(self, body, code=200):
        self._b, self.status_code = body, code

    def json(self):
        return self._b

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


def gemini_body(rows):
    return {"candidates": [{"content": {"parts": [{"text": "```json\n" + json.dumps({"fixtures": rows}) + "\n```"}]}}]}


def fake_get(*a, **k):
    return R({"models": [{"name": "models/gemini-3.5-flash-lite", "supportedGenerationMethods": ["generateContent"]}],
              "data": []})


FX = [{"id": 0, "fixture": "A v B", "home": "A", "away": "B", "league": "L", "kickoff_utc": "x", "sport": "football"},
      {"id": 1, "fixture": "C v D", "home": "C", "away": "D", "league": "L", "kickoff_utc": "x", "sport": "football"}]

# ── clean ────────────────────────────────────────────────────────────────────
assert S.clean({"direction": "home", "confidence": 0.7, "sources": ["https://a.b", "junk"], "finding": "x"})["sources"] == ["https://a.b"]
assert S.clean({"direction": "home", "confidence": None}) is None, "a call needs a probability"
assert S.clean({"direction": "home", "confidence": 1.4}) is None
assert S.clean({"direction": "none", "confidence": 0.9})["confidence"] is None
assert S.clean({"direction": "over", "confidence": 0.6}, S.NBA_DIRECTIONS) is None, "no goals lines in the NBA"
assert S.clean({"direction": "sideways"}) is None and S.clean("junk") is None

# ── outcome ──────────────────────────────────────────────────────────────────
assert S.outcome("football", "home", "2-1") and not S.outcome("football", "away", "2-1")
assert S.outcome("football", "draw", "1-1") and S.outcome("football", "over", "2-1") and S.outcome("football", "under", "1-1")
assert S.outcome("nba", "away", "94-103") and S.outcome("nba", "over", "94-103") is None
assert S.outcome("football", "none", "1-1") is None and S.outcome("football", "home", "") is None

# ── kill switch ──────────────────────────────────────────────────────────────
os.environ.pop("SCOUT_ENABLED", None)
assert S.enabled()
os.environ["SCOUT_ENABLED"] = "0"
assert not S.enabled() and S.run(["2026-11-03"])[0].startswith("scout: switched off")
assert S.summary_line() == "Scout: switched off"
os.environ.pop("SCOUT_ENABLED")

# ── scout(): Gemini answers; unusable rows dropped ───────────────────────────
calls = []


def post_ok(url, **k):
    calls.append(url)
    return R(gemini_body([{"id": 0, "direction": "home", "confidence": 0.71, "finding": "XI confirmed", "sources": ["https://x.com/a"]},
                          {"id": 1, "direction": "home"}]))


res = S.scout(FX, keys={"gemini": "k"}, get=fake_get, post=post_ok, sleep=lambda s: None)
assert [f["fixture"] for f in res["fixtures"]] == ["A v B"] and res["fixtures"][0]["tag"] == "scout"

# ── never raises; Gemini 429 everywhere -> NVIDIA fallback, no search ────────
def post_429_then_nvidia(url, **k):
    if "generativelanguage" in url and "generateContent" in url:
        return R({}, 429)
    return R({"choices": [{"message": {"content": json.dumps({"fixtures": [
        {"id": 0, "direction": "away", "confidence": 0.6, "finding": "f", "sources": []}]})}}]})


res = S.scout(FX, keys={"gemini": "k", "nvidia": "n"}, get=fake_get, post=post_429_then_nvidia, sleep=lambda s: None)
assert res["fixtures"] and res["fixtures"][0]["via"].startswith("nvidia") and res["fixtures"][0]["sources"] == []


def boom(*a, **k):
    raise RuntimeError("down")


res = S.scout(FX, keys={"gemini": "k"}, get=boom, post=boom, sleep=lambda s: None)
assert res["fixtures"] == [], "a failing scout returns nothing, never raises"

# ── run(): writes beside the verdicts, once a day; a failure is only a line ──
with tempfile.TemporaryDirectory() as t:
    led, out = Path(t, "picks"), Path(t, "reasoning")
    led.mkdir()
    (led / "picks_2026-11-03.json").write_text(json.dumps({"date": "2026-11-03", "singles": [
        {"fixture": "A v B", "home": "A", "away": "B", "league": "L", "kickoff_utc": "x"}], "rated": []}))
    (led / "nba_2026-11-03.json").write_text(json.dumps({"date": "2026-11-03", "picks": [
        {"home": "Orlando Magic", "away": "Washington Wizards", "score": "94-103", "stage": "regular"}], "picks_dropped": []}))
    kw = dict(keys={"gemini": "k"}, get=fake_get, post=post_ok, sleep=lambda s: None)
    lines = S.run(["2026-11-03"], ledger_dir=led, out_dir=out, **kw)
    assert (out / "scout_2026-11-03.json").exists() and len(lines) == 2, lines
    doc = json.loads((out / "scout_2026-11-03.json").read_text())
    assert doc["recorded_only"] and doc["tag"] == "scout" and doc["fixtures"][0]["direction"] == "home"
    assert S.run(["2026-11-03"], ledger_dir=led, out_dir=out, **kw) == [], "one scout per board per day"
    # ── grading: A v B ended 1-2, home call lost; Brier/log-loss ──
    (led / "picks_2026-11-03.json").write_text(json.dumps({"date": "2026-11-03", "singles": [], "rated": [
        {"fixture": "A v B", "ft": "1-2"}]}))
    rec = Path(t, "scout_record.json")
    assert S.grade(out, led, rec) == 2 and S.grade(out, led, rec) == 0, "football + NBA call, graded once"
    st = S.stats(S.load_record(rec)["history"])
    assert st["n"] == 2 and st["hit"] == 0
    line = S.summary_line(rec)
    assert line.startswith("Scout (recorded only): 2 graded calls, hit 0%") and "Brier" in line and "log-loss" in line

# ── recorded only: nothing in the scout touches picks, stakes or gates ───────
src = Path(ROOT, "engine", "scout.py").read_text()
for banned in ("stake", "assert_paper_only", "variant_selection", "booking_tracker", "constitution"):
    assert banned not in src.replace("Nothing here selects, stakes", ""), banned
print("scout_test: ok")
