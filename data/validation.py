"""Data validation + schema checks for the OLP XDV data layer.

WHY THIS EXISTS
  The daily run trusts upstream CSVs/JSON to look like last season. When a
  source changes schema (renamed a column), truncates a file, or starts
  emitting out-of-range values, the old parser silently degraded — usually to
  zero rows or implausible model inputs that still LOOK fine on the board.
  This module is the guardrail: it checks the SHAPE before parse, and each
  parsed row for sanity, so a broken feed fails loudly as NO DATA — PENDING
  rather than poisoning the engine fit.

HR35 is preserved throughout: validation RAISES or drops-with-reason; it never
interpolates, guesses, or coerces a bad value into a good-looking one.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

# A sane score is non-negative and, for football, essentially never above 15.
MAX_GOALS = 15
# A result row dated more than 2 days in the future is almost certainly a data
# error (fixtures leak into the results feed).
FUTURE_TOLERANCE_DAYS = 2


@dataclass
class ValidationIssue:
    """One concrete, human-readable problem found in a data row or header."""
    row: Optional[int]        # None for a schema-level issue
    field: str
    problem: str


def validate_header(required_columns: list[str], fieldnames: list[str],
                    source: str = "csv") -> Optional[ValidationIssue]:
    """Check that every required column is present in the header.

    Returns a ValidationIssue (schema-level, row=None) when a column is
    missing, else None. A missing column means the source changed its schema —
    parsing on would silently produce wrong/empty rows."""
    missing = [c for c in required_columns if c not in fieldnames]
    if not missing:
        return None
    return ValidationIssue(
        row=None,
        field=",".join(missing),
        problem=f"{source} header is missing required column(s): "
                f"{', '.join(missing)} — schema changed or file truncated",
    )


def validate_score_field(name: str, raw, row: int) -> Optional[ValidationIssue]:
    """A score must be a non-negative integer within a sane range."""
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return ValidationIssue(row, name,
                               f"{name}={raw!r} is not an integer")
    if value < 0:
        return ValidationIssue(row, name, f"{name}={value} is negative")
    if value > MAX_GOALS:
        return ValidationIssue(row, name,
                               f"{name}={value} exceeds sane max {MAX_GOALS}")
    return None


def validate_date_iso(raw: str, row: int) -> Optional[ValidationIssue]:
    """An ISO date that is real (not 2026-02-31) and not implausibly future."""
    try:
        d = datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return ValidationIssue(row, "Date", f"Date={raw!r} is not a real date")
    if (datetime.now(timezone.utc).date() - d).days < -FUTURE_TOLERANCE_DAYS:
        return ValidationIssue(row, "Date",
                               f"Date={raw} is in the future for a result row")
    return None


def validate_result_consistency(home: int, away: int, ftr: str,
                                row: int) -> Optional[ValidationIssue]:
    """The FTR letter must agree with the scoreline, when FTR is present.

    A row that says H with away goals greater than home goals is a data error
    worth surfacing — it would teach the engine a lie."""
    if not ftr:
        return None
    expected = ("H" if home > away else
                "A" if away > home else "D")
    if ftr.strip().upper() != expected:
        return ValidationIssue(
            row, "FTR",
            f"FTR={ftr!r} contradicts score {home}-{away} (expected {expected})")
    return None


def validate_odds_value(name: str, value: Optional[float],
                        row: int) -> Optional[ValidationIssue]:
    """An odds value must be >= 1.0 when present (a bookmaker never prices
    below evens) and finite."""
    if value is None:
        return None
    if value < 1.0:
        return ValidationIssue(row, name, f"{name}={value} below evens (1.0)")
    return None


def find_duplicates(rows: list[tuple[str, str, str]], key_label: str = "date|home|away"
                    ) -> list[str]:
    """Return the duplicated keys in a list of (date, home, away) tuples.

    The same pairing recurs every season, so duplicates are only meaningful
    WITHIN one season file — callers pass one season's rows only."""
    seen: set[tuple[str, str, str]] = set()
    dupes: list[str] = []
    for date_, home, away in rows:
        key = (date_, home, away)
        if key in seen:
            dupes.append(f"{date_} {home} v {away}")
        seen.add(key)
    return dupes
