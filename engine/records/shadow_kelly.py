"""
SHADOW KELLY — to-do #7 idea 6 (RECORDED ONLY: a number beside the stake, never the stake).

single["kelly"]:
    full        (p * price - 1) / (price - 1) with p = the board's chance (0 when negative)
    market      the same with p = Matchbook's de-margined chance (sharp_p)
    disagree    |chance - sharp_p|: how far the model and the sharp market are apart
    shrunk      KELLY_FRACTION * full * max(0, 1 - disagree / DISAGREE_ZERO): the more the model
                and the market disagree, the less of the model's Kelly survives
    no_edge     the other side of the line at the sharp book's fair price, by the model's chance:
                (1 - chance) / (1 - sharp_p) - 1 (> 0 the model would rather back the other side)
"""
from __future__ import annotations

from engine.records._common import num, singles

KELLY_FRACTION = 0.25
DISAGREE_ZERO = 0.10


def kelly(p: float | None, price: float | None) -> float | None:
    if p is None or not price or price <= 1:
        return None
    return round(max(0.0, (p * price - 1) / (price - 1)), 4)


def record(s: dict) -> dict:
    p, q, price = num(s.get("chance")), num(s.get("sharp_p")), num(s.get("price"))
    full, market = kelly(p, price), kelly(q, price)
    d = round(abs(p - q), 4) if p is not None and q is not None else None
    shrunk = None
    if full is not None:
        shrunk = round(KELLY_FRACTION * full * (max(0.0, 1 - d / DISAGREE_ZERO) if d is not None else 0.5), 4)
    no_edge = round((1 - p) / (1 - q) - 1, 4) if p is not None and q is not None and q < 1 else None
    return {"full": full, "market": market, "disagree": d, "shrunk": shrunk, "no_edge": no_edge}


def annotate_doc(doc: dict, target: str) -> str:
    n = 0
    for s in singles(doc):
        s["kelly"] = record(s)
        n += 1
    return f"kelly {n}"
