"""The framework's data is private (Architect 2026-10-30; step D 2026-11-05): only code (*.py) under output/,
memory/ and data/ is tracked in this public repo, every job's private checkout is required (a job without its
data must fail, not run blind), and no workflow commits a data path publicly."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ("output/", "memory/", "data/", "backtest/", "clv/", "research/")


def main() -> int:
    tracked = subprocess.run(["git", "ls-files", "--", "output", "memory", "data", "backtest", "clv", "research"], cwd=ROOT,  # noqa: S603,S607
                             capture_output=True, text=True, check=True).stdout.split()
    public = [f for f in tracked if not f.endswith(".py")]
    assert not public, f"data tracked in the public framework: {public[:5]}"
    gi = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "# >>> data lives in framework-data" in gi and "# <<< data lives in framework-data" in gi
    for wf in sorted((ROOT / ".github/workflows").glob("*.yml")):
        s = wf.read_text(encoding="utf-8")
        for m in re.finditer(r"- name: Check out the private data.*?(?=\n      - )", s, re.S):
            assert "continue-on-error" not in m.group(0), f"{wf.name}: the private checkout must be required"
        for line in s.splitlines():
            if re.match(r"\s*git add ", line) and "fdata" not in line:
                toks = line.split("git add ", 1)[1].split()
                bad = [t for t in toks if t.startswith(DATA) and not t.endswith(".py")]
                assert not bad, f"{wf.name}: public git add of data {bad}"
    print("no public data: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
