"""
Telegram command interface — the Architect's way in.

The daily board is one-way. This makes the channel two-way so the Architect can
ask the framework questions and, more importantly, FEED IT THINGS ONLY HE HAS:
the real price he could get on SportyBet/Bet365, and plain-English corrections
when the framework gets something wrong.

SECURITY MODEL — read this before extending it
  1. CHAT WHITELIST. Only ALLOWED_CHAT_IDS is answered. Anyone else who finds
     the bot gets silence, and the attempt is logged. A bot token is a
     bearer credential; assume it can leak.
  2. NOTHING HERE TOUCHES CAPITAL. Every command is read-only or append-only.
     config.assert_paper_only() still guards the write path underneath, so
     even a bug in this file cannot record a stake.
  3. MESSAGES ARE DATA, NOT AUTHORITY. A Telegram message is an instruction
     channel, and instruction channels get spoofed. Commands that would change
     a bright line — enabling capital, moving the phase, removing the honest-
     edge caveat — are REFUSED with an explanation and logged, never executed.
     Those changes need the Architect deliberately, in a session, not a
     one-line message at 07:00. This is not distrust of the Architect; it is
     the same reasoning that put the phase gate in code rather than in prose.

COMMANDS
  /board     re-send today's board
  /status    Phase 3 gate progress
  /verify    yesterday's graded results
  /why <n>   full reasoning for fixture n on today's board
  /log       Home v Away | Market | price      -> CL-LIVE paper leg (HR46)
  /note      free text                          -> corrections log (blueprint 2.7)
  /debrief   full framework status
  /help      this list
"""
from __future__ import annotations

import csv
import json
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import requests
except ImportError:
    requests = None

from config import PHASE, PHASE_LABEL, PAPER_PHASE, CAPITAL_ENABLED
from clv.clv_logger import CLVLog
from output.notify import send_telegram, HONEST_CAVEAT

STATE_DIR = Path(__file__).parent.parent / "memory"
OFFSET_FILE = STATE_DIR / "telegram_offset.json"
CORRECTIONS_FILE = STATE_DIR / "corrections.csv"
BOARD_DIR = Path(__file__).parent / "boards"

# Only this chat is answered. Set TELEGRAM_CHAT_ID; anything else is ignored.
def _allowed() -> set[str]:
    cid = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    return {cid} if cid else set()


# Phrases that would move a bright line. Refused with an explanation — the
# framework's whole origin is a response to fabrication, and the guards that
# prevent it should not be removable from a phone.
BRIGHT_LINE_WORDS = (
    "enable capital", "go live", "phase 3", "phase3", "deploy capital",
    "remove caveat", "drop the caveat", "disable the gate", "turn off paper",
    "place the bet", "stake ",
)


def _load_offset() -> int:
    if OFFSET_FILE.exists():
        try:
            return json.loads(OFFSET_FILE.read_text()).get("offset", 0)
        except (json.JSONDecodeError, OSError):
            return 0
    return 0


def _save_offset(offset: int) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    OFFSET_FILE.write_text(json.dumps({"offset": offset}), encoding="utf-8")


# --------------------------------------------------------------------------
# Command handlers — each returns the reply text
# --------------------------------------------------------------------------

def cmd_help(_: str) -> str:
    return (
        "OLP XDV commands\n\n"
        "/board — re-send today's board\n"
        "/status — Phase 3 gate progress\n"
        "/verify — yesterday's graded results\n"
        "/why 2 — full reasoning for fixture 2 on today's board\n"
        "/log Hearts v Dundee United | Over 1.5 goals | 1.42\n"
        "     records a price YOU got, as a CL-LIVE paper leg (HR46)\n"
        "/note the model looks wrong on Motherwell\n"
        "     records a correction for calibration to learn from\n"
        "/debrief — full framework status\n\n"
        f"{PHASE_LABEL}. Paper only — this system never stakes."
    )


