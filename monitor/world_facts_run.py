"""
Football world facts: every finished football match Flashscore lists, with its half-time score, and for a
polite number per run the team stats by half and every goal's minute (engine/world_facts.py). RECORD ONLY:
writes data/world_facts/, data/world_facts_detail/ and output/world_facts/latest.json and nothing else; no
pick, stake or board reads it.

    python monitor/world_facts_run.py        (world_facts.yml, started by the Oracle VM clock four times a day)
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import world_facts  # noqa: E402


def main() -> int:
    print(world_facts.run())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
