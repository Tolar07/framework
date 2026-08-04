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
