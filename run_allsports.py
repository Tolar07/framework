"""
THE BETFAIR BOARD runner: every sport except football (output/allsports_board.py; Architect 2026-11-06,
layout approved the same day). Sections: basketball (NBA + world + NCAA) first, then
ice hockey and every multi-sport board sport.

  python run_allsports.py                 build today's board (UK date) -> output/boards/allsports_<day>.txt
  python run_allsports.py --send          ... and send it to Telegram (split between sport sections)
  python run_allsports.py --day 2026-11-12 --sport tennis    one day / one sport, printed

Started by .github/workflows/multisport.yml mode=board (Oracle VM clock: morning picks, evening results).
Reads files only (HR59): the boards the loops froze and the Betfair bot's published ledger (.bots/).
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from output import allsports_board as AB  # noqa: E402


def send(parts: list[str]) -> str:
    tok, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not tok or not chat:
        return "telegram: no token/chat, not sent"
    import urllib.parse
    import urllib.request
    for p in parts:
        data = urllib.parse.urlencode({"chat_id": chat, "text": p}).encode()
        urllib.request.urlopen(f"https://api.telegram.org/bot{tok}/sendMessage", data=data, timeout=20)  # noqa: S310
    return f"telegram: sent {len(parts)} message(s)"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", default=None)
    ap.add_argument("--sport", default=None)
    ap.add_argument("--send", action="store_true")
    a = ap.parse_args()
    now = datetime.now(UTC)
    day = a.day or now.astimezone(AB.UK).date().isoformat()
    run_id = f"OLPXDV-BF-{now:%Y%m%d-%H%M}-{os.environ.get('GITHUB_RUN_ID', 'local')}"
    only = AB.sport_alias(a.sport) if a.sport else None
    text = AB.render(day, now, run_id, only=only)
    if only:
        print(text)
        return
    p = AB.path_for(day)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    parts = AB.split(text)
    print(text)
    print(f"\nboard: {p.relative_to(ROOT)} ({len(text)} chars, {len(parts)} message(s))")
    if a.send:
        print(send(parts))


if __name__ == "__main__":
    main()
