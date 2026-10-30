"""monitor/fdata.py: two jobs saving to framework-data at once keep each
other's work — both appends to a union log, no stale copy written back, a
deleted file stays deleted, code (*.py) never laid over the workspace."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from monitor import fdata  # noqa: E402

ENV = ("-c", "user.name=t", "-c", "user.email=t@t", "-c", "core.autocrlf=false")


def git(*a: str, cwd: Path) -> None:
    subprocess.run(["git", *ENV, *a], cwd=cwd, check=True, capture_output=True)  # noqa: S603,S607


def job(tmp: Path, name: str) -> Path:
    ws = tmp / name
    ws.mkdir()
    git("clone", "-q", "--depth", "1", (tmp / "remote.git").as_uri(), str(ws / ".fdata"), cwd=tmp)
    git("config", "core.autocrlf", "false", cwd=ws / ".fdata")
    return ws


def use(ws: Path) -> None:
    fdata.ROOT, fdata.FD = ws, ws / ".fdata"
    fdata.STATE = fdata.FD / ".git" / "olp-fdata-base.json"


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="fdata-test-"))
    git("init", "-q", "--bare", "-b", "main", "remote.git", cwd=tmp)
    seed = tmp / "seed"
    git("clone", "-q", (tmp / "remote.git").as_uri(), str(seed), cwd=tmp)
    for rel, text in {".gitattributes": "output/nba_markets/*.jsonl merge=union\n",
                      "output/nba_markets/m.jsonl": "a1\n", "memory/k.json": '{"x":1}\n',
                      "data/f.txt": "old\n", "data/del.txt": "gone\n", "data/code.py": "x=1\n"}.items():
        (seed / rel).parent.mkdir(parents=True, exist_ok=True)
        (seed / rel).write_bytes(text.encode())
    git("add", ".gitattributes", "output", "memory", "data", cwd=seed)
    git("commit", "-qm", "seed", cwd=seed)
    git("push", "-q", "origin", "HEAD:main", cwd=seed)

    a, b = job(tmp, "A"), job(tmp, "B")
    for ws in (a, b):
        use(ws)
        assert "4 files" in fdata.pull(), "code must not be laid over the workspace"
        assert not (ws / "data" / "code.py").exists()
    with (a / "output/nba_markets/m.jsonl").open("ab") as f:
        f.write(b"a2\n")
    (a / "data/del.txt").unlink()
    with (b / "output/nba_markets/m.jsonl").open("ab") as f:
        f.write(b"b2\n")
    (b / "data/f.txt").write_bytes(b"new\n")
    use(a)
    assert fdata.save(["output", "memory", "data"], "A").startswith("framework-data: saved 2")
    use(b)
    assert fdata.save(["output", "memory", "data"], "B").startswith("framework-data: saved 2")
    use(a)
    (a / "memory/k.json").write_bytes(b'{"x":2}\n')
    assert fdata.save(["memory", "data"], "A2").startswith("framework-data: saved 1")
    assert fdata.save(["memory", "data"], "A3") == "framework-data: nothing new to save"
    assert fdata.on_main("data/f.txt") is True and fdata.on_main("data/nope") is False

    check = tmp / "check"
    git("clone", "-q", (tmp / "remote.git").as_uri(), str(check), cwd=tmp)
    assert (check / "output/nba_markets/m.jsonl").read_bytes() == b"a1\na2\nb2\n"
    assert (check / "data/f.txt").read_bytes() == b"new\n", "A wrote back a stale copy"
    assert (check / "memory/k.json").read_bytes() == b'{"x":2}\n'
    assert not (check / "data/del.txt").exists()
    assert (a / "data/f.txt").read_bytes() == b"new\n", "A's workspace should pick up B's file"
    use(b)
    assert "refreshed" in fdata.refresh()
    assert (b / "memory/k.json").read_bytes() == b'{"x":2}\n'
    # stage B: a file framework still tracks keeps framework's copy
    c = job(tmp, "C")
    (c / "memory").mkdir()
    (c / "memory/k.json").write_bytes(b"framework's\n")
    git("init", "-q", cwd=c)
    git("add", "memory/k.json", cwd=c)
    use(c)
    os.environ["FDATA_SOURCE"] = ""
    assert "source: framework" in fdata.pull()
    assert (c / "memory/k.json").read_bytes() == b"framework's\n"
    assert (c / "data/f.txt").read_bytes() == b"new\n"
    os.environ["FDATA_SOURCE"] = "fd"
    assert "source: fd" in fdata.pull()
    assert (c / "memory/k.json").read_bytes() == b'{"x":2}\n'
    print("fdata: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
