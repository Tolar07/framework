"""
Offline test of NBA team news per pick (engine/nba_team_news.py, framework #329): which side a pick
leans on, minutes-lost share (Out and Questionable weighted), HURT / HELPED / NEUTRAL verdicts for
winner, team total and game total picks, PENDING when data is missing (HR35), record-only output,
alerts only on a change. No network.
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine import nba_team_news as t


def rows(team, mins):
    out = []
    for g in ("g1", "g2", "g3"):
        for pid, m in mins.items():
            out.append({"d": "2026-11-0" + g[1], "g": g, "t": team, "p": pid, "n": pid.upper(), "m": m,
                        "pts": m / 2, "s": m > 25})
    return out


R = rows("BOS", {"a": 36, "b": 30, "c": 24, "d": 20, "e": 20, "f": 20, "g": 20, "h": 20, "i": 20, "j": 10}) \
    + rows("LAL", {"k": 36, "l": 30, "m": 24, "n": 20, "o": 20, "p": 20, "q": 20, "r": 20, "s": 20, "t": 10})

assert t.pick_side("219", "Home") == "home" and t.pick_side("228", "Over 110.5") == "away"
assert t.pick_side("225", "Over 220.5") is None
assert t.sits_chance("Out") == 1.0 and t.sits_chance("Questionable") == 0.5 and t.sits_chance("Probable") == 0.0

inj_star = {"BOS": [{"id": "a", "name": "A", "status": "Out"}], "LAL": []}
h = t.team_loss(R, "BOS", inj_star["BOS"])
assert abs(h["lost_share"] - 36 / 220) < 0.001, h
q = t.team_loss(R, "BOS", [{"id": "a", "name": "A", "status": "Questionable"}])
assert abs(q["lost_share"] - 18 / 220) < 0.001, "questionable counts half"
a = t.team_loss(R, "LAL", [])
assert a["lost_share"] == 0.0

assert t.assess("219", "Home", h, a)["verdict"] == "HURT"
assert t.assess("219", "Away", h, a)["verdict"] == "HELPED"
assert t.assess("228", "Over 100.5", h, a)["verdict"] == "NEUTRAL", "away team total ignores the home absence"
assert t.assess("227", "Under 100.5", h, a)["verdict"] == "HELPED"
assert t.assess("225", "Over 220.5", h, a)["verdict"] == "HURT"
assert t.assess("225", "Under 220.5", h, a)["verdict"] == "HELPED"
assert t.assess("66", "Home (-2.5)", h, a)["verdict"] == "NOT JUDGED"
assert t.assess("219", "Home", h, a)["level"] == "CAUTION"

none = t.team_loss(R, "BOS", None)
assert t.assess("219", "Home", none, a)["verdict"] == "PENDING", "missing report reads PENDING"
assert t.team_loss([], "BOS", [])["lost_share"] is None, "no box scores reads PENDING"

picks = [{"event_id": "e1", "pick": "Boston to win", "market_id": "219", "outcome": "Home"}]
v = t.assess_game(R, "BOS", "LAL", inj_star, picks)
assert v[0]["verdict"] == "HURT" and v[0]["event_id"] == "e1"
seen = {}
assert len(t.changes(v, seen)) == 1 and t.changes(v, seen) == [], "alert once, then only on change"
with tempfile.TemporaryDirectory() as d:
    t.record("2026-11-06", "now", "LAL@BOS", v, Path(d))
    assert (Path(d) / "2026-11-06.jsonl").read_text().count("HURT") == 1
print("nba_team_news_test OK")
