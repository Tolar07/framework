"""
ROUTINES on Telegram — /routines and /run <name> (Architect 2026-11-04: one place for every
scheduled routine, with next run, last result and run-now).

The view is built hourly in the private matchbook-agent repo (oracle_clock/routines.py,
routines.yml) with the Oracle clock's token. This side only reads it and queues requests, through
the matchbook-agent deploy key the bot grader already uses (secret BOT_LEDGER_KEY_MATCHBOOK, passed to
commands.yml as MB_DEPLOY_KEY):

    /routines      problems first, then every routine: status, last run, next run
    /run <name>    append {"name", "by", "at"} to oracle_clock/run_requests.jsonl and push; the push
                   starts routines.yml, which dispatches the matching schedule entry. The Architect's
                   chat only (the caller checks); only schedule entries can be started.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path

REPO = "git@github.com:Tolar07/matchbook-agent.git"
CLONE = Path(__file__).resolve().parent.parent / "data" / "cache" / "matchbook-agent"
VIEW = "oracle_clock/routines.json"
REQUESTS = "oracle_clock/run_requests.jsonl"
BAD = ("FAILED", "NOT STARTED", "UNREADABLE")


def _git(*args: str, key: Path, cwd: Path | None = None) -> subprocess.CompletedProcess:
    env = {**os.environ, "GIT_SSH_COMMAND": f'ssh -i "{key}" -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new'}
    return subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True, text=True, timeout=90)  # noqa: S603,S607


def _key() -> Path | None:
    text = os.environ.get("MB_DEPLOY_KEY", "").strip()
    if not text:
        return None
    path = Path(tempfile.gettempdir()) / "olp_mb_deploy_key"
    path.write_text(text + "\n", encoding="utf-8")
    path.chmod(0o600)
    return path


def fresh_clone(key: Path) -> Path | None:
    """matchbook-agent main, freshly fetched (shallow)."""
    if (CLONE / ".git").exists():
        ok = _git("fetch", "-q", "--depth", "1", "origin", "main", key=key, cwd=CLONE).returncode == 0
        ok = ok and _git("reset", "-q", "--hard", "origin/main", key=key, cwd=CLONE).returncode == 0
    else:
        CLONE.parent.mkdir(parents=True, exist_ok=True)
        ok = _git("clone", "-q", "--depth", "1", REPO, str(CLONE), key=key).returncode == 0
    return CLONE if ok else None


def _ago(iso: str | None, now: datetime) -> str:
    if not iso:
        return "—"
    m = int((now - datetime.fromisoformat(iso.replace("Z", "+00:00"))).total_seconds() // 60)
    if m < 0:
        return f"in {-m // 60}h{-m % 60:02d}"
    return f"{m}m ago" if m < 90 else f"{m // 60}h ago"


def format_view(doc: dict, now: datetime) -> str:
    rows = doc.get("routines") or []
    bad = [r for r in rows if str(r.get("status", "")).startswith(BAD)]
    lines = [f"ROUTINES — {len(rows)} scheduled, {len(bad)} need attention "
             f"(built {_ago(doc.get('built_at'), now)})", ""]
    if bad:
        lines.append("NEEDS ATTENTION")
        for r in bad:
            lines.append(f"✗ {r['name']} ({r['repo'].split('/')[-1]}) — {r['status']}, "
                         f"last {_ago((r.get('last') or {}).get('at'), now)}")
        lines.append("")
    for repo in sorted({r["repo"] for r in rows}):
        lines.append(repo.split("/")[-1].upper())
        for r in sorted((x for x in rows if x["repo"] == repo and x not in bad), key=lambda x: x["name"]):
            lines.append(f"· {r['name']} — {r['status']}, last {_ago((r.get('last') or {}).get('at'), now)}, "
                         f"next {_ago(r.get('next'), now)}")
    lines += ["", "Start one: /run <name>  (e.g. /run edge)"]
    return "\n".join(lines)


def cmd_routines(_: str = "", now: datetime | None = None) -> str:
    key = _key()
    if key is None:
        return "Routines: not configured here (MB_DEPLOY_KEY missing)."
    clone = fresh_clone(key)
    if clone is None or not (clone / VIEW).exists():
        return "Routines: the view could not be read (matchbook-agent oracle_clock/routines.json)."
    return format_view(json.loads((clone / VIEW).read_text(encoding="utf-8")), now or datetime.now(UTC))


def cmd_run(arg: str, now: datetime | None = None) -> str:
    name = " ".join(arg.split())
    if not name:
        return "Usage: /run <name>  — the names are in /routines (e.g. /run edge, /run daily slot=morning)"
    key = _key()
    if key is None:
        return "Run: not configured here (MB_DEPLOY_KEY missing)."
    clone = fresh_clone(key)
    if clone is None:
        return "Run: matchbook-agent could not be reached; nothing was started."
    now = now or datetime.now(UTC)
    path = clone / REQUESTS
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"name": name, "by": "telegram", "at": now.isoformat()}) + "\n")
    _git("config", "user.name", "olp-xdv-agent", key=key, cwd=clone)
    _git("config", "user.email", "olp-xdv-agent@users.noreply.github.com", key=key, cwd=clone)
    _git("add", REQUESTS, key=key, cwd=clone)
    _git("commit", "-q", "-m", f"routines: run {name} (Telegram)", key=key, cwd=clone)
    for _ in range(3):
        if _git("push", "-q", "origin", "HEAD:main", key=key, cwd=clone).returncode == 0:
            return (f"Requested: {name}. It starts within about a minute if it is a scheduled routine; "
                    "/routines shows the result after the run.")
        _git("pull", "-q", "--rebase", "origin", "main", key=key, cwd=clone)
    return f"Run: the request for {name} could not be saved (push refused); nothing was started."
