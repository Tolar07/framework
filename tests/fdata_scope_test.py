"""monitor/fdata.py save scope (2026-11-05): every data file the job changed reaches framework-data, even
outside the paths it names (world basketball picks, tip boards, the NBA blend were missed), but nothing
framework's .gitignore keeps out (caches), nothing the job did not change, and deletions only under `paths`."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from monitor import fdata  # noqa: E402
from tests.fdata_test import git, job, use  # noqa: E402


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="fdata-scope-"))
    git("init", "-q", "--bare", "-b", "main", "remote.git", cwd=tmp)
    seed = tmp / "seed"
    git("clone", "-q", (tmp / "remote.git").as_uri(), str(seed), cwd=tmp)
    for rel, text in {"output/picks/p.json": "1\n", "memory/m.json": "1\n", "data/keep.txt": "1\n"}.items():
        (seed / rel).parent.mkdir(parents=True, exist_ok=True)
        (seed / rel).write_bytes(text.encode())
    git("add", "output", "memory", "data", cwd=seed)
    git("commit", "-qm", "seed", cwd=seed)
    git("push", "-q", "origin", "HEAD:main", cwd=seed)

    ws = job(tmp, "W")
    git("init", "-q", cwd=ws)                                  # the framework checkout, with its .gitignore
    (ws / ".gitignore").write_bytes(
        b"# >>> data lives in framework-data\noutput/\nmemory/\ndata/\n# <<< data lives in framework-data\n"
        b"*.jsonl\ndata/cache/\n.fdata/\n")
    use(ws)
    fdata.pull()
    (ws / "output/world_basketball").mkdir(parents=True)
    (ws / "output/world_basketball/wb.json").write_bytes(b"wb\n")   # NOT in the paths below
    (ws / "data/cache").mkdir()
    (ws / "data/cache/big.json").write_bytes(b"cache\n")            # ignored
    (ws / "output/picks/p.json").write_bytes(b"2\n")                # in the paths
    (ws / "data/study").mkdir()
    (ws / "data/study/live.jsonl").write_bytes(b"x\n")              # *.jsonl guard does not apply to data
    (ws / "data/keep.txt").unlink()                                   # outside the paths: never deleted
    assert "saved 3 file(s)" in fdata.save(["output/picks"], "t"), "expected picks + wb + study log"

    check = tmp / "check"
    git("clone", "-q", (tmp / "remote.git").as_uri(), str(check), cwd=tmp)
    assert (check / "output/world_basketball/wb.json").read_bytes() == b"wb\n"
    assert (check / "output/picks/p.json").read_bytes() == b"2\n"
    assert not (check / "data/cache").exists(), "an ignored cache reached framework-data"
    assert (check / "data/keep.txt").exists(), "a deletion outside the named paths was saved"
    assert (check / "memory/m.json").read_bytes() == b"1\n"
    assert (check / "data/study/live.jsonl").exists(), "a data .jsonl was dropped by the *.jsonl guard"
    print("fdata scope: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
