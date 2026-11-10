"""engine/wb_markets.py + backtest/wb_market_study.py - record-only every-market twin (framework#394). Offline."""
from __future__ import annotations

import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backtest"))

from backtest import wb_market_study as study  # noqa: E402
from engine import wb_markets as wm  # noqa: E402

NOW = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)
KO = NOW + timedelta(hours=5)
KOS = KO.strftime("%Y-%m-%dT%H:%M:%SZ")
ROW = {"id": "sr:1", "sport": "basketball", "comp": "NCAA", "home": "Home State", "away": "Away Tech", "ko": KOS}
G = {"hs": 80, "as": 70, "h1": (38, 30), "ot": False}


def event(*_a):
    def m(i, spec, outs):
        return {"id": i, "desc": f"m{i}", "specifier": spec, "status": 0,
                "outcomes": [{"desc": d, "odds": p} for d, p in outs]}
    return {"markets": [m("219", "", [("Home", 1.60), ("Away", 2.40)]),
                        m("68", "total=70.5", [("Over", 1.85), ("Under", 1.85)]),
                        m("66", "hcp=-5.5", [("Home (-5.5)", 1.9), ("Away (+5.5)", 1.9)]),
                        m("90", "total=70.5", [("Over", 1.9), ("Under", 1.9)])]}


def espn(row, ko):
    return {"id": "e1"}


def test_settle_halves_and_full():
    assert wm.settle_ncaa("219", "", "Home", G) == 1
    assert wm.settle_ncaa("68", "total=66.5", "Over", G) == 1 and wm.settle_ncaa("68", "total=70.5", "Over", G) == 0
    assert wm.settle_ncaa("66", "hcp=-7.5", "Home (-7.5)", G) == 1       # half margin +8
    assert wm.settle_ncaa("66", "hcp=-8", "Home (-8)", G) is None        # push
    assert wm.settle_ncaa("60", "", "Home", G) == 1
    assert wm.settle_ncaa("90", "total=70.5", "Over", G) is None         # 2nd half rule unconfirmed: PENDING


def test_update_records_only_upcoming_non_covered_basketball_and_skips_unreadable():
    with tempfile.TemporaryDirectory() as t:
        d = Path(t)
        rows = [ROW, {**ROW, "id": "sr:2", "sport": "football"}, {**ROW, "id": "sr:3", "covered": True},
                {**ROW, "id": "sr:4", "ko": (NOW - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")}]
        assert wm.update(rows, NOW, d, event, espn) == 1
        assert wm.update([ROW], NOW, d, lambda e: (_ for _ in ()).throw(OSError("down")), espn) == 0
        assert len(wm.load(d)) == 1 and wm.load(d)[0]["espn_id"] == "e1"


def test_non_ncaa_has_no_result_so_pending_never_invented():
    snap = wm.snapshot({**ROW, "comp": "EuroLeague"}, NOW, event, espn)
    assert snap["espn_id"] is None and snap["sharp"] is None
    snap["tip"] = KOS
    graded, st = wm.grade([snap], {"e1": G})
    assert graded == [] and st["pending"] == 8


def test_grade_and_study_report():
    snap = wm.snapshot(ROW, NOW, event, espn)
    snap["sharp"] = {"total": 140.5, "spread": -5.5, "ml_home": 1.5, "ml_away": 2.7}
    graded, st = wm.grade([snap], {"e1": G})
    assert len(graded) == 6 and st["pending"] == 2                        # the 2nd-half total stays pending
    assert all(abs(r["fair"] - 0.5) < 0.2 for r in graded)
    text = study.build([{**snap, "at": NOW.strftime("%Y-%m-%dT%H:%M:%SZ")}], {"e1": G})
    assert "Per market" in text and "1 games: real share 45.33%" in text
    assert "NO GRADED DATA YET - PENDING" in study.build([], {})


def main() -> None:
    for n, f in sorted(globals().items()):
        if n.startswith("test_"):
            f()
    print("wb_markets_test OK")


if __name__ == "__main__":
    main()
