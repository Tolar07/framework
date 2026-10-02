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
OVER_35 = "OVER_3_5"
UNDER_35 = "UNDER_3_5"
DC_1X = "DC_1X"        # home or draw
DC_X2 = "DC_X2"        # draw or away
DC_12 = "DC_12"        # home or away

ALL = (HOME, DRAW, AWAY, OVER_25, UNDER_25, OVER_15, UNDER_15, BTTS_YES, BTTS_NO,
       OVER_35, UNDER_35, DC_1X, DC_X2, DC_12)

# --- ID405 MARKET GATE (ratified 2026-08-04) --------------------------------
# Measured on the 2024/25 walk-forward backtest, 5 leagues, corrected engine.
# Both markets are negative for the MODEL and for RANDOM SELECTION alike, which
# is what makes them a property of the market rather than a model failing.
#
# This gate only ever NARROWS what may carry capital. It cannot admit a market
# that was previously excluded.
BLOCKED: dict[str, str] = {}   # Architect 2026-08-10: all markets open


def blocked(key: str) -> Optional[str]:
    """Why this market may not carry capital, or None if it may.

    The SINGLE place a market is excluded. Board rendering, leg logging and
    deploy eligibility all call this, so a market cannot be blocked in one
    path and live in another."""
    return BLOCKED.get(key)


def _ladder():
    from engine import full_markets
    return full_markets


def display(key: str, home_team: str = "Home", away_team: str = "Away") -> str:
    """Plain-language name for a human (HR53: full club names, market in words).

    Derived from the key rather than stored alongside it, so a reworded label
    can never fall out of step with what the gate matches."""
    if key and key.startswith("SB:"):
        return _ladder().display_key(key, home_team, away_team)
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
        OVER_35: "Over 3.5 goals",
        UNDER_35: "Under 3.5 goals",
        DC_1X: f"{home_team} or draw",
        DC_X2: f"{away_team} or draw",
        DC_12: f"{home_team} or {away_team}",
    }.get(key, key)


def settle(key: str, fthg: int, ftag: int) -> Optional[bool]:
    """Did this market win? HR15 90-minute basis.

    Returns None for a key with no settlement rule — never a guessed verdict."""
    if key and key.startswith("SB:"):
        return _ladder().settle_key(key, fthg, ftag)   # None on a push (void)
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
        OVER_35: total > 3,
        UNDER_35: total <= 3,
        DC_1X: fthg >= ftag,
        DC_X2: ftag >= fthg,
        DC_12: fthg != ftag,
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
        OVER_35: probs.p_over_35,
        UNDER_35: 1.0 - probs.p_over_35,
        DC_1X: probs.p_home + probs.p_draw,
        DC_X2: probs.p_draw + probs.p_away,
        DC_12: probs.p_home + probs.p_away,
    }.get(key)


def quote(key: str, fixture_odds) -> Optional[object]:
    """The live MarketQuote for this market, from a FixtureOdds."""
    if fixture_odds is None:
        return None
    if key and key.startswith("SB:"):
        pk = _ladder().parse_key(key)
        for m in getattr(fixture_odds, "raw_markets", []) or []:
            if pk and int(m.get("id") or 0) == pk[0] and (m.get("specifier") or "") == pk[1]:
                for o in m.get("outcomes", []):
                    if o.get("desc") == pk[2] and o.get("odds"):
                        from pipeline.odds import MarketQuote
                        return MarketQuote(price=float(o["odds"]), bookmaker="sportybet",
                                           n_books=1)
        return None
    return {
        HOME: fixture_odds.home,
        DRAW: fixture_odds.draw,
        AWAY: fixture_odds.away,
        OVER_25: fixture_odds.over25,
        UNDER_25: fixture_odds.under25,
        OVER_15: getattr(fixture_odds, "over15", None),
        UNDER_15: getattr(fixture_odds, "under15", None),
        OVER_35: getattr(fixture_odds, "over35", None),
        UNDER_35: getattr(fixture_odds, "under35", None),
        BTTS_YES: getattr(fixture_odds, "btts_yes", None),
        BTTS_NO: getattr(fixture_odds, "btts_no", None),
        DC_1X: getattr(fixture_odds, "dc_1x", None),
        DC_X2: getattr(fixture_odds, "dc_x2", None),
        DC_12: getattr(fixture_odds, "dc_12", None),
    }.get(key)


# Markets that can carry capital: EVERY market with a live price that isn't
# blocked (Architect 2026-10-02: alternative markets open — Double Chance,
# Over/Under 1.5 / 2.5 / 3.5, BTTS — all priced and bookable on SportyBet).
DEPLOYABLE = tuple(k for k in ALL if k not in BLOCKED)
