"""
PRICE SHOP — to-do #7 idea 10 (RECORDED ONLY). Which book pays more for the pick, and for the
other side of the line, from SportyBet's price and Matchbook's de-margined chance (sharp_p).

single["shop"]:
    sb_price        SportyBet's board price
    mb_price        Matchbook's fair price after commission: 1 + (1 / sharp_p - 1) * (1 - MB_COMMISSION)
    best            "sportybet" / "matchbook" for the pick ("yes")
    sb_edge         sb_price * sharp_p - 1: SportyBet's price against the sharp chance
    no_mb_price     the other side's fair Matchbook price (1 / (1 - sharp_p), after commission)
"""
from __future__ import annotations

from engine.records._common import num, singles

MB_COMMISSION = 0.02


def net(fair: float) -> float:
    return round(1 + (fair - 1) * (1 - MB_COMMISSION), 3)


def record(s: dict) -> dict | None:
    price, q = num(s.get("price")), num(s.get("sharp_p"))
    if not price or q is None or not 0 < q < 1:
        return None
    mb = net(1 / q)
    return {"sb_price": price, "mb_price": mb, "best": "sportybet" if price >= mb else "matchbook",
            "sb_edge": round(price * q - 1, 4), "no_mb_price": net(1 / (1 - q))}


def annotate_doc(doc: dict, target: str) -> str:
    n = 0
    for s in singles(doc):
        s["shop"] = record(s)
        n += s["shop"] is not None
    return f"shop {n}"
