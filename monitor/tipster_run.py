"""
TIPSTER RUN — decode new SportyBet slip codes, grade the slips whose games
have finished, rewrite the study (engine/tipsters.py, backtest/tipster_study.py).

    python monitor/tipster_run.py --dir C:\\Users\\Motunrayo\\tipster_slips

Everything it writes (decoded_*.jsonl, graded_*.jsonl, TIPSTER_STUDY.md) goes
into --dir and nowhere else: the slips stay private until the Architect has
decided on poster names. The universe sweep runs the same steps on the repo's
data/tipsters/ only once that folder exists.
"""
from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backtest"))

from engine import tipsters as tp  # noqa: E402
from engine import universe as uv  # noqa: E402


def run(folder: Path, now: datetime, out: Path | None = None) -> list[str]:
    from data import flashscore_results as fr
    notes = tp.decode_pending(folder, now)
    index = {}
    for sport, fs_sport in (("football", 1), ("basketball", 3)):
        try:
            index[sport] = uv.ResultIndex(fr.results_since(7, sport=fs_sport))
        except Exception as e:  # noqa: BLE001 — grading waits for the next run
            notes.append(f"{sport}: Flashscore unavailable ({str(e)[:60]})")
    notes += tp.grade_due(folder, index, now)
    import tipster_study
    tipster_study.write(folder, out or folder / "TIPSTER_STUDY.md")
    return notes


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    a = ap.parse_args(argv)
    for n in run(Path(a.dir), datetime.now(UTC)):
        print(" ", n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
