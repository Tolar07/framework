"""
The duplicate guard's "sent" marker must reach main even when the run's
persist commit is dropped (2026-10-08: the 7 Oct evening board's commit lost
a rebase conflict on an NBA ladder file, the marker went with it, and the
00:24 UTC late cron sent the board to everyone a second time).

Offline: a bare "origin", the run's checkout, and a second workflow pushing
to the same append-only file in between — the 7 Oct sequence.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from monitor import push_marker as pm  # noqa: E402

MARKER = "output/boards/sent_2026-10-08_evening"
LADDER = "output/nba_ladders/2026-10-07.jsonl"


def git(cwd, *args, check=True):
    r = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],  # noqa: S603,S607
                       cwd=cwd, capture_output=True, text=True)
    if check and r.returncode:
        raise RuntimeError(f"git {args}: {r.stderr}")
    return r


def on_main(origin, path):
    return git(origin, "cat-file", "-e", f"main:{path}", check=False).returncode == 0


def setup(d: Path, union: bool):
    d.mkdir(parents=True)
    origin = d / "origin.git"
    git(d, "init", "-q", "--bare", "-b", "main", str(origin))
    seed = d / "seed"
    git(d, "clone", "-q", str(origin), str(seed))
    git(seed, "checkout", "-q", "-b", "main")
    (seed / "output/nba_ladders").mkdir(parents=True)
    (seed / "output/boards").mkdir(parents=True)
    (seed / LADDER).write_text('{"row": 0}\n')
    (seed / "output/boards/board_2026-10-07.txt").write_text("old board\n")
    if union:
        (seed / ".gitattributes").write_text("output/nba_ladders/*.jsonl merge=union\n")
    git(seed, "add", ".")
    git(seed, "commit", "-q", "-m", "seed")
    git(seed, "push", "-q", "origin", "main")
    run = d / "run"                       # the daily.yml checkout
    git(d, "clone", "-q", "-b", "main", str(origin), str(run))
    other = d / "other"                   # the NBA line watch, pushing meanwhile
    git(d, "clone", "-q", "-b", "main", str(origin), str(other))
    with (other / LADDER).open("a") as f:
        f.write('{"row": "watch"}\n')
    git(other, "commit", "-q", "-am", "nba watch")
    git(other, "push", "-q", "origin", "main")
    # The run: the NBA board appends to the same file; the board is delivered
    # and the marker written.
    with (run / LADDER).open("a") as f:
        f.write('{"row": "daily"}\n')
    (run / "output/boards/board_2026-10-08.txt").write_text("new board\n")
    (run / MARKER).write_text("2026-10-07T22:11:18Z\n")
    return origin, run


def persist(run):
    """daily.yml's persist step, as written before and after the fix."""
    git(run, "add", "output")
    git(run, "commit", "-q", "-m", "daily board")
    if git(run, "pull", "--rebase", "-q", "origin", "main", check=False).returncode:
        git(run, "rebase", "--abort", check=False)
    git(run, "push", "-q", "origin", "HEAD:main", check=False)


with tempfile.TemporaryDirectory() as d:
    # 1. The 7 Oct failure, reproduced: marker only in the persist commit.
    origin, run = setup(Path(d) / "before", union=False)
    persist(run)
    assert not on_main(origin, MARKER), \
        "reproduction: the conflict drops the persist commit and the marker with it"
    assert not on_main(origin, "output/boards/board_2026-10-08.txt")

with tempfile.TemporaryDirectory() as d:
    # 2. The fix: the marker goes to main on its own first, then the same
    # conflicting persist runs — the marker survives, so a late run skips.
    origin, run = setup(Path(d) / "after", union=False)
    assert pm.push_file(MARKER, "board sent [skip ci]", repo=run)
    assert on_main(origin, MARKER), "marker saved on its own, before the persist"
    assert git(run, "status", "--porcelain", "--", LADDER).stdout.strip(), \
        "the run's own checkout is left untouched for the persist step"
    persist(run)
    assert on_main(origin, MARKER), "the marker survives the dropped persist commit"
    assert git(run, "worktree", "list").stdout.count("\n") == 1, "temporary worktree removed"
    # Saving the same marker again is a no-op, not a second commit.
    head = git(origin, "rev-parse", "main").stdout
    assert pm.push_file(MARKER, "again", repo=run) and git(origin, "rev-parse", "main").stdout == head

with tempfile.TemporaryDirectory() as d:
    # 3. With the append-only ladder files merged as a union (.gitattributes),
    # the 7 Oct conflict does not happen: the whole persist commit is saved,
    # both workflows' rows are kept, and the identical marker merges cleanly.
    origin, run = setup(Path(d) / "union", union=True)
    assert pm.push_file(MARKER, "board sent [skip ci]", repo=run)
    persist(run)
    assert on_main(origin, "output/boards/board_2026-10-08.txt"), "persist commit saved"
    rows = git(origin, "show", f"main:{LADDER}").stdout
    assert '"watch"' in rows and '"daily"' in rows, "both workflows' ladder rows kept"
    assert on_main(origin, MARKER)

# The live repo carries the union rule and daily.yml saves the marker on its own.
attrs = (ROOT / ".gitattributes").read_text(encoding="utf-8")
assert "output/nba_ladders/*.jsonl merge=union" in attrs
wf = (ROOT / ".github/workflows/daily.yml").read_text(encoding="utf-8")
run_step = wf.split("- name: Run the daily board")[1].split("- name:")[0]
assert 'python monitor/push_marker.py "$MARKER"' in run_step, \
    "the marker is pushed right after delivery, in the run step"
persist_step = wf.split("- name: Persist the CLV log and board")[1].split("- name:")[0]
assert "git rebase --abort" in persist_step and "::warning::persist" in persist_step, \
    "a dropped persist commit is said, never silent"
print("✅ sent marker survives a dropped persist commit: OK")
