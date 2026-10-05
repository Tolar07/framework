"""A --no-send run works on scratch copies and never touches the real records.

On 2026-10-05 tests/stress_test.py (run_daily.run(send=False)) rewrote the real
5 Oct board, picks ledger and CLV log with an unsent board. This checks the
sandbox run_daily.run uses for every dry run: inside it the ledger, CLV log,
boards and frozen-codes paths point at a scratch copy holding the same files;
after it, every path is back and the real files are unchanged. Offline.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import clv.clv_logger as clv  # noqa: E402
import run_daily  # noqa: E402
from engine import freeze, picks_ledger  # noqa: E402


def _digest(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else "missing"


def test_dry_run_sandbox() -> None:
    real = (run_daily.BOARD_DIR, picks_ledger.LEDGER_DIR, clv.DEFAULT_LOG_PATH, freeze.BOARD_DIR)
    clv_before = _digest(real[2])
    with run_daily._dry_run_sandbox() as tmp:
        assert run_daily.BOARD_DIR == tmp / "boards" == freeze.BOARD_DIR
        assert picks_ledger.LEDGER_DIR == tmp / "picks"
        assert clv.DEFAULT_LOG_PATH == tmp / "clv_log.json"
        assert clv.CLVLog().path == tmp / "clv_log.json"
        assert freeze.paths("2026-10-05")[0].parent == tmp / "boards"
        # the scratch copy starts with the real records, so grading, learning
        # and the frozen-codes check behave as in a real run
        for f in real[1].glob("picks_*.json"):
            assert (tmp / "picks" / f.name).exists()
        # writes land in the scratch copy only
        (picks_ledger.LEDGER_DIR / "picks_2099-01-01.json").write_text("{}", encoding="utf-8")
        (run_daily.BOARD_DIR / "board_2099-01-01.txt").write_text("x", encoding="utf-8")
        clv.DEFAULT_LOG_PATH.write_text("[]", encoding="utf-8")
    assert (run_daily.BOARD_DIR, picks_ledger.LEDGER_DIR, clv.DEFAULT_LOG_PATH,
            freeze.BOARD_DIR) == real
    assert not (real[1] / "picks_2099-01-01.json").exists()
    assert not (real[0] / "board_2099-01-01.txt").exists()
    assert _digest(real[2]) == clv_before


def test_send_false_uses_the_sandbox() -> None:
    seen = {}

    def fake_run(**kw):
        seen["ledger"] = picks_ledger.LEDGER_DIR
        seen["send"] = kw["send"]
        return "board"

    orig = run_daily._run
    run_daily._run = fake_run
    try:
        assert run_daily.run(send=False) == "board"
        assert seen["send"] is False and seen["ledger"] != picks_ledger.LEDGER_DIR
        assert run_daily.run(send=True) == "board"
        assert seen["ledger"] == picks_ledger.LEDGER_DIR   # a real run writes the real ledger
    finally:
        run_daily._run = orig


if __name__ == "__main__":
    test_dry_run_sandbox()
    test_send_false_uses_the_sandbox()
    print("dry-run sandbox: OK")
