"""
ID402 — Matchday Slate Engine + Section 7.4 evidence-based softness ranking.
"Wide eyes, narrow hands" — SCAN covers every whitelisted league; DEPLOY only
ever draws from softness A/B, capped at 6 fixtures.

Softness is a hypothesis about where to look, not proof — only logged CLV
(clv/clv_logger.py) confirms edge. This module only gates WHICH fixtures are
eligible to appear in PART 1; it never claims any of them are a good bet.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

DEPLOY_POOL_CAP = 6  # ID402 hard cap on THE CALL

# Section 7.4 — evidence-based softness ranking (15-league whitelist, ID401)
SOFTNESS_TIER = {
    # Tier A — deploy eligible
    "Eredivisie": "A",
    "Danish Superliga": "A",
    # Tier B — deploy eligible
    "Belgian Pro League": "B",
    "Scottish Premiership": "B",
    "Ekstraklasa": "B",
    # Tier C — scan-only
    "HNL": "C",
    "Championship": "C",
    "Serie A": "C",
    "Bundesliga": "C",
    "Ligue 1": "C",
    "Europa League": "C",
    # Tier D — scan-only
    "Primeira Liga": "D",
    "Premier League": "D",
    "La Liga": "D",
    "Champions League": "D",
    # Austrian Bundesliga — ratified 2026-08-07: scan-only, captured via the
    # odds feed (soccer_austria_bundesliga, verified active). No history source
    # covers it, so its fixtures list unrated NO DATA — PENDING until one does.
    "Austrian Bundesliga": "D",
    # EFL Cup — ratified 2026-08-06 (Architect): an ACTIVE Odds sport with real
    # prices, but was never scanned (not in the whitelist), so its matches
    # (e.g. Bristol City v Walsall that night) were invisible. Tier D = scan
    # only, never a capital pick.
    "EFL Cup": "D",
}

DEPLOY_ELIGIBLE_TIERS = {"A", "B"}

# --- MARKET GATE (ratified 2026-08-04, evidence below) ----------------------
#
# Measured on the 2024/25 walk-forward backtest, 5 leagues, corrected engine.
# Two markets are structurally negative — for the MODEL and for random
# selection alike, which is what makes them a market property rather than a
# model failing:
#
#     1X2 Away    -1.883%  t=-4.515  (606 legs)   placebo also -1.707%
#     Over 2.5    -0.716%  t=-2.783  (442 legs)
#
# Removing them flips the whole backtest from -0.404% to +0.326%. This gate
# only ever NARROWS what can be deployed — it can never admit a market that
# was previously excluded — so it is a conservative restriction, not a new
# licence. Capital authority is unchanged and remains the Architect's.
BLOCKED_DEPLOY_MARKETS = {
    "away win": "1X2 Away: -1.883% mean CLV (t=-4.515) across 606 backtest legs. "
                "Random selection loses on it too (-1.707%), so this is "
                "favourite-longshot drift in the market, not a model error to fix.",
    "over 2.5 goals": "Over 2.5: -0.716% mean CLV (t=-2.783) across 442 legs. "
                      "The model under-predicts goals, so its Overs are taken "
                      "into lines that then move against it.",
    # Ratified 2026-08-08 (10-league pressure test, both seasons). Home is
    # negative for the model in both 2425 (-0.640%, t=-2.326) and 2526
    # (-0.625%, t=-2.458) and for random selection in 2425 (-0.524%, t=-2.731) —
    # the same favourite-longshot drift pattern that blocked away. Narrows only.
    "home win": "1X2 Home: -0.640% (2425) / -0.625% (2526) mean CLV across 10 "
                "leagues. Random selection loses on it too in 2425, so this is "
                "market drift, not a model error to fix.",
}


def market_blocked(market_name: str) -> Optional[str]:
    """Reason this market cannot carry capital, or None if it may.

    Matched on the plain-language market name the board renders, so the gate
    and the thing the Architect reads are the same string."""
    key = (market_name or "").strip().lower()
    for blocked, reason in BLOCKED_DEPLOY_MARKETS.items():
        if blocked in key:
            return reason
    return None


def softness_tier(league: str) -> str:
    """Returns the league's softness tier, or '?' if not on the whitelist at
    all (ID401 default-ban / HR34 — an unratified league is never scan- or
    deploy-eligible)."""
    return SOFTNESS_TIER.get(league, "?")


def is_deploy_eligible(league: str) -> bool:
    return softness_tier(league) in DEPLOY_ELIGIBLE_TIERS


@dataclass
class SlateDecision:
    league: str
    tier: str
    scan_eligible: bool
    deploy_eligible: bool


def classify(league: str) -> SlateDecision:
    tier = softness_tier(league)
    return SlateDecision(
        league=league, tier=tier,
        scan_eligible=tier != "?",     # HR34: an unratified league scans as NO DATA, never silently included
        deploy_eligible=tier in DEPLOY_ELIGIBLE_TIERS,
    )


def _confidence(c) -> float:
    """Ranking key: the model's strongest DEPLOYABLE market probability.

    Deliberately NOT an edge/EV figure — that would need a market price, and
    prices are ARCHITECT-FED (Section 7.2), so no EV number exists at board
    time. This ranks by model conviction only, which is what the engine
    actually knows.

    The key uses ONLY markets that can actually carry capital — home, draw,
    under 2.5 (the ID405 market gate). An away win or an Over 2.5 can never
    be deployed, so their conviction must not be what lifts a fixture into
    THE CALL: otherwise the CALL ranks on exactly the markets the framework
    refuses to log, and the user is told to bet what the ledger will not
    record. Fixtures with no probabilities sort last."""
    probs = getattr(c, "probs", None)
    if probs is None:
        return -1.0
    # p_home / p_draw / 1-p_over_25 are the three deployable markets' model
    # probabilities (mkt.model_prob for HOME/DRAW/UNDER_25).
    return max(probs.p_home, probs.p_draw, 1.0 - probs.p_over_25)


def call_key(c) -> tuple:
    """THE CALL ranking key: tier first (A outranks B), then PRICED picks
    ahead of unpriced, then expected value descending (best_mes_ev, set by
    run_daily after the odds pull) — unpriced rows rank by model conviction
    as a fallback.

    EV is the figure that actually decides a bet, so every fixture with a
    live price outranks one without (conviction is unmeasurable against a
    number). Without the priced-first separator, a 70%-confident unpriced
    row's key could beat a +20%-EV priced row and the CALL would read wrong.

    Public so the renderer sorts THE CALL into the same order it was selected
    — otherwise the right six are picked but shown in scan order, which reads
    as if the ranking failed."""
    ev = getattr(c, "best_mes_ev", None)
    if ev is not None:
        return (c.softness_tier, 0, -ev)          # priced first
    return (c.softness_tier, 1, -_confidence(c))  # unpriced after


def build_deploy_shortlist(candidates: list) -> list:
    """Softness A/B only, capped at DEPLOY_POOL_CAP — 'wide eyes, narrow
    hands' enforced here rather than left to a judgment call at render time.

    Ranked before truncating. Previously this returned `eligible[:6]`, i.e. it
    kept whichever six happened to come first — and since leagues are scanned
    in dict order, one league's fixtures could fill the entire CALL while a
    higher-value fixture in the next league was silently dropped. Tier A
    outranks tier B, then expected value descending (conviction as fallback).

    The ID405 MARKET GATE is enforced at this boundary too: a fixture whose
    headlined market is blocked (an away win or an Over 2.5 can never carry
    capital) is excluded even if it is softness A/B. Priced fixtures already
    get a deployable headlined market from run_daily, so this is a structural
    backstop — the gate cannot silently widen later."""
    from engine import markets as mkt
    eligible = [c for c in candidates
                if c.softness_tier in DEPLOY_ELIGIBLE_TIERS
                and not (getattr(c, "best_market_key", None)
                         and mkt.blocked(c.best_market_key))]
    ranked = sorted(eligible, key=call_key)
    return ranked[:DEPLOY_POOL_CAP]
