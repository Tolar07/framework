"""engine/nba_shadow.py — the SHADOW markets side by side with the NBA board. Offline."""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine import nba_shadow as nsh  # noqa: E402
from engine import nba_value as nv  # noqa: E402

nv.BLEND = {}                 # model-only chances: the test never depends on memory/nba_blend.json

SHARP = {"ml_home": 1.5, "ml_away": 2.6, "spread": -5.5, "total": 226.5}


def _look(at="2026-11-05T22:00:00Z", price=1.75, q1_price=1.75):
    return {"at": at, "stage": "regular", "event_id": "sr:match:1", "espn_id": "401", "espn_date": "2026-11-06",
            "tip": "2026-11-06T00:30Z", "home": "LAC", "away": "MIA", "sharp": SHARP, "markets": [
                # away team 1st-half points: mean 0.501 x 110.5 = 55.4; Under 58.5 ~ 65% -> +14% at 1.75
                {"id": "70", "spec": "total=58.5", "open": True,
                 "outcomes": [["Over 58.5", 1.6], ["Under 58.5", price]]},
                # a board line (Q1 total): recorded too since every market went live (2026-11-05)
                {"id": "236", "spec": "total=60.5|quarternr=1", "open": True,
                 "outcomes": [["Over 60.5", 1.8], ["Under 60.5", q1_price]]},
                {"id": "70", "spec": "total=40.5", "open": False, "outcomes": [["Over 40.5", 1.9]]}]}


def test_freezes_first_entry_per_family():
    with tempfile.TemporaryDirectory() as t:
        d = Path(t)
        assert nsh.update([_look()], "2026-11-05", d) == 2           # team 1H points + Q1 total
        assert nsh.update([_look(at="2026-11-05T23:00:00Z", price=1.85)], "2026-11-05", d) == 0  # frozen
        assert nsh.update([_look(at="2026-11-06T01:00:00Z")], "2026-11-05", d) == 0              # after tip
        p = json.loads((d / "shadow_2026-11-05.json").read_text(encoding="utf-8"))["picks"]
        assert len(p) == 2 and p[0]["family"] == "Away team 1st half points" and p[0]["price"] == 1.75
        assert p[0]["outcome"] == "Under 58.5" and p[0]["result"] is None


def test_grades_from_espn_us_date_and_reports():
    with tempfile.TemporaryDirectory() as t:
        d = Path(t)
        nsh.update([_look()], "2026-11-05", d)
        g = SimpleNamespace(id="401", completed=True, hs=110, as_=104, q_home=[28, 27, 30, 25],
                            q_away=[26, 30, 24, 24])
        seen = []

        def sb(day):
            seen.append(day.isoformat())
            return [g] if day.isoformat() == "2026-11-05" else []      # US date of a 00:30 UTC tip
        assert nsh.grade(datetime(2026, 11, 6, 12, tzinfo=UTC), d, scoreboard=sb) == 2
        ps = json.loads((d / "shadow_2026-11-05.json").read_text(encoding="utf-8"))["picks"]
        p = ps[0]
        assert p["result"] == "won", "away 1st half 56 < 58.5"
        assert ps[1]["result"] == "won", "Q1 54 < 60.5"
        assert "2026-11-05" in seen
        rep = nsh.report(d)
        assert "Away team 1st half points | 1 | 100%" in rep and "COLLECTING (1 of 100)" in rep


def test_blend_weight_zero_finds_no_value():
    """A group whose blend weight is 0 prices at SportyBet's own (margin-free) chance: never value."""
    nv.BLEND = {"team period points": 0.0}
    try:
        fams = {c["family"] for c in nsh.candidates(_look())}
        assert "Away team 1st half points" not in fams and "Quarter total Q1" in fams
    finally:
        nv.BLEND = {}


def test_report_empty():
    with tempfile.TemporaryDirectory() as t:
        assert "NO DATA — PENDING" in nsh.report(Path(t))


def main() -> None:
    test_freezes_first_entry_per_family()
    test_blend_weight_zero_finds_no_value()
    test_grades_from_espn_us_date_and_reports()
    test_report_empty()
    print("nba_shadow_test OK")


if __name__ == "__main__":
    main()
