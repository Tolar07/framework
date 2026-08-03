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
}

DEPLOY_ELIGIBLE_TIERS = {"A", "B"}


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
    """Ranking key: the model's strongest market probability for this fixture.

    Deliberately NOT an edge/EV figure — that would need a market price, and
    prices are ARCHITECT-FED (Section 7.2), so no EV number exists at board
    time. This ranks by model conviction only, which is what the engine
    actually knows. Fixtures with no probabilities sort last."""
    probs = getattr(c, "probs", None)
    if probs is None:
        return -1.0
    return max(probs.p_home, probs.p_draw, probs.p_away,
               probs.p_over_15, 1 - probs.p_over_15,
               probs.p_btts_yes, 1 - probs.p_btts_yes)


def build_deploy_shortlist(candidates: list) -> list:
    """Softness A/B only, capped at DEPLOY_POOL_CAP — 'wide eyes, narrow
    hands' enforced here rather than left to a judgment call at render time.

    Ranked before truncating. Previously this returned `eligible[:6]`, i.e. it
    kept whichever six happened to come first — and since leagues are scanned
    in dict order, one league's fixtures could fill the entire CALL while a
    higher-conviction fixture in the next league was silently dropped. Tier A
    outranks tier B, then model conviction descending."""
    eligible = [c for c in candidates if c.softness_tier in DEPLOY_ELIGIBLE_TIERS]
    ranked = sorted(eligible, key=lambda c: (c.softness_tier, -_confidence(c)))
    return ranked[:DEPLOY_POOL_CAP]
