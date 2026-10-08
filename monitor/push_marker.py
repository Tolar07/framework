"""
Save ONE file to main straight away, on its own — for the board's
"sent" marker (output/boards/sent_<date>_<slot>), the record the duplicate
guard in daily.yml reads.

Why (2026-10-08): the 7 Oct 22:07 UTC run delivered the board, then its
persist step's `git pull --rebase` hit a conflict in an NBA ladder file
another workflow had just pushed, so the whole commit — marker included —
was dropped. The 00:24 UTC late GitHub cron found no marker and sent the
board, the bet365 board and the heartbeat to everyone a second time.

The marker is a new file nobody else writes, so committing it alone on top
of the LATEST main can never conflict. It is built in a separate worktree,
so the run's own checkout (with the board, picks and CLV log still to be
saved) is left untouched. A push rejected because main moved meanwhile is
retried on the new main.

Usage: python monitor/push_marker.py <path> "<commit message>"
Exit 0 when the file is on main; 1 when it could not be saved (the run says
so loudly — the board was already delivered, so it must not fail the run).
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

AUTHOR = ("-c", "user.name=olp-xdv-agent",
          "-c", "user.email=olp-xdv-agent@users.noreply.github.com")


def _git(cwd: str | Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *AUTHOR, *args], cwd=cwd,  # noqa: S603,S607 (fixed git args)
                          capture_output=True, text=True)


def push_file(rel_path: str, message: str, repo: str | Path = ".",
              remote: str = "origin", branch: str = "main", tries: int = 5) -> bool:
    """Commit `rel_path` (as it is in `repo`'s working tree) alone on top of
    the latest `remote/branch` and push it. True when it is on the branch."""
    repo = Path(repo).resolve()
    src = repo / rel_path
    if not src.is_file():
        return False
    tmp = Path(tempfile.mkdtemp(prefix="olp-marker-"))
    wt = tmp / "wt"
    try:
        for _ in range(tries):
            if _git(repo, "fetch", "-q", remote, branch).returncode != 0:
                continue
            if wt.exists():
                _git(repo, "worktree", "remove", "--force", str(wt))
            if _git(repo, "worktree", "add", "-q", "--detach", str(wt),
                    f"{remote}/{branch}").returncode != 0:
                continue
            dst = wt / rel_path
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
            _git(wt, "add", rel_path)
            if _git(wt, "diff", "--cached", "--quiet").returncode == 0:
                return True                     # already on main, same content
            if _git(wt, "commit", "-q", "-m", message).returncode != 0:
                continue
            if _git(wt, "push", "-q", remote, f"HEAD:{branch}").returncode == 0:
                return True
        return False
    finally:
        if wt.exists():
            _git(repo, "worktree", "remove", "--force", str(wt))
        _git(repo, "worktree", "prune")
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2:
        print(__doc__)
        return 2
    ok = push_file(args[0], args[1])
    print(f"{args[0]}: saved to main" if ok else
          f"::warning::{args[0]} could NOT be saved to main — a late duplicate run may resend this board")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
