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
# Double chance — DERIVED from 1X2 probs (1X = home or draw, etc.), not a
# separate 1X2 identity. A bookmaker price exists (api-football "Double Chance"),
# so it can carry capital like any other priced market (Architect 2026-08-11
# multi-market selection).
DC_1X = "DC_1X"
DC_X2 = "DC_X2"
DC_12 = "DC_12"

ALL = (HOME, DRAW, AWAY, OVER_25, UNDER_25, OVER_15, UNDER_15, BTTS_YES, BTTS_NO)

# The full market universe a fixture's pick is chosen from (Architect 2026-08-11):
# 1X2 + Over/Under 1.5 + Over/Under 2.5 + BTTS + Double Chance. A market enters a
# bookable leg ONLY when it carries a real bookmaker price (HR35 — model_prob is
# never a price). `ALL` stays the 9 canonical markets (outcome/settlement loops
# iterate it); this adds the DC derivations for the selection engine.
EDGE_MARKETS = ALL + (DC_1X, DC_X2, DC_12)

# Market key -> index into implied_1x2()'s (home, draw, away) tuple. Used by
# run_daily/webapp to anchor a market's EV on the bookmaker's devigged implied
# probability (ID413/ID414). Referenced since 6a976ca but the constant was never
# defined — masked while no odds were present, exposed the moment the
# API-Football fallback started pricing fixtures.
MARKETS_1X2 = {HOME: 0, DRAW: 1, AWAY: 2}

# --- ID405 MARKET GATE (ratified 2026-08-04) --------------------------------
# OPENED 2026-08-10 by ARCHITECT order — every market may carry capital again.
# SCOPE OVERRIDDEN 2026-08-11 (Architect directive, named): away wins may now be
# RECOMMENDED, not just shown — all markets remain open, the brain learns from
# live legs. The recommendation-layer exclusions ("never recommended" wording,
# accumulator_prep slip exclusions) were removed the same day; recorded in
# RATIFICATIONS.md (2026-08-11 entry) so it is never silently re-applied.
# The gate was originally ratified on backtest evidence that these markets are
# negative for the MODEL and for RANDOM SELECTION alike (favourite-longshot
# drift), which is what made them a property of the market rather than a model
# failing:
#
#     1X2 Away    -1.883%  t=-4.515  (606 legs)   placebo also -1.707%
#     Over 2.5    -0.716%  t=-2.783  (442 legs)
#     1X2 Home    -0.640%  (2425) / -0.625% (2526)  placebo loses 2425 too
#
# The Architect chose to open the gate anyway (2026-08-10), as part of the
# same order that removed the softness tier system, and to override the away-
# recommendation scope on 2026-08-11. Both REVERSE ratified bright lines and
# widen the deploy book to evidence-negative markets; both are recorded in
# RATIFICATIONS.md so the reversals are never silent. `blocked()` is kept so any
# future gate is enforced in ONE place.
#
# A gate that is emptied here cannot silently widen later — re-adding a key to
# BLOCKED re-engages it everywhere (DEPLOYABLE below is derived from it).
BLOCKED: dict[str, str] = {}


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
        DC_1X: f"{home_team} or Draw (double chance)",
        DC_X2: f"{away_team} or Draw (double chance)",
        DC_12: f"{home_team} or {away_team} (double chance)",
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
        DC_1X: fthg >= ftag,
        DC_X2: ftag >= fthg,
        DC_12: fthg != ftag,
    }.get(key)


def model_prob(key: str, probs) -> Optional[float]:
    """The model's probability for this market, from a FixtureProbabilities.

    Returns None if the source probability is None (e.g. ClubElo stretch
    ratings only provide 1X2, goals/BTTS markets are honestly unpriced)."""
    if probs is None:
        return None

    # Direct probabilities
    direct = {
        HOME: probs.p_home,
        DRAW: probs.p_draw,
        AWAY: probs.p_away,
        OVER_25: probs.p_over_25,
        OVER_15: probs.p_over_15,
        BTTS_YES: probs.p_btts_yes,
    }
    if key in direct:
        return direct[key]

    # Derived probabilities — only compute if source is not None
    if key == UNDER_25:
        return 1.0 - probs.p_over_25 if probs.p_over_25 is not None else None
    if key == UNDER_15:
        return 1.0 - probs.p_over_15 if probs.p_over_15 is not None else None
    if key == BTTS_NO:
        return 1.0 - probs.p_btts_yes if probs.p_btts_yes is not None else None
    if key == DC_1X:
        return (probs.p_home + probs.p_draw) if probs.p_home is not None and probs.p_draw is not None else None
    if key == DC_X2:
        return (probs.p_draw + probs.p_away) if probs.p_draw is not None and probs.p_away is not None else None
    if key == DC_12:
        return (probs.p_home + probs.p_away) if probs.p_home is not None and probs.p_away is not None else None

    return None


def quote(key: str, fixture_odds) -> Optional[object]:
    """The live MarketQuote for this market, from a FixtureOdds.

    Over/Under 1.5, BTTS and Double Chance have no price on The Odds API free
    tier — they fill from the api-football parser (Architect 2026-08-11 multi-
    market selection). A market with no price stays honest scan-only (HR35)."""
    if fixture_odds is None:
        return None
    return {
        HOME: fixture_odds.home,
        DRAW: fixture_odds.draw,
        AWAY: fixture_odds.away,
        OVER_25: fixture_odds.over25,
        UNDER_25: fixture_odds.under25,
        OVER_15: getattr(fixture_odds, "over15", None),
        UNDER_15: getattr(fixture_odds, "under15", None),
        BTTS_YES: getattr(fixture_odds, "btts_yes", None),
        BTTS_NO: getattr(fixture_odds, "btts_no", None),
        DC_1X: getattr(fixture_odds, "dc_1x", None),
        DC_X2: getattr(fixture_odds, "dc_x2", None),
        DC_12: getattr(fixture_odds, "dc_12", None),
    }.get(key)


# Markets that can carry capital on the base price feeds: everything with a live
# price that isn't blocked. The Odds API free tier serves exactly these five.
# Over/Under 1.5, BTTS and Double Chance get prices from the api-football parser
# (2026-08-11) — they are priced per-fixture and the acca builder admits any
# market with a real price, so DEPLOYABLE here is the minimum, not the ceiling.
DEPLOYABLE = tuple(k for k in (HOME, DRAW, AWAY, OVER_25, UNDER_25) if k not in BLOCKED)

# APPROVED_MARKETS — the full set of markets the Architect approved for
# DISPLAY/SCAN/RANKING. This is SEPARATE from DEPLOYABLE (capital gate).
# Approved list (ratified 2026-08-09): Win (HOME), Away Win (AWAY),
# Double Chance, Over/Under 1.5, Over/Under 2.5, BTTS.
# The market gate was opened 2026-08-10 (Architect), so DEPLOYABLE now equals
# this deployable set — the capital gate no longer excludes any market. This
# list remains for BOARD VISIBILITY of the non-priced scan markets.
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
