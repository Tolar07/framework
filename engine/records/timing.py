"""
TIMING — to-do #7 idea 3 (RECORDED ONLY). single["timing"]:

    hours_to_ko     hours from this board write to kick-off
    after_lineups   line-ups known (lineup_check filled, or within LINEUP_HOURS of kick-off)
    sb_move         SportyBet price now / at the first board - 1 (< 0: shortened, money came in)
    sharp_gap       Matchbook's de-margined chance - SportyBet's implied chance (1 / price)
    yes / no        the same gap read for the pick's side and for the other side of the line
    signal          "steam"  SportyBet shortened and the sharp book agrees (gap > 0)
                    "rlm"    reverse line move: SportyBet drifted out though the sharp book
                             rates the pick higher than SportyBet's price does
                    "fade"   SportyBet drifted out and the sharp book agrees
                    None     no move or no sharp price
"""
from __future__ import annotations

from engine.records._common import num, singles, when

LINEUP_HOURS = 1.0
MOVE = 0.01          # a move under 1% is noise


def timing(s: dict, written) -> dict:
    price, first, sharp = num(s.get("price")), num(s.get("first_price")), num(s.get("sharp_p"))
    ko = when(s.get("kickoff_utc"))
    hours = round((ko - written).total_seconds() / 3600, 2) if ko and written else None
    move = round(price / first - 1, 4) if price and first else None
    gap = round(sharp - 1 / price, 4) if sharp is not None and price else None
    signal = None
    if move is not None and gap is not None and abs(move) >= MOVE:
        if move < 0:
            signal = "steam" if gap > 0 else None
        else:
            signal = "rlm" if gap > 0 else "fade"
    return {"hours_to_ko": hours,
            "after_lineups": bool(s.get("lineup_check")) or (hours is not None and hours <= LINEUP_HOURS),
            "sb_move": move, "sharp_gap": gap,
            "yes": gap, "no": None if gap is None else round(-gap, 4),
            "signal": signal}


def annotate_doc(doc: dict, target: str) -> str:
    written = when(doc.get("generated_at"))
    n = 0
    for s in singles(doc):
        s["timing"] = timing(s, written)
        n += 1
    return f"timing {n}"
