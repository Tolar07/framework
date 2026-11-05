"""output/routines_cmd.py + the /routines and /run wiring in output/telegram_commands.py."""
from __future__ import annotations

import os
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from output import routines_cmd as rc  # noqa: E402
from output import telegram_commands as tc  # noqa: E402

NOW = datetime(2026, 11, 4, 23, 30, tzinfo=UTC)
DOC = {"built_at": "2026-11-04T23:11:00+00:00", "routines": [
    {"name": "edge", "repo": "Tolar07/framework", "status": "NOT STARTED",
     "last": {"at": "2026-11-04T15:30:41Z"}, "next": "2026-11-04T23:43:00+00:00"},
    {"name": "daily slot=evening", "repo": "Tolar07/framework", "status": "OK",
     "last": {"at": "2026-11-04T21:47:30Z"}, "next": "2026-11-05T21:47:00+00:00"},
    {"name": "placer", "repo": "Tolar07/sportybet-agent", "status": "RUNNING", "last": None, "next": None},
]}


def test_view_puts_problems_first():
    text = rc.format_view(DOC, NOW)
    assert text.startswith("ROUTINES — 3 scheduled, 1 need attention (built 19m ago)")
    assert text.index("NEEDS ATTENTION") < text.index("FRAMEWORK")
    assert "✗ edge (framework) — NOT STARTED, last 7h ago" in text
    assert "· daily slot=evening — OK, last 1h ago" in text
    assert "next in 22h17" in text and "SPORTYBET-AGENT" in text


def test_not_configured_and_usage():
    os.environ.pop("MB_DEPLOY_KEY", None)
    assert "not configured" in rc.cmd_routines()
    assert rc.cmd_run("").startswith("Usage: /run")
    assert "not configured" in rc.cmd_run("edge")


def test_run_is_architect_only_and_fails_closed():
    os.environ.pop("TELEGRAM_CHAT_ID", None)
    assert tc.handle("/run edge", chat_id="123").startswith("REFUSED")     # no chat configured
    os.environ["TELEGRAM_CHAT_ID"] = "999"
    assert tc.handle("/run edge", chat_id="123").startswith("REFUSED")     # someone else's chat
    assert tc.handle("/run edge", chat_id=None).startswith("REFUSED")
    os.environ.pop("TELEGRAM_CHAT_ID", None)
    assert "/routines" in tc.cmd_help("") and "/routines" in tc.HANDLERS


def main() -> None:
    test_view_puts_problems_first()
    test_not_configured_and_usage()
    test_run_is_architect_only_and_fails_closed()
    print("routines_cmd_test OK")


if __name__ == "__main__":
    main()
