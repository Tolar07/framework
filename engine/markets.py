"""
CANONICAL MARKET IDENTITIES — one key per market, everywhere.

WHY THIS EXISTS
  The same market was being named three different ways: the logger wrote
  "Match result — away win", the board rendered "Aberdeen to win", and the
  ID405 gate matched on the substring "away win". Two of those three agreed,
  so the gate blocked the leg from being LOGGED while the board could still
  headline it as THE CALL — the framework recommending exactly what it refuses
  to record.

  A gate that matches on display text is a gate that fails whenever anyone
  rewords a label. So identity and presentation are separated here: code
  compares KEYS, humans read the string produced by `display()`, and the two
  can never drift apart because the display string is derived from the key.

HR53 is served by `display()` returning full club names and the market spelled
out in words. HR35 is served by `blocked()` being the single place any market
can be excluded, so a market cannot be live in one path and blocked in another.
"""
from __future__ import annotations

from typing import Optional

# Canonical keys. These are what code compares; they are never shown to a human.
HOME = "1X2_HOME"
DRAW = "1X2_DRAW"
AWAY = "1X2_AWAY"
OVER_25 = "OVER_2_5"
UNDER_25 = "UNDER_2_5"
OVER_15 = "OVER_1_5"
UNDER_15 = "UNDER_1_5"
BTTS_YES = "BTTS_YES"
BTTS_NO = "BTTS_NO"

ALL = (HOME, DRAW, AWAY, OVER_25, UNDER_25, OVER_15, UNDER_15, BTTS_YES, BTTS_NO)

# Market key -> index into implied_1x2()'s (home, draw, away) tuple. Used by
# run_daily/webapp to anchor a market's EV on the bookmaker's devigged implied
# probability (ID413/ID414). Referenced since 6a976ca but the constant was never
# defined — masked while no odds were present, exposed the moment the
# API-Football fallback started pricing fixtures.
MARKETS_1X2 = {HOME: 0, DRAW: 1, AWAY: 2}

# --- ID405 MARKET GATE (ratified 2026-08-04) --------------------------------
# Measured on the 2024/25 walk-forward backtest, 5 leagues, corrected engine.
# Both markets are negative for the MODEL and for RANDOM SELECTION alike, which
# is what makes them a property of the market rather than a model failing.
#
# This gate only ever NARROWS what may carry capital. It cannot admit a market
# that was previously excluded.
BLOCKED: dict[str, str] = {
    AWAY: ("1X2 Away: -1.883% mean CLV (t=-4.515) across 606 backtest legs. "
           "Random selection loses on it too (-1.707%), so this is "
           "favourite-longshot drift in the market, not a model error to fix."),
    OVER_25: ("Over 2.5: -0.716% mean CLV (t=-2.783) across 442 legs. The model "
              "under-predicts goals, so its Overs are taken into lines that "
              "then move against it."),
    HOME: ("1X2 Home: -0.640% mean CLV (t=-2.326) on 2425 (994 legs) and "
           "-0.625% (t=-2.458) on 2526 (963 legs), all 10 leagues with a "
           "closing-odds source. Random selection loses on it too in 2425 "
           "(-0.524%, t=-2.731), so this is market drift, not a model error "
           "to fix — the same favourite-longshot pattern that blocked Away. "
           "Blocked per ID405's one-way-narrows rule on 2026-08-08; see "
           "RATIFICATIONS.md."),
}


def blocked(key: str) -> Optional[str]:
    """Why this market may not carry capital, or None if it may.

    The SINGLE place a market is excluded. Board rendering, leg logging and
    deploy eligibility all call this, so a market cannot be blocked in one
    path and live in another."""
    return BLOCKED.get(key)


def display(key: str, home_team: str = "Home", away_team: str = "Away") -> str:
    """Plain-language name for a human (HR53: full club names, market in words).

    Derived from the key rather than stored alongside it, so a reworded label
    can never fall out of step with what the gate matches."""
    return {
        HOME: f"{home_team} to win",
        DRAW: "Draw",
        AWAY: f"{away_team} to win",
        OVER_25: "Over 2.5 goals",
        UNDER_25: "Under 2.5 goals",
        OVER_15: "Over 1.5 goals",
        UNDER_15: "Under 1.5 goals",
        BTTS_YES: "Both teams to score — yes",
        BTTS_NO: "Both teams to score — no",
    }.get(key, key)


def settle(key: str, fthg: int, ftag: int) -> Optional[bool]:
    """Did this market win? HR15 90-minute basis.

    Returns None for a key with no settlement rule — never a guessed verdict."""
    total = fthg + ftag
    return {
        HOME: fthg > ftag,
        DRAW: fthg == ftag,
        AWAY: ftag > fthg,
        OVER_25: total > 2,
        UNDER_25: total <= 2,
        OVER_15: total > 1,
        UNDER_15: total <= 1,
        BTTS_YES: fthg > 0 and ftag > 0,
        BTTS_NO: not (fthg > 0 and ftag > 0),
    }.get(key)


def model_prob(key: str, probs) -> Optional[float]:
    """The model's probability for this market, from a FixtureProbabilities."""
    if probs is None:
        return None
    return {
        HOME: probs.p_home,
        DRAW: probs.p_draw,
        AWAY: probs.p_away,
        OVER_25: probs.p_over_25,
        UNDER_25: 1.0 - probs.p_over_25,
        OVER_15: probs.p_over_15,
        UNDER_15: 1.0 - probs.p_over_15,
        BTTS_YES: probs.p_btts_yes,
        BTTS_NO: 1.0 - probs.p_btts_yes,
    }.get(key)


