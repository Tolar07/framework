"""engine/ms_team_news.py (framework#354): each rollout sport's own team news flags its picks, RECORDED ONLY,
without false flags (a tandem, a priced-in absence, a re-scheduled match are not news). Offline: ESPN stubbed."""
import json
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from engine import ms_team_news as T  # noqa: E402

NOW = datetime(2026, 11, 12, 12, 0, tzinfo=UTC)

# ── the pick's side ─────────────────────────────────────────────────────────
assert T.pick_side("H:406||Home") == "home" and T.pick_side("tennis:186||Away") == "away"
assert T.pick_side("rugby:16|hcp=-24.5|Home (-24.5)") == "home" and T.pick_side("H:18|total=5.5|Under 5.5") is None
assert T.is_total("H:18|total=5.5|Under 5.5") == "under" and T.is_total("H:406||Home") is None

# ── ice hockey: a backup in net is news; a tandem or a priced-in No.1 injury is not ──
gs = [{"name": "Sergei Bobrovsky", "gs": 12}, {"name": "Anthony Stolarz", "gs": 6}]
assert T.hockey_side("Sergei Bobrovsky", gs, [])[0]["level"] == "OK"
assert T.hockey_side("Anthony Stolarz", gs, [])[0]["level"] == "CAUTION"
assert T.hockey_side("Anthony Stolarz", [{"name": "A B", "gs": 9}, {"name": "Anthony Stolarz", "gs": 8}], [])[0]["level"] == "OK"
assert T.hockey_side("Anthony Stolarz", gs, [{"name": "Sergei Bobrovsky", "status": "Injured Reserve"}])[0]["level"] == "OK"
assert T.hockey_side(None, gs, [])[0]["level"] == "PENDING", "no probable goalie: PENDING, never guessed"

# ── NFL: the starting QB only; old or IR reports are priced in ──
qb = "Joe Burrow"
assert T.nfl_side(qb, [{"name": qb, "status": "Out", "pos": "QB", "date": "2026-11-10T10:00Z"}], NOW)[0]["level"] == "RISK"
assert T.nfl_side(qb, [{"name": qb, "status": "Questionable", "pos": "QB", "date": "2026-11-11T10:00Z"}], NOW)[0]["level"] == "CAUTION"
assert T.nfl_side(qb, [{"name": qb, "status": "Out", "pos": "QB", "date": "2026-10-01T10:00Z"}], NOW)[0]["level"] == "OK"
assert T.nfl_side(qb, [{"name": qb, "status": "Injured Reserve", "pos": "QB", "date": "2026-11-11T10:00Z"}], NOW)[0]["level"] == "OK"
fl = T.nfl_side(qb, [{"name": "Kyle Dugger", "status": "Out", "pos": "S", "date": "2026-11-11T10:00Z"}], NOW)
assert T.worst(fl) == "OK" and "noted, not flagged" in fl[-1]["why"]

# ── MLB: a scratched starter; rugby: a heavily rotated XV ──
assert T.mlb_side("Drew Rasmussen", "Drew Rasmussen")[0]["level"] == "OK"
assert T.mlb_side("Shane Baz", "Drew Rasmussen")[0]["level"] == "CAUTION" and T.mlb_side(None, None)[0]["level"] == "PENDING"
SUR = ["Dupont", "Ntamack", "Ramos", "Penaud", "Jalibert", "Alldritt", "Ollivon", "Flament", "Meafou", "Atonio",
       "Mauvaka", "Baille", "Fickou", "Moefana", "Villiere"]
NEW = ["Lucu", "Carbonel", "Attissogbe", "Gailleton", "Jaminet", "Boudehent", "Jegou", "Woki", "Taofifenua",
       "Aldegheri", "Marchand", "Gros"]
xv = [f"Antoine {n}" for n in SUR]
assert T.rugby_side(xv, xv)[0]["level"] == "OK"
assert T.rugby_side(xv[:6] + [f"Louis {n}" for n in NEW[:9]], xv)[0]["level"] == "CAUTION"    # 6/15 kept
assert T.rugby_side(xv[:3] + [f"Louis {n}" for n in NEW], xv)[0]["level"] == "RISK"   # 3/15 kept
assert T.rugby_side(None, xv)[0]["level"] == "PENDING"

# ── withdrawals: dropped near the start while the competition is still listed; not a re-listing ──
def side(first, last):
    return {"x:186||Home": {"first": {"at": first}, "last": {"at": last}}}


doc = {"games": {
    "a": {"comp": "C", "home": "P1", "away": "P2", "ko": "2026-11-12T14:00:00Z", "sides": side("2026-11-12T06:49Z", "2026-11-12T10:49Z")},
    "b": {"comp": "C", "home": "P3", "away": "P4", "ko": "2026-11-12T16:00:00Z", "sides": side("2026-11-12T06:49Z", "2026-11-12T12:49Z")}}}
assert T.withdrawn(doc, "a") and not T.withdrawn(doc, "b")
doc["games"]["a2"] = {"comp": "C", "home": "P1", "away": "P2", "ko": "2026-11-12T15:00:00Z",
                      "sides": side("2026-11-12T12:49Z", "2026-11-12T12:49Z")}
assert not T.withdrawn(doc, "a"), "re-listed under another id: not a withdrawal"
far = {"games": {
    "a": {"comp": "C", "home": "P1", "away": "P2", "ko": "2026-11-13T14:00:00Z", "sides": side("2026-11-12T06:49Z", "2026-11-12T08:49Z")},
    "b": {"comp": "C", "home": "P3", "away": "P4", "ko": "2026-11-13T16:00:00Z", "sides": side("2026-11-12T06:49Z", "2026-11-12T12:49Z")}}}
