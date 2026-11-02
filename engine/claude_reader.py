"""
CLAUDE READER — Claude as a fact-sheet member (Architect 2026-11-02: "use you as a reader").
RECORDED ONLY, like the fact sheet itself. Nothing here selects, stakes or moves a chance.

The free models kept running out (Gemini 429 all evening on 01-11) and no fact was ever agreed by
two of them. Claude runs on the Architect's PC, on the Claude subscription (no API token), once per
board: scripts/claude-brain.ps1 asks this module what is still unread, gives Claude the prompt with
the web-search tool, and hands the answer back here. The answers are saved to
output/facts/claude_<date>.json and folded into facts_<date>.json as one more member
(fact_sheet.add_outside). A fact still needs two members: Claude plus one other, never Claude alone.

    python -m engine.claude_reader --pending          # dates whose board Claude has not read yet
    python -m engine.claude_reader --prompt 2026-11-02 > prompt.txt
    python -m engine.claude_reader --save 2026-11-02 < answer.txt
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Optional

from engine import fact_sheet as FS

NAME = "claude"
MAX_FIXTURES = 20             # the board's singles first, then rated games, so one run stays small
EVIDENCE_CHARS = 700
# Team news lands close to kick-off: the 01:52 reading of the 2 Nov board found nothing anywhere. So a
# board is read again every READ_EVERY_H hours while a game kicks off within SOON_H hours, and those
# re-reads ask only about the games that are near.
READ_EVERY_H = 4
SOON_H = 6

PROMPT = """You are the fact-checking reader of a football betting framework. For each fixture below,
SEARCH THE WEB for today's team news (injuries, suspensions, expected line-ups), the previous match
of each team, the league situation, the weather forecast and the referee. Fill the fact sheet from
what you find. Other models' evidence is shown when there is some: check it, do not copy it. Two
fields are stable facts you may answer from general knowledge: "derby" and "away_long_travel".
Every other field must come from a source you found today; when you are not sure, null. A wrong
fact is worse than a null.
""" + FS.FIELD_DOC + """
Also give "evidence": 1-3 short sentences of what you found, each naming its source.
Return JSON only, no prose before or after:
{"fixtures": [{"id": <id>, "evidence": "...", <fields>}]}

FIXTURES:
"""


def facts_path(day: str) -> Path:
    return FS.OUT_DIR / f"facts_{day}.json"


def picks_path(day: str) -> Path:
    return FS.LEDGER_DIR / f"picks_{day}.json"


def _load(p: Path) -> Optional[dict]:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _future(fx: dict, now: datetime) -> bool:
    try:
        k = datetime.fromisoformat(str(fx.get("kickoff_utc")).replace("Z", "+00:00"))
    except ValueError:
        return True           # no kick-off time: read it rather than miss it
    # rated games carry kick-offs without an offset; they are UTC (2026-11-02 01:24: TypeError)
    return (k if k.tzinfo else k.replace(tzinfo=UTC)) > now


def _kickoff(fx: dict) -> Optional[datetime]:
    try:
        k = datetime.fromisoformat(str(fx.get("kickoff_utc")).replace("Z", "+00:00"))
    except ValueError:
        return None
    return k if k.tzinfo else k.replace(tzinfo=UTC)


def _reading(day: str, picks: dict) -> dict:
    """Claude's saved reading of THIS board ({} when none, or of an older board)."""
    mine = _load(FS.outside_path(day, NAME)) or {}
    return mine if mine.get("picks_generated_at") == picks.get("generated_at") else {}


def _soon(fx: dict, now: datetime) -> bool:
    k = _kickoff(fx)
    return k is not None and now < k <= now + timedelta(hours=SOON_H)


def pending(now: Optional[datetime] = None) -> list[str]:
    """Today's and tomorrow's boards Claude should read now: never read, or last read READ_EVERY_H+ hours
    ago while one of its games kicks off within SOON_H hours."""
    now = now or datetime.now(UTC)
    out = []
    for d in (now.date(), now.date() + timedelta(days=1)):
        day = d.isoformat()
        picks = _load(picks_path(day))
        if not picks or not any(_future(s, now) for s in picks.get("singles") or []):
            continue
        mine = _reading(day, picks)
        if not mine:
            out.append(day)
            continue
        try:
            last = datetime.fromisoformat(str(mine.get("run_at")))
        except ValueError:
            last = now - timedelta(days=1)
        if now - last >= timedelta(hours=READ_EVERY_H) and any(_soon(fx, now) for fx in targets(picks, now)):
            out.append(day)
    return out


