"""
STUDY RECORD — how the study boards' stated chances have held up (Architect
2026-10-13: "use the high-chance study pick record as a warning ... but I'm
not stopping any markets").

Every graded study day (data/study/<date>/grades.json + engine_board.json)
gives, per study pick, the engine's stated chance to win and what happened.
Grouped by stated chance, that is the record a new study pick of the same
chance stands on. A warning only: no pick is dropped or changed by it.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
STUDY = ROOT / "data" / "study"
BANDS = ((0.50, 0.65), (0.65, 0.75), (0.75, 0.85), (0.85, 1.01))


def picks(folder: Path = STUDY) -> list[dict]:
    """[{date, match, fam, stated, result}] for every graded study pick."""
    out = []
    for day in sorted(p for p in folder.iterdir() if p.is_dir()):
        g, b = day / "grades.json", day / "engine_board.json"
        if not (g.exists() and b.exists()):
            continue
        stated = {leg["match"]: leg["pick"] for leg in json.loads(b.read_text(encoding="utf-8"))["legs"] if leg["pick"]}
        for leg in json.loads(g.read_text(encoding="utf-8"))["study"]["legs"]:
            p = stated.get(leg["match"])
            if p and leg["result"] in ("won", "lost"):
                out.append({"date": day.name, "match": leg["match"], "fam": p["fam"],
                            "stated": float(p["win"]), "result": leg["result"]})
    return out


def band_of(chance: float) -> tuple[float, float] | None:
    return next((b for b in BANDS if b[0] <= chance < b[1]), None)


def record(rows: list[dict]) -> dict[tuple[float, float], tuple[int, int, float]]:
    """{band: (picks, won, average stated chance)}."""
    out = {}
    for b in BANDS:
        rs = [r for r in rows if b[0] <= r["stated"] < b[1]]
        if rs:
            out[b] = (len(rs), sum(r["result"] == "won" for r in rs), sum(r["stated"] for r in rs) / len(rs))
    return out


def warning(chance: float, rows: list[dict] | None = None) -> str:
    """One line for a study pick of this stated chance: how earlier study picks
    stated in the same band landed. '' when there is no graded record yet."""
    rows = picks() if rows is None else rows
    b = band_of(chance)
    rec = record(rows).get(b) if b else None
    if not rec:
        return ""
    n, won, avg = rec
    gap = won / n - avg
    flag = "⚠ " if gap <= -0.10 else ""
    return f"{flag}study picks stated {b[0]:.0%}–{min(b[1], 1):.0%}: landed {won}/{n} ({won / n:.0%}) vs {avg:.0%} stated"


def summary(rows: list[dict] | None = None) -> list[str]:
    rows = picks() if rows is None else rows
    days = sorted({r["date"] for r in rows})
    out = [f"STUDY RECORD ({len(rows)} graded study picks, {', '.join(days) or 'none yet'})"]
    for b, (n, won, avg) in record(rows).items():
        out.append(f"  stated {b[0]:.0%}–{min(b[1], 1):.0%}: {won}/{n} landed ({won / n:.0%}) vs {avg:.0%} stated")
    return out
