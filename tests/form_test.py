"""
Tests for engine.form — league table + recent form from results (offline).
"""
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.form import compute_table, fixture_form, form_support


@dataclass
class R:
    home_team: str
    away_team: str
    fthg: Optional[int]
    ftag: Optional[int]
    date: str


# A tiny 3-team round: A beats B, A beats C, B draws C. Plus an unplayed match.
RESULTS = [
    R("A", "B", 2, 0, "2026-08-01"),
    R("C", "A", 0, 1, "2026-08-08"),
    R("B", "C", 1, 1, "2026-08-15"),
    R("A", "B", None, None, "2026-09-01"),  # not played — must be ignored
]


def test_table_points_and_position() -> None:
    t = compute_table(RESULTS)
    assert t["A"].points == 6 and t["A"].played == 2 and t["A"].position == 1
    assert t["B"].points == 1 and t["C"].points == 1
    assert t["A"].gd == 3
    # unplayed match ignored: A has 2 games, not 3
    assert t["A"].won == 2


def test_last5_form() -> None:
    t = compute_table(RESULTS)
    assert t["A"].last5_points == 6 and t["A"].last5_played == 2
    assert round(t["A"].last5_ppg, 2) == 3.0


def test_form_support_sign_and_bounds() -> None:
    t = compute_table(RESULTS)
    ff = fixture_form(t, "A", "B")
    s_home = form_support(ff, "home")   # A in far better form than B
    assert s_home is not None and s_home > 0
    s_away = form_support(ff, "away")   # backing B contradicts form
    assert s_away is not None and s_away < 0
    assert -1.0 <= s_home <= 1.0
    # unknown team -> no fabricated signal
    assert form_support(fixture_form(t, "A", "Zzz"), "home") is None


def main() -> None:
    test_table_points_and_position()
    test_last5_form()
    test_form_support_sign_and_bounds()
    print("form_test: OK")


if __name__ == "__main__":
    main()
