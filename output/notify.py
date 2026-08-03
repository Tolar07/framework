"""
Board delivery.

Telegram is the default channel (blueprint 2.5): free, instant on mobile, and
it handles the long plain-text board without mangling it.

Two things are enforced here rather than left to the caller, because the
caller is a scheduled job that nobody reads before it sends:

  1. The honest-edge caveat is appended UNCONDITIONALLY. It cannot be
     suppressed by a flag, because "just this once" is exactly how a standing
     caveat erodes.
  2. Every message is stamped with the phase. At 07:00 on a phone, a board of
     model probabilities and trigger prices could be misread as a slate of
     live picks; the stamp makes that misreading impossible.
"""
from __future__ import annotations

import os
import sys
import textwrap
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import requests
except ImportError:
    requests = None

from config import PHASE, PHASE_LABEL, CAPITAL_ENABLED

TELEGRAM_API = "https://api.telegram.org/bot{token}"

# Telegram hard-limits a message to 4096 characters. The board is longer than
# that, so it is split on blank lines rather than mid-fixture.
TELEGRAM_MAX = 3900

HONEST_CAVEAT = (
    "Honest edge status: an excellent informed process, NOT a demonstrated "
    "profitable edge. Capital authority: THE ARCHITECT — nothing here is live "
    "until you deploy it."
)


def _stamp(body: str) -> str:
    """Phase banner + the caveat that never comes off."""
    banner = f"OLP XDV — {PHASE_LABEL}"
    if not CAPITAL_ENABLED:
        banner += "\nPAPER ONLY. No stake is placed by this system."
    return f"{banner}\n{'=' * 34}\n\n{body}\n\n{'=' * 34}\n{HONEST_CAVEAT}"


def _chunk(text: str, limit: int = TELEGRAM_MAX) -> list[str]:
    """Split on paragraph boundaries so a fixture block never straddles two
    messages — a half-rendered pick is worse than a second notification."""
    if len(text) <= limit:
        return [text]
    chunks, current = [], ""
    for para in text.split("\n\n"):
        if len(current) + len(para) + 2 > limit and current:
            chunks.append(current.rstrip())
            current = ""
        if len(para) > limit:
            for line in textwrap.wrap(para, limit):
                chunks.append(line)
            continue
        current += para + "\n\n"
    if current.strip():
        chunks.append(current.rstrip())
    return chunks


def send_telegram(body: str, token: Optional[str] = None,
                   chat_id: Optional[str] = None) -> tuple[bool, list[str]]:
    """Returns (ok, notes). Never raises — a delivery failure must not lose the
    board, which is written to disk regardless by the caller."""
    notes: list[str] = []
    token = token or os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID")
    if requests is None:
        return False, ["requests not installed — cannot send"]
    if not token or not chat_id:
        return False, ["TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set — "
                       "board written to disk but not delivered"]

    ok = True
    for i, part in enumerate(_chunk(_stamp(body)), 1):
        try:
            r = requests.post(f"{TELEGRAM_API.format(token=token)}/sendMessage",
                               json={"chat_id": chat_id, "text": part,
                                     "disable_web_page_preview": True},
                               timeout=30)
            payload = r.json()
            if not payload.get("ok"):
                ok = False
                notes.append(f"part {i} failed: {payload.get('description')}")
        except Exception as e:
            ok = False
            notes.append(f"part {i} failed: {e}")
    if ok:
        notes.append("delivered to Telegram")
    return ok, notes


def deliver(body: str, save_to: Optional[Path] = None) -> list[str]:
    """Write the board to disk, then try to send it. Disk first, deliberately:
    a failed send must never mean a lost board."""
    notes: list[str] = []
    if save_to:
        save_to.parent.mkdir(parents=True, exist_ok=True)
        save_to.write_text(_stamp(body), encoding="utf-8")
        notes.append(f"board saved to {save_to}")
    ok, send_notes = send_telegram(body)
    return notes + send_notes
