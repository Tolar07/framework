"""
HR30 — Numerical MES Required.
Every capital pick must carry a numerical Market Edge Score, including the
O1.5 floor market.

CANONICAL EDGE METRIC (Architect ratified 2026-08-19):
    edge = model_probability - market_implied_probability
    where market_implied_probability = 1 / decimal_odds

This is the probability-gap formulation (proposed 14 Aug 2026, now canonical).
The standard EV formula (model_prob * price - 1) is retained as `mes_numeric_ev`
for Kelly/staking calculations only — it is NOT the selection edge.

Trigger price (breakeven odds) remains: trigger = 1 / model_prob
"""
from __future__ import annotations
from typing import Optional


def market_implied_prob(market_price: float | None) -> float | None:
    """Implied probability from decimal odds: 1 / price. None if price is None or 0."""
    if market_price is None or market_price <= 0:
        return None
    return round(1.0 / market_price, 4)


def edge_diff(model_prob: float, market_price: float | None) -> float | None:
    """CANONICAL EDGE: probability difference = model_prob - implied_prob.
    Positive = model sees value the market doesn't. Negative = market disagrees.
    This is the selection metric for all market-gate decisions (ID405)."""
    if market_price is None or model_prob is None:
        return None
    implied = 1.0 / market_price
    return round(model_prob - implied, 4)


def mes_numeric_ev(model_prob: float, market_price: float | None) -> float | None:
    """Expected value per unit stake: model_prob * price - 1.
    RETENTION ONLY — for Kelly fraction, staking, CLV math.
    NOT the canonical edge for market selection (use edge_diff)."""
    if market_price is None or model_prob is None:
        return None
    return round(model_prob * market_price - 1, 4)


def trigger_price(model_prob: float | None, edge_buffer_pct: float = 0.0) -> float | None:
    """Breakeven decimal odds: 1 / model_prob. None if model_prob is None or 0.
    Optional edge buffer (pct) raises the required price above pure breakeven."""
    if model_prob is None or not (0 < model_prob <= 1):
        return None
    breakeven = 1.0 / model_prob
    return round(breakeven * (1 + edge_buffer_pct / 100), 2)


# Backward-compat alias — call sites that used mes_numeric() expecting EV
# now get the canonical edge_diff. If a call site genuinely needs EV for
# Kelly/staking, it must explicitly call mes_numeric_ev().
def mes_numeric(model_prob: float, market_price: float | None) -> float | None:
    """BACKWARD COMPAT: now returns canonical edge_diff (probability gap).
    For EV, use mes_numeric_ev() explicitly."""
    return edge_diff(model_prob, market_price)