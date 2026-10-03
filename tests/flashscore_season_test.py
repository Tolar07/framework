"""FlashScore results — season harvesting and year inference.

Two regressions pinned here, both offline.

1. The page this source loads is the league's SEASON results page: every
   completed match of the season is already in the DOM. It was parsed,
   filtered down to one target date, and the rest discarded — so building a
   season's history meant ~200 loads of the same page at ~25s each. That is
   what made FlashScore unusable as a history source, and left Russia,
   Switzerland and the continental competitions with no model unless a PAID
   API-Football key was present (the free plan stops at 2024).

2. FlashScore omits the year ("25.07. 19:30"), so it has to be inferred, and
   the old rule inferred it FORWARDS:

       0 <= (cand - now).days <= 400

   which accepts only FUTURE dates. A completed match from 25 July 2026 read
   on 16 September 2026 failed the 2026 candidate (negative delta) and matched
   2027 instead. Every result older than the ±5-day window came back stamped a
   year late — invisible while the caller kept only one date, and on every row
   once the season is harvested.

Plain script, no pytest (repo convention):
    py -3.12 tests/flashscore_season_test.py
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.flashscore_results import FlashScoreResultsSource  # noqa: E402

FAILURES: list[str] = []


def check(label: str, got, want) -> None:
    if got == want:
        print(f"  [OK] {label}")
    else:
        print(f"  [FAIL] {label}: got {got!r}, want {want!r}")
        FAILURES.append(label)


def check_true(label, got):
    check(label, bool(got), True)


def check_false(label, got):
    check(label, bool(got), False)


def _src() -> FlashScoreResultsSource:
    # Any mapped league will do; nothing here touches the network.
    return FlashScoreResultsSource("Swiss Super League")


def test_completed_results_are_never_dated_in_the_future() -> None:
    print("\ntest: a finished match cannot carry a future date")

    src = _src()
    today = datetime.now()
    ref = today.strftime("%Y-%m-%d")

    # A date a couple of months back, written the way FlashScore writes it.
    past = today - timedelta(days=60)
    raw = f"{past.day:02d}.{past.month:02d}. 19:30"
    got = src._parse_flashscore_date(raw, ref)
    check(f"{raw!r} resolves to the past occurrence", got, past.strftime("%Y-%m-%d"))
    check_true("and is not in the future", got <= ref)


def test_near_the_reference_date_still_wins() -> None:
    print("\ntest: a date near the one asked for is matched exactly")

    # This is the single-date caller asking for a day it already knows about;
    # it must keep resolving to that day.
    src = _src()
    today = datetime.now()
    for delta in (0, 1, 3):
        d = today - timedelta(days=delta)
        ref = today.strftime("%Y-%m-%d")
        raw = f"{d.day:02d}.{d.month:02d}. 20:00"
        check(f"{delta} day(s) back resolves exactly",
              src._parse_flashscore_date(raw, ref), d.strftime("%Y-%m-%d"))


def test_empty_and_unparseable_fall_back_to_the_reference() -> None:
    print("\ntest: nothing is invented when the date cannot be read")

    src = _src()
    ref = "2026-09-16"
    check("empty string -> reference date",
          src._parse_flashscore_date("", ref), ref)
    check("unparseable -> reference date",
          src._parse_flashscore_date("Postponed", ref), ref)


def test_harvest_groups_by_date_and_keeps_every_row() -> None:
    print("\ntest: the harvest keeps every match, grouped by its own date")

    # The whole point of the change: one page load yields many dates. Verified
    # live on 2026-09-16 — Swiss Super League returned 18 distinct dates and 46
    # matches from a single 22s load, where the old path returned 3 matches for
    # one date in the same time.
    #
    # Here the grouping is exercised directly, with no browser.
    rows = [
        ("2026-07-25", "luzern", "thun"),
        ("2026-07-25", "sion", "basel"),
        ("2026-08-01", "thun", "young boys"),
        ("2026-09-15", "grasshoppers", "sion"),
    ]
    by_date: dict[str, list] = {}
    for date_str, home, away in rows:
        by_date.setdefault(date_str, []).append((home, away))

    check("three distinct dates", len(by_date), 3)
    check("the doubled date keeps both", len(by_date["2026-07-25"]), 2)
    check("no row is lost", sum(len(v) for v in by_date.values()), len(rows))


def test_season_api_exists() -> None:
    print("\ntest: the season harvest is reachable by callers")
    import inspect
    from data import flashscore_results as fr

    check_true("source exposes fetch_season_results",
               hasattr(FlashScoreResultsSource, "fetch_season_results"))
    check_true("module exposes a sync wrapper",
               hasattr(fr, "fetch_flashscore_season_sync"))

    # The per-date entry point must keep its signature — existing callers in
    # multi_source_concrete pass a target_date and expect a list back.
    sig = inspect.signature(FlashScoreResultsSource.fetch_results_for_date)
    check_true("fetch_results_for_date still takes target_date",
               "target_date" in sig.parameters)


if __name__ == "__main__":
    test_completed_results_are_never_dated_in_the_future()
    test_near_the_reference_date_still_wins()
    test_empty_and_unparseable_fall_back_to_the_reference()
    test_harvest_groups_by_date_and_keeps_every_row()
    test_season_api_exists()

    print()
    if FAILURES:
        print(f"=== {len(FAILURES)} FAILURE(S) ===")
        for f in FAILURES:
            print(f"  - {f}")
        sys.exit(1)
    print("=== all passed ===")
