"""The analyst (engine/analyst.py): list picks against the framework's own model, AGREE booked for the SportyBet
bot, the rest kept on paper. Synthetic rows only; no network, no private data."""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import analyst as an  # noqa: E402
from engine import calibration as cal  # noqa: E402

NOW = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)
KO = "2026-11-14T15:00:00Z"


def _pick(lid, key, home="Alpha FC", away="Beta", ko=KO, result=None):
    return {"list": lid, "title": lid, "date": ko[:10], "ko": ko, "event": f"sr:match:{lid}", "home": home,
            "away": away, "country": "X", "comp": "League", "pick": key, "key": key, "price": 1.8,
            "sport": "football", "result": result}


def _rated(btts=0.40, o25=0.55, h=0.5, d=0.25, a=0.25, src="model"):
    return {"home": "Alpha", "away": "Beta", "src": src, "p": [h, d, a, 0.75, o25, 0.3, btts]}


def _event(mid, spec, desc, oid="74"):
    return {"eventId": "e1", "markets": [{"id": mid, "specifier": spec, "status": 0,
                                          "outcomes": [{"id": oid, "desc": desc, "odds": "1.85", "isActive": 1}]}]}


def _root(rated):
    root = Path(tempfile.mkdtemp())
    (root / "output" / "picks").mkdir(parents=True)
    (root / "output" / "picks" / "picks_2026-11-14.json").write_text(json.dumps({"rated": rated}))
    return root


def test_framework_chance_is_the_boards_calibrated_number():
    r = _rated(btts=0.40, o25=0.55, h=0.5, d=0.25)
    assert an.framework_chance("btts_yes", r) == round(cal.model_prob("BTTS_YES", 0.40), 4)
    assert an.framework_chance("btts_no", r) == round(cal.model_prob("BTTS_NO", 0.60), 4)
    assert an.framework_chance("over25", r) == round(cal.model_prob("OVER_2_5", 0.55), 4)
    assert an.framework_chance("dc_home", r) == round(cal.model_prob("DC_1X", 0.75), 4)
    assert an.framework_chance("corners|9.5|over", r) is None           # no framework number: no view
    assert an.framework_chance("btts_yes", None) is None


def test_market_implied_rows_and_two_alike_games_are_no_view():
    root = _root([_rated(src="market")])
    assert an.rated_rows("2026-11-14", root) == []
    two = [_rated(), {**_rated(), "away": "Beta Town"}]
    assert an.find_rated(_pick("x", "btts_yes", away="Beta"), two) is None
    assert an.find_rated(_pick("x", "btts_yes"), [_rated()])["home"] == "Alpha"


def test_agree_is_booked_disagree_and_no_view_stay_on_paper():
    root = _root([_rated(btts=0.30, o25=0.70)])                         # BTTS yes ~45%, over 2.5 ~59%
    book = {"picks": {"a|1": _pick("ou_leagues", "over25"), "b|1": _pick("btts_leagues", "btts_yes"),
                      "c|1": _pick("draws", "draw", home="Gamma", away="Delta")}}
    (root / "data" / "list_picks").mkdir(parents=True)
    (root / "data" / "list_picks" / "book_universe.json").write_text(json.dumps(book))
    pages = {"over25": _event("18", "total=2.5", "Over 2.5", oid="12")}
    booked = []

    def book_code(sel):
        booked.append(sel)
        return "ABC123"
    msg = an.attach(NOW, root, get=lambda url: {"data": pages["over25"]}, book_code=book_code)
    assert "1 agree, 1 disagree, 1 booked" in msg, msg
    state = json.loads((root / "data/analyst/state.json").read_text())
    assert state["a|1"]["verdict"] == "agree" and state["a|1"]["code"] == "ABC123"
    assert state["b|1"]["verdict"] == "disagree" and not state["b|1"].get("code")
    assert state["c|1"]["verdict"] == "no_view"
    assert booked == [{"eventId": "e1", "marketId": "18", "specifier": "total=2.5", "outcomeId": "12", "odds": 1.85}]
    doc = json.loads((root / "output/analyst/agree_2026-11-14.json").read_text())
    assert doc["stake_ngn"] == 500 and doc["accounts"] == [1]
    [p] = doc["picks"]
    assert p["code"] == "ABC123" and p["market_id"] == "18" and p["ko"] == KO and p["price"] == 1.85
    assert p["accounts"] == [1]
    # frozen: a later model run that disagrees never takes the agreed pick back
    (root / "output/picks/picks_2026-11-14.json").write_text(json.dumps({"rated": [_rated(o25=0.10)]}))
    an.attach(NOW + timedelta(hours=3), root, get=lambda url: {"data": {}}, book_code=book_code)
    state = json.loads((root / "data/analyst/state.json").read_text())
    assert state["a|1"]["verdict"] == "agree" and len(booked) == 1


def test_no_code_close_to_kick_off_and_switch_off():
    root = _root([_rated(o25=0.80)])
    soon = (NOW + timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    book = {"picks": {"a|1": _pick("ou_leagues", "over25", ko=soon)}}
    (root / "output/picks/picks_2026-11-13.json").write_text(json.dumps({"rated": [_rated(o25=0.80)]}))
    state: dict = {}
    n = an.review(book, state, NOW, root, get=lambda u: {"data": _event("18", "total=2.5", "Over 2.5")},
                  book_code=lambda s: "X")
    assert state["a|1"]["verdict"] == "agree" and n["booked"] == 0
    import os
    os.environ["ANALYST_AGREE"] = "0"
    try:
        later = {"picks": {"b|1": _pick("ou_leagues", "over25")}}
        root2 = _root([_rated(o25=0.80)])
        n = an.review(later, {}, NOW, root2, get=lambda u: {"data": _event("18", "total=2.5", "Over 2.5")},
                      book_code=lambda s: "X")
        assert n["agree"] == 1 and n["booked"] == 0
    finally:
        del os.environ["ANALYST_AGREE"]


def test_record_by_verdict_and_lessons():
    picks, state = {}, {}
    for i in range(120):                                               # a list that wins when the framework disagrees
        pid = f"draws|{i}"
        picks[pid] = {**_pick("draws", "draw"), "price": 3.4, "result": 1 if i % 2 else 0}
        state[pid] = {"verdict": "disagree"}
    picks["ou|1"] = {**_pick("ou_leagues", "over25"), "result": 0}
    state["ou|1"] = {"verdict": "agree"}
    rec = an.record({"picks": picks}, state)
    assert rec["by_verdict"]["agree"]["graded"] == 1 and rec["by_verdict"]["disagree"]["graded"] == 120
    assert rec["lists"]["draws"]["disagree"]["ready"] is True
    assert [x["list"] for x in rec["lessons"]] == ["draws"]


def main() -> None:
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("analyst_test OK")


if __name__ == "__main__":
    main()