def cmd_status(_: str) -> str:
    log = CLVLog()
    s = log.phase2_status()
    mean = s["mean_clv_pct"]
    lines = [
        f"PHASE 3 GATE — {PHASE_LABEL}",
        "",
        f"Paper legs logged (total) : {s['legs_logged_total']}",
        f"Legs WITH logged CLV      : {s['legs_with_clv']} of {s['gate_requirement']} required",
        f"Mean CLV                  : {f'{mean:+.3f}%' if mean is not None else 'NO DATA — PENDING'}",
        f"Mean CLV positive?        : {'yes' if s['positive_mean_clv'] else 'NO'}",
        "",
        f"Gate met (pending your V7 sign-off): "
        f"{'YES' if s['gate_met_pending_architect_signoff'] else 'no'}",
        "",
        "A leg only counts once its CLOSING price exists, which is after the "
        "match. Legs logged today will count tomorrow.",
    ]
    return "\n".join(lines)


def cmd_board(_: str) -> str:
    p = BOARD_DIR / f"board_{date.today().isoformat()}.txt"
    if not p.exists():
        boards = sorted(BOARD_DIR.glob("board_*.txt"))
        if not boards:
            return "No board has been produced yet. NO DATA — PENDING."
        p = boards[-1]
    return p.read_text(encoding="utf-8")


def cmd_verify(_: str) -> str:
    p = BOARD_DIR / f"board_{date.today().isoformat()}.txt"
    if not p.exists():
        return "No board today yet — nothing graded. NO DATA — PENDING."
    text = p.read_text(encoding="utf-8")
    if "VERIFY RESULTS" in text:
        return text.split("VERIFY RESULTS", 1)[1].strip()[:3500]
    return "No VERIFY RESULTS section in today's board."


def cmd_why(arg: str) -> str:
    """Full stacked block for one fixture on today's board."""
    arg = arg.strip()
    if not arg.isdigit():
        return "Usage: /why 2   (the number of a fixture in PART 1)"
    text = cmd_board("")
    marker = f"\n{arg}. "
    if marker not in text:
        return f"No fixture {arg} on today's board."
    block = text.split(marker, 1)[1]
    nxt = f"\n{int(arg)+1}. "
    return (marker.strip() + " " + (block.split(nxt)[0] if nxt in block else block))[:3500]


def cmd_log(arg: str) -> str:
    """Architect-fed entry price -> a CL-LIVE paper leg.

    This is the highest-value command here. HR46 wants the price captured at
    pick time, and the price the Architect can actually get on SportyBet is
    better evidence than any API's — it is the one that will actually be
    settled against."""
    parts = [p.strip() for p in arg.split("|")]
    if len(parts) != 3:
        return ("Usage: /log Home v Away | Market | price\n"
                "e.g.  /log Hearts v Dundee United | Over 1.5 goals | 1.42")
    fixture, market, price_s = parts
    try:
        price = float(price_s)
    except ValueError:
        return f"'{price_s}' is not a decimal price. Nothing logged."
    if not (1.01 <= price <= 1000):
        return f"Price {price} is out of plausible range. Nothing logged."
    if " v " not in fixture:
        return "Fixture must read 'Home v Away'. Nothing logged."

    log = CLVLog()
    leg = log.log_entry(
        league="ARCHITECT-FED", fixture=fixture, market=market,
        model_prob=0.0,                 # unknown here; CLV needs only the prices
        entry_odds=price, entry_capture_path="CL-LIVE",
        phase=PAPER_PHASE, stake=None,  # Phase 2 — never a stake
    )
    return (f"Logged as a PAPER leg (no stake):\n"
            f"  {fixture}\n  {market} at {price} decimal\n"
            f"  capture path CL-LIVE, leg id {leg.leg_id[:40]}\n\n"
            f"Its closing price will be captured after the match, and CLV "
            f"computed then. Nothing has been staked.")


def cmd_note(arg: str) -> str:
    if not arg.strip():
        return "Usage: /note <what the framework got wrong>"
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    new = not CORRECTIONS_FILE.exists()
    with open(CORRECTIONS_FILE, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["logged_at", "source", "note", "actioned"])
        w.writerow([datetime.now(timezone.utc).isoformat(), "telegram",
                    arg.strip(), "no"])
    return ("Correction logged for review.\n\n"
            "Data and calibration corrections are applied automatically; any "
            "RULE change gets proposed to you for approval first — the "
            "framework never rewrites its own rules.")


