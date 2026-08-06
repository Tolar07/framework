"""
Email delivery — the daily push's zero-approval copy channel.

Telegram is phone-critical; email is an instant, reliable second channel that
needs no template approval or webhook. SMTP via a Gmail app-password (the user
enables 2FA + generates an App Password once). The message carries the SAME
stamped text Telegram delivers (reuses notify._stamp), so every channel says
the same thing.

Same discipline as output/notify.py and output/whatsapp_deliver.py: never
raises, returns (ok, notes), retries transient faults, and refuses to send if
credentials are missing (unset/empty ⇒ silently off — the framework behaves as
today).
"""
from __future__ import annotations

import os
import smtplib
import time
from datetime import date
from email.message import EmailMessage
from pathlib import Path
from typing import Optional

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import PHASE_LABEL
from output import notify

_ENV_KEYS = ("EMAIL_USER", "EMAIL_APP_PASSWORD", "EMAIL_TO")


def send_email(body: str, user: Optional[str] = None,
               app_password: Optional[str] = None, to: Optional[str] = None,
               host: Optional[str] = None,
               port: Optional[int] = None) -> tuple[bool, list[str]]:
    """Send the stamped board text as one email. Returns (ok, notes). Never
    raises. Email has no practical length limit, so the whole text goes in a
    single message (no chunking — unlike Telegram/WhatsApp)."""
    notes: list[str] = []
    user = user or os.environ.get("EMAIL_USER")
    app_password = app_password or os.environ.get("EMAIL_APP_PASSWORD")
    to = to or os.environ.get("EMAIL_TO")
    host = host or os.environ.get("EMAIL_SMTP_HOST") or "smtp.gmail.com"
    port = port or int(os.environ.get("EMAIL_SMTP_PORT") or "587")

    missing = [k for k, v in zip(_ENV_KEYS, (user, app_password, to)) if not v]
    if missing:
        return False, [f"{', '.join(missing)} not set — email delivery skipped"]

    msg = EmailMessage()
    msg["Subject"] = f"OLP XDV — Daily Board {date.today().isoformat()} · {PHASE_LABEL}"
    msg["From"] = user
    msg["To"] = to
    msg.set_content(notify._stamp(body))  # UTF-8 content, same text as Telegram

    last_err = None
    for attempt in range(3):
        try:
            with smtplib.SMTP(host, port, timeout=30) as server:
                server.starttls()
                server.login(user, app_password)
                server.send_message(msg)
            last_err = None
            break
        except Exception as e:
            last_err = str(e)[:120]
        time.sleep(2 * (attempt + 1))
    if last_err:
        return False, [f"email FAILED after 3 attempts: {last_err}"]
    notes.append("delivered 1 part(s) to email")
    return True, notes


def deliver(body: str) -> tuple[bool, list[str]]:
    """Best-effort email copy of the push. No disk save — Telegram already
    wrote the board; email is a mirror. Returns (ok, notes)."""
    return send_email(body)
