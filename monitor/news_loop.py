"""
PRE-KICKOFF LOOP — runs news_check.py every 20 minutes, 09:00-20:40 UTC.

GitHub drops scheduled runs here: news.yml's 20-minute cron ran 6 times in
its first three days (2026-10-04 audit), so lineup alerts, price-drift alerts
and closing prices (orders 17, 20, 25) were almost always missing. Instead of
one short job per cron tick, ONE job now stays up and checks every 20 minutes:

  * daily.yml starts it after each board run before 20:00 UTC — the morning
    board is started on time by a Routine, so the loop is too;
  * a few cron ticks stay as a backup starter: a run that finds the loop
    already going exits at once;
  * a GitHub job may run 6 hours at most, so after HANDOFF_AFTER the loop
    starts a fresh news.yml run (marked as a handoff) and ends.

Each round pulls main first (the board may have been rebuilt), runs the check
and pushes the picks ledger straight away, so a lineup checked is saved and
never alerted twice.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

WINDOW = ((9, 0), (20, 40))          # UTC, first and last round
EVERY_MIN = 20
HANDOFF_AFTER = timedelta(hours=5, minutes=30)   # GitHub's job limit is 6 h
EARLIEST = timedelta(hours=4)    # never sit idle longer than this before 09:00
API = "https://api.github.com/repos/{repo}/actions/workflows/news.yml"


def _at(now: datetime, hm: tuple[int, int]) -> datetime:
    return now.replace(hour=hm[0], minute=hm[1], second=0, microsecond=0)


def in_window(now: datetime) -> bool:
    return _at(now, WINDOW[0]) <= now <= _at(now, WINDOW[1]) + timedelta(minutes=1)


def finished(now: datetime) -> bool:
    """Past today's last round: nothing more to do until tomorrow."""
    return now > _at(now, WINDOW[1]) + timedelta(minutes=1)


def next_round(now: datetime) -> datetime:
    """The next :00 / :20 / :40, or the window's start if it hasn't opened."""
    start = _at(now, WINDOW[0])
    if now < start:
        return start
    nxt = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
    while nxt.minute % EVERY_MIN:
        nxt += timedelta(minutes=1)
    return nxt


def should_hand_off(started: datetime, now: datetime, wake: datetime) -> bool:
    """Hand off when sleeping until `wake` would run past the job's limit."""
    return wake - started >= HANDOFF_AFTER and not finished(wake)


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"}


def other_loop_running(repo: str, token: str, my_run_id: int) -> bool:
    """An older news.yml run still in progress means a loop is already going."""
    url = API.format(repo=repo) + "/runs?status=in_progress&per_page=20"
    req = urllib.request.Request(url, headers=_headers(token))  # noqa: S310 (fixed https URL)
    with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310 (fixed https URL)
        runs = json.load(r).get("workflow_runs", [])
    return any(int(r["id"]) < my_run_id for r in runs)


def hand_off(repo: str, token: str) -> None:
    body = json.dumps({"ref": "main", "inputs": {"handoff": "true"}}).encode()
    req = urllib.request.Request(API.format(repo=repo) + "/dispatches", data=body,  # noqa: S310
                                 method="POST", headers=_headers(token))
    with urllib.request.urlopen(req, timeout=30):  # noqa: S310 (fixed https URL)
        pass


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], capture_output=True, text=True)  # noqa: S603,S607 (fixed git args)


def sync() -> None:
    """Start each round from the latest main (the board may have changed)."""
    _git("fetch", "-q", "origin", "main")
    _git("reset", "-q", "--hard", "origin/main")


def persist(now: datetime) -> str:
    """Save the round's lineup checks, drift and closing prices at once."""
    _git("add", "output/picks")
    if _git("diff", "--staged", "--quiet").returncode == 0:
        return "nothing to save"
    _git("commit", "-q", "-m", f"lineup check {now:%H:%M} [skip ci]")
    for _ in range(3):
        if _git("push", "-q", "origin", "HEAD:main").returncode == 0:
            return "saved"
        if _git("pull", "-q", "--rebase", "origin", "main").returncode != 0:
            _git("rebase", "--abort")
            break
    return "NOT SAVED — main moved and the picks file conflicted; the next round re-checks"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="OLP XDV pre-kickoff loop")
    ap.add_argument("--handoff", action="store_true",
                    help="started by the previous loop run — don't wait for it to end")
    a = ap.parse_args(argv)
    repo, token = os.environ.get("GITHUB_REPOSITORY", ""), os.environ.get("GITHUB_TOKEN", "")
    run_id = int(os.environ.get("GITHUB_RUN_ID", "0") or 0)
    started = datetime.now(UTC)
    if finished(started):
        print("after 20:40 UTC — today's pre-kickoff checks are done")
        return 0
    if next_round(started) - started > EARLIEST:
        print("too early — the morning board run starts the loop")
        return 0
    if not a.handoff and repo and token and other_loop_running(repo, token, run_id):
        print("a pre-kickoff loop is already running — nothing to do")
        return 0

    import news_check
    if a.handoff:                   # the previous run just did this round
        time.sleep(max(0.0, (next_round(started) - datetime.now(UTC)).total_seconds()))
    while True:
        now = datetime.now(UTC)
        if in_window(now):
            sync()
            try:
                print(f"[{now:%H:%M}Z] {news_check.run(now=now)}")
            except Exception as e:  # noqa: BLE001 — one bad round never ends the loop
                print(f"[{now:%H:%M}Z] round failed: {e}")
            print(f"[{now:%H:%M}Z] {persist(now)}")
        wake = next_round(datetime.now(UTC))
        if finished(wake):
            print("last round done")
            return 0
        if should_hand_off(started, now, wake):
            if repo and token:
                hand_off(repo, token)
                print("handed off to a fresh run (job time limit)")
            return 0
        time.sleep(max(0.0, (wake - datetime.now(UTC)).total_seconds()))


if __name__ == "__main__":
    raise SystemExit(main())
