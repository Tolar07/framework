"""FlashScore kickoffs must reach the board as ISO datetimes.

The regression this pins: the FlashScore fixtures adapter stored the page's
DISPLAYED kickoff verbatim as the fixture's kickoff_utc, so fixtures arrived
carrying "13.09. 14:15". No date filter can read that, which means "today's
fixtures only" could not identify them and settlement had no timestamp to work
from.

Measured 2026-09-16 on La Liga: 9 of 13 fixtures had a non-ISO kickoff_utc.
After the fix, 0 of 6.

Also pins the map_team fallthrough, which is what lets a FlashScore spelling
reach a model key at all.

Plain script, no pytest (repo convention):
    py -3.12 tests/flashscore_kickoff_test.py
"""
from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.multi_source_concrete import _flashscore_kickoff_to_iso  # noqa: E402

FAILURES: list[str] = []
ISO = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")

NOW = datetime(2026, 9, 16, 15, 0)


def check(label: str, got, want) -> None:
    if got == want:
        print(f"  [OK] {label}")
    else:
        print(f"  [FAIL] {label}: got {got!r}, want {want!r}")
        FAILURES.append(label)


def check_true(label, got):
    check(label, bool(got), True)


def test_day_and_month_form() -> None:
    print("\ntest: 'DD.MM. HH:MM' resolves to a full ISO datetime")

    CASES = [
        ("13.09. 14:15", "2026-09-13T14:15:00"),
        ("17.09. 19:30", "2026-09-17T19:30:00"),
        ("20.09. 12:00", "2026-09-20T12:00:00"),
        ("15.09. 18:00", "2026-09-15T18:00:00"),
    ]
    for raw, want in CASES:
        check(f"{raw!r}", _flashscore_kickoff_to_iso(raw, NOW), want)


def test_time_only_is_today() -> None:
    print("\ntest: 'HH:MM' alone means today")

    check("'14:15' is today", _flashscore_kickoff_to_iso("14:15", NOW),
          "2026-09-16T14:15:00")
    check("'19:30' is today", _flashscore_kickoff_to_iso("19:30", NOW),
          "2026-09-16T19:30:00")


def test_trailing_status_is_tolerated() -> None:
    print("\ntest: a status suffix does not break the parse")

    # FlashScore appends markers like "Pen" / "AET" to a finished tie.
    check("'15.09. 18:30Pen'", _flashscore_kickoff_to_iso("15.09. 18:30Pen", NOW),
          "2026-09-15T18:30:00")


def test_unreadable_values_yield_none() -> None:
    print("\ntest: what is not a kickoff is dropped, not stored")

    # Returning None leaves the field absent rather than poisoning it with a
    # string nothing downstream can parse (HR35).
    for raw in ("Postponed", "", "   ", "FRO", "Awarded", "99:99", "abc"):
        check(f"{raw!r} -> None", _flashscore_kickoff_to_iso(raw, NOW), None)


def test_year_is_the_nearest_candidate() -> None:
    print("\ntest: the missing year is the one nearest to now")

    # The page never shows a year. Picking the nearest candidate is what keeps
    # a fixture a few days either side of New Year on the right side of it.
    on_new_year = datetime(2027, 1, 2, 12, 0)
    check("late-December fixture read in January stays in the old year",
          _flashscore_kickoff_to_iso("28.12. 20:00", on_new_year),
          "2026-12-28T20:00:00")
    check("early-January fixture read in January stays in the new year",
          _flashscore_kickoff_to_iso("05.01. 20:00", on_new_year),
          "2027-01-05T20:00:00")


def test_output_shape_is_parseable() -> None:
    print("\ntest: every value returned is something downstream can read")

    # The pipeline does datetime.fromisoformat(v.replace("Z", "+00:00")) and
    # elsewhere takes v[:10] as the date, so both must work.
    for raw in ("13.09. 14:15", "14:15", "20.09. 12:00"):
        got = _flashscore_kickoff_to_iso(raw, NOW)
        check_true(f"{raw!r} matches the ISO shape", ISO.match(got or ""))
        datetime.fromisoformat((got or "").replace("Z", "+00:00"))
        check_true(f"{raw!r} date half is 10 chars", len((got or "")[:10]) == 10)


def test_map_team_falls_through_to_the_reverse_resolver() -> None:
    print("\ntest: a FlashScore spelling reaches a model key")

    from data.thesportsdb_fixtures import map_team

    # TEAM_ALIASES was built for TheSportsDB and has no FlashScore spellings,
    # so these passed straight through and the fixture was rated NO DATA.
    CASES = [
        ("La Liga", "A Coruna", "La Coruna"),
        ("La Liga", "Ath. Bilbao", "Ath Bilbao"),
        ("La Liga", "Atl. Madrid", "Ath Madrid"),
        ("La Liga", "Celta Vigo", "Celta"),
    ]
    for league, feed_name, model_key in CASES:
        check(f"{feed_name!r} -> {model_key!r}", map_team(league, feed_name), model_key)

    # An unknown name must still pass through unchanged, so the engine reports
    # NO DATA — PENDING rather than guessing a match.
    check("unknown name unchanged",
          map_team("La Liga", "Nonexistent Rovers"), "Nonexistent Rovers")


if __name__ == "__main__":
    test_day_and_month_form()
    test_time_only_is_today()
    test_trailing_status_is_tolerated()
    test_unreadable_values_yield_none()
    test_year_is_the_nearest_candidate()
    test_output_shape_is_parseable()
    test_map_team_falls_through_to_the_reverse_resolver()

    print()
    if FAILURES:
        print(f"=== {len(FAILURES)} FAILURE(S) ===")
        for f in FAILURES:
            print(f"  - {f}")
        sys.exit(1)
    print("=== all passed ===")
