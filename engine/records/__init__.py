"""
REASONING RECORDS — to-do #7 ideas 3-10, RECORDED ONLY (no stake, no threshold, no pick changes).

engine/picks_ledger.write_ledger calls annotate_doc(doc, target) once per board write. Every module
in this package whose name does not start with "_" is run in name order; each adds its own fields
to the board singles (single["timing"], single["kelly"], ...) or to the doc. A module that fails
is skipped with a note — the ledger is always written. Nothing on the board reads these fields to
pick or stake; each idea is measured out of sample first (docs/REASONING_IDEAS_AUDIT.md), and
wiring one into stakes needs the Architect's OK.

Markets are yes/no: every record weighs the pick's side and the other side of the same line.
"""
from __future__ import annotations

import importlib
import pkgutil


def annotate_doc(doc: dict, target: str) -> list[str]:
    notes = []
    for m in sorted(pkgutil.iter_modules(__path__), key=lambda m: m.name):
        if m.name.startswith("_"):
            continue
        try:
            mod = importlib.import_module(f"{__name__}.{m.name}")
            notes.append(f"{m.name}: {mod.annotate_doc(doc, target)}")
        except Exception as e:  # noqa: BLE001 — the ledger is always written
            notes.append(f"{m.name} skipped ({str(e)[:60]})")
    return notes
