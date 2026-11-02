"""
CLAUDE REVIEW — the brain's nightly review (Architect 2026-11-02: "the whole framework knows what it
is doing right and what it's doing wrong, and it can think with you as the brain").

Once a day, after the results are graded, Claude (on the Architect's PC, on the Claude subscription,
via scripts/claude-brain.ps1) reads the framework's own graded record: every reasoning verdict and
how it ended, the fact-sheet study, the learned weights and the reasoning step's own lessons. It
writes what the framework is doing right, what it is doing wrong, and at most MAX_LESSONS concrete,
testable lessons to memory/claude_review.json. The reasoning step reads those lessons before every
board (engine/reasoning.teaching), next to its own. Verdicts can only lower a stake (back / lower /
veto), so the review can make the bots more careful, never bolder. BRAIN_REVIEW=0 turns it off.

    python -m engine.claude_review --due                # prints "due" when today's review is missing
    python -m engine.claude_review --prompt > prompt.txt
    python -m engine.claude_review --save < answer.txt
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Optional

from engine import fact_sheet as FS
from engine import reasoning as R

ROOT = Path(__file__).parent.parent
REVIEW = ROOT / "memory" / "claude_review.json"
WEIGHTS = ROOT / "memory" / "learned_weights.json"
MAX_LESSONS = 8
MAX_ROWS = 120                # newest graded verdicts shown per sport
STALE_DAYS = 4                # older than this, the reasoning step stops reading the review

PROMPT = """You are the brain of a sports betting framework, doing the nightly review of its own
graded record. The framework bets football and NBA singles; a reasoning step (Gemini) gives every
pick a verdict: back (full stake), lower (0.75) or veto (0.5). Below is everything it has graded.

Work out, from the numbers, not from general betting wisdom:
1. RIGHT: what the framework is doing well (verdict types, markets, leagues, price bands that beat
   the de-margined market price). Name the counts.
2. WRONG: what is losing it money or being called wrong (e.g. vetoes that win as often as backs,
   a market that loses, a price band that is overconfident). Name the counts.
3. LESSONS: at most {n} short, concrete, testable rules for the reasoning step, each one backed by the
   record ("vetoes on team news alone won 11 of 14: only veto on a confirmed starter out"). A sample
   under 15 graded picks is a hypothesis: say so in the lesson. Never tell it to stake more.
4. FACTS: which fact-sheet facts are earning attention and which fields keep coming back empty.

Return JSON only, no prose before or after:
{{"right": ["..."], "wrong": ["..."], "lessons": ["..."], "facts": ["..."], "summary": "<one sentence>"}}

"""


def load(path: Path = REVIEW) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def due(today: Optional[str] = None, path: Path = REVIEW) -> bool:
    return load(path).get("date") != (today or datetime.now(UTC).date().isoformat())


def fresh_lessons(path: Path = REVIEW, today: Optional[str] = None) -> tuple[Optional[str], list[str]]:
    """(review date, lessons) when the review is recent enough to be read, else (None, [])."""
    rev = load(path)
    try:
        age = (datetime.fromisoformat(today or datetime.now(UTC).date().isoformat()).date()
               - datetime.fromisoformat(str(rev.get("date"))).date()).days
    except (TypeError, ValueError):
        return None, []
    if age > STALE_DAYS:
        return None, []
    return rev.get("date"), [str(x) for x in rev.get("lessons") or []][:MAX_LESSONS]


def _rows(sport: str) -> list[dict]:
    rows = R.graded_verdicts(sport)[-MAX_ROWS:]
    return [{"date": r.get("date"), "fixture": r.get("fixture"), "pick": r.get("pick"), "price": r.get("price"),
             "verdict": r.get("verdict"), "ai_chance": r.get("ai_chance"), "won": r.get("won"),
             "why": str(r.get("reasons") or "")[:120]} for r in rows]


def prompt() -> str:
    parts = [PROMPT.format(n=MAX_LESSONS)]
    for sport in ("football", "nba"):
        try:
            rows = _rows(sport)
        except Exception as e:  # noqa: BLE001 — one sport's record missing must not stop the review
            parts.append(f"{sport.upper()}: record unavailable ({type(e).__name__})\n")
            continue
        parts.append(f"{sport.upper()} SCORECARD:\n" + R.teaching(sport).strip() + "\n")
        parts.append(f"{sport.upper()} GRADED VERDICTS (newest {len(rows)}, oldest first):\n"
                     + "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n")
    try:
        parts.append("FACT-SHEET STUDY:\n" + json.dumps(FS.study(), ensure_ascii=False)[:4000] + "\n")
    except Exception as e:  # noqa: BLE001
        parts.append(f"FACT-SHEET STUDY: unavailable ({type(e).__name__})\n")
    try:
        parts.append("LEARNED WEIGHTS:\n" + WEIGHTS.read_text(encoding="utf-8")[:2000] + "\n")
    except OSError:
        pass
    old = load()
    if old.get("lessons"):
        parts.append(f"YOUR PREVIOUS REVIEW ({old.get('date')}) LESSONS (keep, rewrite or drop):\n"
                     + "\n".join(f"- {x}" for x in old["lessons"]) + "\n")
    return "\n".join(parts)


def parse(text: str) -> dict:
    i, j = text.find("{"), text.rfind("}")
    if i < 0 or j <= i:
        return {}
    try:
        doc = json.loads(text[i:j + 1])
    except ValueError:
        return {}
    return doc if isinstance(doc, dict) else {}


def save(text: str, model: str = "", path: Path = REVIEW) -> dict:
    doc = parse(text)
    lessons = [str(x).strip()[:300] for x in doc.get("lessons") or [] if str(x).strip()][:MAX_LESSONS]
    if not lessons:
        raise SystemExit("claude review: no lessons in the answer; the old review stays")
    rev = {"date": datetime.now(UTC).date().isoformat(), "run_at": datetime.now(UTC).isoformat(timespec="seconds"),
           "model": model or None, "recorded_only": False, "lowers_only": True,
           "right": [str(x)[:300] for x in doc.get("right") or []][:8],
           "wrong": [str(x)[:300] for x in doc.get("wrong") or []][:8],
           "lessons": lessons, "facts": [str(x)[:300] for x in doc.get("facts") or []][:6],
           "summary": str(doc.get("summary") or "")[:300]}
    path.write_text(json.dumps(rev, indent=1, ensure_ascii=False), encoding="utf-8")
    return rev


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--due", action="store_true")
    ap.add_argument("--prompt", action="store_true")
    ap.add_argument("--save", action="store_true")
    ap.add_argument("--model", default="")
    ap.add_argument("--file", help="write the prompt to / read the answer from this file (UTF-8)")
    a = ap.parse_args(argv)
    if a.due:
        print("due" if due() else "done")
    elif a.prompt:
        text = prompt()
        if a.file:
            Path(a.file).write_text(text, encoding="utf-8")
        else:
            sys.stdout.reconfigure(encoding="utf-8")
            print(text)
    elif a.save:
        r = save((Path(a.file).read_bytes() if a.file else sys.stdin.buffer.read()).decode("utf-8-sig", "replace"), a.model)
        print(f"claude review {r['date']}: {len(r['lessons'])} lessons · {r['summary']}")
    else:
        ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