def targets(picks: dict, now: Optional[datetime] = None, soon_only: bool = False) -> list[dict]:
    """The fixtures Claude reads, numbered as the fact sheet numbers them: the singles first, then rated
    games not bet on; games already kicked off are skipped (their ids are kept)."""
    now = now or datetime.now(UTC)
    fxs = FS.fixtures((picks.get("singles") or []) + FS.rated_unbet(picks))
    return [fx for fx in fxs if (_soon(fx, now) if soon_only else _future(fx, now))][:MAX_FIXTURES]


def prompt(day: str) -> str:
    picks = _load(picks_path(day)) or {}
    singles = picks.get("singles") or []
    sheet = {f["fixture"]: f for f in (_load(facts_path(day)) or {}).get("fixtures") or []}
    news = FS.load_news(day)
    rows = []
    for fx in targets(picks, soon_only=bool(_reading(day, picks))):
        ev = str((sheet.get(fx["fixture"]) or {}).get("evidence") or "")
        if not ev or ev == "PENDING":
            # the framework's own FotMob check and news notes, as the free readers get them
            ev = "; ".join(x for x in (FS.fotmob_evidence(news, fx["fixture"]),
                                       FS.local_evidence(singles, fx["fixture"])) if x)
        row = {"id": fx["id"], "fixture": fx["fixture"], "league": fx.get("league"), "kickoff_utc": fx.get("kickoff_utc")}
        if ev:
            row["other_evidence"] = ev[:EVIDENCE_CHARS]
        rows.append(row)
    return PROMPT + json.dumps(rows, ensure_ascii=False, indent=1) + "\n"


def parse(text: str) -> list[dict]:
    """The fixtures list from Claude's answer (it may wrap the JSON in prose or a code fence)."""
    i, j = text.find("{"), text.rfind("}")
    if i < 0 or j <= i:
        return []
    try:
        doc = json.loads(text[i:j + 1])
    except ValueError:
        return []
    rows = doc.get("fixtures") if isinstance(doc, dict) else None
    return [r for r in rows or [] if isinstance(r, dict)]


def save(day: str, text: str, model: str = "") -> dict:
    """Save Claude's answers and fold them into the day's fact sheet. Returns the saved reading."""
    picks = _load(picks_path(day))
    if not picks:
        raise SystemExit(f"no ledger for {day}")
    by_id = {fx["id"]: fx["fixture"] for fx in FS.fixtures((picks.get("singles") or []) + FS.rated_unbet(picks))}
    old = _reading(day, picks)
    # a re-read asks only about the near games: keep the earlier answers for the rest
    answers, evidence = dict(old.get("fixtures") or {}), dict(old.get("evidence") or {})
    for r in parse(text):
        fx = by_id.get(r.get("id")) if isinstance(r.get("id"), int) else None
        if not fx:
            continue
        a = {k: FS.clean(k, r.get(k)) for k in FS.all_fields()}
        if any(v is not None for v in a.values()):
            answers[fx] = a
            if r.get("evidence"):
                evidence[fx] = str(r["evidence"])[:800]
    reading = {"date": day, "picks_generated_at": picks.get("generated_at"),
               "run_at": datetime.now(UTC).isoformat(timespec="seconds"), "model": model or None,
               "recorded_only": True, "answered": len(answers), "asked": len(by_id), "reads": int(old.get("reads") or 0) + 1,
               "fixtures": answers, "evidence": evidence}
    FS.OUT_DIR.mkdir(parents=True, exist_ok=True)
    FS.outside_path(day, NAME).write_text(json.dumps(reading, indent=1, ensure_ascii=False), encoding="utf-8")
    doc = _load(facts_path(day))
    if doc and doc.get("picks_generated_at") == picks.get("generated_at"):
        merged = FS.merge_outside(doc, picks, {NAME: reading})
        facts_path(day).write_text(json.dumps(merged, indent=1, ensure_ascii=False), encoding="utf-8")
        reading["fields_agreed"] = merged["fields_agreed"]
    return reading


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pending", action="store_true")
    ap.add_argument("--prompt", metavar="DATE")
    ap.add_argument("--save", metavar="DATE")
    ap.add_argument("--model", default="")
    ap.add_argument("--file", help="write the prompt to / read the answer from this file (UTF-8)")
    a = ap.parse_args(argv)
    if a.pending:
        print("\n".join(pending()))
    elif a.prompt:
        text = prompt(a.prompt)
        if a.file:
            Path(a.file).write_text(text, encoding="utf-8")
        else:
            sys.stdout.reconfigure(encoding="utf-8")
            print(text)
    elif a.save:
        r = save(a.save, (Path(a.file).read_bytes() if a.file else sys.stdin.buffer.read()).decode("utf-8-sig", "replace"), a.model)
        print(f"claude reader {a.save}: answered {r['answered']}/{r['asked']} fixtures"
              + (f" · sheet now {r['fields_agreed']} fields agreed" if "fields_agreed" in r else " · no sheet yet"))
    else:
        ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
