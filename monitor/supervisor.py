"""
SUPERVISOR — the olp-xdv-supervisor agent's daily check, run automatically
after every board run (Architect 2026-10-04: "put all the agents to work").

.github/workflows/supervisor.yml starts this when daily.yml finishes. It
looks at what the run actually left behind on main — not at what "should"
have happened — and sends the Architect ONE Telegram status:

  * the board run's own conclusion;
  * the day's board, bet365 board and sent marker exist;
  * the board carries a Run ID (HR59);
  * the picks: how many, how many market families, the largest family's
    share (one family on most picks = every slip is the same bet), main and
    alternative-market codes booked (orders 5, 31), NO-DATA fixtures;
  * the last tests.yml run on main, the latest watchdog and pre-kickoff
    (news.yml) runs.

Anything wrong is listed first with ⚠. It never changes the board, never
raises from the CLI (a supervisor that crashes is just more silence) and
reads only files and the GitHub API.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

BOARDS = ROOT / "output" / "boards"
PICKS = ROOT / "output" / "picks"
API = "https://api.github.com/repos/{repo}/actions/workflows/{wf}/runs?per_page=5{q}"
ONE_FAMILY_WARN = 0.75      # one market family on 75%+ of the picks


def latest_slot(boards: Path = BOARDS) -> tuple[str, str] | None:
    """(date, slot) of the newest sent marker, by the UTC time inside it."""
    best = None
    for m in boards.glob("sent_*_*"):
        parts = m.name.split("_")
        if len(parts) != 3:
            continue
        stamp = m.read_text(encoding="utf-8").strip()
        if best is None or stamp > best[0]:
            best = (stamp, parts[1], parts[2])
    return (best[1], best[2]) if best else None


def pick_stats(day: str, picks: Path = PICKS) -> dict:
    """Counts from the day's picks ledger (what the board recommended)."""
    from engine.learning import family
    path = picks / f"picks_{day}.json"
    if not path.exists():
        return {}
    doc = json.loads(path.read_text(encoding="utf-8"))
    singles = doc.get("singles", [])
    fams = Counter(family(s.get("market")) for s in singles)
    top = fams.most_common(1)[0] if fams else ("—", 0)
    slips = doc.get("accas", []) + doc.get("safe3", []) + doc.get("megas", [])
    alts = doc.get("alts", [])
    return {"picks": len(singles), "families": len(fams), "top_family": top[0],
            "top_share": top[1] / len(singles) if singles else 0.0,
            "single_codes": sum(1 for s in singles if s.get("code")),
            "slips": len(slips), "slip_codes": sum(1 for s in slips if s.get("code")),
            "alts": len(alts), "alt_codes": sum(1 for a in alts if a.get("code"))}


def board_facts(day: str, boards: Path = BOARDS) -> dict:
    path = boards / f"board_{day}.txt"
    if not path.exists():
        return {"board": False}
    text = path.read_text(encoding="utf-8")
    nd = re.search(r"(\d+) fixture\(s\) unresolved — NO DATA", text)
    return {"board": True,
            "run_id": bool(re.search(r"Run ID: OLPXDV-\d{8}-\d{4}-[0-9a-f]{6}", text)),
            "no_data": int(nd.group(1)) if nd else 0,
            "bet365": (boards / f"bet365_{day}.txt").exists()}


def _get(url: str, token: str) -> dict:
    req = urllib.request.Request(url, headers={  # noqa: S310 (fixed https URL)
        "Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"})
    with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310 (fixed https URL)
        return json.load(r)


def last_run(repo: str, token: str, wf: str, branch: str | None = "main") -> str:
    """'success' / 'failure' / 'in_progress' / 'none' / 'unknown' for a workflow."""
    try:
        q = f"&branch={branch}" if branch else ""
        runs = _get(API.format(repo=repo, wf=wf, q=q), token).get("workflow_runs", [])
        if not runs:
            return "none"
        r = runs[0]
        return r.get("conclusion") or r.get("status") or "unknown"
    except Exception:  # noqa: BLE001 — a status we can't read is said, not guessed
        return "unknown"


