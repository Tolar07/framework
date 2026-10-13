"""
Send one saved study file to the Architect's own chat (Architect 2026-10-13:
"send [it to] Telegram so I can follow up"). Study boards are not the live
board: they go to the Architect only, never to a subscriber chat.

    python scripts/send_study.py data/study/<date>/telegram.txt
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

STUDY = (ROOT / "data" / "study").resolve()


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: send_study.py data/study/<date>/<file>.txt")
        return 2
    path = (ROOT / argv[0]).resolve()
    if STUDY not in path.parents or path.suffix != ".txt" or not path.is_file():
        print(f"refused: {argv[0]} is not a .txt file under data/study/")
        return 2
    owner = (os.environ.get("TELEGRAM_OWNER_CHAT_ID", "").strip()
             or os.environ.get("TELEGRAM_CHAT_ID", "").strip())
    if not owner or not os.environ.get("TELEGRAM_BOT_TOKEN"):
        print("not sent: no Telegram settings here")
        return 1
    from output import notify
    ok, notes = notify.send_telegram(path.read_text(encoding="utf-8"), chat_id=owner)   # the Architect only
    print(f"{'sent' if ok else 'NOT sent'}: {path.relative_to(ROOT)} {notes}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
