"""
ONE-DAY BOARD OVERRIDES (Architect 2026-11-01 23:40, "a mixture of the two" boards for 2 Nov).

config/day_overrides.json maps a board date to the changes the Architect approved for that day only:

  forced_edge  replaces engine/short_legs.FORCED_EDGE for the day (0.0 = a fallback market needs only to
               reach SportyBet's break-even, not beat it by 5 pts)
  no_single    home teams whose game gets no single that day (picks the Architect struck off)
  only_singles home teams whose games alone may get a single that day (the Architect's vetted list:
               a game the vetted board did not have, e.g. after a price move, gets none)

A date with no entry runs the normal rules. Entries are kept as the record of what changed and when.
"""
from __future__ import annotations

import json
from pathlib import Path

FILE = Path(__file__).resolve().parent.parent / "config" / "day_overrides.json"


def get(target: str, path: Path | None = None) -> dict:
    """The overrides for a board date, or {}."""
    try:
        data = json.loads((path or FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data.get(str(target)) or {}


def struck(ov: dict, home: str) -> bool:
    """The Architect struck this game's single off for the day."""
    h = (home or "").strip().lower()
    only = ov.get("only_singles")
    if only is not None and h not in {str(x).strip().lower() for x in only}:
        return True
    return any(h == str(x).strip().lower() for x in ov.get("no_single") or [])
