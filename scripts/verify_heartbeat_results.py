"""
Verify every recorded heartbeat prediction against REAL match results.

Architect directive 2026-09-17: "go and verify all the heartbeat results, all
the prediction, verify it. If you verify it, you will see where we stopped
because it's supposed to continue from where we stop."

WHY THIS IS NOT REDUNDANT
data/heartbeat/history.jsonl and lineage_ledger.jsonl both assert the same
outcomes, but they are not independent of each other -- the ledger was
populated FROM the history (scripts/populate_lineage_ledger.py). Two files
agreeing proves only that the copy worked. This script goes to the actual
match scores and checks the claim, which is the only thing that can confirm
the 7W-2L record is real rather than merely self-consistent.

HR35: a fixture whose real score cannot be fetched is reported UNVERIFIED.
It is never assumed to match the recorded result.

Usage:
    python scripts/verify_heartbeat_results.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from output.heartbeat import HISTORY_FILE  # noqa: E402
from verification.fixture_matcher import names_match  # noqa: E402


def load_records() -> list[dict]:
    rows = []
    for line in HISTORY_FILE.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return sorted(rows, key=lambda r: (r.get("date") or "", r.get("fixture") or ""))


def strip_league(fixture: str) -> str:
    """'A v B (League)' -> 'A v B'."""
    return fixture.rsplit(" (", 1)[0] if fixture.endswith(")") and " (" in fixture else fixture


def split_fixture(fixture: str) -> tuple[str, str]:
    core = strip_league(fixture)
    if " v " in core:
        h, a = core.split(" v ", 1)
        return h.strip(), a.strip()
    return core.strip(), ""


def fetch_day(date: str):
    """Real results for a date. Returns [] when the source is unavailable."""
    try:
        from data.espn_results import fetch_results_for_date
        return fetch_results_for_date(date)
    except Exception as e:
        print(f"    ! result fetch failed for {date}: {type(e).__name__}: {e}")
        return []


# The possible picks within each market family. Used to re-grade records whose
# pick text was lost: if no candidate in the family supports the recorded
# result, that result is wrong no matter which one was actually picked.
CANDIDATES: dict[str, list[str]] = {
    "BTTS": ["BTTS_YES", "BTTS_NO"],
    "DC": ["DC_HOME_DRAW", "DC_DRAW_AWAY", "DC_HOME_AWAY"],
    "1X2": ["HOME", "DRAW", "AWAY"],
    "O/U": ["O1.5", "U1.5", "O2.5", "U2.5", "O3.5", "U3.5"],
}


def evaluate(market: str, home_goals: int, away_goals: int) -> dict[str, bool]:
    """Which outcomes actually happened, per market family."""
    total = home_goals + away_goals
    return {
        "HOME": home_goals > away_goals,
        "DRAW": home_goals == away_goals,
        "AWAY": away_goals > home_goals,
        "BTTS_YES": home_goals > 0 and away_goals > 0,
        "BTTS_NO": not (home_goals > 0 and away_goals > 0),
        "O1.5": total > 1.5, "U1.5": total < 1.5,
        "O2.5": total > 2.5, "U2.5": total < 2.5,
        "O3.5": total > 3.5, "U3.5": total < 3.5,
        "DC_HOME_DRAW": home_goals >= away_goals,
        "DC_DRAW_AWAY": away_goals >= home_goals,
        "DC_HOME_AWAY": home_goals != away_goals,
    }


def main() -> int:
    records = load_records()
    print(f"Verifying {len(records)} recorded heartbeat(s) against real match results")
    print("=" * 78)

    by_date: dict[str, list] = {}
    for r in records:
        by_date.setdefault(r["date"], []).append(r)

    confirmed = unverified = contradicted = 0
    last_verified_date = None

    for date in sorted(by_date):
        results = fetch_day(date)
        print(f"\n{date}  ({len(results)} completed match(es) fetched)")

        for rec in by_date[date]:
            home, away = split_fixture(rec["fixture"])
            match = None
            for m in results:
                if names_match(m.home_team, home) and names_match(m.away_team, away):
                    match = m
                    break

            claimed = rec.get("result")
            label = f"  {rec['fixture'][:46]:<46}"

            if match is None:
                print(f"{label} claimed {claimed:<4} -> UNVERIFIED (no result found)")
                unverified += 1
                continue

            score = f"{match.home_score}-{match.away_score}"
            outcomes = evaluate(rec.get("market_type") or "", match.home_score, match.away_score)
            pick = rec.get("pick")

            # The pick TEXT is null on 8 of 9 restored records, so for those the
            # exact selection cannot be re-graded. What CAN be verified is that
            # the match was played and its real score exists -- and, where the
            # pick survives, whether the claimed result holds.
            if not pick:
                # The pick TEXT was lost when a CWD-relative test teardown
                # deleted history.jsonl, but the MARKET FAMILY survived in the
                # ledger -- and a market family has only a handful of possible
                # picks. So grade every candidate against the real score and
                # report which ones the claimed result is consistent with.
                # That is weaker than re-grading the actual pick, and stronger
                # than shrugging: if NO candidate supports the claim, the
                # recorded result is wrong regardless of which one was picked.
                cands = CANDIDATES.get((rec.get("market_type") or "").upper(), [])
                if not cands:
                    print(f"{label} claimed {claimed:<4} -> score {score} PLAYED, "
                          f"market '{rec.get('market_type')}' has no candidate set "
                          f"— UNVERIFIED")
                    unverified += 1
                    last_verified_date = date
                    continue

                supports = [c for c in cands
                            if (outcomes[c] and claimed == "WIN")
                            or (not outcomes[c] and claimed == "LOSS")]
                refutes = [c for c in cands if c not in supports]

                if not supports:
                    print(f"{label} claimed {claimed:<4} -> score {score}, "
                          f"NO {rec.get('market_type')} pick gives {claimed} "
                          f"— CONTRADICTED")
                    contradicted += 1
                elif not refutes:
                    print(f"{label} claimed {claimed:<4} -> score {score}, "
                          f"every {rec.get('market_type')} option gives {claimed} "
                          f"— CONFIRMED")
                    confirmed += 1
                else:
                    print(f"{label} claimed {claimed:<4} -> score {score}, "
                          f"{claimed} only if pick was {'/'.join(supports)} "
                          f"(would be {'WIN' if claimed == 'LOSS' else 'LOSS'} "
                          f"if {'/'.join(refutes)}) — AMBIGUOUS")
                    unverified += 1
                last_verified_date = date
                continue

            hit = None
            p = pick.lower()
            if "over 2.5" in p:
                hit = outcomes["O2.5"]
            elif "over 1.5" in p:
                hit = outcomes["O1.5"]
            elif "over 3.5" in p:
                hit = outcomes["O3.5"]
            elif "both teams" in p or "btts" in p:
                hit = outcomes["BTTS_NO"] if " no" in p else outcomes["BTTS_YES"]
            elif "draw" in p and "or" not in p:
                hit = outcomes["DRAW"]

            if hit is None:
                print(f"{label} claimed {claimed:<4} -> score {score}, "
                      f"pick '{pick}' not machine-gradable — UNVERIFIED")
                unverified += 1
            elif (hit and claimed == "WIN") or ((not hit) and claimed == "LOSS"):
                print(f"{label} claimed {claimed:<4} -> score {score}, "
                      f"'{pick}' CONFIRMED")
                confirmed += 1
            else:
                print(f"{label} claimed {claimed:<4} -> score {score}, "
                      f"'{pick}' CONTRADICTED (real outcome says "
                      f"{'WIN' if hit else 'LOSS'})")
                contradicted += 1
            last_verified_date = date

    print("\n" + "=" * 78)
    print(f"CONFIRMED {confirmed} · CONTRADICTED {contradicted} · UNVERIFIED {unverified}")
    print(f"Last date with any heartbeat record: {max(by_date) if by_date else 'NONE'}")
    if last_verified_date:
        print(f"Last date whose match was confirmed played: {last_verified_date}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
