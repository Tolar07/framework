"""Runner of engine/stat_lines.py: record SportyBet's corners / bookings / 1st-half total lines before kick-off,
grade the finished ones from the world_facts archive, then rewrite the study. RECORD ONLY."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import stat_lines  # noqa: E402


def main() -> int:
    print(stat_lines.run(fetch_detail=stat_lines.flashscore_detail))
    sys.path.insert(0, str(ROOT / "backtest"))
    try:
        import stat_lines_study
        print(stat_lines_study.main())
    except Exception as e:  # noqa: BLE001 - the study never stops the recorder
        print(f"stat lines study skipped ({type(e).__name__}: {str(e)[:80]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
