"""Lightweight error tracking — records errors to JSONL, aggregates by error_id.
No external dependencies (no Sentry), stdlib only.
"""
from __future__ import annotations

import json
import logging
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).parent.parent
ERROR_LOG_PATH = ROOT / "logs" / "errors.jsonl"

# Rotation config for error log (5MB / 5 backups)
ERROR_MAX_BYTES = 5 * 1024 * 1024
ERROR_BACKUP_COUNT = 5


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
    }


def _setup_error_logger() -> logging.Logger:
    """Create/return the rotating error logger."""
    from monitor.json_log import setup_json_logging
    logger = setup_json_logging(
        log_path=ERROR_LOG_PATH,
        level=logging.ERROR,
        max_bytes=ERROR_MAX_BYTES,
        backup_count=ERROR_BACKUP_COUNT,
    )
    return logger


def _make_error_id(exc: BaseException, context: str) -> str:
    """Generate a stable error_id from exception type + context."""
    exc_type = type(exc).__name__
    # Hash the context to keep it short but deterministic
    import hashlib
    ctx_hash = hashlib.md5(context.encode()).hexdigest()[:8]
    return f"{exc_type}:{ctx_hash}"


def record_error(
    exc: BaseException,
    context: str = "",
    extra: dict | None = None,
    tags: list[str] | None = None,
) -> str:
    """
    Record an error to logs/errors.jsonl with aggregation fields.

    Args:
        exc: The exception instance
        context: Where it happened (e.g., "run_daily.grade_open_legs")
        extra: Additional structured fields to include
        tags: Categorization tags (e.g., ["odds", "quota"])

    Returns:
        The error_id used for aggregation
    """
    error_id = _make_error_id(exc, context)
    tags = tags or []

    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))

    record = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "level": "error",
        "logger": "olp.errors",
        "message": str(exc),
        "error_id": error_id,
        "error_type": type(exc).__name__,
        "context": context,
        "traceback": tb,
        "tags": tags,
    }
    if extra:
        record["extra"] = extra

    logger = _setup_error_logger()
    logger.error(str(exc), extra={"extra_fields": record})

    # Auto-alert on critical patterns (configurable via env)
    _maybe_alert_on_error(error_id, exc, context, tags)

    return error_id


def _maybe_alert_on_error(
    error_id: str,
    exc: BaseException,
    context: str,
    tags: list[str],
) -> None:
    """Auto-alert on errors matching critical patterns (opt-in via env)."""
    alert_patterns = os.environ.get("ERROR_ALERT_PATTERNS", "")
    if not alert_patterns:
        return

    patterns = [p.strip() for p in alert_patterns.split(",") if p.strip()]
    error_text = f"{type(exc).__name__}: {exc} in {context}".lower()

    for pattern in patterns:
        if pattern.lower() in error_text:
            try:
                from monitor import alert_dispatcher
                alert_dispatcher.dispatch_alert(
                    "error",
                    f"OLP XDV Error: {type(exc).__name__}",
                    f"Error in {context}:\n{exc}\n\nError ID: {error_id}",
                    tags=tags + ["auto-alert", "error-tracker"],
                )
            except Exception:
                # Alert dispatch failure must not break error recording
                pass
            break


def get_error_summary(
    limit: int = 100,
    since_hours: int | None = None,
    error_id: str | None = None,
) -> dict:
    """
    Return aggregated error summary for the web dashboard.

    Returns:
        {
            "total_errors": int,
            "unique_error_ids": int,
            "by_error_id": {error_id: {"count": int, "first_seen": ts, "last_seen": ts, "context": str, "tags": list}},
            "recent": [record, ...]  # last N records
        }
    """
    if not ERROR_LOG_PATH.exists():
        return {
            "total_errors": 0,
            "unique_error_ids": 0,
            "by_error_id": {},
            "recent": [],
        }

    cutoff_ts = None
    if since_hours:
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(hours=since_hours)
        cutoff_ts = cutoff.timestamp()

    errors_by_id: dict[str, dict] = {}
    recent: list[dict] = []
    total = 0

    for line in ERROR_LOG_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue

        # Filter by time
        if cutoff_ts:
            try:
                rec_ts = datetime.fromisoformat(rec.get("ts", "").replace("Z", "+00:00")).timestamp()
                if rec_ts < cutoff_ts:
                    continue
            except Exception:
                pass

        # Filter by error_id
        if error_id and rec.get("error_id") != error_id:
            continue

        total += 1
        if len(recent) < limit:
            recent.append(rec)

        eid = rec.get("error_id", "unknown")
        if eid not in errors_by_id:
            errors_by_id[eid] = {
                "count": 0,
                "first_seen": rec.get("ts"),
                "last_seen": rec.get("ts"),
                "context": rec.get("context", ""),
                "error_type": rec.get("error_type", ""),
                "tags": rec.get("tags", []),
                "sample_message": rec.get("message", ""),
            }
        agg = errors_by_id[eid]
        agg["count"] += 1
        agg["last_seen"] = rec.get("ts", agg["last_seen"])

    return {
        "total_errors": total,
        "unique_error_ids": len(errors_by_id),
        "by_error_id": errors_by_id,
        "recent": recent[-limit:],
    }


def install_excepthook() -> None:
    """Install a global sys.excepthook that records unhandled exceptions."""
    old_hook = sys.excepthook

    def _hook(exc_type, exc_value, exc_tb):
        if exc_value is not None:
            record_error(exc_value, context="unhandled_exception", tags=["unhandled"])
        old_hook(exc_type, exc_value, exc_tb)

    sys.excepthook = _hook


if __name__ == "__main__":
    # CLI: python -m monitor.error_tracker --summary [--hours N] [--error-id ID]
    import argparse
    ap = argparse.ArgumentParser(description="OLP XDV Error Tracker")
    ap.add_argument("--summary", action="store_true", help="Print error summary")
    ap.add_argument("--hours", type=int, default=24, help="Hours to look back")
    ap.add_argument("--error-id", type=str, default=None, help="Filter by error_id")
    ap.add_argument("--limit", type=int, default=100, help="Max recent records")
    a = ap.parse_args()

    if a.summary:
        summary = get_error_summary(limit=a.limit, since_hours=a.hours, error_id=a.error_id)
        print(json.dumps(summary, indent=2, default=str))
    else:
        print("Usage: python -m monitor.error_tracker --summary [--hours 24] [--error-id ID]")