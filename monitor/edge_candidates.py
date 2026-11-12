"""
EDGE CANDIDATES -> the framework's decision making. Run after every trend study.

The Architect, 2026-11-12: "when the study is complete and all these trends are being mapped out, how is it going to
be integrated into the framework decision making?"

The path, every step automatic except money:
  1. STUDIES  backtest/trend_atlas_study.py (football), backtest/sport_atlas_study.py (every other sport),
              backtest/stat_lines_study.py (corners / cards / 1st-half lines) each list EDGE CANDIDATES: a trend rule
              that beat the real pre-match price on games it was NOT chosen on (100+ bets, 90% range above 0).
  2. THIS     a candidate seen for the first time opens one `self-improvement` issue (the PC builder builds it):
              daily paper picks for the rule on the day's real games, graded, registered with the experiment engine
              (engine/experiments.py) as a SHADOW strategy that counts only from the day it was written.
  3. ENGINE   the experiment engine scores it every day beside the live strategy on the same days. One that beats
              it on CLV and on return (100+ graded bets, one-sided z-test) is promoted where a slot can take it, or
              FLAGGED to the Architect where it can't (rules picking games the board doesn't hold).
  4. MONEY    stakes stay the Architect's (and the bots' order-51 decision layer inside its caps). Nothing here, or
              in the issue it opens, places, sizes or blocks a bet.
A candidate keeps one issue forever (memory/edge_candidates_seen.json); a later run that no longer finds it says so
in the summary, it does not reopen anything.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEEN = ROOT / "memory" / "edge_candidates_seen.json"
SOURCES = {
    "football trend atlas": (ROOT / "output" / "trend_atlas" / "study.json", "backtest/trend_atlas_study.py"),
    "sport atlas": (ROOT / "output" / "sport_atlas" / "study.json", "backtest/sport_atlas_study.py"),
    "stat lines": (ROOT / "output" / "stat_lines" / "candidates.json", "backtest/stat_lines_study.py"),
}


def key(source: str, c: dict) -> str:
    return "|".join(str(x) for x in (source, c.get("sport") or c.get("venue") or "", c.get("kind") or "",
                                     c.get("market"), c.get("side"), c.get("gap")))


def collect(sources: dict = SOURCES) -> list[tuple[str, str, dict]]:
    out = []
    for name, (path, study) in sources.items():
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for c in doc.get("candidates") or []:
            out.append((name, study, c))
    return out


def _pct(x) -> str:
    return "PENDING" if x is None else f"{100 * x:+.1f}%"


def issue(name: str, study: str, c: dict) -> tuple[str, str]:
    what = f"{c.get('sport') or c.get('venue') or ''} {c['market']} {str(c['side']).upper()} (trend gap {c['gap']})".strip()
    title = f"Edge candidate: {what} - paper picks + shadow strategy"
    body = (f"**Found by** `{study}` ({name}), judged on bets it was not chosen on: {c.get('hold_n')} bets, ROI "
            f"{_pct(c.get('hold_roi'))} (90% range {_pct(c.get('hold_lo'))} to {_pct(c.get('hold_hi'))}); chosen "
            f"period {c.get('disc_n')} bets, ROI {_pct(c.get('disc_roi'))}.\n\n"
            "**Build (record-only / shadow, monitor/edge_candidates.py step 2):**\n"
            "1. Daily paper picks for this rule on the day's real games with a real price (the same trend calculation "
            "and gap as the study, earlier games only), saved and graded like every other paper pick.\n"
            "2. Register it with the experiment engine (`engine/experiments.py`) as a SHADOW strategy counted from the "
            "day it is written (`since`), so the evidence that found it is never its test.\n"
            "3. The engine promotes or flags it on its own rule (100+ graded bets beating the live strategy on CLV and "
            "return). Stakes and money stay the Architect's: nothing here places, sizes or blocks a bet.\n")
    return title, body


def open_issue(title: str, body: str) -> str | None:
    """A framework `self-improvement` issue (built by the PC fixer). Only inside Actions."""
    if os.environ.get("GITHUB_ACTIONS") != "true":
        return None
    r = subprocess.run(["gh", "issue", "create", "-R", os.environ.get("GITHUB_REPOSITORY", "Tolar07/framework"),
                        "--label", "self-improvement", "-t", title, "-b", body], capture_output=True, text=True)
    return r.stdout.strip() or None


def run(sources: dict = SOURCES, seen_path: Path = SEEN, opener=open_issue, now: datetime | None = None) -> str:
    now = now or datetime.now(UTC)
    seen = json.loads(seen_path.read_text(encoding="utf-8")) if seen_path.exists() else {}
    cands = collect(sources)
    current = {key(n, c) for n, _, c in cands}
    opened = []
    for name, study, c in cands:
        k = key(name, c)
        if k in seen:
            continue
        title, body = issue(name, study, c)
        url = opener(title, body)
        seen[k] = {"first_seen": now.strftime("%Y-%m-%d"), "issue": url, "title": title}
        opened.append(title)
    seen_path.parent.mkdir(parents=True, exist_ok=True)
    seen_path.write_text(json.dumps(seen, indent=1), encoding="utf-8")
    gone = [v["title"] for k, v in seen.items() if k not in current]
    return (f"edge candidates: {len(cands)} now, {len(opened)} new issue(s)"
            + "".join(f" | NEW {t}" for t in opened)
            + (f" | {len(gone)} earlier candidate(s) not found this run" if gone else ""))


if __name__ == "__main__":
    print(run())
    sys.exit(0)