def quote(key: str, fixture_odds) -> Optional[object]:
    """The live MarketQuote for this market, from a FixtureOdds."""
    if fixture_odds is None:
        return None
    return {
        HOME: fixture_odds.home,
        DRAW: fixture_odds.draw,
        AWAY: fixture_odds.away,
        OVER_25: fixture_odds.over25,
        UNDER_25: fixture_odds.under25,
    }.get(key)


# Markets that can carry capital: everything with a live price that isn't
# blocked. Over/Under 1.5 and BTTS have no price source, so they are scan-only
# by data availability rather than by rule.
DEPLOYABLE = tuple(k for k in (HOME, DRAW, AWAY, OVER_25, UNDER_25) if k not in BLOCKED)

# APPROVED_MARKETS — the full set of markets the Architect approved for
# DISPLAY/SCAN/RANKING. This is SEPARATE from DEPLOYABLE (capital gate).
# Approved list (ratified 2026-08-09): Win (HOME), Away Win (AWAY),
# Double Chance, Over/Under 1.5, Over/Under 2.5, BTTS.
# The market gate (BLOCKED) still prevents capital deployment on negative-CLV
# markets (Away, Over 2.5, Home) — this list is for BOARD VISIBILITY ONLY.
APPROVED_MARKETS = (
    HOME,          # Win
    DRAW,          # Draw
    AWAY,          # Away Win
    OVER_15,       # Over 1.5
    UNDER_15,      # Under 1.5
    OVER_25,       # Over 2.5
    UNDER_25,      # Under 2.5
    BTTS_YES,      # BTTS Yes
    BTTS_NO,       # BTTS No
)
# Double Chance is derived from 1X2 probs (1X, X2, 12) — not a separate key.


def implied_1x2(fixture_odds) -> Optional[tuple[float, float, float]]:
    """Bookmaker implied 1X2, margin removed by proportional devig (ID413).

    Decimal odds carry an in-built margin: 1/odds over the three outcomes
    sums to more than 1 (the overround). Proportional devig normalises by
    that sum, so the three implied probabilities total exactly 1 and fit the
    consensus vote/average machinery:

        p_i = (1/odds_i) / (1/odds_h + 1/odds_d + 1/odds_a)

    This is the bookmaker ENGINE's opinion — the aggregate of real money, the
    sharpest single calibration source in football — and it joins Dixon-Coles,
    Elo, and xG as an equal fourth voter in the cross-engine consensus. It
    never changes what is logged (DC stays canonical for legs/CLV/calibration).

    HR35: returns None unless ALL three prices are present. A two-price "1X2"
    would require fabricating the missing side — which is worse than an honest
    gap. A price <= 1.0 (degenerate decimal odds) is also refused."""
    if fixture_odds is None:
        return None
    prices = [fixture_odds.home.price, fixture_odds.draw.price,
              fixture_odds.away.price]
    if any(p is None or p <= 1.0 for p in prices):
        return None
    inv = [1.0 / p for p in prices]
    s = sum(inv)
    return tuple(x / s for x in inv)


# Blend thresholds for disagreement_weighting. Measured on the 2425 backtest
# (all 5577 predictions, not just selected legs): the model is well-calibrated
# where it AGREES with the market's devigged implied, but +10-14pp overconfident
# exactly where it DISAGREES — and the min_mes screen only ever bets the
# disagreement bucket. These thresholds come from that measurement: |model -
# market| below BLEND_NOOP_AT is a healthy agreement (keep the model's honest
# number), at BLEND_FULL_AT it saturates (fully defer to the sharper market
# prior). Values are evidence-anchored, not tuned to make the backtest green.
BLEND_NOOP_AT = 0.04   # 4pp of disagreement = agreement, keep model
BLEND_FULL_AT = 0.12   # 12pp of disagreement = market wins, defer fully
BLEND_MAX_WEIGHT = 0.70  # never fully discard the model (it is honest at 0)


def blend_toward_market(model_p: Optional[float],
                        market_p: Optional[float],
                        noop_at: float = BLEND_NOOP_AT,
                        full_at: float = BLEND_FULL_AT,
                        max_weight: float = BLEND_MAX_WEIGHT) -> Optional[float]:
    """The market-anchored probability: model_p pulled toward the market's
    devigged implied probability by an amount proportional to DISAGREEMENT.

    WHY: the model is honest where it agrees with the market and overconfident
    where it disagrees (measured). A raw model_p presented as "value" is exactly
    the model's disagreement with real money — and the market wins that bucket.
    This returns the probability the board should display and the EV should be
    priced on: the model's honest estimate when it agrees with the market, and
    a blend deferring toward the market as disagreement grows.

    HR35: either input None -> None (no fabricated number). model_p is never
    pushed past the market side of the disagreement, so the blend cannot turn a
    market-mispriced longshot into a fabricated certainty."""
    if model_p is None or market_p is None:
        return None
    d = abs(model_p - market_p)
    if d <= noop_at:
        return model_p  # agreement — the model's number is the honest one
    w = min(max_weight, max_weight * (d - noop_at) / (full_at - noop_at))
    # Blend toward the market, but never across it: the blended value stays
    # between the two inputs, so it cannot overshoot into a new disagreement.
    return model_p + w * (market_p - model_p)
