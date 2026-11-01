"""
NO FORCED PICKS + SHORT 3-LEG SLIPS (Architect 2026-11-01, improvement plan point 3: "do option 1 and 3,
they work hand in hand").

31 Oct: 28 board singles came from games whose safest outcome (mostly Over 1.5) was priced under the
1.20 floor. The board then forced another 1.20+ market (Under 4.5/5.5, Double Chance, team goals,
handicaps): 21/28 won, -2.09 units at 1 unit each. Over 1.5 itself on those games: -1.73.

1. NO FORCED PICKS (run_daily's selection loop): when the game's safest outcome the model backs is
   under 1.20, a 1.20-2.00 market is kept only when its chance beats SportyBet's break-even
   (1 / price) by FORCED_EDGE; with none left the game gets no single.
2. SHORT 3-LEG SLIPS (build): those sub-1.20 legs the model backs best (chance >= LEG_MIN and
   LEG_EDGE over break-even), one per game, three to a slip inside one kickoff window, combined
   odds >= SLIP_MIN_ODDS. Booked on SportyBet, shown on the board and graded (picks ledger
   section "short3"), PAPER: no bot stakes them until the Architect approves (like every new
   slip type since 2026-10-31).
"""
from __future__ import annotations

from engine.slate import DEPLOY_ODDS_MIN

SHORT_MIN_PRICE = 1.05      # below this a leg adds nothing to a slip
FORCED_EDGE = 0.05          # a fallback market's chance - 1/price
LEG_MIN = 0.85              # a short leg's chance
LEG_EDGE = 0.02             # a short leg's chance - 1/price
SLIP_LEGS = 3
SLIP_MIN_ODDS = 1.30
MAX_SLIPS = 6


def is_short_price(price) -> bool:
    return price is not None and SHORT_MIN_PRICE <= price < DEPLOY_ODDS_MIN


def safest_is_short(short_legs: list, cands: list) -> bool:
    """The model's likeliest outcome on the ladder is priced under the floor."""
    if not short_legs or not cands:
        return False
    return max(w for w, _k, _p in short_legs) >= max(c[0] for c in cands)


def with_edge(cands: list) -> list:
    """Candidates (chance, ev, key, model, market, quote) beating break-even by FORCED_EDGE."""
    return [c for c in cands if c[5] is not None and c[5].price
            and c[0] - 1.0 / c[5].price >= FORCED_EDGE]


def best_leg(bf):
    """(chance, key, price) of the game's strongest short leg, or None."""
    legs = [x for x in getattr(bf, "short_legs", None) or []
            if x[0] >= LEG_MIN and x[0] - 1.0 / x[2] >= LEG_EDGE]
    return max(legs, default=None)


def build(board: list) -> list[tuple]:
    """[("Short-3 #n", [(bf, pick, chance, key, price)] * 3, combined chance)], strongest first."""
    from engine import cohorts
    from engine import markets as mkt
    legs = []
    for bf in board:
        p = getattr(bf, "probs", None)
        x = best_leg(bf)
        if p is None or x is None:
            continue
        ch, key, price = x
        legs.append((bf, mkt.display(key, p.home_team, p.away_team), ch, key, price))
    legs.sort(key=lambda r: -r[2])
    out = []
    for cid, merged, group in cohorts.buckets(legs, lambda b: len(b) >= SLIP_LEGS):
        group = sorted(group, key=lambda r: -r[2])
        while len(group) >= SLIP_LEGS and len(out) < MAX_SLIPS:
            slip, group = group[:SLIP_LEGS], group[SLIP_LEGS:]
            odds = chance = 1.0
            for r in slip:
                odds *= r[4]
                chance *= r[2]
            if odds < SLIP_MIN_ODDS:
                continue
            cohorts.remember(slip, cid, merged)
            out.append((f"Short-3 #{len(out) + 1}", slip, chance))
    return out
