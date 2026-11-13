"""The framework's worldwide view (engine/world_view.py) and the analyst using it. Synthetic archives only; no
network, no private data."""
from __future__ import annotations

import gzip
import json
import math
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import analyst as an  # noqa: E402
from engine import world_view as wv  # noqa: E402

NOW = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)
TEAMS = ["Alpha", "Beta", "Gamma", "Delta"]


def _universe(root: Path):
    rows = []
    for i in range(48):
        h, a = TEAMS[i % 4], TEAMS[(i + 1 + i // 4) % 4]
        if h == a:
            a = TEAMS[(i + 2) % 4]
        big = "Alpha" in (h, a)
        rows.append({"id": f"f{i}", "sport": "football", "country": "Ruritania", "comp": "Liga 2", "home": h, "away": a,
                     "ko": f"2026-11-{1 + i % 9:02d}T15:00:00Z",
                     "result": {"h": 3 if big else 0, "a": 2 if big else 1, "ht": [2 if big else 0, 1 if big else 0]}})
        rows.append({"id": f"b{i}", "sport": "basketball", "country": "Ruritania", "comp": "BBL", "home": h, "away": a,
                     "ko": f"2026-11-{1 + i % 9:02d}T19:00:00Z",
                     "result": {"h": 95 if big else 80, "a": 90 if big else 78}})
    (root / "data" / "universe").mkdir(parents=True, exist_ok=True)
    with gzip.open(root / "data" / "universe" / "graded_2026-11-10_0000.jsonl.gz", "wt", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")


def test_maths():
    m = wv.goals_markets(1.4, 1.1)
    assert abs(m["win_home"] + m["draw"] + m["win_away"] - 1) < 1e-6
    assert abs(m["btts_yes"] + m["btts_no"] - 1) < 1e-9 and m["dc_home"] > m["win_home"]
    assert abs(wv.negbin_over(10, 9.5, 1.0) - wv.poisson_over(10, 9.5)) < 1e-9
    assert wv.negbin_over(10, 9.5, 2.0) < wv.poisson_over(10, 9.5)       # a wider spread: the over is less sure
    assert abs(wv.normal_over(160, 15, 160) - 0.5) < 1e-9


def test_world_goals_first_half_and_basketball():
    root = Path(tempfile.mkdtemp())
    _universe(root)
    w = wv.World(root, NOW)
    base = {"country": "Ruritania", "comp": "Liga 2", "home": "Alpha", "away": "Beta"}
    p, src = w.chance({**base, "key": "over25"})
    assert src == "world goals" and p > 0.5
    p2, _ = w.chance({**base, "home": "Gamma", "away": "Delta", "key": "over25"})
    assert p2 < p                                                          # the quiet teams: fewer goals
    fh, src = w.chance({**base, "key": "first_half|0.5|over"})
    assert src == "world first half" and 0 < fh < 1
    assert w.chance({**base, "home": "Nobody", "key": "over25"}) is None  # too few games: no view, never a guess
    bb, src = w.chance({"country": "Ruritania", "comp": "BBL", "home": "Alpha", "away": "Beta", "key": "bb_over",
                        "line": 170.5})
    assert src == "world basketball" and bb > 0.5
    lo, _ = w.chance({"country": "Ruritania", "comp": "BBL", "home": "Gamma", "away": "Delta", "key": "bb_over",
                      "line": 170.5})
    assert lo < bb


def test_corners_through_the_list_rosters():
    root = Path(tempfile.mkdtemp())
    rows = []
    for i in range(40):
        h, a = TEAMS[i % 4], TEAMS[(i + 1 + i // 4) % 4]
        if h == a:
            a = TEAMS[(i + 2) % 4]
        rows.append({"id": f"e{i}", "date": f"2026-11-{1 + i % 9:02d}T15:00Z", "lid": "77", "league": "Ruritania Liga",
                     "year": 2026, "hid": h, "aid": a, "home": h, "away": a, "ft": [1, 1], "ht": [0, 0], "goals": [],
                     "corners": [9, 6] if "Alpha" in (h, a) else [3, 2],
                     "cards": [[20, 0, "Y"], [50, 1, "Y"]] + ([[60, 0, "Y"], [70, 1, "Y"]] if "Alpha" in (h, a) else [])})
    (root / "data" / "espn_matches").mkdir(parents=True)
    (root / "data" / "espn_matches" / "2026-11.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
    (root / "output" / "stat_lists").mkdir(parents=True)
    (root / "output" / "stat_lists" / "pick_index.json").write_text(json.dumps(
        {"cands": {}, "rosters": {"77": {"teams": TEAMS}}}))
    w = wv.World(root, NOW)
    hi, src = w.chance({"home": "Alpha FC", "away": "Beta", "key": "corners|9.5|over"})
    lo, _ = w.chance({"home": "Gamma", "away": "Delta", "key": "corners|9.5|over"})
    assert src == "world corners" and hi > 0.5 > lo
    un, _ = w.chance({"home": "Gamma", "away": "Delta", "key": "corners|9.5|under"})
    assert math.isclose(lo + un, 1.0)
    bk, src = w.chance({"home": "Alpha", "away": "Beta", "key": "bookings|3.5|over"})
    assert src == "world bookings" and 0 < bk < 1
    assert w.chance({"home": "Alpha", "away": "Unknown Town", "key": "corners|9.5|over"}) is None


def test_selection_for_line_markets_and_basketball():
    ev = {"eventId": "e1", "markets": [
        {"id": "166", "specifier": "total=9.5", "status": 0,
         "outcomes": [{"id": "12", "desc": "Over 9.5", "odds": "1.9", "isActive": 1},
                      {"id": "13", "desc": "Under 9.5", "odds": "1.8", "isActive": 1}]},
        {"id": "225", "specifier": "total=170.5", "status": 0,
         "outcomes": [{"id": "12", "desc": "Over 170.5", "odds": "1.85", "isActive": 1}]}]}
    assert an.selection(ev, "corners|9.5|under")["outcomeId"] == "13"
    assert an.selection(ev, "bb_over", 170.5)["marketId"] == "225"
    assert an.selection(ev, "bookings|3.5|over") is None                   # not on the page: unbooked, never assumed


def test_analyst_takes_the_world_view_when_the_board_has_none():
    root = Path(tempfile.mkdtemp())
    _universe(root)
    book = {"picks": {"x|1": {"list": "ou_leagues", "title": "t", "date": "2026-11-14", "ko": "2026-11-14T15:00:00Z",
                              "event": "sr:match:1", "home": "Alpha", "away": "Beta", "country": "Ruritania",
                              "comp": "Liga 2", "pick": "Over 2.5", "key": "over25", "price": 1.8, "result": None}}}
    state: dict = {}
    an.review(book, state, NOW, root, get=lambda u: {"data": {}}, book_code=lambda s: None)
    assert state["x|1"]["verdict"] == "no_view"                            # 27 h out: wait for the day's board
    from datetime import timedelta
    n = an.review(book, state, NOW + timedelta(hours=4), root, get=lambda u: {"data": {}}, book_code=lambda s: None)
    assert state["x|1"]["source"] == "world goals" and state["x|1"]["verdict"] == "agree" and n["agree"] == 1
    rec = an.record(book, state)
    assert rec["by_source"]["world goals"]["agree"]["picks"] == 1


def test_each_job_keeps_its_own_files():
    """The stat-lines run and the universe sweep never write the same file (a lost booking could be staked twice)."""
    root = Path(tempfile.mkdtemp())
    (root / "data" / "list_picks").mkdir(parents=True)
    pick = {"list": "team_corners", "title": "t", "date": "2026-11-13", "ko": "2026-11-13T15:00:00Z",
            "event": "sr:match:9", "home": "A", "away": "B", "country": "X", "comp": "Y", "pick": "Corners Over 9.5",
            "key": "corners|9.5|over", "line": "9.5", "price": 1.9, "result": None}
    (root / "data" / "list_picks" / "book_lines.json").write_text(json.dumps({"picks": {"team_corners|9": pick}}))
    msg = an.attach(NOW, root, get=lambda u: {"data": {}}, book_code=lambda s: None, source="lines")
    assert msg.startswith("analyst (lines)")
    assert (root / "data/analyst/state_lines.json").exists() and not (root / "data/analyst/state.json").exists()
    assert not (root / "output/analyst/record.json").exists()            # the shared views are the sweep's
    an.attach(NOW, root, get=lambda u: {"data": {}}, book_code=lambda s: None)
    rec = json.loads((root / "output/analyst/record.json").read_text())
    assert rec["by_verdict"]["no_view"]["picks"] == 1                       # the lines pick is in the shared record


def test_agreed_picks_also_go_on_as_one_acca():
    """Architect 2026-11-13: "book it as single, book it as acca". One leg per game, frozen, never reused."""
    from datetime import timedelta
    book = {"picks": {}}
    state: dict = {}
    for i, (ev, ch, mins) in enumerate((("e1", 0.62, 60), ("e1", 0.70, 60), ("e2", 0.58, 80), ("e3", 0.66, 300))):
        pid = f"l{i}|{ev}"
        ko = (NOW + timedelta(minutes=mins)).strftime("%Y-%m-%dT%H:%M:%SZ")
        book["picks"][pid] = {"list": f"l{i}", "event": ev, "ko": ko, "home": f"H{ev}", "away": f"A{ev}",
                              "pick": "Over 2.5", "price": 1.5, "result": None}
        state[pid] = {"verdict": "agree", "chance": ch, "code": f"C{i}", "market_id": "18", "specifier": "total=2.5",
                      "outcome_id": "12", "booked_price": 1.5}
    state["l9|e4"] = {"verdict": "disagree", "chance": 0.4}
    book["picks"]["l9|e4"] = {"list": "l9", "event": "e4", "ko": book["picks"]["l0|e1"]["ko"], "price": 2.0}
    sent: list = []
    accas: dict = {"accas": []}
    assert an.build_accas(book, state, accas, NOW - timedelta(hours=3), lambda s: sent.append(s) or "AC1") == 0
    assert an.build_accas(book, state, accas, NOW, lambda s: sent.append(s) or "AC1") == 1
    [a] = accas["accas"]
    assert a["code"] == "AC1" and sorted(a["legs"]) == ["l1|e1", "l2|e2", "l3|e3"]   # e1 once (the likelier leg)
    assert len(sent[0]) == 3 and a["odds"] == round(1.5 ** 3, 2)
    assert an.build_accas(book, state, accas, NOW, lambda s: "AC2") == 0             # nothing left: no second slip
    files = an.acca_files(book, state, accas)
    [doc] = files.values()
    assert doc["stake_ngn"] == 500 and doc["accas"][0]["code"] == "AC1" and len(doc["accas"][0]["legs"]) == 3


def main() -> None:
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("world_view_test OK")


if __name__ == "__main__":
    main()
