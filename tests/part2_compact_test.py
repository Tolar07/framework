"""HR57 compact Layer 2 view test (Fixtures | Selected Pick | Booking Code).

Asserts the fast-scan block renders ABOVE the full grid with:
  - the exact two-line header (PART 2 — COMPACT (fast-scan) / column titles),
  - one row per fixture,
  - an UNRATED fixture keeps its row as 'NO DATA — PENDING' (HR35, never
    dropped or fabricated),
  - a rated fixture with best_market uses it; a rated fixture without
    best_market falls back to the 1X2 result pick in words,
  - the Booking Code column carries ONE code across the whole Layer 2 scan
    (ID409) when the bridge produced a "Layer 2" aggregate code, else the
    honest 'NO DATA — PENDING' fallback (HR35, never a fabricated code).

Run as:  python tests/part2_compact_test.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.dixon_coles import FixtureProbabilities
from output.produce_bet import BoardFixture, render_part2_compact
from verification.id403 import verify, SourcedDatum

TODAY = "2026-08-17"


def _rated_bf(fixture, home, away, best_market=None):
    return BoardFixture(
        fixture=fixture,
        probs=FixtureProbabilities(
            home, away,
            lambda_home=1.8, lambda_away=0.9,
            p_home=0.56, p_draw=0.24, p_away=0.20,
            p_over_15=0.71, p_over_25=0.45,
            p_over_35=0.22, p_btts_yes=0.55,
            modal_scoreline=(1, 0)),
        verification=verify([SourcedDatum(
            domain="thesportsdb.com", value="x", url="https://x", structured=True)]),
        on_deploy_shortlist=True,
        best_market=best_market,
        kickoff_date=TODAY)


def _unrated_bf(fixture, reason):
    return BoardFixture(
        fixture=fixture, probs=None,
        verification=verify([SourcedDatum(
            domain="thesportsdb.com", value="x", url="https://x", structured=True)]),
        rejection_reason=reason)


_board = [
    _rated_bf("Arsenal v Chelsea (Premier League)", "Arsenal", "Chelsea",
              best_market="Over 2.5 goals"),
    _rated_bf("Liverpool v Everton (Premier League)", "Liverpool", "Everton"),
    _unrated_bf("Tottenham v Fulham (Premier League)", "no rated model"),
]

# --- 1. structure: two-line header + one row per fixture -------------------
txt = render_part2_compact(_board)
lines = txt.splitlines()
assert lines[0] == "PART 2 — COMPACT (fast-scan)", lines[0]
assert lines[1] == "Fixture | Selected Pick | Booking Code", lines[1]
assert len(lines) == 2 + len(_board), (len(lines), len(_board))
print("1. header + one row per fixture: OK")

# --- 2. unrated fixture keeps its row honest (HR35) ------------------------
pending = [l for l in lines if "NO DATA — PENDING" in l]
assert pending, "expected an honest NO DATA — PENDING row for the unrated fixture"
assert any(l.startswith("Tottenham v Fulham (Premier League) | NO DATA — PENDING")
           for l in pending), pending
print("2. unrated fixture keeps row as NO DATA — PENDING (HR35): OK")

# --- 3. best_market preferred over 1X2 fallback ----------------------------
assert "Arsenal v Chelsea (Premier League) | Over 2.5 goals |" in txt, txt
print("3. rated fixture with best_market uses it: OK")

# --- 4. 1X2 result fallback when no best_market ----------------------------
# Liverpool p_home is highest (0.56) -> "Liverpool to win".
assert "Liverpool v Everton (Premier League) | Liverpool to win |" in txt, txt
print("4. rated fixture without best_market falls back to 1X2 result pick: OK")

# --- 5. one Layer 2 code across the whole scan (ID409) ---------------------
codes_with = {"results": [{"label": "Layer 2", "code": "L2XYZ"}]}
txt_c = render_part2_compact(_board, codes=codes_with)
rows_c = [l for l in txt_c.splitlines() if l.startswith(("Arsenal", "Liverpool", "Tottenham"))]
assert all(l.endswith("| L2XYZ") for l in rows_c), rows_c
print("5. one 'Layer 2' booking code across all rows (ID409): OK")

# --- 6. honest NO DATA — PENDING when bridge produced no Layer 2 code ------
txt_n = render_part2_compact(_board, codes={"results": [{"label": "Acca A", "code": "AA1"}]})
rows_n = [l for l in txt_n.splitlines() if l.startswith(("Arsenal", "Liverpool", "Tottenham"))]
assert all(l.endswith("| NO DATA — PENDING") for l in rows_n), rows_n
print("6. no Layer 2 code -> honest NO DATA — PENDING, never fabricated (HR35): OK")

# --- 7. no codes argument at all -> honest fallback ------------------------
txt_none = render_part2_compact(_board)
assert "Booking Code" in txt_none and "NO DATA — PENDING" in txt_none, txt_none
print("7. absent codes argument -> honest NO DATA — PENDING fallback (HR35): OK")

print("\n[OK] ALL PART 2 COMPACT VIEW TESTS PASSED")
