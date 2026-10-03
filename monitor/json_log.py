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

# Rotation config for high-volume logs (poller, launcher, etc.)
DEFAULT_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
DEFAULT_BACKUP_COUNT = 5

# Log files written by .bat redirection (>> logs/x.log 2>&1) — these need
# external rotation because the shell owns the file handle, not Python.
# Rotator is run as a scheduled task or pre-run hook.
BAT_REDIRECTED_LOGS = [
    "poller.log",
    "launcher.log",
    "health_monitor.log",
    "web_server.log",
    "steward.log",
]

# Log files written from Python via RotatingFileHandler — rotation is built
# into the logger setup. Listed here for documentation / health checks.
PY_MANAGED_LOGS = [
    "web.jsonl",     # setup_json_logging: 5MB / 2 backups
    "errors.jsonl",  # error_tracker: 5MB / 5 backups (Layer 13)
]


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


def rotate_log_file(log_path: Path,
                    max_bytes: int = DEFAULT_MAX_BYTES,
                    backup_count: int = DEFAULT_BACKUP_COUNT) -> bool:
    """Rotate a single log file if it exceeds ``max_bytes``.

    For .bat-redirected logs (poller.log, launcher.log, etc.) the shell owns
    the file handle, so RotatingFileHandler can't help. This function is called
    by ``scripts/rotate_logs.py`` (scheduled pre-run) or by health_monitor's
    self-heal probe. It renames ``file.log`` -> ``file.log.1``, shifts older
    backups down, and truncates the original — preserving the shell's open
    handle (append mode writes to the now-truncated inode).

    Returns True if a rotation was performed, False if the file was under
    the threshold or didn't exist.
    """
    if not log_path.exists():
        return False
    if log_path.stat().st_size <= max_bytes:
        return False
    # Shift existing backups: .5 -> deleted, .4 -> .5, ... .1 -> .2
    for i in range(backup_count, 0, -1):
        older = log_path.parent / f"{log_path.name}.{i}"
        newer = log_path.parent / f"{log_path.name}.{i - 1}" if i > 1 else log_path
        if i == backup_count and older.exists():
            older.unlink()
        if i > 1 and newer.exists():
            older.write_bytes(newer.read_bytes())
    # Move current to .1
    backup1 = log_path.parent / f"{log_path.name}.1"
    if backup1.exists():
        backup1.unlink()
    log_path.rename(backup1)
    # Recreate empty file so the shell's append handle stays valid
    log_path.touch()
    return True


def rotate_all_bat_logs(logs_dir: Path | None = None,
                        max_bytes: int = DEFAULT_MAX_BYTES,
                        backup_count: int = DEFAULT_BACKUP_COUNT) -> dict[str, bool]:
    """Rotate every .bat-redirected log file that exceeds the size threshold.

    Returns a dict {filename: rotated?} for evidence/logging.
    """
    logs_dir = logs_dir or (ROOT / "logs")
    results: dict[str, bool] = {}
    for filename in BAT_REDIRECTED_LOGS:
        log_path = logs_dir / filename
        try:
            results[filename] = rotate_log_file(
                log_path, max_bytes=max_bytes, backup_count=backup_count)
        except OSError:
            results[filename] = False
    return results


def main() -> None:
    """CLI: rotate all .bat-redirected logs, then self-check JSONL logger.

    Usage:
        python -m monitor.json_log              # rotate + self-check
        python -m monitor.json_log --rotate-only # just rotate
    """
    import sys

    results = rotate_all_bat_logs()
    rotated = [k for k, v in results.items() if v]
    if rotated:
        sys.stderr.write(f"Rotated: {', '.join(rotated)}\n")
    else:
        sys.stderr.write("No logs needed rotation.\n")

    if "--rotate-only" in sys.argv:
        return

    logger = setup_json_logging()
    logger.info("json_log self-check", extra={"event": "self_check", "status": 200})
    line = DEFAULT_LOG_PATH.read_text(encoding="utf-8").splitlines()[-1]
    sys.stdout.write(line + "\n")


if __name__ == "__main__":
    main()
