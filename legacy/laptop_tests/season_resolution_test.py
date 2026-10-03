"""SEASON RESOLUTION + fixtures_season threading — wrong-fixtures regressions.

Two independent bugs put another season's fixtures on the board. Both are
pinned here because both failed silently: the pipeline fetched real fixtures,
just from the wrong season, and nothing in the logs said so.

Run directly:  PYTHONIOENCODING=utf-8 py -3.12 tests/season_resolution_test.py
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.multi_source_concrete import _season_start_year

FAILURES: list[str] = []


def check(label, got, want):
    if got == want:
        print(f"  OK {label}")
    else:
        print(f"  FAIL {label}: got {got!r}, want {want!r}")
        FAILURES.append(label)


print("1. season codes resolve to the year the season STARTS in")
# Repo convention: 4-digit span codes.
check("'2526' -> 2025", _season_start_year("2526"), 2025)
check("'2627' -> 2026", _season_start_year("2627"), 2026)

print("\n2. a 4-digit CALENDAR YEAR is not mangled into a span code")
# Regression: int('2026'[:2]) + 2000 == 2020, six years early. api-football
# returned real fixtures for the wrong season and nothing flagged it.
check("'2026' -> 2026 (not 2020)", _season_start_year("2026"), 2026)
check("'1998' -> 1998 (not 2019)", _season_start_year("1998"), 1998)
check("int 2026 passes through", _season_start_year(2026), 2026)

print("\n3. unresolvable seasons return None, never a guess")
# Regression: the None branch claimed an "except -> current year" fallback,
# but the guarded expression could not raise on None, so the fallback was
# dead code. Returning None is correct per HR35 -- the caller raises
# SourceNoData rather than silently fetching some other season.
for bad in (None, "", "abc", "20x6", [], {}):
    check(f"{bad!r} -> None", _season_start_year(bad), None)
check("'9900' -> None (not a span, not a plausible year)",
      _season_start_year("9900"), None)

print("\n4. get_fixtures_for_run_daily actually USES fixtures_season")
# Regression: the parameter was accepted and then discarded -- the call
# passed `season` to the provider chain, so the daily board fetched the
# COMPLETED season's fixtures no matter what --fixtures-season was set to.
from fixtures_and_odds_providers import get_fixtures_for_run_daily  # noqa: E402

src = inspect.getsource(get_fixtures_for_run_daily)
check("fixtures_season is referenced in the body",
      "fixtures_season or season" in src, True)
check("season is not passed directly to the provider chain",
      "get_fixtures_with_fallback(league, season," not in src, True)

# Drive it for real: a stub chain records which season it was handed.
import fixtures_and_odds_providers as fop  # noqa: E402

seen: list[str] = []
_orig = fop.get_fixtures_with_fallback
try:
    fop.get_fixtures_with_fallback = lambda league, season, date_target=None: (
        seen.append(season) or [])
    fop.get_fixtures_for_run_daily(["Premier League"], season="2526",
                                   fixtures_season="2627")
    check("live season wins over completed season", seen, ["2627"])

    seen.clear()
    fop.get_fixtures_for_run_daily(["Premier League"], season="2526",
                                   fixtures_season=None)
    check("falls back to season when fixtures_season is absent", seen, ["2526"])
finally:
    fop.get_fixtures_with_fallback = _orig

print()
if FAILURES:
    print(f"=== {len(FAILURES)} FAILURE(S) ===")
    for f in FAILURES:
        print(f"  - {f}")
    sys.exit(1)
print("=== season resolution: all passed ===")
