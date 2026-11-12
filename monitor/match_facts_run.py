"""
Match facts for every sport's board games except football (basketball: NBA, world leagues, NCAA; ice hockey; tennis; the
other rollout sports): Flashscore's stats by period, each side's last
matches and the head-to-head (engine/match_facts.py). RECORD ONLY: writes output/match_facts/ and the archive
data/match_facts/ and nothing else; no pick, stake or board reads it.

    python monitor/match_facts_run.py        (match_facts.yml, started by the Oracle VM clock every 15 minutes)
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import match_facts  # noqa: E402


def main() -> int:
    print(match_facts.run())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
