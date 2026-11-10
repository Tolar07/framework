"""Gate counter of backtest/sport_gate_study.py: each side lands on exactly one, the first, gate. No network."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import sport_gate_study as sg  # noqa: E402

CFG = sg._cfg("ice_hockey")


def _doc(sides):
    return [("2026-11-01", {"games": {"g": {"sides": sides}}})]


def _s(price, fair=None, model=None, won=True):
    return {"first": {"price": price, "fair": fair, "model": model}, "last": {"price": price, "fair": fair},
            "won": won}


def test_first_gate_order():
    f = sg.first_gate
    assert f("H:1||Home", 2.50, 0.6, "matchbook", CFG) == "band"
    assert f("H:1||Home", 1.80, 0.45, "matchbook", CFG) == "chance"
    assert f("H:1||Home", 1.80, None, None, CFG) == "chance"
    assert f("H:1||Home", 1.80, 0.55, "matchbook", CFG) == "value bar"
    assert f("H:1||Home", 1.80, 0.58, "sportybet", CFG) == "exchange/model"
    assert f("H:1||Home", 1.80, 0.75, "matchbook", CFG) == "value cap"
    assert f("H:1||Home", 1.80, 0.60, "matchbook", CFG) == "passes all gates"
    assert f("H:18|t=5|Over", 1.80, 0.58, "matchbook", CFG) == "value bar"   # line bar is +5%


def test_every_side_counted_once():
    sides = {"H:1||Home": _s(1.80, fair=0.60, won=True), "H:1||Away": _s(2.60, fair=0.40, won=False),
             "H:1||Draw": _s(1.50, won=None)}                                 # ungraded: skipped
    res = sg.study(_doc(sides), CFG)
    assert sum(b["n"] for b in res.values()) == 2
    assert res["passes all gates"]["n"] == 1 and abs(res["passes all gates"]["pnl"] - 0.8) < 1e-9
    assert res["band"]["n"] == 1 and res["band"]["pnl"] == -1.0


def test_report_has_every_gate():
    md = sg.report("ice_hockey", sg.study(_doc({"H:1||Home": _s(1.80, fair=0.60)}), CFG))
    assert all(g in md for g in sg.GATES) and "PENDING" in md


def test_multisport_wiring_and_market_split():
    cfg = sg._cfg("american_football")
    f = sg.first_gate
    assert f("american_football:219||Home", 1.80, 0.55, "matchbook", cfg) == "value bar"      # winner bar +3%
    assert f("american_football:219||Home", 1.80, 0.58, "matchbook", cfg) == "passes all gates"
    assert f("american_football:18|t=5|Over", 1.80, 0.58, "matchbook", cfg) == "value bar"   # line bar +5%
    assert f("american_football:219||Home", 2.40, 0.60, "matchbook", cfg) == "band"


def test_snooker_wired_on_shared_board():
    cfg = sg._cfg("snooker")
    f = sg.first_gate
    assert f("snooker:186||Home", 1.80, 0.55, "matchbook", cfg) == "value bar"
    assert f("snooker:186||Home", 1.80, 0.58, "matchbook", cfg) == "passes all gates"
    assert f("snooker:186||Home", 1.80, 0.40, "matchbook", cfg) == "chance"
