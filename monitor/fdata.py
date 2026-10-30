"""
The framework's picks, boards, records and memory live in the PRIVATE repo
Tolar07/framework-data (Architect 2026-10-30: "hide the framework's picks and
records"). Every job checks it out at `.fdata/` and this module lays it over
the workspace at the SAME paths (output/, memory/, data/), so the engine reads
and writes exactly where it always has. Code (*.py) stays in framework.

Until framework stops holding the data, the repo variable FDATA_SOURCE says
which copy a job reads: unset = framework's own copy of a file it still tracks
(every job writes both, so framework-data catches up), "fd" = framework-data's.

  pull           lay .fdata over the workspace (start of a job)
  refresh        fetch the newest framework-data and lay it over (a loop's new round)
  save MSG P...  commit the files under P that this job changed and push them

Only files the job changed since its last pull are committed, on top of the
commit the job read, then rebased onto the newest framework-data — so two
jobs appending to the same log both keep their lines (merge=union) and a job
never writes back an old copy of a file someone else changed meanwhile.

No file contents are ever printed (the framework's Actions logs are public).
Without `.fdata/` (a fork PR, a laptop) every call is a no-op.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FD = ROOT / ".fdata"
STATE = FD / ".git" / "olp-fdata-base.json"
DATA_DIRS = ("output", "memory", "data")
MAX_GONE = 5
AUTHOR = ("-c", "user.name=olp-xdv-agent",
          "-c", "user.email=olp-xdv-agent@users.noreply.github.com")


def enabled() -> bool:
    """A usable checkout: a failed clone can leave an empty .fdata/.git behind."""
    return (FD / ".git").exists() and _git("rev-parse", "-q", "--verify", "HEAD").returncode == 0


def _git(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *AUTHOR, *args], cwd=cwd or FD,  # noqa: S603,S607 (fixed git args)
                          capture_output=True, text=True)


def _is_data(rel: str) -> bool:
    parts = rel.split("/")
    if parts[0] not in DATA_DIRS or "__pycache__" in parts:
        return False
    return not rel.endswith((".py", ".pyc"))


def _blob(path: Path) -> str | None:
    try:
        b = path.read_bytes()
    except OSError:
        return None
    return hashlib.sha1(b"blob %d\0" % len(b) + b).hexdigest()  # noqa: S324 (git's blob id, not security)


def _tree(rev: str) -> dict[str, str]:
    """{path: blob sha} of the data files at `rev` in framework-data."""
    out = _git("ls-tree", "-r", "-z", rev).stdout
    m = {}
    for rec in out.split("\0"):
        if not rec:
            continue
        meta, _, path = rec.partition("\t")
        if _is_data(path):
            m[path] = meta.split()[2]
    return m


def _head() -> str:
    return _git("rev-parse", "HEAD").stdout.strip()


def _load_base() -> tuple[str, dict[str, str]]:
    try:
        s = json.loads(STATE.read_text())
        return s["commit"], s["files"]
    except (OSError, ValueError, KeyError):
        return "", {}


def _store_base(commit: str, files: dict[str, str]) -> None:
    STATE.write_text(json.dumps({"commit": commit, "files": files, "source": _source()}))


def _source() -> str:
    """"fd" or "framework" — set by the pull step (FDATA_SOURCE), kept for the job."""
    env = os.environ.get("FDATA_SOURCE", "").strip().lower()
    if env:
        return "fd" if env == "fd" else "framework"
    try:
        return json.loads(STATE.read_text()).get("source", "framework")
    except (OSError, ValueError):
        return "framework"


def _keep() -> set[str]:
    """Files the workspace keeps as they are: those framework still tracks,
    unless framework-data is the source."""
    if _source() == "fd":
        return set()
    out = _git("ls-files", "-z", "--", *DATA_DIRS, cwd=ROOT).stdout
    return {r for r in out.split("\0") if r}


def _lay(rels, files: dict[str, str], force: bool, old: dict[str, str]) -> int:
    """Copy framework-data's copy of each path into the workspace. Unless
    `force`, a file the job changed since `old` is left alone."""
    n = 0
    keep = _keep()
    for rel in rels:
        if rel in keep:
            continue
        dst = ROOT / rel
        mine = _blob(dst)
        if not force and mine is not None and mine != old.get(rel):
            continue                      # the job changed it; its save carries it
        if rel in files:
            if mine == files[rel]:
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(FD / rel, dst)
            n += 1
        elif mine is not None and rel in old:
            dst.unlink()                  # removed in framework-data (e.g. a refreeze)
            n += 1
    return n


def pull() -> str:
    """Lay the checked-out framework-data over the workspace (all of it)."""
    if not enabled():
        return "framework-data: not checked out, workspace left as is"
    head = _head()
    files = _tree(head)
    n = _lay(files, files, True, {})
    _store_base(head, files)
    return f"framework-data: {len(files)} files, {n} laid over the workspace (source: {_source()})"


def refresh() -> str:
    """Fetch the newest framework-data and lay it over. For a loop's new round,
    right after it reset the workspace to framework's main (which, until the
    data leaves framework, puts framework's copies back): framework-data wins."""
    if not enabled():
        return "framework-data: not checked out"
    base, old = _load_base()
    if _git("fetch", "-q", "origin", "main").returncode != 0:
        return "framework-data: fetch failed, kept the last copy"
    _git("reset", "-q", "--hard", "FETCH_HEAD")
    head = _head()
    files = _tree(head)
    n = _lay(set(files) | set(old), files, True, old)
    _store_base(head, files)
    return f"framework-data: refreshed, {n} file(s) updated"


