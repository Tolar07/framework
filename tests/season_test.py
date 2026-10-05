"""The fit season follows the date (2026-10-05: was a hard-coded "2526"). Offline."""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import orchestrator  # noqa: E402


def test_fit_season_code() -> None:
    cases = {date(2026, 10, 5): "2526", date(2027, 3, 1): "2526", date(2027, 6, 30): "2526",
             date(2027, 7, 1): "2627", date(2027, 12, 31): "2627", date(2030, 8, 1): "2930",
             date(2099, 8, 1): "9899", date(2100, 8, 1): "9900"}
    for d, want in cases.items():
        assert orchestrator.fit_season_code(d) == want, (d, orchestrator.fit_season_code(d))
    assert orchestrator.next_season_code(orchestrator.fit_season_code(date(2026, 10, 5))) == "2627"


def test_no_fixed_season_default() -> None:
    import inspect

    import run_daily
    assert inspect.signature(run_daily.run).parameters["season"].default is None
    assert inspect.signature(orchestrator.run_all_leagues).parameters["season"].default is None


if __name__ == "__main__":
    test_fit_season_code()
    test_no_fixed_season_default()
    print("season: OK")
