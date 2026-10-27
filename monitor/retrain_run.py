"""Nightly retrain (retrain.yml, Architect 2026-10-20 "auto"): engine/retrain.py
refits the model's calibration on every graded rated fixture and puts live
only what beats the current one on games it was not fitted on.

  python monitor/retrain_run.py --message-file F   refit, save, write the Telegram line to F
  python monitor/retrain_run.py --send F            send F to the Architect only; exit 1 if not delivered
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine import retrain  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--message-file", type=Path)
    ap.add_argument("--send", type=Path)
    args = ap.parse_args(argv)
    if args.send:
        from output.notify import send_architect
        ok, notes = send_architect(args.send.read_text(encoding="utf-8").strip())
        print("\n".join(notes))
        if not ok:
            print("::error::retrain line NOT delivered to the Architect")
        return 0 if ok else 1
    summary = retrain.run()
    for r in summary["results"]:
        print(r)
    line = retrain.message(summary)
    print(line)
    if args.message_file:
        args.message_file.write_text(line + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
