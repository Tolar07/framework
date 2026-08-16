"""Send the existing board to Telegram.

Uses the pipeline-produced compact file (output/boards/telegram_YYYY-MM-DD.txt)
which is already sized for the channel. Falls back to the full board only if the
compact file is missing. Hard character-level chunking guarantees no message ever
exceeds Telegram's 4096-char limit (we cap at 3900 for safety). No parse_mode is
used so special characters (* _ `) in the board never break the send.
"""
import os
import sys
import requests
from pathlib import Path
from datetime import date

TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '8695416676:AAHqF-YEv2tqzFu5M8dxjk5RCzV-eADIBeQ')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '8074295061')
TELEGRAM_API = f"https://api.telegram.org/bot{TOKEN}"
TELEGRAM_MAX = 3900

def pick_source(target_date: str) -> Path:
    boards = Path('output/boards')
    compact = boards / f"telegram_{target_date}.txt"
    if compact.exists():
        return compact
    full = boards / f"board_{target_date}.txt"
    if full.exists():
        return full
    raise SystemExit(f"No board file for {target_date} in {boards}")

def chunk_text(text: str, limit: int = TELEGRAM_MAX) -> list[str]:
    """Hard character-level chunking. Never splits a line across messages if the
    line itself fits; if a single line exceeds the limit it is force-split."""
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    buf = ""
    for line in text.split("\n"):
        # Line alone exceeds the cap — hard-split it.
        if len(line) > limit:
            if buf:
                chunks.append(buf)
                buf = ""
            while line:
                chunks.append(line[:limit])
                line = line[limit:]
            continue
        # Adding this line would exceed the cap — flush the buffer.
        if buf and len(buf) + 1 + len(line) > limit:
            chunks.append(buf)
            buf = line
        else:
            buf = f"{buf}\n{line}" if buf else line
    if buf:
        chunks.append(buf)
    return chunks

def main() -> int:
    target_date = sys.argv[1] if len(sys.argv) > 1 else date.today().isoformat()
    src = pick_source(target_date)
    body = src.read_text(encoding='utf-8')
    chunks = chunk_text(body)
    print(f"Sending {src.name} ({len(body)} chars) as {len(chunks)} chunk(s)...")

    ok = 0
    for i, chunk in enumerate(chunks, 1):
        r = requests.post(
            f"{TELEGRAM_API}/sendMessage",
            json={
                "chat_id": CHAT_ID,
                "text": chunk,
                "disable_web_page_preview": True,
            },
            timeout=30,
        )
        data = r.json()
        if data.get("ok"):
            ok += 1
            print(f"  Chunk {i}/{len(chunks)}: OK ({len(chunk)} chars)")
        else:
            print(f"  Chunk {i}/{len(chunks)}: FAILED - {data.get('description')}")
    print(f"Done. {ok}/{len(chunks)} chunks delivered.")
    return 0 if ok == len(chunks) else 1

if __name__ == '__main__':
    raise SystemExit(main())
