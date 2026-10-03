"""
HR30 — Numerical MES Required.
Every capital pick must carry a numerical Market Edge Score, including the
O1.5 floor market.

MES here is implemented as a breakeven TRIGGER PRICE: the minimum decimal
odds at which the bet is zero-EV against the model's probability. Since
"odds are ARCHITECT-FED" (Section 7.2 — no readable live-odds source exists),
this module never invents a market price; it only tells the Architect the
threshold to check the real price against on SportyBet/Bet365.

trigger_price = 1 / model_probability  (no margin — pure breakeven)

A small edge buffer can be added on top (edge_buffer_pct) to require the
market to be beating breakeven by a margin before it's shortlist-eligible —
this is a deliberate, visible parameter, not a hidden fudge.
"""
from __future__ import annotations


def trigger_price(model_prob: float, edge_buffer_pct: float = 0.0) -> float | None:
    """Returns None (never a fabricated number) if prob is not in (0, 1]."""
    if model_prob is None or not (0 < model_prob <= 1):
        return None
    breakeven = 1.0 / model_prob
    return round(breakeven * (1 + edge_buffer_pct / 100), 2)


def mes_numeric(model_prob: float, market_price: float | None) -> float | None:
    """Numerical MES = model_prob * market_price - 1 (expected value per unit
    staked, i.e. standard EV%). Returns None if market_price is not yet
    ARCHITECT-FED — HR30 requires an explicit exception note in that case,
    not a silently omitted number."""
    if market_price is None or model_prob is None:
        return None
    return round(model_prob * market_price - 1, 4)
