"""monitor/fdata.py save survives a file stored with CRLF in framework-data while .gitattributes says eol=lf.

2026-11-08: two world-basketball acca files were committed by hand with CRLF (06-11 23:13). Every checkout then
showed them as modified, the save's rebase stopped with "cannot rebase: You have unstaged changes", and the daily
board's picks file was NOT SAVED (picks_2026-11-09 on three runs, picks_2026-11-07 the night before). The save must
still land, and must not commit the line-ending noise as this job's change."""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from monitor import fdata  # noqa: E402

ENV = ("-c", "user.name=t", "-c", "user.email=t@t", "-c", "core.autocrlf=false")


def git(*a: str, cwd: Path) -> str:
    r = subprocess.run(["git", *ENV, *a], cwd=cwd, check=True, capture_output=True, text=True)  # noqa: S603,S607
    return r.stdout


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="fdata-crlf-"))
    git("init", "-q", "--bare", "-b", "main", "remote.git", cwd=tmp)
    seed = tmp / "seed"
    git("clone", "-q", (tmp / "remote.git").as_uri(), str(seed), cwd=tmp)
    # the CRLF file goes in BEFORE the eol rule, the way a hand commit from Windows left it in the index
    (seed / "output/wb").mkdir(parents=True)
    (seed / "output/wb/acca.json").write_bytes(b'{\r\n "a": 1\r\n}\r\n')
    (seed / "output/picks").mkdir(parents=True)
    (seed / "output/picks/old.json").write_bytes(b"{}\n")
    git("add", "output", cwd=seed)
    git("commit", "-qm", "seed", cwd=seed)
    (seed / ".gitattributes").write_bytes(b"*.json text eol=lf\n")
    git("add", ".gitattributes", cwd=seed)
    git("commit", "-qm", "eol rule", cwd=seed)
    git("push", "-q", "origin", "HEAD:main", cwd=seed)

    ws = tmp / "job"
    ws.mkdir()
    git("clone", "-q", "--depth", "1", (tmp / "remote.git").as_uri(), str(ws / ".fdata"), cwd=tmp)
    git("config", "core.autocrlf", "false", cwd=ws / ".fdata")
    fdata.ROOT, fdata.FD = ws, ws / ".fdata"
    fdata.STATE = fdata.FD / ".git" / "olp-fdata-base.json"
    fdata.pull()

    # another job saves meanwhile, so this save needs a real rebase
    (seed / "output/picks/other.json").write_bytes(b'{"o": 1}\n')
    git("add", "output", cwd=seed)
    git("commit", "-qm", "other job", cwd=seed)
    git("push", "-q", "origin", "HEAD:main", cwd=seed)

    (ws / "output/picks").mkdir(parents=True, exist_ok=True)
    (ws / "output/picks/picks_2026-11-09.json").write_bytes(b'{"date": "2026-11-09"}\n')
    msg = fdata.save(["output/picks"], "daily board")
    assert msg.startswith("framework-data: saved"), msg

    git("fetch", "-q", "origin", "main", cwd=seed)
    files = git("ls-tree", "-r", "--name-only", "FETCH_HEAD", cwd=seed).split()
    assert "output/picks/picks_2026-11-09.json" in files and "output/picks/other.json" in files, files
    changed = git("show", "--name-only", "--format=", "FETCH_HEAD", cwd=seed).split()
    assert changed == ["output/picks/picks_2026-11-09.json"], f"only this job's file is committed: {changed}"
    print("fdata_crlf_test OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
