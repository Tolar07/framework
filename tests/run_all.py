"""Run every test file in tests/, each in its own Python process.

Most tests here are standalone scripts: module-level checks, or test_*
functions driven by their own main() (which sets up monkeypatches first).
Under a single `pytest tests/` process they share import state and their
test_* functions run without that setup, so they fail spuriously. Running
each file as its own process is how they are written to run.

A file that defines test_* functions but has no __main__ runner is a
pytest-style test, so it runs under pytest instead.

Exit status is non-zero if any file fails. Usage: python tests/run_all.py
"""
from __future__ import annotations

import re
import subprocess
import sys
import time
from pathlib import Path

TESTS = Path(__file__).resolve().parent
ROOT = TESTS.parent
# The stress test runs the full live pipeline; on a big Saturday slate (120+
# fixtures) it ran past 600 s and blocked a merge (2026-10-10). 1200 s still
# fits the job's 30-minute limit.
TIMEOUT_S = 1200


def command_for(path: Path) -> list[str]:
    src = path.read_text(encoding="utf-8", errors="replace")
    has_main = re.search(r"""__name__\s*==\s*['"]__main__['"]""", src)
    has_test_fns = re.search(r"^def test_", src, re.MULTILINE)
    if has_test_fns and not has_main:
        return [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(path)]
    return [sys.executable, str(path)]


def main() -> int:
    files = sorted(
        p for p in TESTS.glob("*.py")
        if p.name != Path(__file__).name
        and (p.name.endswith("_test.py") or p.name.startswith("test_"))
    )
    failed: list[str] = []
    for path in files:
        t0 = time.time()
        try:
            proc = subprocess.run(command_for(path), cwd=ROOT, capture_output=True,  # noqa: S603 (repo test files only)
                                  text=True, timeout=TIMEOUT_S)
            ok, out = proc.returncode == 0, proc.stdout + proc.stderr
        except subprocess.TimeoutExpired:
            ok, out = False, f"timed out after {TIMEOUT_S}s"
        print(f"{'PASS' if ok else 'FAIL'}  {path.name}  ({time.time() - t0:.1f}s)", flush=True)
        if not ok:
            failed.append(path.name)
            print("\n".join("    " + line for line in out.strip().splitlines()[-25:]), flush=True)
    print(f"\n{len(files) - len(failed)}/{len(files)} test files passed")
    if failed:
        print("FAILED: " + ", ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
