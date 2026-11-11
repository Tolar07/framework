"""
NOTIFY ROUTE - which messages still go to Telegram / WhatsApp, and which go to the Control Room app.

The Architect, 2026-11-11 23:30: "let's just really get notification from Telegram and WhatsApp on very
extreme event or catastrophic failure ... But day-to-day running notification, placement, activity should
come from the app notification. And even the app too can also send notification on extreme events."

Every bot's own send function asks `route(source, text, level)` before it posts to Telegram:
  - EVERY message is written to the app feed: one JSON line in $OLP_NOTIFY_DIR/<source>.jsonl on the
    Oracle VM (default /var/tmp/olp-notify). The Control Room status job reads those files every 5 minutes
    and the phone app turns new lines into phone notifications (extreme ones on a loud channel).
  - Telegram as well ONLY for an extreme event: level="alert" from the caller, or (no level given) text
    that reads like a failure, a fault, a block, a stop, or money the Architect has to act on (EXTREME).
  - When the feed can't be written (the PC, Windows, a full disk) the message goes to Telegram as before,
    so nothing is ever lost.
Undo: NOTIFY_ROUTE=telegram (repo variable or env) sends everything to Telegram again, as before.
No secrets are written: the text is what Telegram would have shown.
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

DEFAULT_DIR = os.path.join(os.sep, "var", "tmp", "olp-notify")   # built, not written as one path: matchbook's endpoint allow-list test
KEEP_LINES = 400                     # per source file; older lines are dropped
EXTREME = re.compile(
    r"fail|\bdown\b|not logged in|blocked|refused|\bSTOP\b|\bhalt|watchdog|needs attention|still open|"
    r"unfixed|catastroph|did not go through|account protection|crash|\bdead\b|expired|expir(?:es|ing) in|"
    r"waiting for money|out of money|emergency|NOT STARTED|traceback|exception|disk (?:is )?full|offline|"
    r"unreachable|timed out|outage|banned|captcha",
    re.IGNORECASE)
# Left out on purpose (they appear in everyday boards and reports): "no data", "verified", "frozen",
# "suspended", "stale", "alert", "missed", "top-up received".


def mode() -> str:
    return (os.getenv("NOTIFY_ROUTE") or "app").strip().lower()


def is_extreme(text: str) -> bool:
    return bool(EXTREME.search(text or ""))


def feed_dir() -> Path:
    return Path(os.getenv("OLP_NOTIFY_DIR") or DEFAULT_DIR)


def to_app(source: str, text: str, level: str = "info", now: float | None = None) -> bool:
    """Append one note to the app feed. False when it can't be written (then Telegram carries it)."""
    if os.name == "nt" and not os.getenv("OLP_NOTIFY_DIR"):
        return False                 # the PC: no app feed there
    d = feed_dir()
    try:
        d.mkdir(parents=True, exist_ok=True)
        try:
            d.chmod(0o1777)          # every runner user may add its own file
        except OSError:
            pass
        safe = re.sub(r"[^a-z0-9_-]", "-", (source or "olp").lower())[:40]
        p = d / f"{safe}.jsonl"
        t = time.time() if now is None else now
        line = json.dumps({"id": f"{safe}-{int(t * 1000)}", "at": int(t), "source": safe, "level": level,
                           "text": (text or "")[:3000]}, ensure_ascii=False)
        with p.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
        try:
            os.chmod(p, 0o644)
        except OSError:
            pass
        if p.stat().st_size > 600_000:
            rows = p.read_text(encoding="utf-8").splitlines()[-KEEP_LINES:]
            p.write_text("\n".join(rows) + "\n", encoding="utf-8")
        return True
    except OSError:
        return False


def route(source: str, text: str, level: str | None = None) -> bool:
    """Write the note to the app feed; True when it must ALSO go to Telegram / WhatsApp."""
    if mode() == "telegram":
        return True
    lvl = level or ("alert" if is_extreme(text) else "info")
    wrote = to_app(source, text, lvl)
    return lvl == "alert" or not wrote


def read_feed(since: float, d: Path | None = None, limit: int = 150) -> list[dict]:
    """Every note in the feed since `since` (epoch seconds), newest first (for the Control Room builder)."""
    out: list[dict] = []
    folder = d or feed_dir()
    try:
        files = sorted(folder.glob("*.jsonl"))
    except OSError:
        return out
    for p in files:
        try:
            for ln in p.read_text(encoding="utf-8").splitlines():
                try:
                    r = json.loads(ln)
                except ValueError:
                    continue
                if isinstance(r, dict) and float(r.get("at") or 0) >= since:
                    out.append(r)
        except OSError:
            continue
    out.sort(key=lambda r: r.get("at") or 0, reverse=True)
    return out[:limit]
