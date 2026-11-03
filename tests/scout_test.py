"""engine/scout.py: recorded-only scout section. Offline: Gemini / NVIDIA / OpenRouter are stubbed."""
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from engine import scout as S  # noqa: E402


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

# ── absences: cleaned, confirmed only by FotMob, signed on each pick ────────
row = {"direction": "over", "confidence": 0.6, "absences": [
    {"player": "Thibaut Courtois", "team": "home", "role": "goalkeeper", "status": "out"},
    {"player": "X", "team": "home", "role": "goalkeeper", "status": "out"},          # name too short
    {"player": "Some One", "team": "middle", "role": "goalkeeper", "status": "out"},  # bad team
    {"player": "Jude Bellingham", "team": "home", "role": "midfielder", "status": "doubtful"}]}
c = S.clean(row)
assert [a["player"] for a in c["absences"]] == ["Thibaut Courtois", "Jude Bellingham"]
assert all(a["confirmed_by"] is None for a in c["absences"])
assert S.same_player("T. Courtois", "Thibaut Courtois") and S.same_player("Thibaut Courtois", "Thibaut Courtois")
assert not S.same_player("Thibaut Courtois", "Andriy Lunin") and not S.same_player("Kevin Courtois", "Thibaut Courtois")
assert S.same_player("Vinícius", "Vinicius")
rec = {"fixture": "Real Madrid v Barcelona", **c}
news = {"Real Madrid v Barcelona": {"absent": [{"name": "Thibaut Courtois", "side": "home", "type": "injury"},
                                               {"name": "Jude Bellingham", "side": "home", "type": "injury"}]}}
assert S.confirm(rec, {}) == 0 and S.confirm(rec, {"Real Madrid v Barcelona": {"absent": [
    {"name": "Thibaut Courtois", "side": "away"}]}}) == 0, "wrong side never confirms"
assert S.confirm(rec, news) == 1, "only an OUT absence confirms (doubtful does not)"
gk = [a for a in rec["absences"] if a["confirmed_by"]]
assert gk[0]["player"] == "Thibaut Courtois"
# the Architect's example: Real Madrid's first goalkeeper out -> goals up, Madrid weaker
assert S.pick_effect("SB:29||Yes", gk) == 1 and S.pick_effect("SB:29||No", gk) == -1
assert S.pick_effect("SB:18|total=2.5|Over 2.5", gk) == 1 and S.pick_effect("SB:18|total=3.5|Under 3.5", gk) == -1
assert S.pick_effect("SB:1||Home", gk) == -1 and S.pick_effect("SB:1||Away", gk) == 1
assert S.pick_effect("SB:10||Home or Draw", gk) == -1 and S.pick_effect("SB:10||Draw or Away", gk) == 1
assert S.pick_effect("SB:16|hcp=-1.5|Away (+1.5)", gk) == 1 and S.pick_effect("SB:33||Yes", gk) == -1
assert S.pick_effect("SB:20|total=1.5|Over 1.5", gk) == 1, "away goals up when the home keeper is out"
assert S.pick_effect("SB:19|total=1.5|Over 1.5", gk) == 0, "home goals: the home keeper doesn't matter"
fwd = [{"player": "Kylian Mbappe", "team": "home", "role": "forward", "status": "out", "confirmed_by": "FotMob"}]
assert S.pick_effect("SB:18|total=4.5|Under 4.5", fwd) == 1 and S.pick_effect("SB:19|total=0.5|Over 0.5", fwd) == -1
assert S.pick_effect("SB:1||Home", [{**gk[0], "confirmed_by": None}]) == 0, "unconfirmed moves nothing"
assert S.pick_effect("SB:10||Home or Away", gk) == 0
# FotMob drops him (he's back): the confirmation is withdrawn
assert S.confirm(rec, {"Real Madrid v Barcelona": {"absent": []}}) == 0
assert not any(a["confirmed_by"] for a in rec["absences"])

