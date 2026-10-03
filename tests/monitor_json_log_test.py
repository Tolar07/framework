"""JSONL logging tests for monitor/json_log.py.

Verifies the JsonFormatter output shape, that extras land at the top level
(path/method/status), idempotent setup (no stacked handlers), and the
fire-and-forget json_log() helper — all against a throwaway file.
"""
import json
import logging
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from monitor import json_log

_tmp = Path(tempfile.mkdtemp(prefix="olp_json_log_test_"))
_logfile = _tmp / "web.jsonl"

# --- formatter shape ----------------------------------------------------------
rec = logging.LogRecord("olp.json", logging.INFO, __file__, 1,
                        "GET /api/board.json", (), None)
rec.path = "/api/board.json"
rec.method = "GET"
rec.status = 200
rec.duration_ms = 12.3
line = json_log.JsonFormatter().format(rec)
obj = json.loads(line)
assert obj["level"] == "info" and obj["logger"] == "olp.json"
assert obj["message"] == "GET /api/board.json"
assert obj["path"] == "/api/board.json"
assert obj["method"] == "GET" and obj["status"] == 200
assert obj["duration_ms"] == 12.3
assert "ts" in obj and "T" in obj["ts"]  # ISO-8601 timestamp
assert set(obj) == {"ts", "level", "logger", "message", "path", "method",
                    "status", "duration_ms"}
print("formatter emits one flat JSON object with extras: OK")

# --- an exception record carries exc ------------------------------------------
try:
    raise ValueError("boom")
except ValueError:
    rec = logging.LogRecord("olp.json", logging.ERROR, __file__, 1,
                            "failed", (), sys.exc_info())
obj = json.loads(json_log.JsonFormatter().format(rec))
assert "exc" in obj and "ValueError" in obj["exc"]
print("formatter includes the exception traceback: OK")

# --- setup writes JSONL and is idempotent -------------------------------------
logger = json_log.setup_json_logging(_logfile)
n_handlers = len(logger.handlers)
logger.info("hello", extra={"extra_fields": {"component": "web"}})
logger2 = json_log.setup_json_logging(_logfile)
assert len(logger2.handlers) == n_handlers, "setup stacked duplicate handlers"
lines = _logfile.read_text(encoding="utf-8").splitlines()
assert len(lines) == 1
obj = json.loads(lines[0])
assert obj["message"] == "hello" and obj["component"] == "web"
assert obj["logger"] == "olp.json"
print("setup writes one JSONL line and is idempotent: OK")

# --- fire-and-forget json_log() helper ----------------------------------------
before = len(_logfile.read_text(encoding="utf-8").splitlines())
json_log.json_log("self-check", status=200, path="/metrics")
after = _logfile.read_text(encoding="utf-8").splitlines()
assert len(after) == before + 1
obj = json.loads(after[-1])
assert obj["event"] == "self-check" and obj["status"] == 200
assert obj["path"] == "/metrics"
print("json_log() helper appends one structured line: OK")

# --- an un-serializable value degrades to repr, never a crash ------------------
rec = logging.LogRecord("olp.json", logging.INFO, __file__, 1,
                        "odd", (), None)
rec.extra_fields = {"weird": object()}
obj = json.loads(json_log.JsonFormatter().format(rec))
assert "weird" in obj and isinstance(obj["weird"], str)
print("un-serializable extra degrades to repr: OK")

print("\n[OK] ALL MONITOR JSON-LOG TESTS PASSED")
