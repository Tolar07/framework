"""Grade the picks ledgers now, without building or sending a board (grade.yml).

Order 53, "grade everything": every picks_<date>.json not newer than today is
graded by `engine/picks_ledger.grade_all` (Flashscore's last 7 days, FotMob for
what Flashscore lacks) exactly as the board run does before each board. This
runs only that step, so a fix to the grader (8 Nov 2026: names and extra time
left the 7 Nov board open) re-grades the past days at once instead of waiting
for the next board, and a board is never sent twice for it.

  python monitor/grade_run.py           grade, print the per-day flags
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> int:
    from data import fotmob
    from data.flashscore_results import results_since
    from engine import picks_ledger
    try:
        events = results_since(7)
    except Exception as e:  # noqa: BLE001 - FotMob still grades what it can
        print(f"Flashscore results unavailable ({e}); FotMob only")
        events = []
    print(f"Flashscore: {len(events)} events over the last 7 days")
    for line in picks_ledger.grade_all(events, fotmob_day=fotmob.matches_on):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
