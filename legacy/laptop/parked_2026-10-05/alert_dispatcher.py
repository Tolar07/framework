#!/usr/bin/env python3
"""
Multi-channel alert dispatcher — fans out to Telegram, email (SMTP), and webhook.
Deduplicates alerts by (title, tags) within a 1-hour window to prevent alert fatigue.

Usage:
    from monitor.alert_dispatcher import dispatch_alert
    dispatch_alert("critical", "Quota exhausted", "Odds API has 1 call left",
                   tags=["quota", "odds"])
"""

from __future__ import annotations

import json
import os
import smtplib
import time
from datetime import datetime, timezone
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

import requests

ROOT = Path(__file__).parent.parent
DEDUP_FILE = ROOT / "logs" / "alert_dedup.json"
DEDUP_WINDOW_SECONDS = 3600  # 1 hour


def _load_env() -> dict[str, str]:
    """Load .env into os.environ (mirrors config.load_dotenv behavior)."""
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
    return {
        "TELEGRAM_BOT_TOKEN": os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        "TELEGRAM_CHAT_ID": os.environ.get("TELEGRAM_CHAT_ID", ""),
        "ALERT_EMAIL_TO": os.environ.get("ALERT_EMAIL_TO", ""),
        "ALERT_SMTP_HOST": os.environ.get("ALERT_SMTP_HOST", ""),
        "ALERT_SMTP_PORT": os.environ.get("ALERT_SMTP_PORT", "587"),
        "ALERT_SMTP_USER": os.environ.get("ALERT_SMTP_USER", ""),
        "ALERT_SMTP_PASS": os.environ.get("ALERT_SMTP_PASS", ""),
        "ALERT_WEBHOOK_URL": os.environ.get("ALERT_WEBHOOK_URL", ""),
    }


def _load_dedup() -> dict:
    """Load deduplication state from disk."""
    if DEDUP_FILE.exists():
        try:
            return json.loads(DEDUP_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_dedup(state: dict) -> None:
    """Save deduplication state to disk."""
    DEDUP_FILE.parent.mkdir(parents=True, exist_ok=True)
    # Prune entries older than 2x the window to prevent unbounded growth
    now = time.time()
    pruned = {k: v for k, v in state.items() if now - v.get("ts", 0) < DEDUP_WINDOW_SECONDS * 2}
    DEDUP_FILE.write_text(json.dumps(pruned), encoding="utf-8")


def _should_alert(key: str) -> bool:
    """Check if alert should fire (not in dedup window)."""
    state = _load_dedup()
    now = time.time()
    if key in state:
        last_ts = state[key].get("ts", 0)
        if now - last_ts < DEDUP_WINDOW_SECONDS:
            return False
    return True


def _mark_alerted(key: str, level: str, title: str, tags: list[str]) -> None:
    """Record that an alert was sent."""
    state = _load_dedup()
    state[key] = {
        "ts": time.time(),
        "level": level,
        "title": title,
        "tags": tags,
    }
    _save_dedup(state)


def _make_key(level: str, title: str, tags: list[str]) -> str:
    """Generate deduplication key from alert identity."""
    tag_str = ",".join(sorted(tags))
    return f"{level}|{title}|{tag_str}"


def _send_telegram(token: str, chat_id: str, text: str) -> tuple[bool, str]:
    """Send alert via Telegram Bot API. Returns (ok, notes)."""
    if not token or not chat_id:
        return False, "missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID"
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        resp = requests.post(url, json={"chat_id": chat_id, "text": text},
                             timeout=30)
        if resp.status_code == 200:
            return True, "telegram ok"
        return False, f"telegram HTTP {resp.status_code}: {resp.text[:200]}"
    except Exception as e:
        return False, f"telegram error: {e}"


def _send_email(smtp_host: str, smtp_port: int, smtp_user: str,
                smtp_pass: str, to_addr: str, subject: str, body: str) -> tuple[bool, str]:
    """Send alert via SMTP. Returns (ok, notes)."""
    if not all([smtp_host, smtp_port, smtp_user, smtp_pass, to_addr]):
        return False, "missing SMTP config"
    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = smtp_user
        msg["To"] = to_addr
        with smtplib.SMTP(smtp_host, int(smtp_port), timeout=30) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        return True, "email ok"
    except Exception as e:
        return False, f"email error: {e}"


def _send_webhook(url: str, payload: dict) -> tuple[bool, str]:
    """Send alert via generic JSON webhook. Returns (ok, notes)."""
    if not url:
        return False, "missing ALERT_WEBHOOK_URL"
    try:
        resp = requests.post(url, json=payload, timeout=30)
        if 200 <= resp.status_code < 300:
            return True, "webhook ok"
        return False, f"webhook HTTP {resp.status_code}: {resp.text[:200]}"
    except Exception as e:
        return False, f"webhook error: {e}"


def dispatch_alert(
    level: str,
    title: str,
    body: str,
    tags: list[str] | None = None,
    telegram_override: Optional[str] = None,
) -> dict[str, tuple[bool, str]]:
    """
    Dispatch an alert to all configured channels.

    Args:
        level: "info" | "warn" | "error" | "critical"
        title: Short alert title (used for deduplication)
        body: Full alert message body
        tags: List of tags for categorization/deduplication
        telegram_override: If provided, use this text for Telegram instead of body

    Returns:
        Dict mapping channel -> (ok, notes)
    """
    tags = tags or []
    key = _make_key(level, title, tags)

    if not _should_alert(key):
        return {"deduplicated": (True, f"suppressed (within {DEDUP_WINDOW_SECONDS}s window)")}

    env = _load_env()
    results: dict[str, tuple[bool, str]] = {}

    # Build common payload
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "title": title,
        "body": body,
        "tags": tags,
    }

    # Telegram
    tg_text = telegram_override or f"[{level.upper()}] {title}\n\n{body}"
    tg_text += "\n\n" + "=" * 34 + "\nOLP XDV — Honest edge: not a demonstrated edge · Capital: Architect only."
    results["telegram"] = _send_telegram(env["TELEGRAM_BOT_TOKEN"],
                                         env["TELEGRAM_CHAT_ID"], tg_text)

    # Email
    subject = f"[OLP XDV {level.upper()}] {title}"
    email_body = f"{body}\n\nTags: {', '.join(tags) if tags else 'none'}\nTimestamp: {payload['timestamp']}"
    results["email"] = _send_email(
        env["ALERT_SMTP_HOST"], int(env["ALERT_SMTP_PORT"] or 587),
        env["ALERT_SMTP_USER"], env["ALERT_SMTP_PASS"],
        env["ALERT_EMAIL_TO"], subject, email_body)

    # Webhook
    results["webhook"] = _send_webhook(env["ALERT_WEBHOOK_URL"], payload)

    # Mark as alerted (after attempting all channels so partial failure doesn't block re-alert)
    if any(ok for ok, _ in results.values()):
        _mark_alerted(key, level, title, tags)

    return results


def main() -> int:
    """CLI for manual testing: python -m monitor.alert_dispatcher 'critical' 'Test' 'Body'"""
    import sys
    if len(sys.argv) < 4:
        print("Usage: python -m monitor.alert_dispatcher <level> <title> <body> [tags...]")
        return 1
    level, title, body = sys.argv[1:4]
    tags = sys.argv[4:] if len(sys.argv) > 4 else []
    results = dispatch_alert(level, title, body, tags)
    for ch, (ok, note) in results.items():
        print(f"{ch}: {'OK' if ok else 'FAIL'} — {note}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())