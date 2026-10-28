"""Shared helpers for engine/records."""
from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PICKS_DIR = ROOT / "output" / "picks"
SLOTS = ("singles", "study", "singles_dropped")


def num(x) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v else None          # NaN -> None


def singles(doc: dict) -> Iterator[dict]:
    for slot in SLOTS:
        yield from (s for s in doc.get(slot) or [] if isinstance(s, dict))


def when(x) -> datetime | None:
    if not x:
        return None
    try:
        return datetime.fromisoformat(str(x).replace("Z", "+00:00"))
    except ValueError:
        return None


def graded_singles(before: str, picks_dir: Path = PICKS_DIR) -> list[dict]:
    """Board singles graded won/lost on boards dated before `before` (oldest first)."""
    out = []
    for f in sorted(picks_dir.glob("picks_*.json")):
        d = f.stem[len("picks_"):]
        if len(d) != 10 or d >= before:
            continue
        try:
            doc = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for s in doc.get("singles") or []:
            if s.get("result") in ("won", "lost") and num(s.get("price")):
                out.append({**s, "date": d})
    return out
