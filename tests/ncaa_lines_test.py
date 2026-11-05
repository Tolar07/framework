"""engine/ncaa_lines.py — NCAA fair chances from the sharp line (backtest/NCAA_STUDY.md shapes)."""
from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine import ncaa_lines as nl  # noqa: E402

LN = {"total": 159.5, "spread": 1.5, "ml_home": 2.1, "ml_away": 1.77, "provider": "DraftKings"}


def test_handicap_both_sides_add_to_one():
    away = nl.fair("B:223|hcp=-1.5|Away (+1.5)", LN)       # away favourite getting points
    home = nl.fair("B:223|hcp=-1.5|Home (-1.5)", LN)
    assert abs(away - 0.618) < 0.005 and abs(home + away - 1) < 1e-9
    assert nl.fair("B:223|hcp=2|Home (+2)", LN) is None      # whole line: pushes, never priced


def test_totals_and_first_half():
    over = nl.fair("B:225|total=159.5|Over 159.5", LN)
    assert 0.5 < over < 0.53                                  # the bias nudges the centre up 0.56
    assert abs(nl.fair("B:225|total=159.5|Under 159.5", LN) + over - 1) < 1e-9
    h1 = nl.fair("B:68|total=75.5|Over 75.5", LN)             # centre 0.4735 x 159.5 = 75.5
    assert abs(h1 - 0.5) < 0.01


def test_moneyline_and_match():
    p = nl.fair("B:219||Away", LN)
    assert 0.53 < p < 0.55
    ko = datetime(2026, 11, 6, 0, 0, tzinfo=UTC)
    gs = [{"id": "1", "tip": ko, "home": ["Lehigh Mountain Hawks", "Lehigh"], "away": ["Cornell Big Red", "Cornell"]}]
    assert nl.match("Lehigh Mountain Hawks", "Cornell Big Red", ko, gs)["id"] == "1"
    assert nl.match("Lehigh", "Cornell", ko + timedelta(hours=2), gs) is None


def main() -> None:
    test_handicap_both_sides_add_to_one()
    test_totals_and_first_half()
    test_moneyline_and_match()
    print("ncaa_lines_test OK")


if __name__ == "__main__":
    main()
