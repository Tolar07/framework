"""
BOARD FOCUS — one competition gets the whole board for a day.

Architect 2026-10-12: "tomorrow's board should be a Champions League alone ...
pour the entire energy, resources and everything we've learned into Champions
League. Any other fixture or competition outside Champions League should be
studied and used for study purposes. So you do a paper bet on the fixtures
outside Champions League ... once the fixture comes back, you learn your
mistakes."

config/focus.json maps a board date to the competitions that board is for:
    {"2026-10-13": ["Champions League"]}
On such a day every fixture is still scanned, rated and recorded (the ledger's
"rated" list, which learning reads for every market family, yes and no side),
but only the focus competitions reach the board, its accas and its codes.
A fixture elsewhere that would have been a deploy pick is kept as a STUDY pick
(ledger "study", graded like a single) and never sent. A day with no entry is
an ordinary board.
"""
from __future__ import annotations

import json
from pathlib import Path

FOCUS_FILE = Path(__file__).resolve().parent.parent / "config" / "focus.json"


def leagues_for(day: str | None, path: Path = FOCUS_FILE) -> list[str]:
    """The focus competitions for a board date, or [] for an ordinary day."""
    if not day or not path.exists():
        return []
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    leagues = doc.get(day[:10]) if isinstance(doc, dict) else None
    return [str(x) for x in leagues] if isinstance(leagues, list) else []


def league_of(b) -> str:
    """The competition of a board fixture ("Home v Away (League)")."""
    return b.fixture.rsplit("(", 1)[-1].rstrip(")").strip()


def on_board(b, focus: list[str]) -> bool:
    """True when the fixture belongs on the day's board."""
    return not focus or league_of(b) in focus


def demote(board: list, focus: list[str]) -> int:
    """Turn every deploy pick outside the focus competitions into a study pick.
    Returns how many were demoted. No-op on an ordinary day."""
    if not focus:
        return 0
    n = 0
    for b in board:
        if getattr(b, "on_deploy_shortlist", False) and not on_board(b, focus):
            b.on_deploy_shortlist = False
            b.study_pick = True
            b.rejection_reason = f"study only — the board is {', '.join(focus)} today"
            n += 1
    return n
