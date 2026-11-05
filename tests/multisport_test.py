"""Multi-sport boards (standing order 50): settlement per sport, exchange keys, Elo learning,
paper switch, the freezing look and the Flashscore parser. No network."""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import multisport as ms  # noqa: E402


def R(final, periods=(), winner=None):
    return {"final": list(final), "periods": [list(p) for p in periods], "winner": winner}


def test_settle_by_sport():
    s = ms.settle
    tennis = R((2, 1), [(6, 4), (3, 6), (7, 6)], 1)
    assert s("tennis", "186", "", "Home", tennis) == 1
    assert s("tennis", "189", "total=31.5", "Over 31.5", tennis) == 1, "6+4+3+6+7+6 = 32 games"
    assert s("tennis", "188", "hcp=-1.5", "Home (-1.5)", tennis) == 0, "won 2-1 in sets"
    assert s("tennis", "187", "hcp=-2.5", "Home (-2.5)", tennis) == 0, "16-16 in games"
    assert s("tennis", "202", "setnr=2", "Away", tennis) == 1
    af = R((31, 30), [(0, 7), (14, 3), (7, 7), (3, 7), (7, 6)], 1)
    assert s("american_football", "219", "", "Home", af) == 1, "winner incl. OT"
    assert s("american_football", "1", "", "Draw", af) == 1, "24-24 after four quarters"
    assert s("american_football", "225", "total=60.5", "Over 60.5", af) == 1
    assert s("american_football", "60", "", "Home", af) == 1, "14-10 at half time"
    rugby = R((52, 17))
    assert s("rugby", "16", "hcp=-30.5", "Home (-30.5)", rugby) == 1
    assert s("rugby", "14", "hcp=0:35", "Draw (0:35)", rugby) == 1
    assert s("rugby", "11", "", "Away", R((20, 20))) is None, "draw no bet void on a draw"
    vb = R((3, 0), [(25, 22), (25, 18), (25, 19)], 1)
    assert s("volleyball", "238", "total=134.5", "Over 134.5", vb) == 0 and s("volleyball", "237", "hcp=-10.5", "Home (-10.5)", vb) == 1
    assert s("darts", "186", "", "Away", R((6, 3), [], 1)) == 0
    assert s("cricket", "340", "", "Away", R((170, 184), [], 2)) == 1


def test_canonical():
    assert ms.canonical("tennis:186||Home") == ["ml|home", "1x2|home"]
    assert ms.canonical("american_football:223|hcp=-3.5|Home (-3.5)") == ["hcp|-3.5|home"]
    assert ms.canonical("american_football:225|total=47.5|Under 47.5") == ["total|47.5|under"]
    assert ms.canonical("tennis:188|hcp=-1.5|Home (-1.5)") == [], "set handicap: Matchbook's handicap is games"
    assert ms.canonical("rugby:16|hcp=-10|Home (-10)") == [], "whole lines can push"


def test_elo_learns_and_scores():
    elo = {"ratings": {}, "games": {}, "seen": [], "brier": [0.0, 0]}
    t0 = datetime(2026, 11, 1, tzinfo=UTC)
    games = [{"home": "Strong A", "away": f"Weak {i % 3}", "winner": 1,
              "kickoff_utc": (t0 + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M:%SZ")} for i in range(40)]
    assert ms.learn(elo, games) == 40 and ms.learn(elo, games) == 0, "each game learned once"
    assert elo["brier"][1] > 0, "pre-game chances scored walk-forward once both sides are rated"
    p = ms.elo_p(elo, "Strong A", "Weak 1")
    assert p is not None and p > 0.8


def test_paper_switch_and_covers():
    assert ms.is_paper("american_football", "2026-11-18") and not ms.is_paper("american_football", "2026-11-19")
    assert ms.is_paper("table_tennis", "2026-12-09") and not ms.is_paper("table_tennis", "2026-12-10")
    assert ms.is_paper("baseball", "2030-01-01"), "season_opening is not a date: stays paper until set"


def test_update_freezes_and_records():
    now = datetime(2026, 11, 6, 12, tzinfo=UTC)
    row = {"id": "e1", "sport": "tennis", "country": "France", "comp": "ATP Paris", "home": "Monteiro, Thiago",
           "away": "Cecchinato, Marco", "ko": "2026-11-06T15:00:00Z",
           "sides": {"tennis:186||Home": 1.95, "tennis:186||Away": 1.85}, "oids": {"tennis:186||Home": "4"}}
    mb = [{"name": "Thiago Monteiro vs Marco Cecchinato", "start": "2026-11-06T15:00:00.000Z", "markets": [
        {"status": "open", "name": "Moneyline", "market-type": "money_line", "runners": [
            {"status": "open", "name": "Thiago Monteiro", "prices": [{"side": "back", "odds": 1.80, "available-amount": 50},
                                                                    {"side": "lay", "odds": 1.82, "available-amount": 50}]},
            {"status": "open", "name": "Marco Cecchinato", "prices": [{"side": "back", "odds": 2.22, "available-amount": 50},
                                                                     {"side": "lay", "odds": 2.26, "available-amount": 50}]}]}]}]
    elo = {"ratings": {}, "games": {}, "seen": [], "brier": [0.0, 0]}
    with tempfile.TemporaryDirectory() as td:
        assert ms.update("tennis", [row], mb, elo, now, folder=Path(td), book=lambda s: "CODE1") == (1, 1)
        doc = json.loads((Path(td) / "tennis" / "ms_2026-11-06.json").read_text(encoding="utf-8"))
        p = doc["picks"][0]
        assert p["key"] == "tennis:186||Home" and p["code"] == "CODE1" and p["paper"] is True
        assert p["source"] == "matchbook" and p["venues"]["matchbook"] is True
        assert set(doc["games"]["e1"]["sides"]) == set(row["sides"]), "every side recorded"


def test_flashscore_parse():
    feed = ("SA÷2¬~ZA÷ATP - SINGLES: Paris¬~AA÷x¬AD÷1793988000¬AB÷3¬AC÷3¬AS÷1¬AE÷Paul T.¬AF÷Halys Q.¬AG÷2¬AH÷0¬"
            "BA÷7¬BB÷6¬BC÷6¬BD÷4¬~")
    ev = ms.parse_flashscore(feed)[0]
    assert ev["final"] == [2, 0] and ev["periods"] == [[7, 6], [6, 4]] and ev["winner"] == 1


def test_no_steam_and_setka_excluded():
    src = (ROOT / "engine" / "multisport.py").read_text(encoding="utf-8").lower()
    assert "import steam" not in src and "steam_" not in src
    assert "setka" in ms.SPORTS["table_tennis"]["exclude"]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("multisport_test: OK")
