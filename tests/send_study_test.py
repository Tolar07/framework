"""
scripts/send_study.py sends only a saved study .txt under data/study/, and only
to the Architect's own chat. Offline: Telegram is stubbed.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]

import send_study as ss  # noqa: E402

from output import notify  # noqa: E402

assert ss.main(["../etc/passwd"]) == 2 and ss.main(["MAP.md"]) == 2, "only data/study/*.txt"
assert ss.main(["data/study/2026-10-13/GRADES.md"]) == 2, "a .md file is refused"
sent = []
real = notify.send_telegram
notify.send_telegram = lambda text, chat_id=None: (sent.append(chat_id) or True, ["ok"])
os.environ.update({"TELEGRAM_BOT_TOKEN": "t", "TELEGRAM_CHAT_ID": "main", "TELEGRAM_OWNER_CHAT_ID": "owner"})
try:
    assert ss.main(["data/study/2026-10-14/telegram.txt"]) == 0 and sent == ["owner"], "the Architect's chat only"
finally:
    notify.send_telegram = real
print("ALL SEND STUDY TESTS PASSED")
