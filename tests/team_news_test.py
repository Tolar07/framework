"""
Offline test of team news (improvement #2): pick-side inference, the
value-weighted absence / rotation assessment, and the pre-kickoff check that
flags a weakened pick and names the slips carrying it. No network.
"""
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine import team_news as tn
from engine import full_markets as fm
import news_check

assert tn.pick_side("1X2_HOME") == "home"
assert tn.pick_side(fm.key(16, "hcp=-1.5", "Away (+1.5)")) == "away"
assert tn.pick_side(fm.key(20, "total=2.5", "Under 2.5")) == "home", "away under = backs home defence"
assert tn.pick_side(fm.key(18, "total=2.5", "Over 2.5")) is None
print("pick side: OK")

full = {"name": "A", "xi_value": 100, "missing": [], "missing_share": 0.0}
weak = {"name": "B", "xi_value": 40, "missing": [{"name": "Star", "value": 40}],
        "missing_share": 0.5}
news = {"lineup_type": "confirmed", "home": full, "away": weak}
assert tn.assess("1X2_AWAY", news, {"home": 100, "away": 90})["level"] == "RISK"
assert tn.assess("1X2_HOME", news)["level"] == "OK", "opponent absences are support, not risk"
assert tn.assess("1X2_HOME", None)["level"] == "NO NEWS"
print("assessment: OK")

with tempfile.TemporaryDirectory() as d:
    news_check.LEDGER_DIR = Path(d)
    pick = {"fixture": "A v B", "home": "A", "away": "B", "market": "1X2_AWAY", "pick": "B to win",
            "price": 1.5, "code": "X1", "fotmob_id": 1, "kickoff_utc": "2026-10-03T14:00:00Z",
            "predicted_xi": {"home": 100, "away": 90}, "lineup_check": None}
    later = dict(pick, fixture="C v D", fotmob_id=2, kickoff_utc="2026-10-03T19:00:00Z")
    doc = {"date": "2026-10-03", "singles": [pick, later],
           "accas": [{"name": "Acca A", "code": "AC1", "legs": ["A v B", "C v D"]}],
           "safe3": [], "megas": []}
    (Path(d) / "picks_2026-10-03.json").write_text(json.dumps(doc), encoding="utf-8")
    news_check.fotmob.team_news = lambda mid: news
    msg = news_check.run(now=datetime(2026, 10, 3, 13, 0, tzinfo=timezone.utc), send=False)
    assert "RISK: A v B" in msg and "Acca A (AC1)" in msg, msg
    out = json.loads((Path(d) / "picks_2026-10-03.json").read_text(encoding="utf-8"))
    assert out["singles"][0]["lineup_check"]["level"] == "RISK"
    assert out["singles"][1]["lineup_check"] is None, "19:00 kickoff is outside the window"
print("pre-kickoff check: OK")

# --- closing-line value capture (#5) ------------------------------------------
event = {"eventId": "sr:match:1", "markets": [
    {"id": "16", "desc": "Asian Handicap", "specifier": "hcp=-1.5",
     "outcomes": [{"desc": "Away (+1.5)", "odds": "1.30"}]},
    {"id": "1", "desc": "1X2", "specifier": "",
     "outcomes": [{"desc": "Home", "odds": "1.40"}]}]}
assert news_check._price(event, {"id": 16, "desc": None, "spec": "hcp=-1.5",
                                 "outcome": "Away (+1.5)"}) == 1.30
assert news_check._price(event, {"id": None, "desc": "1X2", "spec": "",
                                 "outcome": "Home"}) == 1.40
import urllib.request as _ur


class _Resp:
    def __init__(self, body): self.body = body
    def read(self): return self.body
    def __enter__(self): return self
    def __exit__(self, *a): return False


_ur.urlopen = lambda req, timeout=0: _Resp(json.dumps(
    {"data": {"tournaments": [{"events": [event]}]}}).encode())
doc = {"singles": [{"sb_event_id": "sr:match:1", "sb_tid": "sr:tournament:9", "price": 1.50,
                    "kickoff_utc": "2026-10-03T14:00:00Z", "closing_price": None, "clv": None,
                    "sb_market": {"id": None, "desc": "1X2", "spec": "", "outcome": "Home"}}]}
n = news_check.capture_closing(doc, datetime(2026, 10, 3, 13, 40, tzinfo=timezone.utc))
assert n == 1 and doc["singles"][0]["closing_price"] == 1.40
assert doc["singles"][0]["clv"] == round((1.50 / 1.40 - 1) * 100, 2), "entry 1.50 into a 1.40 close = +7.14%"
print("closing-line capture: OK")

print("\n✅ ALL TEAM-NEWS TESTS PASSED")
