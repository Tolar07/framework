"""
Board delivery.

Telegram is the default channel (blueprint 2.5): free, instant on mobile, and
it handles the long plain-text board without mangling it.

Two things are enforced here rather than left to the caller, because the
caller is a scheduled job that nobody reads before it sends:

  1. The honest-edge caveat is appended UNCONDITIONALLY. It cannot be
     suppressed by a flag, because "just this once" is exactly how a standing
     caveat erodes.
  2. Every message carries the Architect's lean banner (2026-08-11 "use this
     always"): `##########OLP XDV#########` + the honest-edge/capital line.
     A board of probabilities and trigger prices could be misread as a slate
     of live picks; the capital line makes that misreading impossible.
"""
from __future__ import annotations

import os
import sys
import textwrap
import time
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import requests
except ImportError:
    requests = None

# Importing config is what loads .env on import (its module-level load_dotenv).
# send_telegram reads TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID from the env, so a
# caller that imports notify without first importing config would otherwise
# silently never deliver. Kept as a side-effect import — no names used.
import config  # noqa: F401


TELEGRAM_API = "https://api.telegram.org/bot{token}"

# Telegram hard-limits a message to 4096 characters. The board is longer than
# that, so it is split on blank lines rather than mid-fixture.
TELEGRAM_MAX = 3900

HONEST_CAVEAT = (
    "Honest edge: not a demonstrated edge · Capital: Architect only."
)


def _stamp(body: str) -> str:
    """Architect banner (2026-08-11) + the caveat that never comes off."""
    banner = "##########OLP XDV#########"
    return f"{banner}\n{'=' * 34}\n\n{body}\n\n{'=' * 34}\n{HONEST_CAVEAT}"


FENCE = "```"


def _balance_fences(chunk: str) -> str:
    """Close a code fence left open at the end of a chunk.

    Splitting mid-fence leaves one message with an unclosed ``` and the next
    with an orphan closer. Both then render as broken plain text and the whole
    point of the table — aligned columns — is lost."""
    return chunk + f"\n{FENCE}" if chunk.count(FENCE) % 2 else chunk


def _chunk(text: str, limit: int = TELEGRAM_MAX) -> list[str]:
    """Split on LINE boundaries, never mid-row, keeping fences balanced.

    Line-level rather than paragraph-level because one league's table can
    exceed the limit on its own: splitting between two rows stays readable,
    splitting through one does not."""
    if len(text) <= limit:
        return [text]
    chunks, current, in_fence = [], "", False
    for line in text.split("\n"):
        # Leave room for a closing fence when inside one.
        room = limit - (len(FENCE) + 1 if in_fence else 0)
        if len(current) + len(line) + 1 > room and current:
            chunks.append(_balance_fences(current.rstrip()))
            current = f"{FENCE}\n" if in_fence else ""
        current += line + "\n"
        if line.strip() == FENCE:
            in_fence = not in_fence
    if current.strip():
        chunks.append(_balance_fences(current.rstrip()))
    return chunks


def send_telegram(body: str, token: Optional[str] = None,
                   chat_id: Optional[str] = None,
                   reply_markup: Optional[dict] = None) -> tuple[bool, list[str]]:
    """Returns (ok, notes). Never raises — a delivery failure must not lose the
    board, which is written to disk regardless by the caller.

    `reply_markup` is a Telegram reply_markup dict (e.g. an inline keyboard).
    It is attached to the LAST chunk only, so a multi-part board carries the
    buttons once, under the final part."""
    notes: list[str] = []
    token = token or os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID")
    if requests is None:
        return False, ["requests not installed — cannot send"]
    if not token or not chat_id:
        return False, ["TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set — "
                       "board written to disk but not delivered"]

    parts = _chunk(_stamp(body))
    ok = True
    for i, part in enumerate(parts, 1):
        # Retry transient network faults. A real 07:00 run lost parts 6-8 to a
        # connection reset followed by DNS failure while parts 1-5 went
        # through, leaving a TRUNCATED board on the phone. A partial board is
        # worse than none, because it looks complete.
        last_err = None
        parse_mode = "Markdown"
        for attempt in range(3):
            try:
                payload = {"chat_id": chat_id, "text": part,
                           "disable_web_page_preview": True}
                if parse_mode:
                    payload["parse_mode"] = parse_mode
                if reply_markup and i == len(parts):
                    payload["reply_markup"] = reply_markup
                r = requests.post(f"{TELEGRAM_API.format(token=token)}/sendMessage",
                                   json=payload, timeout=30)
                data = r.json()
                if data.get("ok"):
                    last_err = None
                    break
                last_err = data.get("description")
                # A markdown PARSE error (e.g. an unbalanced `*`, `_` or `#`
                # left at a chunk boundary) is NOT transient — resending the
                # same markup will fail forever and abort the whole run. Fall
                # back to plain text for THIS part so the board still reaches
                # the phone complete (honest-edge: a complete plain board beats
                # a truncated/invalid-markup one). Only retry-as-plain once.
                if (parse_mode == "Markdown" and last_err
                        and "parse" in (last_err or "").lower()
                        and attempt == 0):
                    parse_mode = None
                    last_err = None
                    continue
            except Exception as e:
                last_err = str(e)[:120]
            time.sleep(2 * (attempt + 1))
        if last_err:
            ok = False
            notes.append(f"part {i} of {len(parts)} FAILED after 3 attempts: {last_err}")
    notes.append(f"delivered {len(parts)} part(s) to Telegram" if ok
                 else f"DELIVERY INCOMPLETE — the board on the phone is TRUNCATED")
    return ok, notes


def send_alert(body: str, **kw) -> tuple[bool, list[str]]:
    """Best-effort ALERT send, gated OFF by default.

    Architect directive 2026-08-11: the bot pushes ONLY the daily run and
    command responses. Monitor alerts (health, watchdog, dead-man's-switch)
    keep logging locally and returning their status, but do NOT message
    Telegram unless TELEGRAM_ALERTS_ENABLED=1 is set in .env. When it is, the
    standing honest/capital stamp still applies (send_telegram wraps _stamp)."""
    if os.environ.get("TELEGRAM_ALERTS_ENABLED", "") not in ("1", "true", "True"):
        return False, ["TELEGRAM_ALERTS_ENABLED not set — alert logged locally, not sent"]
    return send_telegram(body, **kw)


def deliver(body: str, save_to: Optional[Path] = None) -> tuple[bool, list[str]]:
    """Write the board to disk, then send it. Returns (delivered_ok, notes).

    Disk first, deliberately: a failed send must never lose the board. The
    boolean matters — the caller previously discarded it and logged "run
    completed OK" even when three message parts had failed, which is the same
    silent-success failure the scheduler itself suffered from."""
    notes: list[str] = []
    if save_to:
        save_to.parent.mkdir(parents=True, exist_ok=True)
        save_to.write_text(_stamp(body), encoding="utf-8")
        notes.append(f"board saved to {save_to}")
    ok, send_notes = send_telegram(body)
    return ok, notes + send_notes