def report(day: str, slot: str, run_conclusion: str, facts: dict, stats: dict,
           runs: dict[str, str], subscribers: int | None = None) -> str:
    """The one Telegram status. Problems first, each with ⚠.

    subscribers: how many subscriber chats the TELEGRAM_SUBSCRIBER_CHAT_IDS
    secret holds (order 33); None = not checked. Zero is a problem: the
    Architect wants the subscribers to get every board."""
    bad: list[str] = []
    ok: list[str] = []
    if subscribers is not None:
        (ok if subscribers else bad).append(
            f"subscribers: {subscribers} chat(s) get every message except the bet365 board"
            if subscribers else
            "subscribers: none — the TELEGRAM_SUBSCRIBER_CHAT_IDS secret is empty or "
            "not a repository secret, so only your chat gets the board")
    (ok if run_conclusion == "success" else bad).append(f"board run: {run_conclusion}")
    if not facts.get("board"):
        bad.append(f"no board saved for {day}")
    else:
        (ok if facts["run_id"] else bad).append("Run ID " + ("present" if facts["run_id"]
                                                             else "MISSING (HR59)"))
        (ok if facts["bet365"] else bad).append("bet365 board " + ("saved" if facts["bet365"]
                                                                   else "MISSING"))
        if facts["no_data"]:
            bad.append(f"{facts['no_data']} fixture(s) NO DATA")
    if stats:
        n = stats["picks"]
        ok.append(f"{n} pick(s) across {stats['families']} market type(s)")
        if n >= 4 and stats["top_share"] >= ONE_FAMILY_WARN:
            bad.append(f"{stats['top_share']:.0%} of picks are {stats['top_family']} — "
                       f"the slips are close to one bet")
        line = (f"codes: {stats['single_codes']}/{n} singles, "
                f"{stats['slip_codes']}/{stats['slips']} slips, "
                f"{stats['alt_codes']}/{stats['alts']} alt accas")
        missing = (stats["single_codes"] < n or stats["slip_codes"] < stats["slips"]
                   or stats["alt_codes"] < stats["alts"])
        (bad if missing else ok).append(line)
    for wf, label in (("tests.yml", "tests on main"), ("watchdog.yml", "watchdog"),
                      ("news.yml", "pre-kickoff check")):
        if wf not in runs:          # no API access (local run): not checked, not guessed
            continue
        st = runs[wf]
        (ok if st in ("success", "in_progress", "queued", "none") else bad).append(
            f"{label}: {st}")
    head = (f"🛡 SUPERVISOR · {day} {slot} — "
            + ("ALL CLEAR" if not bad else f"{len(bad)} issue(s)"))
    return "\n".join([head] + [f"⚠ {b}" for b in bad] + [f"✓ {o}" for o in ok])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="OLP XDV supervisor status")
    ap.add_argument("--run-conclusion", default="unknown",
                    help="conclusion of the daily.yml run that triggered this")
    ap.add_argument("--no-send", action="store_true")
    a = ap.parse_args(argv)
    try:
        slot = latest_slot()
        if slot is None:
            day, name = "?", "?"
            facts, stats = {"board": False}, {}
        else:
            day, name = slot
            facts, stats = board_facts(day), pick_stats(day)
        repo, token = os.environ.get("GITHUB_REPOSITORY", ""), os.environ.get("GITHUB_TOKEN", "")
        runs = ({wf: last_run(repo, token, wf, None if wf != "tests.yml" else "main")
                 for wf in ("tests.yml", "watchdog.yml", "news.yml")}
                if repo and token else {})
        from output import notify
        text = report(day, name, a.run_conclusion, facts, stats, runs,
                      subscribers=len(notify.subscriber_chats()))
    except Exception as e:  # noqa: BLE001
        text = f"🛡 SUPERVISOR — could not complete its check ({e})"
    print(text)
    if not a.no_send:
        from output import notify
        sent, notes = notify.send_everyone(text)    # Architect + subscribers (order 33)
        print("status sent" if sent else "status NOT sent")
        print("\n".join(notes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
