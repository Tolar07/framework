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
import re
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


FENCE = "```"


def _balance_fences(chunk: str) -> str:
    """Close a code fence left open at the end of a chunk.

    Splitting mid-fence leaves one message with an unclosed ``` and the next
    with an orphan closer. Both then render as broken plain text and the whole
    point of the table — aligned columns — is lost."""
    return chunk + f"\n{FENCE}" if chunk.count(FENCE) % 2 else chunk


def _chunk(text: str, limit: int = TELEGRAM_MAX) -> list[str]:
    """Split on COMPETITION / section boundaries where possible, never mid-row,
    keeping fences balanced (Telegram Output Spec §5, standing order 30).

    The board separates competitions (and sections) with a blank line, so a
    message that must be split ends at the last blank line once at least half
    the message is used. One competition too long for a message on its own is
    split between two rows, and the next message opens with "(cont.)"."""
    if len(text) <= limit and "\nALL CODES\n" not in text:
        return [text]
    chunks: list[str] = []
    cur: list[tuple[str, bool]] = []      # (line, inside a fence before it)
    in_fence = False

    def size(lines: list[tuple[str, bool]]) -> int:
        return sum(len(t) + 1 for t, _ in lines)

    def flush(lines: list[tuple[str, bool]]) -> None:
        body = "\n".join(t for t, _ in lines).rstrip()
        if body.strip():
            chunks.append(_balance_fences(body))

    room = limit - (len(FENCE) + 1)       # always leave room to close a fence
    for line in text.split("\n"):
        # The ALL CODES summary always starts its own (final) message.
        if line.strip() == "ALL CODES" and not in_fence and any(t.strip() for t, _ in cur):
            flush(cur)
            cur = []
        if cur and size(cur) + len(line) + 1 > room:
            half = [i for i in range(1, len(cur)) if size(cur[:i]) >= limit // 2]
            blanks = [i for i in half if not cur[i][0].strip()]
            # else: before a line that starts a block (an acca and its legs
            # "   • ..." stay together), outside any table
            starts = [i for i in half if cur[i][0][:1].strip() and not cur[i][1]]
            cuts = blanks or starts
            if cuts:                      # end at the last competition/block boundary
                head, tail = cur[:cuts[-1]], cur[cuts[-1]:]
                while tail and not tail[0][0].strip():
                    tail = tail[1:]
                reopen = tail[0][1] if tail else in_fence
                cont = []
            else:                         # one competition overflows: split rows
                head, tail, reopen = cur, [], in_fence
                cont = [("(cont.)", reopen)] if reopen else []
            flush(head)
            cur = ([(FENCE, False)] if reopen else []) + cont + tail
            if size(cur) + len(line) + 1 > room and len(cur) > len(cont) + int(reopen):
                flush(cur)
                cur = ([(FENCE, False)] if in_fence else []) + \
                      ([("(cont.)", in_fence)] if in_fence else [])
        cur.append((line, in_fence))
        if line.strip() == FENCE:
            in_fence = not in_fence
    flush(cur)
    return chunks


# HR59 send gate (Telegram Output Spec §1, standing order 30): a board reaches
# Telegram only with a valid Run ID tracing it to the run that built it.
RUN_ID_RE = re.compile(r"Run ID: OLPXDV-\d{8}-\d{4}-[0-9a-f]{6}\b")


def board_gate(text: str) -> Optional[str]:
    """Why a board must NOT be sent, or None when it may be."""
    if not RUN_ID_RE.search(text or ""):
        return "board has no valid Run ID (HR59) — not sent"
    return None


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


def subscriber_chats() -> list[str]:
    """Standing order 33: the chats in the TELEGRAM_SUBSCRIBER_CHAT_IDS secret
    (comma-separated; a secret so nobody's chat id sits in the public repo),
    without the Architect's own chat(s), so the Architect is never sent twice."""
    own = {os.environ.get("TELEGRAM_CHAT_ID", "").strip(),
           os.environ.get("TELEGRAM_OWNER_CHAT_ID", "").strip()}
    out: list[str] = []
    for cid in os.environ.get("TELEGRAM_SUBSCRIBER_CHAT_IDS", "").split(","):
        cid = cid.strip()
        if cid and cid not in own and cid not in out:
            out.append(cid)
    return out


def send_architect(body: str) -> tuple[bool, list[str]]:
    """The Architect's own chat only (order 33): everything that is not the
    board — heartbeat, pre-kickoff alerts, run alerts, the supervisor status,
    the weekly review. Subscribers never see it."""
    return send_telegram(body)


def send_subscribers(body: str) -> tuple[bool, list[str]]:
    """Every subscriber chat only (order 33, Architect 2026-10-09: subscribers
    get the booking codes and nothing else). Returns (all delivered, notes);
    a subscriber that fails is a note, never a failed run. Chats named by
    their last four digits only — run logs of this public repo are public."""
    subs = subscriber_chats()
    sent, notes = 0, []
    for cid in subs:
        s_ok, s_notes = send_telegram(body, chat_id=cid)
        sent += s_ok
        if not s_ok:
            notes.append(f"subscriber chat …{cid[-4:]}: NOT delivered ({s_notes[-1]})")
    if subs:
        notes.append(f"codes delivered to {sent}/{len(subs)} subscriber chat(s)")
    return sent == len(subs), notes


def send_everyone(body: str) -> tuple[bool, list[str]]:
    """The Architect's chat, then every subscriber chat (order 33). Only the
    board goes this way (via deliver); everything else is send_architect.

    Returns (Architect's chat delivered, notes). A subscriber that fails is a
    note and never fails the caller. Notes name a subscriber by the last four
    digits only — run logs of this public repo are public."""
    ok, notes = send_telegram(body)
    subs = subscriber_chats()
    sent = 0
    for cid in subs:
        s_ok, s_notes = send_telegram(body, chat_id=cid)
        sent += s_ok
        if not s_ok:
            notes.append(f"subscriber chat …{cid[-4:]}: NOT delivered ({s_notes[-1]})")
    if subs:
        notes.append(f"delivered to {sent}/{len(subs)} subscriber chat(s)")
    return ok, notes


def deliver(body: str, save_to: Optional[Path] = None) -> tuple[bool, list[str]]:
    """Write the board to disk, then send it to the Architect and every
    subscriber (order 33: subscribers get the board and nothing else).
    Returns (delivered_ok, notes).

    Disk first, deliberately: a failed send must never lose the board. The
    boolean matters — the caller previously discarded it and logged "run
    completed OK" even when three message parts had failed, which is the same
    silent-success failure the scheduler itself suffered from."""
    notes: list[str] = []
    if save_to:
        save_to.parent.mkdir(parents=True, exist_ok=True)
        save_to.write_text(_stamp(body), encoding="utf-8")
        notes.append(f"board saved to {save_to}")
    ok, send_notes = send_everyone(body)
    return ok, notes + send_notes