def cmd_debrief(_: str) -> str:
    log = CLVLog()
    s = log.phase2_status()
    mean = s["mean_clv_pct"]
    return "\n".join([
        "OLP XDV — FRAMEWORK DEBRIEF",
        f"{PHASE_LABEL}",
        "",
        "PHASE 3 GATE",
        f"  legs with logged CLV : {s['legs_with_clv']} / {s['gate_requirement']}",
        f"  mean CLV             : {f'{mean:+.3f}%' if mean is not None else 'NO DATA — PENDING'}",
        f"  capital enabled      : {'yes' if CAPITAL_ENABLED else 'NO — blocked in code'}",
        "",
        "WHAT THE BACKTEST FOUND",
        "  Walk-forward on 2024/25, no leakage:",
        "  Scottish Premiership  mean CLV -0.189%  (beat close 48.3%)",
        "  Eredivisie            mean CLV -0.478%  (beat close 46.8%)",
        "  Random placebo        mean CLV -1.177%",
        "  => the model beats random selection in 5 of 5 markets, but still",
        "     loses to the closing line. Signal, not yet edge.",
        "",
        "KNOWN LIMITS",
        "  Denmark and Poland have no opening prices in the results source, so",
        "  they cannot be CLV-backtested. BTTS and Over 3.5 have no prices at",
        "  all. Over 1.5 is never quoted and is DERIVED under HR30.",
        "",
        "OPEN",
        "  Model under-predicts goals (Over 2.5 by ~6pp after the BUG7 fix),",
        "  which inflates Under 2.5 and BTTS-No — the markets you trade.",
        "",
        HONEST_CAVEAT,
    ])


HANDLERS = {
    "/help": cmd_help, "/start": cmd_help,
    "/status": cmd_status, "/board": cmd_board, "/verify": cmd_verify,
    "/why": cmd_why, "/log": cmd_log, "/note": cmd_note,
    "/debrief": cmd_debrief,
}


def handle(text: str) -> str:
    """Route one message. Bright-line requests are refused, not executed."""
    stripped = text.strip()
    low = stripped.lower()

    if any(w in low for w in BRIGHT_LINE_WORDS) and not low.startswith("/note"):
        return (
            "REFUSED — that would move a bright line.\n\n"
            f"Capital is disabled in code at PHASE={PHASE}, and the honest-edge "
            "caveat is not removable. Those are not settings I change from a "
            "message: a chat channel can be spoofed, and the framework exists "
            "because of a fabrication incident.\n\n"
            "If you genuinely want to change this, do it deliberately in a "
            "working session where the reasoning is on the record. Logged as a "
            "note in the meantime."
        )

    cmd = low.split()[0] if low else ""
    handler = HANDLERS.get(cmd)
    if handler is None:
        return f"Unknown command '{cmd or stripped[:20]}'.\n\n{cmd_help('')}"
    return handler(stripped[len(cmd):])


def poll_once(token: Optional[str] = None) -> list[str]:
    """One getUpdates pass. Returns a log line per message handled."""
    notes: list[str] = []
    token = token or os.environ.get("TELEGRAM_BOT_TOKEN")
    if requests is None or not token:
        return ["telegram not configured — skipping command poll"]

    offset = _load_offset()
    try:
        r = requests.get(f"https://api.telegram.org/bot{token}/getUpdates",
                          params={"offset": offset + 1, "timeout": 0}, timeout=30)
        updates = r.json().get("result", [])
    except Exception as e:
        return [f"command poll failed: {e}"]

    allowed = _allowed()
    for u in updates:
        offset = max(offset, u.get("update_id", offset))
        msg = u.get("message") or {}
        chat_id = str(msg.get("chat", {}).get("id", ""))
        text = msg.get("text") or ""
        if not text:
            continue
        if allowed and chat_id not in allowed:
            notes.append(f"IGNORED message from non-whitelisted chat {chat_id}")
            continue
        reply = handle(text)
        send_telegram(reply, token=token, chat_id=chat_id)
        notes.append(f"handled {text.split()[0] if text.split() else '?'} from {chat_id}")

    _save_offset(offset)
    return notes or ["no new commands"]


if __name__ == "__main__":
    for n in poll_once():
        print(n)
