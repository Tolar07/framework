"""Tests for data/validation.py — schema + row-level sanity checks.

Proves HR35 is kept: a bad value is dropped with a reason, never coerced.
  1. validate_header flags a renamed/missing column (schema change).
  2. validate_score_field rejects negative / non-integer / absurd scores.
  3. validate_date_iso rejects impossible and implausibly-future dates.
  4. validate_result_consistency catches a lying FTR.
  5. find_duplicates reports same-day same-pairing rows.
  6. parse_csv_text drops a malformed row to `skipped` (not silent poison).
"""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from data import validation as V
from data import football_data_source as fds


# --- 1. header schema gate ---------------------------------------------------
issue = V.validate_header(["HomeTeam", "AwayTeam", "Date"],
                          ["HomeTeam", "AwayTeam"], source="test")
assert issue is not None and "missing" in issue.problem.lower()
assert issue.row is None, "schema issue has no row"
ok = V.validate_header(["HomeTeam", "AwayTeam"], ["HomeTeam", "AwayTeam"])
assert ok is None
print("1. header schema gate flags missing columns: OK")

# --- 2. score range ----------------------------------------------------------
assert V.validate_score_field("FTHG", "-1", 1) is not None, "negative score"
assert V.validate_score_field("FTAG", "abc", 1) is not None, "non-integer score"
assert V.validate_score_field("FTHG", "99", 1) is not None, "absurd score"
assert V.validate_score_field("FTHG", "4", 1) is None, "normal score fine"
print("2. score validation rejects bad values, accepts sane ones: OK")

# --- 3. date sanity ----------------------------------------------------------
assert V.validate_date_iso("2026-02-31", 1) is not None, "impossible date"
assert V.validate_date_iso("2099-01-01", 1) is not None, "implausible future"
assert V.validate_date_iso("2026-08-01", 1) is None, "normal date fine"
print("3. date validation rejects impossible/future, accepts sane: OK")

# --- 4. result consistency ---------------------------------------------------
assert V.validate_result_consistency(2, 1, "H", 1) is None, "H matches 2-1"
assert V.validate_result_consistency(1, 1, "D", 1) is None, "D matches 1-1"
assert V.validate_result_consistency(0, 2, "H", 1) is not None, "H contradicts 0-2"
assert V.validate_result_consistency(2, 1, "", 1) is None, "blank FTR tolerated"
print("4. FTR-vs-scoreline consistency check works: OK")

# --- 5. duplicate detection --------------------------------------------------
dupes = V.find_duplicates([("2026-08-01", "AAA", "BBB"),
                           ("2026-08-01", "AAA", "BBB"),
                           ("2026-08-02", "AAA", "BBB")])
assert len(dupes) == 1, f"one duplicate pair expected: {dupes}"
print("5. find_duplicates reports the same-day same-pairing row: OK")

# --- 6. parse_csv_text drops a bad row to skipped, never guesses -------------
GOOD = ("Date,HomeTeam,AwayTeam,FTHG,FTAG,FTR\n"
        "01/08/2026,AAA,BBB,2,1,H\n")
res, sk = fds.parse_csv_text("TestLeague", GOOD)
assert len(res) == 1 and res[0].ftr == "H", "normal row parses"

BAD_SCORE = ("Date,HomeTeam,AwayTeam,FTHG,FTAG,FTR\n"
             "01/08/2026,AAA,BBB,-1,1,H\n")  # negative score
res, sk = fds.parse_csv_text("TestLeague", BAD_SCORE)
assert len(res) == 0 and len(sk) == 1, "negative score must be skipped"
assert "negative" in sk[0]["reason"].lower()

BAD_FTR = ("Date,HomeTeam,AwayTeam,FTHG,FTAG,FTR\n"
           "01/08/2026,AAA,BBB,1,2,H\n")  # H but away won
res, sk = fds.parse_csv_text("TestLeague", BAD_FTR)
assert len(res) == 0 and len(sk) == 1, "lying FTR must be skipped"
assert "contradicts" in sk[0]["reason"].lower()

MISSING_COL = ("Date,HomeTeam,FTHG,FTAG,FTR\n"  # no AwayTeam column
               "01/08/2026,AAA,2,1,H\n")
try:
    fds.parse_csv_text("TestLeague", MISSING_COL)
    raise SystemExit("missing column must raise, not silently parse")
except ValueError as e:
    assert "missing required column" in str(e)
print("6. parse_csv_text drops bad rows and raises on schema change: OK")

print("\n✅ ALL VALIDATION TESTS PASSED")
