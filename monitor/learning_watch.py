"""
LEARNING-LOOP WATCH (Architect 2026-10-28: the match-study "why" loop sat
stalled — every tactics lesson at test_n 0 — and no alarm fired).

A learning loop that produces no new TESTED evidence is a fault, not a quiet
day. Every loop the framework learns through is checked for fresh evidence:

  * FRESH: the newest evidence it wrote (a dated row / field) is no older than
    its allowance;
  * GREW: a counter of tested evidence is higher than it was `days` ago (read
    from git history, so no state is kept), and above 0.

Any stalled loop makes the run exit 1. learning_watch.yml runs this daily on
main, so a stall is a red run on main, which the matchbook-agent watchdog
turns into an `auto-fix` issue for the fixer (memory: watchdog fixes, not
reports). The table is also written to memory/learning_health.json for the
weekly self-improvement review (scripts/self_improve.py).

    python monitor/learning_watch.py [--days 3] [--no-git]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
HEALTH = ROOT / "memory" / "learning_health.json"


def _jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    return out


def _json(text: str | None) -> dict:
    try:
        return json.loads(text) if text else {}
    except ValueError:
        return {}


def _read(rel: str) -> str | None:
    p = ROOT / rel
    return p.read_text(encoding="utf-8") if p.exists() else None


def _git_old(rel: str, before: str) -> str | None:
    """The file as it stood on main at `before` (None: no history / no git)."""
    try:
        sha = subprocess.run(["git", "rev-list", "-1", f"--before={before}", "HEAD", "--", rel],
                             cwd=ROOT, capture_output=True, text=True, timeout=60).stdout.strip()
        if not sha:
            return None
        r = subprocess.run(["git", "show", f"{sha}:{rel}"], cwd=ROOT, capture_output=True,
                           text=True, encoding="utf-8", timeout=120)
        return r.stdout if r.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


# ── evidence readers ──────────────────────────────────────────────────────


def newest_graded_single() -> str | None:
    days = []
    for p in (ROOT / "output" / "picks").glob("picks_*.json"):
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if any(s.get("result") in ("won", "lost", "void") for s in doc.get("singles", [])):
            days.append(doc.get("date") or "")
    return max(days) if days else None


def newest_why() -> str | None:
    rows = [r for r in _jsonl(ROOT / "memory" / "why_record.jsonl") if r.get("class") != "UNCLASSED"]
    return max((r.get("date") or "") for r in rows) if rows else None


def newest_study() -> str | None:
    rows = _jsonl(ROOT / "memory" / "match_study_log.jsonl")
    return max((r.get("ko") or "")[:10] for r in rows) if rows else None


def tactics_tested(text: str | None) -> int:
    return sum(int(x.get("test_n") or 0) for x in _json(text).get("lessons", {}).values())


def postmortem_slips(text: str | None) -> int:
    return int(_json(text).get("slips_graded") or 0)


def reasoning_date() -> str | None:
    d = _json(_read("memory/reasoning_lessons.json")).get("football") or {}
    return d.get("date") if isinstance(d, dict) else None


def strategies_date() -> str | None:
    return (_json(_read("memory/strategies.json")).get("evaluated_at") or "")[:10] or None


def retrain_date() -> str | None:
    rows = _jsonl(ROOT / "memory" / "retrain_log.jsonl")
    return max((r.get("at") or "")[:10] for r in rows) if rows else None


def shadow_picks(text: str | None) -> int:
    return int(_json(text).get("picks") or 0)


# (name, what it learns, kind, reader, file for GREW, allowance days)
LOOPS: list[tuple] = [
    ("results learning", "engine/learning.py chance shift per family / league", "fresh",
     newest_graded_single, None, 3),
    ("match study", "monitor/match_study_run.py per-match expected v happened v why", "fresh",
     newest_study, None, 3),
    ("why record", "engine/why_record.py right / unlucky / outplayed / game-changed", "fresh",
     newest_why, None, 4),
    ("tactics lessons", "engine/tactics_study.py lessons tested on unseen matches", "grew",
     tactics_tested, "memory/tactics_lessons.json", 5),
    ("slip post-mortem", "engine/leg_postmortem.py slip-killer leg classes", "grew",
     postmortem_slips, "memory/leg_postmortem.json", 4),
    ("why-weighted shadow", "engine/why_learning.py walk-forward v the live learner", "grew",
     shadow_picks, "memory/why_learning_shadow.json", 4),
    ("reasoning lessons", "engine/reasoning.py daily market rules", "fresh", reasoning_date, None, 3),
    ("experiment engine", "engine/experiments.py strategies in shadow", "fresh", strategies_date, None, 3),
    ("nightly refit", "engine/retrain.py out-of-sample refit", "fresh", retrain_date, None, 3),
]


def check(today: date | None = None, use_git: bool = True,
          loops: list[tuple] | None = None, git_old: Callable = _git_old) -> list[dict]:
    today = today or datetime.now(UTC).date()
    out = []
    for name, what, kind, reader, rel, allow in (loops if loops is not None else LOOPS):
        row = {"loop": name, "what": what, "kind": kind, "allowance_days": allow}
        if kind == "fresh":
            newest = reader()
            row["newest"] = newest
            age = (today - date.fromisoformat(newest[:10])).days if newest else None
            row["age_days"] = age
            row["ok"] = age is not None and age <= allow
            row["note"] = (f"newest evidence {newest} ({age} d old)" if newest
                           else "no evidence at all")
        else:
            now_v = reader(_read(rel))
            row["now"] = now_v
            if not use_git:
                row["ok"] = now_v > 0
                row["note"] = f"{now_v} tested (history not checked)"
            else:
                old_text = git_old(rel, (today - timedelta(days=allow)).isoformat())
                old_v = reader(old_text) if old_text is not None else None
                row["then"] = old_v
                if old_v is None:          # younger than its allowance: judge on > 0 only
                    row["ok"] = now_v > 0
                    row["note"] = f"{now_v} tested (no history {allow} d back)"
                else:
                    row["ok"] = now_v > 0 and now_v > old_v
                    row["note"] = f"{old_v} -> {now_v} tested over {allow} d"
        out.append(row)
    return out


def render(rows: list[dict]) -> str:
    L = ["| loop | ok | evidence |", "|---|---|---|"]
    for r in rows:
        L.append(f"| {r['loop']} | {'yes' if r['ok'] else '**STALLED**'} | {r['note']} |")
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-git", action="store_true")
    ap.add_argument("--write", action="store_true", help="write memory/learning_health.json")
    a = ap.parse_args(argv)
    rows = check(use_git=not a.no_git)
    text = render(rows)
    print(text)
    bad = [r["loop"] for r in rows if not r["ok"]]
    if a.write:
        HEALTH.write_text(json.dumps({"checked": datetime.now(UTC).strftime("%Y-%m-%dT%H:%MZ"),
                                      "stalled": bad, "loops": rows}, indent=1), encoding="utf-8")
    summary = Path(__import__("os").environ.get("GITHUB_STEP_SUMMARY", "")) if \
        __import__("os").environ.get("GITHUB_STEP_SUMMARY") else None
    if summary:
        with summary.open("a", encoding="utf-8") as f:
            f.write("## Learning loops\n\n" + text + "\n")
    if bad:
        print(f"\nLEARNING LOOP STALLED: {', '.join(bad)} — no new tested evidence inside the allowance. "
              "Fix the loop at source (see each loop's module).")
        return 1
    print("\nall learning loops produced new tested evidence")
    return 0


if __name__ == "__main__":
    sys.exit(main())
