"""Stat lists 7-21 (engine/stat_lists.py) and the live list test (engine/list_picks.py). Synthetic rows only;
no network, no private data."""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import list_picks as lp  # noqa: E402
from engine import stat_lists as sl  # noqa: E402

NOW = datetime(2026, 11, 12, 12, 0, tzinfo=UTC)
TEAMS = ["Alpha", "Beta", "Gamma", "Delta", "Paris FC", "Paris Saint-Germain"]


def espn_rows(lid="1", league="Test League", n=40, year=2026):
    out = []
    for i in range(n):
        h, a = TEAMS[i % 6], TEAMS[(i + 1 + i // 6) % 6]
        if h == a:
            a = TEAMS[(i + 2) % 6]
        hg, ag = (3, 2) if h == "Alpha" or a == "Alpha" else (0, 0)
        goals = [[10, 0], [20, 1], [50, 0], [60, 1], [80, 0]] if hg else []
        out.append({"id": f"{lid}-{i}", "date": (NOW - timedelta(days=n - i)).strftime("%Y-%m-%dT15:00Z"), "lid": lid,
                    "league": league, "year": year, "hid": f"t{TEAMS.index(h)}", "aid": f"t{TEAMS.index(a)}",
                    "home": h, "away": a, "ft": [hg, ag], "goals": goals, "ht": [1, 1] if hg else [0, 0],
                    "cards": [[30, 0, "Y"], [70, 1, "Y"]], "corners": [8, 4] if h == "Alpha" else [3, 2],
                    "fouls": [12, 10], "shots": [15, 9], "sot": [6, 3]})
    return out


def test_lists_are_built_from_this_season_only_and_missing_inputs_stay_out():
    rows = espn_rows() + espn_rows(lid="2", league="Old League", year=2024)
    for r in rows:
        if r["lid"] == "2":
            r["date"] = "2024-05-01T15:00Z"                       # not played in the last 40 days: left out
    rows[0]["corners"] = None                                     # a match with no corner count is not a 0
    lists, index = sl.football_lists(rows, NOW)
    by = {x["id"]: x for x in lists}
    assert [r[0] for r in by["ou_leagues"]["rows"]] == ["Test League"]
    assert by["team_corners"]["rows"][0][0] == "Alpha"            # most corners in its games
    blank = {r[0]: r[5] for r in by["clean_sheets"]["rows"]}
    assert blank["Alpha"] == "0%" and by["clean_sheets"]["rows"][0][0] != "Alpha"   # every Alpha game ends 3-2
    assert by["fh_corners"]["rows"] == [] and "PENDING" in by["fh_corners"]["note"]
    assert set(index["rosters"]) == {"1"} and len(index["rosters"]["1"]["teams"]) == 6
    assert index["cands"]["team_corners"][0] == {"team": "Alpha", "league": "Test League", "lid": "1"}


def test_cups_stay_out_of_league_lists_and_women_out_of_the_test():
    rows = espn_rows(league="Test Cup, Round of 16") + espn_rows(lid="3", league="Women's Test League")
    lists, index = sl.football_lists(rows, NOW)
    by = {x["id"]: x for x in lists}
    assert [r[0] for r in by["ou_leagues"]["rows"]] == ["Women's Test League"]     # listed ...
    assert index["cands"]["ou_leagues"] == []                                       # ... but never picked
    assert all("Women" not in c["league"] for c in index["cands"]["clean_sheets"])


def test_names_match_strictly():
    assert lp.same_team(lp.norm("FC Twente"), lp.norm("FC Twente Enschede"))
    assert lp.same_team(lp.norm("Celta Vigo"), lp.norm("Celta"))
    assert not lp.same_team(lp.norm("Lyon"), lp.norm("Lens"))
    assert lp.is_variant({"home": "Arsenal U21", "away": "Aston Villa U21"})
    assert lp.is_variant({"home": "Twente SRL", "away": "Ajax SRL"})
    assert lp.is_variant({"home": "A", "away": "B", "comp": "Premier League Women"})
    assert not lp.is_variant({"home": "Club Brugge", "away": "Gent", "comp": "Pro League", "country": "Belgium"})
    idx = lp.Index({"cands": {}, "rosters": {"1": {"teams": TEAMS}}}, Path("/nonexistent"))
    # 'Paris' could be either Paris club: no match, never a guess
    assert idx.match({"team": "Paris Saint-Germain", "lid": "1"}, {"home": "Paris", "away": "Alpha"}) is None
    assert idx.match({"team": "Paris Saint-Germain", "lid": "1"}, {"home": "Paris FC", "away": "Alpha"}) is None
    assert idx.match({"team": "Paris FC", "lid": "1"}, {"home": "Alpha", "away": "Paris FC"}) == "away"
    # the opponent must be in the same league's list (a same-named club elsewhere is not the team)
    assert idx.match({"team": "Alpha", "lid": "1"}, {"home": "Alpha", "away": "Nobody United"}) is None
    assert idx.match({"lid": "1", "league": "Test League"}, {"home": "Beta", "away": "Gamma"}) == "league"


def game(eid, home, away, ko, **p):
    return {"sport": p.pop("sport", "football"), "id": eid, "country": "Testland", "comp": "Test League",
            "ko": ko.strftime("%Y-%m-%dT%H:%MZ"), "home": home, "away": away, "last": {"at": "x", "p": p}}


def test_universe_picks_are_made_graded_and_recorded_on_paper():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "output/stat_lists").mkdir(parents=True)
        (root / "output/stat_lists/pick_index.json").write_text(json.dumps({
            "cands": {"ou_leagues": [{"league": "Test League", "lid": "1"}],
                      "clean_sheets": [{"team": "Gamma", "league": "Test League", "lid": "1"}],
                      "luck": [{"team": "Delta", "league": "Test League", "lid": "1"}],
                      "draws": [{"team": "Beta", "league": "Test League", "lid": "1"}]},
            "rosters": {"1": {"league": "Test League", "teams": TEAMS}}}))
        ko = NOW + timedelta(hours=2)
        pend = {g["id"]: g for g in (
            game("e1", "Alpha", "Beta", ko, **{"ou2.5": [1.8, 2.0], "btts": [1.7, 2.1], "1x2": [2.0, 3.4, 3.6]}),
            game("e2", "Gamma FC", "Delta", ko, **{"ou2.5": [1.9, 1.9], "btts": [1.8, 1.95], "1x2": [2.5, 3.2, 2.8]}),
            game("e3", "Alpha U21", "Beta U21", ko, **{"ou2.5": [1.5, 2.5]}),          # youth: never picked
            game("e4", "Alpha", "Beta", NOW - timedelta(hours=1), **{"ou2.5": [1.5, 2.5]}))}   # started: never
        msg = lp.attach_universe(pend, [], NOW, root)
        assert "4 new" in msg, msg
        book = lp.load_book("universe", root / "data/list_picks")
        got = {p["list"]: (p["event"], p["pick"], p["price"]) for p in book["picks"].values()}
        assert got == {"ou_leagues": ("e1", "Over 2.5", 1.8), "clean_sheets": ("e2", "BTTS No", 1.95),
                       "luck": ("e2", "Delta to win", 2.8), "draws": ("e1", "Draw", 3.4)}
        # next run: the league list takes its other game (up to PER_DAY a day); a team is never picked twice a game
        assert "1 new" in lp.attach_universe(pend, [], NOW + timedelta(minutes=5), root)
        assert "0 new" in lp.attach_universe(pend, [], NOW + timedelta(minutes=10), root)
        graded = [{**pend["e1"], "result": {"h": 2, "a": 2}}, {**pend["e2"], "result": {"h": 0, "a": 1}}]
        msg = lp.attach_universe({}, graded, NOW + timedelta(hours=5), root)
        assert "5 graded" in msg, msg
        rec = json.loads((root / "output/list_picks/record_universe.json").read_text())
        assert rec["paper_only"] is True
        assert rec["lists"]["ou_leagues"] == {"title": "Goals over and under, by league", "picks": 2, "graded": 2,
                                              "won": 1, "roi": -0.1, "ready": False}
        assert rec["lists"]["luck"]["won"] == 1 and rec["lists"]["draws"]["won"] == 1
        assert rec["all"]["graded"] == 5 and rec["all"]["won"] == 4
        assert rec["acca"]["days"] == 1 and rec["acca"]["won"] == 1             # the day's four first picks
        assert "late_goals" in rec["not_tested"]
        day = json.loads((root / f"output/list_picks/universe_{ko:%Y-%m-%d}.json").read_text())
        assert len(day["picks"]) == 5 and day["paper_only"] is True


def test_extra_time_and_pushes_are_void_never_guessed():
    assert lp.settle_universe("over25", {"h": 2, "a": 2, "after_90": True}, "football") is None
    assert lp.settle_universe("bb_over", {"h": 100, "a": 100}, "basketball", 200.0) is None
    assert lp.settle_universe("bb_over", {"h": 101, "a": 100}, "basketball", 200.0) == 1
    assert lp.settle_universe("dc_away", {"h": 1, "a": 1}, "football") == 1
    assert lp.settle_universe("btts_no", None, "football") is None


def test_lines_picks_use_the_main_line_and_grade_from_the_recorder():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "output/stat_lists").mkdir(parents=True)
        (root / "output/stat_lists/pick_index.json").write_text(json.dumps({
            "cands": {"team_corners": [{"team": "Alpha", "league": "Test League", "lid": "1"}],
                      "early_goal": [{"league": "Test League", "lid": "1"}]},
            "rosters": {"1": {"league": "Test League", "teams": TEAMS}}}))
        ko = (NOW + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%MZ")
        pend = {"m1": {"id": "m1", "ko": ko, "home": "Alpha", "away": "Beta", "country": "Testland", "comp": "Test League",
                       "last": {"at": "x", "lines": {"corners": {"8.5": [1.4, 2.8], "10.5": [1.9, 1.85], "12.5": [3.0, 1.3]},
                                                      "first_half": {"0.5": [1.35, 3.0], "1.5": [2.6, 1.45]}}}}}
        assert "2 new" in lp.attach_lines(pend, [], NOW, root)
        book = lp.load_book("lines", root / "data/list_picks")
        got = {p["list"]: (p["pick"], p["key"], p["price"]) for p in book["picks"].values()}
        assert got == {"team_corners": ("Corners Over 10.5", "corners|10.5|over", 1.9),
                       "early_goal": ("1st half Over 0.5", "first_half|0.5|over", 1.35)}
        done = [{"id": "m1", "result": {"corners": 9, "first_half": 1},
                 "graded": {"corners": {"10.5": {"over": 0, "under": 1}}, "first_half": {"0.5": {"over": 1, "under": 0}}}}]
        assert "2 graded" in lp.attach_lines({}, done, NOW + timedelta(hours=5), root)
        rec = json.loads((root / "output/list_picks/record_lines.json").read_text())
        assert rec["lists"]["team_corners"]["won"] == 0 and rec["lists"]["early_goal"]["won"] == 1
        assert rec["all"]["roi"] == round((-1 + 0.35) / 2, 4)


def main() -> None:
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("list_picks_test OK")


if __name__ == "__main__":
    main()
