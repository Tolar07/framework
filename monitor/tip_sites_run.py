"""
TIP SITES RUN — read the prediction sites' tips for today's upcoming games, grade the finished ones
and rewrite data/tip_sites/TIP_SITES_STUDY.md (engine/tip_sites.py). Paper only.

    python monitor/tip_sites_run.py [--dir data/tip_sites] [--no-collect]
"""
from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "monitor"))

from engine import tip_board as tb  # noqa: E402
from engine import tip_sites as ts  # noqa: E402
from engine import tipsters as tp  # noqa: E402


def _open_issue(title: str, body: str) -> str | None:
    """A framework `self-improvement` issue (built by the PC fixer as shadow work). Only inside Actions."""
    import os
    import subprocess
    if os.environ.get("GITHUB_ACTIONS") != "true":
        return None
    r = subprocess.run(["gh", "issue", "create", "-R", os.environ.get("GITHUB_REPOSITORY", "Tolar07/framework"),
                        "--label", "self-improvement", "-t", title, "-b", body], capture_output=True, text=True)
    return r.stdout.strip() or None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=str(ts.FOLDER))
    ap.add_argument("--no-collect", action="store_true")
    a = ap.parse_args(argv)
    folder, now = Path(a.dir), datetime.now(UTC)
    notes = [] if a.no_collect else ts.collect(folder, now)
    import tipster_run
    notes += tipster_run.run(folder, now)
    study = ts.write_study(folder, tp.load_graded(folder), now)
    if folder == ts.FOLDER:     # the tip board, its results and the eligibility test (engine/tip_board.py)
        notes += tb.run(now, open_issue=_open_issue)
    for n in notes:
        print(" ", n)
    print(f"  study: {study}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
