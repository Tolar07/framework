"""Structured JSON-lines (JSONL) logging.

A tiny stdlib-only logging Formatter + RotatingFileHandler that emits one JSON
object per line, so the web server's access log and any pipeline event are
machine-readable without adding a pip dependency (loguru & friends are out of
scope for this repo). ``setup_json_logging()`` returns a logger that appends to
``logs/web.jsonl`` and rotates at 5 MB keeping 2 backups.

Every line carries at minimum:

    {"ts": "2026-08-09T...", "level": "info", "logger": "olp.json",
     "message": "..."}

HTTP access records add ``path`` / ``method`` / ``status`` / ``duration_ms`` /
``ip`` (these are safe ``extra`` keys — none collide with LogRecord attrs).
Any extra dict under ``extra_fields`` is merged at the top level too.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LOG_PATH = ROOT / "logs" / "web.jsonl"

# Optional attributes the formatter knows to hoist from the LogRecord.
_EXTRA_ATTRS = ("path", "method", "status", "duration_ms", "ip",
                "event", "component")


def _now_iso() -> str:
    """Local-time ISO-8601 with timezone, second precision (jq-friendly)."""
    return dt.datetime.now(dt.UTC).astimezone().isoformat(
        timespec="seconds")


class JsonFormatter(logging.Formatter):
    """Format a record as one JSON object; unknown values stringify safely."""

    def format(self, record: logging.LogRecord) -> str:
        rec: dict[str, object] = {
            "ts": _now_iso(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
        }
        for attr in _EXTRA_ATTRS:
            val = getattr(record, attr, None)
            if val is not None:
                rec[attr] = val
        extra = getattr(record, "extra_fields", None)
        if isinstance(extra, dict):
            rec.update({k: v for k, v in extra.items() if k not in rec})
        if record.exc_info:
            rec["exc"] = self.formatException(record.exc_info)
        try:
            return json.dumps(rec, ensure_ascii=False, default=str)
        except (TypeError, ValueError):  # unpicklable value -> repr it
            rec["message"] = repr(record.getMessage())
            return json.dumps(rec, ensure_ascii=False, default=str)


def setup_json_logging(log_path: str | Path = DEFAULT_LOG_PATH,
                       level: int = logging.INFO,
                       max_bytes: int = 5 * 1024 * 1024,
                       backup_count: int = 2) -> logging.Logger:
    """Idempotent: returns the shared ``olp.json`` logger, creating its
    RotatingFileHandler on first call so tests and the server can both wire in
    without stacking duplicate handlers."""
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("olp.json")
    if any(isinstance(h, RotatingFileHandler) and getattr(h, "baseFilename", "")
           == str(path) for h in logger.handlers):
        return logger
    handler = RotatingFileHandler(
        path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8")
    handler.setFormatter(JsonFormatter())
    logger.setLevel(level)
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def json_log(message: str, **fields: object) -> None:
    """Fire-and-forget structured event; configures the logger on demand."""
    setup_json_logging().info(message, extra={"event": message, **fields})


def main() -> None:
    """CLI self-check: append one JSON line and print it back."""
    import sys

    logger = setup_json_logging()
    logger.info("json_log self-check", extra={"event": "self_check", "status": 200})
    line = DEFAULT_LOG_PATH.read_text(encoding="utf-8").splitlines()[-1]
    sys.stdout.write(line + "\n")


if __name__ == "__main__":
    main()
