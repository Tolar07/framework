"""
LOOP UTIL — the discipline every all-day Actions loop needs, in one place.

GitHub's scheduler is the reason these loops exist. Measured on this repo on
2026-10-14: `commands.yml`'s hourly cron produced 6 runs in 35 hours;
`daily.yml`'s crons fired 3-7 hours late; `weekly.yml` ran 9 hours late two
Mondays running. A short job per cron tick therefore cannot be relied on.
Instead ONE job stays up and does the work on its own clock, and the crons
become backup STARTERS.

Three rules make that safe, learned the hard way by the pre-kickoff loop
(`monitor/news_loop.py`, which keeps its own copies and is deliberately left
alone — it is load-bearing and proven):

  one loop at a time   a run that finds an OLDER run of its own workflow still
                       going exits at once, so a dropped cron tick costs
                       nothing and a doubled one does no work twice;
  hand off, don't die  a job may run 6 hours; before that limit the loop starts
                       a fresh run of itself and ends, so the day is covered;
  save as you go       state is committed every few rounds, so a job that is
                       killed loses minutes rather than a whole day.

Used by `monitor/live_loop.py` and `monitor/commands_loop.py`.
"""
from __future__ import annotations

import json
import subprocess
import urllib.request
from datetime import timedelta

HANDOFF_AFTER = timedelta(hours=5, minutes=30)   # GitHub's job limit is 6 h
_API = "https://api.github.com/repos/{repo}/actions/workflows/{wf}"


def headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"}


def other_loop_running(wf: str, repo: str, token: str, my_run_id: int) -> bool:
    """True when an OLDER run of this workflow is still in progress."""
    url = _API.format(repo=repo, wf=wf) + "/runs?status=in_progress&per_page=20"
    req = urllib.request.Request(url, headers=headers(token))  # noqa: S310 (fixed https URL)
    with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310 (fixed https URL)
        runs = json.load(r).get("workflow_runs", [])
    return any(int(x["id"]) < my_run_id for x in runs)


def hand_off(wf: str, repo: str, token: str, inputs: dict | None = None) -> None:
    """Start a fresh run of this workflow, marked as a handoff."""
    body = json.dumps({"ref": "main", "inputs": {"handoff": "true", **(inputs or {})}}).encode()
    req = urllib.request.Request(_API.format(repo=repo, wf=wf) + "/dispatches", data=body,  # noqa: S310
                                 method="POST", headers=headers(token))
    with urllib.request.urlopen(req, timeout=30):  # noqa: S310 (fixed https URL)
        pass


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], capture_output=True, text=True)  # noqa: S603,S607 (fixed git args)


def save(paths: list[str], message: str) -> str:
    """Save to framework (while it still holds the data) and to the private
    framework-data (monitor/fdata.py). Both outcomes are reported."""
    from monitor import fdata
    # framework-data first: framework's pull below may drop files
    fd = fdata.save(paths, message) if fdata.enabled() else ""
    fw = _save_framework(paths, message)
    return f"{fw} · {fd}" if fd else fw


def _save_framework(paths: list[str], message: str) -> str:
    """Commit and push the named paths. Says exactly what happened — a push
    that could not land is never reported as saved (HR35)."""
    for p in paths:
        git("add", p)
    if git("diff", "--staged", "--quiet").returncode == 0:
        return "nothing new to save"
    git("commit", "-q", "-m", message)
    for _ in range(3):
        if git("push", "-q", "origin", "HEAD:main").returncode == 0:
            return "saved"
        if git("pull", "-q", "--rebase", "origin", "main").returncode != 0:
            git("rebase", "--abort")
            break
    return "NOT SAVED — main moved and a file conflicted; the next save carries it"