# ── run(): FotMob confirms at scout time; a new board is re-searched, the same board only re-checked ──
with tempfile.TemporaryDirectory() as t:
    led, out, nd = Path(t, "picks"), Path(t, "reasoning"), Path(t, "features")
    led.mkdir(), nd.mkdir()
    board = {"date": "2026-11-04", "generated_at": "g1", "rated": [], "singles": [
        {"fixture": "Real Madrid v Barcelona", "home": "Real Madrid", "away": "Barcelona", "league": "La Liga",
         "kickoff": "2026-11-04", "market": "SB:18|total=3.5|Under 3.5"}]}
    (led / "picks_2026-11-04.json").write_text(json.dumps(board))
    n_posts = []

    def post_gk(url, **k):
        n_posts.append(url)
        return R(gemini_body([{"id": 0, "direction": "over", "confidence": 0.58, "finding": "Courtois out",
                               "sources": ["https://x.com/rm"], "absences": [
                                   {"player": "Thibaut Courtois", "team": "home", "role": "goalkeeper", "status": "out"}]}]))
    kw = dict(keys={"gemini": "k"}, get=fake_get, post=post_gk, sleep=lambda s: None)
    S.run(["2026-11-04"], ledger_dir=led, out_dir=out, news_folder=nd, **kw)
    S._EFFECTS.clear()
    s1 = board["singles"][0]
    assert S.single_effect(s1, out) == 0, "no FotMob news yet: nothing confirmed"
    (nd / "news_2026-11-04.json").write_text(json.dumps(news))
    lines = S.run(["2026-11-04"], ledger_dir=led, out_dir=out, news_folder=nd, **kw)
    assert len(n_posts) == 1 and "re-checked" in lines[0] and "1 absences confirmed" in lines[0], lines
    S._EFFECTS.clear()
    assert S.single_effect(s1, out) == -1, "Under 3.5 hurt by a confirmed goalkeeper absence"
    (nd / "news_2026-11-04.json").write_text(json.dumps({"Real Madrid v Barcelona": {"absent": []}}))
    S.run(["2026-11-04"], ledger_dir=led, out_dir=out, news_folder=nd, **kw)
    S._EFFECTS.clear()
    assert S.single_effect(s1, out) == 0 and len(n_posts) == 1, "he's back: the withdrawal is saved, no new search"
    assert S.run(["2026-11-04"], ledger_dir=led, out_dir=out, news_folder=nd, **kw) == [], "nothing new: no write"
    (nd / "news_2026-11-04.json").write_text(json.dumps(news))
    S.run(["2026-11-04"], ledger_dir=led, out_dir=out, news_folder=nd, **kw)
    board["generated_at"] = "g2"
    (led / "picks_2026-11-04.json").write_text(json.dumps(board))
    S.run(["2026-11-04"], ledger_dir=led, out_dir=out, news_folder=nd, **kw)
    assert len(n_posts) == 2, "a new board (morning refresh) is searched again"
    # ── experiment engine: S10 / A8 / T8 drop what a confirmed absence hurts ──
    from engine import experiments as X
    S._EFFECTS.clear()
    S.OUT_DIR, old_dir = out, S.OUT_DIR
    try:
        lg = X.leg(s1)
        assert lg["scout"] == -1
        by = {st.name: st for st in X.strategies()}
        assert not by["S10 scout: no confirmed hurt"].keep(lg, {}) and by["S10 scout: no confirmed hurt"].wireable
        assert not by["A8 accas: no scout-hurt leg"].keep(lg, {}) and not by["T8 50%+ accas: no scout-hurt leg"].keep(lg, {})
        os.environ["SCOUT_ENABLED"] = "0"
        S._EFFECTS.clear()
        assert X.leg(s1)["scout"] == 0, "kill switch: the scout moves nothing"
        os.environ.pop("SCOUT_ENABLED")
    finally:
        S.OUT_DIR = old_dir
        S._EFFECTS.clear()

# ── FotMob checked directly (full list, not the 3-a-side file) ──────────────
class FM:
    calls = []

    def team_news(self, mid):
        FM.calls.append(mid)
        return {"home": {"missing": [{"name": f"Player {i}", "type": "injury"} for i in range(5)]
                         + [{"name": "Thibaut Courtois", "type": "injury"}]}, "away": {"missing": []}}


bd = {"singles": [{"fixture": "Real Madrid v Barcelona", "fotmob_id": 99}, {"fixture": "Quiet v Game", "fotmob_id": 7}]}
dc = {"fixtures": [{"fixture": "Real Madrid v Barcelona", "absences": [
    {"player": "Thibaut Courtois", "team": "home", "role": "goalkeeper", "status": "out", "confirmed_by": None}]},
    {"fixture": "Quiet v Game", "absences": []}]}
fresh = S.fotmob_news(bd, dc, FM())
assert FM.calls == [99], "only fixtures where the scout reported a starter missing"
assert S.confirm_doc(dc, fresh) == 1, "the 6th name on FotMob's list still confirms"
assert S.fotmob_news(bd, dc, type("Down", (), {"team_news": staticmethod(boom)})()) == {}, "FotMob down: nothing, no raise"

# ── board-time cutoff: a confirmation after the board was built doesn't count for that board ──
ab = [{"player": "T Courtois", "team": "home", "role": "goalkeeper", "status": "out",
       "confirmed_by": "FotMob", "confirmed_at": "2026-11-04T12:00:00Z"}]
assert S.pick_effect("SB:29||No", ab) == -1
assert S.pick_effect("SB:29||No", ab, before="2026-11-04T06:47:00Z") == 0, "board built before the confirmation"
assert S.pick_effect("SB:29||No", ab, before="2026-11-04T13:00:00Z") == -1

# ── recorded only: nothing in the scout touches picks, stakes or gates ───────
src = Path(ROOT, "engine", "scout.py").read_text()
for banned in ("stake_pct", "assert_paper_only", "variant_selection", "booking_tracker", "constitution"):
    assert banned not in src, banned
print("scout_test: ok")