assert not T.withdrawn(far, "a"), "a draw placeholder dropped a day ahead is not a withdrawal"

# ── one NHL board end to end (ESPN + NHL stubbed), written to its own file, then graded ──
PICK = {"sb_event_id": "g1", "home": "Toronto Maple Leafs", "away": "New Jersey Devils", "comp": "NHL",
        "ko": "2026-11-13T00:00:00Z", "pick": "Toronto Maple Leafs", "key": "H:406||Home", "price": 1.9, "fair": 0.55}
BOARD = {"date": "2026-11-13", "games": {"g1": {"comp": "NHL", "home": "Toronto Maple Leafs", "away": "New Jersey Devils",
                                                "ko": "2026-11-13T00:00:00Z", "matchbook": True, "result": None,
                                                "sides": {"H:406||Home": {"first": {"price": 1.9, "at": "x"}},
                                                          "H:406||Away": {"first": {"price": 2.0, "at": "x"}}}}},
         "picks": [PICK]}


def fake_get(url):
    if "scoreboard" in url:
        return {"events": [{"id": "401", "date": "2026-11-13T00:00Z", "competitions": [{"competitors": [
            {"homeAway": "home", "team": {"displayName": "Toronto Maple Leafs", "abbreviation": "TOR"},
             "probables": [{"name": "probableStartingGoalie", "athlete": {"displayName": "Anthony Stolarz"}}]},
            {"homeAway": "away", "team": {"displayName": "New Jersey Devils", "abbreviation": "NJ"},
             "probables": [{"name": "probableStartingGoalie", "athlete": {"displayName": "Jake Allen"}}]}]}]}]}
    if "summary" in url:
        return {"injuries": []}
    if "club-stats/TOR" in url:
        return {"goalies": [{"firstName": {"default": "Sergei"}, "lastName": {"default": "Bobrovsky"}, "gamesStarted": 12},
                            {"firstName": {"default": "Anthony"}, "lastName": {"default": "Stolarz"}, "gamesStarted": 6}]}
    if "club-stats/NJD" in url:
        return {"goalies": [{"firstName": {"default": "Jake"}, "lastName": {"default": "Allen"}, "gamesStarted": 10}]}
    raise RuntimeError(url)


tn = T.assess_day("ice_hockey", "2026-11-13", BOARD, None, None, fake_get, NOW)
g = tn["games"]["g1"]
assert tn["recorded_only"] and g["level"] == {"home": "CAUTION", "away": "OK"} and g["espn_id"] == "401"
assert tn["picks"][0]["level"] == "CAUTION" and "Stolarz" in tn["picks"][0]["note"]
assert "chance" not in PICK and "news" not in PICK, "the board's pick is never touched"
under = dict(PICK, key="H:18|total=5.5|Under 5.5", pick="Under 5.5")
tn2 = T.assess_day("ice_hockey", "2026-11-13", dict(BOARD, picks=[under]), None, None, fake_get, NOW)
assert tn2["picks"][0]["level"] == "CAUTION", "a backup goalie lifts goals: an Under is flagged"
dead = T.assess_day("ice_hockey", "2026-11-13", BOARD, None, None, lambda u: (_ for _ in ()).throw(RuntimeError()), NOW)
assert dead["picks"][0]["level"] == "PENDING", "ESPN down: PENDING, never a guess"

with tempfile.TemporaryDirectory() as t:
    out, ih = Path(t, "tn"), Path(t, "ih")
    ih.mkdir()
    (ih / "ih_2026-11-13.json").write_text(json.dumps(BOARD), encoding="utf-8")
    lines = T.run(["2026-11-13"], out_dir=out, get=fake_get, now=NOW, scout_dir=Path(t, "none"), ms_dir=Path(t, "ms"), ih_dir=ih)
    assert lines[0].startswith("team news ice_hockey 2026-11-13: 1 games, 1 sides flagged, picks 1 (1 flagged"), lines
    later = T.run(["2026-11-13"], out_dir=out, get=fake_get, now=datetime(2026, 11, 13, 1, tzinfo=UTC),
                  scout_dir=Path(t, "none"), ms_dir=Path(t, "ms"), ih_dir=ih)
    saved = json.loads((out / "ice_hockey" / "tn_2026-11-13.json").read_text(encoding="utf-8"))
    assert saved["games"]["g1"]["first_level"]["home"] == "CAUTION", "the pre-game flag stands after the start"
    board = dict(BOARD)
    board["games"] = {"g1": dict(BOARD["games"]["g1"], result={"final": [2, 3]})}
    (ih / "ih_2026-11-13.json").write_text(json.dumps(board), encoding="utf-8")
    rec = T.record(out, Path(t, "ms"), ih)
    assert rec["sports"]["ice_hockey"]["CAUTION"] == {"n": 1, "won": 0, "price_said": 0.526}
    assert rec["sports"]["ice_hockey"]["OK"]["won"] == 1
    assert T.summary_line(rec).startswith("Multi-sport team news (recorded only): ice_hockey CAUTION 0/1")
    assert T.lines_for_context("ice_hockey", "2026-11-13", out)["g1|H:406||Home"].startswith("CAUTION")

if __name__ == "__main__":
    print("ms_team_news_test: OK")
