"""
ID402 — Matchday Slate Engine.

SOFTNESS TIERING RETIRED (2026-09-30, Architect's instruction): the old A/B/C/D
"softness" ranking is gone. Every whitelisted league is now BOTH scan- and
deploy-eligible — "all fixtures eligible", the Architect's standing position.
The DEPLOY shortlist is ranked purely by model conviction (with recent form as a
tie-breaker) and capped at DEPLOY_POOL_CAP; it no longer favours any league tier.

What this module still does:
  - Holds the league whitelist (ID401 / HR34: an unratified league is never
    silently included — it scans as NO DATA, never guessed).
  - The evidence-based MARKET GATE (below), which narrows what can carry capital.
  - Builds the capped DEPLOY shortlist.

It never claims any fixture is a good bet — only logged CLV (clv/) confirms edge.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

DEPLOY_POOL_CAP = 6  # ID402 hard cap on THE CALL

# --- DEPLOY ODDS BAND (Architect's standing rule) ---------------------------
# A single is only deployable when its price sits inside this band:
#   * DEPLOY_ODDS_MAX = 2.00 — the hard ceiling. Above 2.0 the market is roughly
#     90/10 in the bookmaker's favour; the Architect treats anything over 2.0 as
#     a loss and never deploys it.
#   * DEPLOY_ODDS_MIN = 1.20 — the floor. Below this the return doesn't justify
#     the stake; 1.20+ is where the "assured outcome" picks live.
#   * DEPLOY_ODDS_SAFE = 1.50 — the safest target inside the band, used only to
#     rank/label; it is not a gate.
# This narrows what can carry capital (like the MARKET GATE); it never widens it.
DEPLOY_ODDS_MIN = 1.20
DEPLOY_ODDS_MAX = 2.00
DEPLOY_ODDS_SAFE = 1.50


def in_deploy_band(price: Optional[float]) -> bool:
    """True when a decimal price is inside the Architect's deploy band
    [DEPLOY_ODDS_MIN, DEPLOY_ODDS_MAX] (inclusive). A missing price is NOT in
    band — no price, no deploy (HR35: never assume one)."""
    return price is not None and DEPLOY_ODDS_MIN <= price <= DEPLOY_ODDS_MAX

# ID401 league whitelist. Membership alone decides eligibility now — no tiers.
# Every league here is scan- AND deploy-eligible; anything not here is refused
# (HR34 default-ban), never silently scanned.
WHITELIST_LEAGUES = (
    "Eredivisie",
    "Danish Superliga",
    "Belgian Pro League",
    "Scottish Premiership",
    "Ekstraklasa",
    "HNL",
    "Championship",
    "Serie A",
    "Bundesliga",
    "Ligue 1",
    "Europa League",
    "Primeira Liga",
    "Premier League",
    "La Liga",
    "Champions League",
)

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


def is_whitelisted(league: str) -> bool:
    return league in WHITELIST_LEAGUES


# Deploy-eligibility is now identical to being whitelisted — kept as a named
# function so callers read intently rather than testing the tuple inline.
def is_deploy_eligible(league: str) -> bool:
    return is_whitelisted(league)


@dataclass
class SlateDecision:
    league: str
    scan_eligible: bool
    deploy_eligible: bool


def classify(league: str) -> SlateDecision:
    ok = is_whitelisted(league)
    return SlateDecision(league=league, scan_eligible=ok, deploy_eligible=ok)


def _confidence(c) -> float:
    """Ranking key: the model's strongest market probability for this fixture.

    Deliberately NOT an edge/EV figure — that would need a market price. Ranks by
    model conviction only. Fixtures with no probabilities sort last."""
    probs = getattr(c, "probs", None)
    if probs is None:
        return -1.0
    return max(probs.p_home, probs.p_draw, probs.p_away,
               probs.p_over_15, 1 - probs.p_over_15,
               probs.p_btts_yes, 1 - probs.p_btts_yes)


def build_deploy_shortlist(candidates: list) -> list:
    """The DEPLOY shortlist: highest model conviction first, capped at
    DEPLOY_POOL_CAP. No league tiering — every candidate competes on conviction
    alone, with recent form (engine.form, bounded [-1,1]) as the tie-breaker.

    Candidates are expected to be deploy-eligible already (their league is
    whitelisted); this ranks and caps them. Form can only reorder near-equal
    picks, never manufacture conviction."""
    ranked = sorted(
        candidates,
        key=lambda c: (-_confidence(c), -(getattr(c, "form_support", None) or 0.0)))
    return ranked[:DEPLOY_POOL_CAP]