def on_main(rel: str) -> bool | None:
    """Is `rel` on framework-data's main right now? None: can't tell (no
    checkout, or the fetch failed). For the board's "sent" duplicate guard."""
    if not enabled() or _git("fetch", "-q", "origin", "main").returncode != 0:
        return None
    return _git("cat-file", "-e", f"FETCH_HEAD:{rel}").returncode == 0


def _walk(paths) -> set[str]:
    rels = set()
    for p in paths:
        p = p.strip("/")
        full = ROOT / p
        if full.is_file():
            rels.add(p)
        elif full.is_dir():
            for f in full.rglob("*"):
                if f.is_file():
                    rels.add(f.relative_to(ROOT).as_posix())
    return {r for r in rels if _is_data(r)}


def save(paths, message: str) -> str:
    """Commit what this job changed under `paths` to framework-data and push.
    Says exactly what happened (HR35): a push that did not land is never 'saved'."""
    if not enabled():
        return "framework-data: not checked out, nothing saved there"
    base, old = _load_base()
    if not base:
        return "framework-data: NOT SAVED — no pull recorded in this job"
    prefixes = tuple(p.strip("/") + "/" for p in paths)
    in_scope = lambda r: r in paths or r.startswith(prefixes)  # noqa: E731
    changed = {r for r in _walk(paths) if _blob(ROOT / r) != old.get(r)}
    gone = {r for r in old if in_scope(r) and not (ROOT / r).exists()}
    if len(gone) > MAX_GONE:
        # a refreeze removes a file or two; dozens missing at once means the
        # workspace lost them (framework untracking the data, a git reset) — keep them
        print(f"::warning::framework-data: {len(gone)} files missing from the workspace, NOT deleting them")
        gone = set()
    if not changed and not gone:
        return "framework-data: nothing new to save"
    # commit on the commit the job read, so the rebase below is a real 3-way merge
    _git("reset", "-q", "--hard", base)
    for r in changed:
        dst = FD / r
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / r, dst)
    for r in gone:
        (FD / r).unlink(missing_ok=True)
    _git("add", "-A", "--", *sorted(changed | gone))
    if _git("diff", "--staged", "--quiet").returncode == 0:
        return "framework-data: nothing new to save"
    _git("commit", "-q", "-m", message)
    saved = False
    for attempt in range(1, 6):
        if _git("fetch", "-q", "origin", "main").returncode == 0:
            x = ["-X", "theirs"] if attempt >= 3 else []   # 3rd try on: this run's copy wins
            if _git("rebase", "-q", *x, "FETCH_HEAD").returncode != 0:
                _git("rebase", "--abort")
                time.sleep(attempt * 3)
                continue
        if _git("push", "-q", "origin", "HEAD:main").returncode == 0:
            saved = True
            break
        time.sleep(attempt * 3)
    if not saved:
        return f"framework-data: NOT SAVED after {attempt} tries ({len(changed | gone)} file(s))"
    # bring in what others pushed meanwhile, except files this job changed since
    head = _head()
    files = _tree(head)
    mine = {r: _blob(ROOT / r) for r in changed}
    _lay(set(files) | set(old), files, False, {**old, **mine})
    _store_base(head, files)
    return f"framework-data: saved {len(changed | gone)} file(s) (try {attempt})"


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in ("pull", "refresh", "save", "has"):
        print(__doc__)
        return 2
    if argv[0] == "has":                  # exit 0: on framework-data's main; 1: not; 2: can't tell
        r = on_main(argv[1])
        return 2 if r is None else (0 if r else 1)
    if argv[0] == "pull":
        print(pull())
        return 0
    if argv[0] == "refresh":
        print(refresh())
        return 0
    if len(argv) < 3:
        print("usage: fdata.py save MESSAGE PATH...")
        return 2
    msg = save(argv[2:], argv[1])
    print(msg)
    # a failed save is loud but never fails the run (the board may already be out);
    # FDATA_STRICT=1 makes it fail the step
    return 1 if "NOT SAVED" in msg and os.environ.get("FDATA_STRICT") == "1" else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
