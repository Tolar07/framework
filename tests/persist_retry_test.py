"""
daily.yml's persist step must save the board's picks even when main moved and
a file conflicts (2026-10-15: the evening board's commit — picks_2026-10-15.json,
codes already sent — was dropped because the NBA line watch appended to the same
output/nba_markets file).

Offline: a bare "origin", the run's checkout, and a second writer pushing to the
same files in between. Runs the persist step's REAL shell text from daily.yml.
"""
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASH = shutil.which("bash")


def git(cwd, *args, check=True):
    r = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],  # noqa: S603,S607
                       cwd=cwd, capture_output=True, text=True)
    if check and r.returncode:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr}")
    return r.stdout


def persist_script() -> str:
    y = (ROOT / ".github" / "workflows" / "daily.yml").read_text(encoding="utf-8")
    block = y.split("- name: Persist the CLV log and board", 1)[1].split("\n      - name:", 1)[0]
    body = block.split("run: |", 1)[1]
    lines = [ln[10:] if ln.startswith(" " * 10) else ln.strip() for ln in body.splitlines()]
    return re.sub(r"\bsleep \$\(\(attempt \* 5\)\)", ":", "\n".join(lines))


def setup(d: Path):
    origin, seed, run, other = d / "origin.git", d / "seed", d / "run", d / "other"
    git(d, "init", "-q", "--bare", "-b", "main", str(origin))
    git(d, "clone", "-q", "-c", "core.autocrlf=false", str(origin), str(seed))
    shutil.copy(ROOT / ".gitattributes", seed / ".gitattributes")
    for p, text in {"output/nba_markets/2026-10-14.jsonl": '{"look": 1}\n', "clv/clv_log.json": '{"v": 0}\n',
                    "output/picks/.keep": "", "output/boards/.keep": "", "memory/.keep": "",
                    "backtest/NBA_MARKET_STUDY.md": "", "backtest/NBA_LADDER_STUDY.md": ""}.items():
        (seed / p).parent.mkdir(parents=True, exist_ok=True)
        (seed / p).write_text(text, encoding="utf-8")
    git(seed, "add", "-A")
    git(seed, "commit", "-qm", "seed")
    git(seed, "push", "-q", "origin", "main")
    git(d, "clone", "-q", "-c", "core.autocrlf=false", str(origin), str(run))
    git(d, "clone", "-q", "-c", "core.autocrlf=false", str(origin), str(other))
    return origin, run, other


def test_conflicting_nba_log_and_clv_still_save_the_picks():
    if not BASH:
        print("persist_retry_test: SKIP — no bash")
        return
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        origin, run, other = setup(d)
        # the board run: new picks, an appended NBA look, its CLV log
        (run / "output/picks/picks_2026-10-15.json").write_text('{"codes": ["SENT1"]}\n', encoding="utf-8")
        with open(run / "output/nba_markets/2026-10-14.jsonl", "a", encoding="utf-8") as f:
            f.write('{"look": "board"}\n')
        (run / "clv/clv_log.json").write_text('{"v": "board"}\n', encoding="utf-8")
        # meanwhile the line watch and another run push to the same files
        with open(other / "output/nba_markets/2026-10-14.jsonl", "a", encoding="utf-8") as f:
            f.write('{"look": "watch"}\n')
        (other / "clv/clv_log.json").write_text('{"v": "other"}\n', encoding="utf-8")
        git(other, "add", "-A")
        git(other, "commit", "-qm", "nba watch")
        git(other, "push", "-q", "origin", "main")
        r = subprocess.run([BASH, "-c", persist_script()], cwd=run, capture_output=True, text=True)  # noqa: S603
        out = r.stdout + r.stderr
        assert "saved to main" in out, out
        main = d / "check"
        git(d, "clone", "-q", "-c", "core.autocrlf=false", str(origin), str(main))
        assert (main / "output/picks/picks_2026-10-15.json").exists(), "the board's picks reached main"
        nba = (main / "output/nba_markets/2026-10-14.jsonl").read_text(encoding="utf-8")
        assert '"board"' in nba and '"watch"' in nba, f"union kept both sides' NBA looks: {nba}"
        assert '"board"' in (main / "clv/clv_log.json").read_text(encoding="utf-8"), "this run's CLV log kept"


if __name__ == "__main__":
    test_conflicting_nba_log_and_clv_still_save_the_picks()
    print("persist_retry_test: OK")
