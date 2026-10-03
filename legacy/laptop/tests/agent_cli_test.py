#!/usr/bin/env python3
"""Test suite for agent_cli.py — plain-script test on throwaway brains.

Repo convention: module asserts + print("N. ...: OK") checkpoints +
print("\nALL ... TESTS PASSED") at end.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Insert repo root
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

import agent_cli  # noqa: E402  (repo root is on sys.path only after insert)


def test_success_envelope():
    """Test success() returns correct envelope."""
    result = agent_cli.success({"foo": "bar"}, "message")
    assert result["status"] is True
    assert result["data"] == {"foo": "bar"}
    assert result["message"] == "message"
    print("1. success() envelope: OK")


def test_error_envelope():
    """Test error() returns correct envelope."""
    result = agent_cli.error("something went wrong", {"code": 500})
    assert result["status"] is False
    assert result["data"] == {"code": 500}
    assert result["message"] == "something went wrong"
    print("2. error() envelope: OK")


def test_print_json():
    """Test print_json writes valid JSON to stdout."""
    from io import StringIO
    old_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        agent_cli.print_json({"a": 1})
        output = sys.stdout.getvalue()
        parsed = json.loads(output.strip())
        assert parsed == {"a": 1}
    finally:
        sys.stdout = old_stdout
    print("3. print_json(): OK")


def test_print_text():
    """Test print_text writes text to stdout."""
    from io import StringIO
    old_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        agent_cli.print_text("hello")
        output = sys.stdout.getvalue()
        assert output == "hello\n"
    finally:
        sys.stdout = old_stdout
    print("4. print_text(): OK")


def test_build_parser():
    """Test argument parser builds and parses correctly."""
    parser = agent_cli.build_parser()

    # Test global args
    args = parser.parse_args(["stats", "--json", "--brain", "/tmp/test.db", "--phase", "phase2_paper", "--limit", "50"])
    assert args.command == "stats"
    assert args.json is True
    assert args.brain == "/tmp/test.db"
    assert args.phase == "phase2_paper"
    assert args.limit == 50

    # Test lookup with query
    args = parser.parse_args(["lookup", "Fenerbahce", "--json"])
    assert args.command == "lookup"
    assert args.query == "Fenerbahce"

    # Test board with date
    args = parser.parse_args(["board", "--date", "2026-01-15", "--raw", "--json"])
    assert args.command == "board"
    assert args.date == "2026-01-15"
    assert args.raw is True

    # Test clv with --by
    args = parser.parse_args(["clv", "--by", "league", "--json"])
    assert args.command == "clv"
    assert args.by == "league"

    # Test audit
    args = parser.parse_args(["audit", "--no-odds", "--league", "Danish Superliga", "--json"])
    assert args.command == "audit"
    assert args.no_odds is True
    assert args.league == "Danish Superliga"

    # Test leagues
    args = parser.parse_args(["leagues", "--json"])
    assert args.command == "leagues"

    # Test schema
    args = parser.parse_args(["schema", "--json"])
    assert args.command == "schema"

    print("5. build_parser() parsing: OK")


def test_cmd_stats_missing_brain():
    """Test cmd_stats handles missing brain gracefully."""
    from io import StringIO
    old_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        args = MagicMock()
        args.json = True
        args.brain = "/nonexistent/path.db"
        args.phase = "phase2_paper"
        args.limit = 30
        result = agent_cli.cmd_stats(args)
        output = sys.stdout.getvalue()
        parsed = json.loads(output.strip())
        assert result == 1
        assert parsed["status"] is False
        assert "Brain not found" in parsed["message"]
    finally:
        sys.stdout = old_stdout
    print("6. cmd_stats missing brain: OK")


def test_cmd_lookup_missing_brain():
    """Test cmd_lookup handles missing brain gracefully."""
    from io import StringIO
    old_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        args = MagicMock()
        args.json = True
        args.brain = "/nonexistent/path.db"
        args.query = "Fenerbahce"
        args.limit = 100
        result = agent_cli.cmd_lookup(args)
        output = sys.stdout.getvalue()
        parsed = json.loads(output.strip())
        assert result == 1
        assert parsed["status"] is False
        assert "Brain not found" in parsed["message"]
    finally:
        sys.stdout = old_stdout
    print("7. cmd_lookup missing brain: OK")


def test_cmd_board_no_dates():
    """Test cmd_board handles no published boards."""
    from io import StringIO
    old_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        with patch("webapp.schema.list_published_dates", return_value=[]):
            args = MagicMock()
            args.json = True
            args.date = None
            args.raw = False
            result = agent_cli.cmd_board(args)
            output = sys.stdout.getvalue()
            parsed = json.loads(output.strip())
            assert result == 1
            assert parsed["status"] is False
            assert "No published boards found" in parsed["message"]
    finally:
        sys.stdout = old_stdout
    print("8. cmd_board no dates: OK")


def test_cmd_clv_missing_brain():
    """Test cmd_clv handles missing brain gracefully."""
    from io import StringIO
    old_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        args = MagicMock()
        args.json = True
        args.brain = "/nonexistent/path.db"
        args.by = "market"
        args.phase = "phase2_paper"
        result = agent_cli.cmd_clv(args)
        output = sys.stdout.getvalue()
        parsed = json.loads(output.strip())
        assert result == 1
        assert parsed["status"] is False
        assert "Brain not found" in parsed["message"]
    finally:
        sys.stdout = old_stdout
    print("9. cmd_clv missing brain: OK")


def test_cmd_clv_unknown_by():
    """Test cmd_clv handles unknown --by value."""
    from io import StringIO
    old_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        args = MagicMock()
        args.json = True
        args.brain = "/nonexistent/path.db"
        args.by = "unknown"
        args.phase = "phase2_paper"
        result = agent_cli.cmd_clv(args)
        output = sys.stdout.getvalue()
        parsed = json.loads(output.strip())
        assert result == 1
        assert parsed["status"] is False
        assert "Unknown --by value" in parsed["message"]
    finally:
        sys.stdout = old_stdout
    print("10. cmd_clv unknown --by: OK")


def test_cmd_gate_missing_brain():
    """Test cmd_gate handles missing brain gracefully."""
    from io import StringIO
    old_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        args = MagicMock()
        args.json = True
        args.brain = "/nonexistent/path.db"
        args.phase = "phase2_paper"
        result = agent_cli.cmd_gate(args)
        output = sys.stdout.getvalue()
        parsed = json.loads(output.strip())
        assert result == 1
        assert parsed["status"] is False
        assert "Brain not found" in parsed["message"]
    finally:
        sys.stdout = old_stdout
    print("11. cmd_gate missing brain: OK")


def test_cmd_schema():
    """Test cmd_schema returns valid schema structure."""
    from io import StringIO
    old_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        args = MagicMock()
        args.json = True
        result = agent_cli.cmd_schema(args)
        output = sys.stdout.getvalue()
        parsed = json.loads(output.strip())
        assert result == 0
        assert parsed["status"] is True
        assert "commands" in parsed["data"]
        commands = parsed["data"]["commands"]
        assert len(commands) == 8
        cmd_names = {c["name"] for c in commands}
        expected = {"stats", "lookup", "board", "clv", "gate", "audit", "leagues", "schema"}
        assert cmd_names == expected
        # Check each command has required fields
        for cmd in commands:
            assert "name" in cmd
            assert "description" in cmd
            assert "parameters" in cmd
            assert cmd["parameters"]["type"] == "object"
            assert "properties" in cmd["parameters"]
    finally:
        sys.stdout = old_stdout
    print("12. cmd_schema structure: OK")


def test_main_keyboard_interrupt():
    """Test main() handles KeyboardInterrupt."""
    from io import StringIO
    old_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        with patch.object(sys, "argv", ["agent_cli.py", "stats"]), \
             patch("agent_cli.build_parser") as mock_parser:
            mock_parser.return_value.parse_args.side_effect = KeyboardInterrupt()
            result = agent_cli.main()
            assert result == 130
    finally:
        sys.stdout = old_stdout
    print("13. main() KeyboardInterrupt: OK")


def test_main_exception():
    """Test main() handles generic exceptions gracefully."""
    from io import StringIO
    old_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        with patch.object(sys, "argv", ["agent_cli.py", "stats", "--json"]), \
             patch("agent_cli.build_parser") as mock_parser:
            mock_parser.return_value.parse_args.side_effect = ValueError("test error")
            result = agent_cli.main()
            output = sys.stdout.getvalue()
            parsed = json.loads(output.strip())
            assert result == 1
            assert parsed["status"] is False
            assert "ValueError: test error" in parsed["message"]
    finally:
        sys.stdout = old_stdout
    print("14. main() generic exception: OK")


def test_main_no_command():
    """Test main() handles no command (argparse usage + exit 2)."""
    from io import StringIO
    old_stderr = sys.stderr
    old_stdout = sys.stdout
    sys.stderr = StringIO()
    sys.stdout = StringIO()
    try:
        with patch.object(sys, "argv", ["agent_cli.py"]):
            result = agent_cli.main()
            assert result == 2
    finally:
        sys.stderr = old_stderr
        sys.stdout = old_stdout
    print("15. main() no command: OK")


def run_all_tests():
    """Run all tests."""
    print("Running agent_cli tests...\n")

    test_success_envelope()
    test_error_envelope()
    test_print_json()
    test_print_text()
    test_build_parser()
    test_cmd_stats_missing_brain()
    test_cmd_lookup_missing_brain()
    test_cmd_board_no_dates()
    test_cmd_clv_missing_brain()
    test_cmd_clv_unknown_by()
    test_cmd_gate_missing_brain()
    test_cmd_schema()
    test_main_keyboard_interrupt()
    test_main_exception()
    test_main_no_command()

    print("\nALL AGENT_CLI TESTS PASSED")


if __name__ == "__main__":
    run_all_tests()
