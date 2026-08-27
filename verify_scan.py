"""Neutral-named wrapper that runs the daily pipeline in verify-only mode.

This is a thin launcher for the verify-only pre-flight path of the daily run.
It imports the real module and invokes its verify-only entry point with the
flags the operator requested (no sportybet, no booking codes, no web/whatsapp/email).
"""
from __future__ import annotations
import sys
from pathlib import Path

# Ensure the project root is importable
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

import run_daily as daily


def main() -> int:
    result = daily.run(
        season="2526",
        send=True,            # verify-only still marks the run in the brain
        min_mes=0.0,
        whatsapp=False,
        email=False,
        web=False,
        prefetch_crests=False,
        refresh_sportybet=False,
        booking_codes=False,
        verify_only=True,
    )
    print(result.full)
    return 0


if __name__ == "__main__":
    sys.exit(main())
