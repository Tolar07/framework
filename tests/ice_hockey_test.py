"""Ice hockey board (standing order 50): model markets, settlement, exchange keys, paper switch,
the look that freezes picks, and the Flashscore parser. No network."""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import hockey_model as hm  # noqa: E402
from engine import ice_hockey as ih  # noqa: E402


def _games(n=200):
    out, t0 = [], datetime(2025, 10, 1, tzinfo=UTC)
    teams = ["AAA", "BBB", "CCC", "DDD"]
    for i in range(n):
        h, a = teams[i % 4], teams[(i + 1 + i // 4) % 4]
        if h == a:
            a = teams[(i + 2) % 4]
        hs, as_ = (4, 2) if h == "AAA" else (2, 3) if a == "AAA" else (3, 3) if i % 5 == 0 else (2, 1)
        period = "REG"
        if hs == as_:
            hs, period = hs + 1, "OT"
        out.append({"id": i, "season": 20252026, "type": 2, "ko": (t0 + timedelta(days=i)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "date": "", "home": h, "away": a, "home_name": h, "away_name": a, "hs": hs, "as": as_, "period": period})
    return out


def test_model_sums_and_strength():
    m = hm.fit(_games(), "2027-01-01T00:00:00Z")
    g = m.grid("AAA", "BBB")
    assert abs(sum(map(sum, g)) - 1) < 1e-9
    h, d, a = (hm.chance("1", "", x, g, m.ot_home) for x in ("Home", "Draw", "Away"))
    assert abs(h + d + a - 1) < 1e-9 and h > a, "AAA is the strong side"
    w = hm.chance("406", "", "Home", g, m.ot_home) + hm.chance("406", "", "Away", g, m.ot_home)
    assert abs(w - 1) < 1e-9, "winner incl. OT has no draw"
    o = hm.chance("18", "total=5.5", "Over 5.5", g, m.ot_home) + hm.chance("18", "total=5.5", "Under 5.5", g, m.ot_home)
    assert abs(o - 1) < 1e-9
    hp = hm.chance("410", "hcp=1.5", "Home (+1.5)", g, m.ot_home) + hm.chance("410", "hcp=-1.5", "Away (-1.5)", g, m.ot_home)
    assert abs(hp - 1) < 1e-9, "+1.5 / -1.5 incl. OT partition the result"
    assert hm.chance("18", "total=5", "Over 5", g, m.ot_home) is None, "whole lines can push: not priced"


def test_settle():
    s = hm.settle
    assert s("1", "", "Draw", (2, 2), (3, 2)) == 1 and s("406", "", "Home", (2, 2), (3, 2)) == 1
    assert s("410", "hcp=1.5", "Away (+1.5)", (2, 2), (3, 2)) == 1, "lost by one in OT covers +1.5"
    assert s("410", "hcp=-1.5", "Home (-1.5)", (2, 2), (3, 2)) == 0
    assert s("16", "hcp=-0.5", "Home (-0.5)", (2, 2), (3, 2)) == 0, "Asian handicap is 60 minutes"
    assert s("18", "total=5.5", "Under 5.5", (3, 2), (3, 2)) == 1
    assert s("14", "hcp=0:1", "Draw (0:1)", (3, 2), (3, 2)) == 1
    assert s("29", "", "Yes", (1, 0), (2, 0)) == 0, "GG is 60 minutes"


def test_canonical():
    assert ih.canonical("H:406||Home") == "ml|home"
    assert ih.canonical("H:1||Draw") == "1x2|draw"
    assert ih.canonical("H:410|hcp=1.5|Away (-1.5)") == "hcp|-1.5|away"
    assert ih.canonical("H:18|total=5.5|Over 5.5") is None, "exchange totals include OT: not the same bet"


def test_paper_switch():
    assert ih.is_paper("2026-11-05") and not ih.is_paper("2026-11-12")
    cfg = json.loads(ih.ROLLOUT.read_text(encoding="utf-8"))
    hk = next(s for s in cfg["sports"] if s["sport"] == "ice_hockey")
    assert ih.is_paper((datetime.fromisoformat(hk["live_from"]) - timedelta(days=1)).strftime("%Y-%m-%d"))


def test_update_freezes_one_pick_and_records_all_sides():
    now = datetime(2026, 11, 6, 12, tzinfo=UTC)
    row = {"id": "sr:match:1", "country": "Sweden", "comp": "SHL", "home": "Frolunda", "away": "Lulea",
           "ko": "2026-11-06T18:00:00Z", "sides": {"H:406||Home": 1.95, "H:406||Away": 1.85},
           "oids": {"H:406||Home": "4", "H:406||Away": "5"}}
    mb = [{"name": "Lulea at Frolunda", "start": "2026-11-06T18:00:00.000Z", "markets": [
        {"status": "open", "name": "Moneyline", "market-type": "money_line", "runners": [
            {"status": "open", "name": "Frolunda", "prices": [{"side": "back", "odds": 1.80, "available-amount": 50},
                                                             {"side": "lay", "odds": 1.82, "available-amount": 50}]},
            {"status": "open", "name": "Lulea", "prices": [{"side": "back", "odds": 2.22, "available-amount": 50},
                                                          {"side": "lay", "odds": 2.26, "available-amount": 50}]}]}]}]
    with tempfile.TemporaryDirectory() as td:
        seen, added = ih.update([row], mb, None, now, folder=Path(td), book=lambda s: "ABC123")
        assert (seen, added) == (1, 1)
        doc = json.loads((Path(td) / "ih_2026-11-06.json").read_text(encoding="utf-8"))
        p = doc["picks"][0]
        assert p["key"] == "H:406||Home" and p["code"] == "ABC123" and p["paper"] is True and doc["paper"] is True
        assert p["source"] == "matchbook" and p["value"] > 0.03
        assert set(doc["games"]["sr:match:1"]["sides"]) == {"H:406||Home", "H:406||Away"}, "every side recorded"
        ih.update([row], mb, None, now + timedelta(hours=1), folder=Path(td), book=lambda s: "X")
        doc = json.loads((Path(td) / "ih_2026-11-06.json").read_text(encoding="utf-8"))
        assert len(doc["picks"]) == 1 and doc["picks"][0]["code"] == "ABC123", "frozen at first look"


def test_flashscore_parse_and_grade():
    feed = ("SA÷4¬~ZA÷SWEDEN: SHL¬~AA÷x1¬AD÷1793988000¬AB÷3¬AC÷10¬AE÷Frolunda¬AF÷Lulea¬AG÷3¬AH÷2¬"
            "BA÷1¬BB÷0¬BC÷0¬BD÷1¬BE÷1¬BF÷1¬BG÷1¬BH÷0¬~")
    ev = ih.parse_flashscore(feed)
    assert ev and ev[0]["reg"] == [2, 2] and ev[0]["final"] == [3, 2]
    doc = {"games": {"g": {"home": "Frolunda", "away": "Lulea", "ko": ev[0]["kickoff_utc"], "result": None,
                           "sides": {"H:1||Draw": {"first": {"price": 4.0}, "last": {"price": 4.2, "fair": 0.25}}}}},
           "picks": [{"sb_event_id": "g", "key": "H:1||Draw", "market_id": "1", "specifier": "", "outcome": "Draw",
                      "price": 4.0, "result": None}]}
    later = datetime.fromisoformat(ev[0]["kickoff_utc"].replace("Z", "+00:00")) + timedelta(hours=5)
    assert ih.grade_doc(doc, ev, later) == 1
    p = doc["picks"][0]
    assert p["result"] == "won" and p["pnl"] == 3.0 and p["clv_fair"] == 0.0
    sb = ih.scoreboard([("d", doc)])
    assert sb["picks"] == 1 and sb["all_sides_by_market"]["1"]["won"] == 1


def test_no_steam():
    src = (ROOT / "engine" / "ice_hockey.py").read_text(encoding="utf-8").lower()
    assert "import steam" not in src and "steam_" not in src, "order 50: no steam on new sports"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("ice_hockey_test: OK")


def test_hockey_recal_pending_then_ok():
    from engine import hockey_recal as hr
    assert hr.check([])["status"] == "PENDING"
    rows = []
    for i in range(300):
        won = i % 2
        rows.append({"day": f"2026-11-{1 + i // 20:02d}", "key": "k", "model": 0.7 if won else 0.3,
                     "fair": 0.5, "won": won})
    res = hr.check(rows)
    assert res["status"] == "OK" and res["tries"] == 11
    assert res["w"] == 1.0 and res["blend_beats_exchange"]
    assert res["fit"] >= hr.MIN_FIT and res["holdout"] >= hr.MIN_HOLDOUT


def test_hockey_recal_reads_graded_record():
    from engine import hockey_recal as hr
    doc = {"games": {"1": {"sides": {
        "x|1|1": {"first": {"model": 0.6, "fair": 0.5}, "won": True},
        "x|1|2": {"first": {"model": None, "fair": 0.5}, "won": False},
        "x|1|3": {"first": {"model": 0.2, "fair": 0.3}}}}}}
    got = hr.sides_of([("2026-11-05", doc)])
    assert len(got) == 1 and got[0]["won"] == 1
    with tempfile.TemporaryDirectory() as td:
        lg = Path(td) / "l.jsonl"
        assert hr.run([("2026-11-05", doc)], log=lg)["status"] == "PENDING"
        assert lg.read_text().count("\n") == 1


def test_league_study():
    from engine import hockey_league_study as hs
    g = lambda comp, res, won, fair: {"comp": comp, "result": res, "sides": {"1|x": {"first": {"fair": fair}, "won": won}}}
    docs = [("d", {"games": {"1": g("SHL", {"reg": [1, 0]}, 1, 0.6), "2": g("SHL", None, None, 0.5),
                             "3": g("KHL", {"reg": [0, 1]}, 0, None)}})]
    r = hs.study(docs)
    assert r["SHL"]["seen"] == 2 and r["SHL"]["graded"] == 1 and r["SHL"]["fair_brier"] == 0.16
    assert r["SHL"]["status"] == "PENDING" and r["KHL"]["fair_brier"] is None
    assert "PENDING" in hs.render(r)
