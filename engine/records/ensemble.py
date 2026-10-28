"""
ENSEMBLE — to-do #7 idea 7 (RECORDED ONLY). The model's chance and the sharp market's chance,
blended with a weight learned OUT OF SAMPLE: only board singles graded on boards dated before
this one are used (log-loss over a grid of weights).

single["blend"] = {"w", "n_fit", "yes", "no"}
    w       weight on the model (1 - w on Matchbook's sharp_p); None until MIN_FIT graded picks
    yes     the blended chance of the pick; no = 1 - yes (the other side of the line)
Dixon-Coles / Elo / xG are not on the board single yet; they join the blend once recorded there.
"""
from __future__ import annotations

import math

from engine.records._common import graded_singles, num, singles

MIN_FIT = 100
GRID = [i / 20 for i in range(21)]
_W: dict[str, tuple[float | None, int]] = {}


def fit(rows: list[dict]) -> tuple[float | None, int]:
    pts: list[tuple[float, float, bool]] = []
    for r in rows:
        p, q = num(r.get("chance")), num(r.get("sharp_p"))
        if p is not None and q is not None:
            pts.append((p, q, r["result"] == "won"))
    if len(pts) < MIN_FIT:
        return None, len(pts)

    def loss(w: float) -> float:
        tot = 0.0
        for p, q, y in pts:
            b = min(max(w * p + (1 - w) * q, 1e-4), 1 - 1e-4)
            tot -= math.log(b if y else 1 - b)
        return tot
    return min(GRID, key=loss), len(pts)


def annotate_doc(doc: dict, target: str) -> str:
    if target not in _W:
        _W.clear()
        _W[target] = fit(graded_singles(target))
    w, n_fit = _W[target]
    for s in singles(doc):
        p, q = num(s.get("chance")), num(s.get("sharp_p"))
        yes = None if w is None or p is None or q is None else round(w * p + (1 - w) * q, 4)
        s["blend"] = {"w": w, "n_fit": n_fit, "yes": yes, "no": None if yes is None else round(1 - yes, 4)}
    return f"blend w={w} on {n_fit}"
