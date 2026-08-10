"""
Unified league pool (2026-08-10) — the softness tier system is gone.

The A/B/C/D softness ranking (ID402) was removed by Architect order: every
approved league is ONE pool — no tier priority, no deploy cap, no scan-only
classification. The whitelist itself (ID401) survives as the single source of
truth: a league on it is scan- AND deploy-eligible; a league off it (HR34) is
neither.

The ID405 MARKET GATE was also opened (2026-08-10, Architect order): every
market may carry capital again. The `engine/markets.py` BLOCKED dict is empty;
`build_deploy_shortlist` still calls `mkt.blocked()` as a structural backstop so
a future market gate would be honoured automatically, but today it never blocks.

The `softness_tier()` function name is retained ONLY as a back-compat storage
slot: the database column and JSON payload still carry a tier string, which is
now always "ONE" for a whitelisted league (and "?" for an unrated one). It is a
pool marker, never a rank.

Softness was always a hypothesis about where to look, not proof — only logged
CLV (clv/clv_logger.py) confirms edge. Removing it widens what the shortlist may
contain; it claims nothing about whether any of it is a good bet.
"""
from __future__ import annotations

from dataclasses import dataclass

# Section 7.4 — the ID401 whitelist. A single unified pool (no tiers). Kept
# sorted; HR34: a league not listed here is never scan- or deploy-eligible.
WHITELISTED_LEAGUES: list[str] = [
    "Austrian Bundesliga",
    "Belgian Pro League",
    "Bundesliga",
    "Champions League",
    "Championship",
    "Danish Superliga",
    "EFL Cup",
    "Ekstraklasa",
    "Eredivisie",
    "Europa League",
    "HNL",
    "La Liga",
    "Ligue 1",
    "Premier League",
    "Primeira Liga",
    "Scottish Premiership",
    "Serie A",
]

# The single pool marker every whitelisted league carries in the back-compat
# `softness_tier` storage slot. Never a rank — all leagues are equal.
ONE_POOL = "ONE"


def softness_tier(league: str) -> str:
    """Returns the league's pool marker, or '?' if not on the whitelist at
    all (ID401 default-ban / HR34 — an unratified league is never scan- or
    deploy-eligible). Retained name: the DB/JSON field this feeds is still
    called `softness_tier`; its value is now always ONE_POOL for whitelisted
    leagues, never a rank."""
    return ONE_POOL if league in WHITELISTED_LEAGUES else "?"


def is_deploy_eligible(league: str) -> bool:
    """Every whitelisted league is deploy-eligible (unified pool). HR34 still
    excludes a league that is not on the whitelist at all."""
    return softness_tier(league) != "?"


@dataclass
class SlateDecision:
    league: str
    tier: str
    scan_eligible: bool
    deploy_eligible: bool


def classify(league: str) -> SlateDecision:
    """Classify a league against the unified pool: whitelisted = scan- AND
    deploy-eligible; anything else is excluded (HR34)."""
    eligible = is_deploy_eligible(league)
    return SlateDecision(
        league=league, tier=softness_tier(league),
        scan_eligible=eligible,
        deploy_eligible=eligible,
    )


def _confidence(c) -> float:
    """Ranking key: the model's strongest market probability.

    Ranks by model conviction only — what the engine actually knows. Fixtures
    with no probabilities sort last."""
    probs = getattr(c, "probs", None)
    if probs is None:
        return -1.0
    # p_home / p_draw / p_away / 1-p_over_25 are the model's probabilities for
    # the deployable markets.
    return float(max(probs.p_home, probs.p_draw, probs.p_away, 1.0 - probs.p_over_25))


def call_key(c) -> tuple:
    """THE CALL ranking key: PRICED picks ahead of unpriced, then expected value
    descending (best_mes_ev, set by run_daily after the odds pull) — unpriced
    rows rank by model conviction as a fallback.

    EV is the figure that actually decides a bet, so every fixture with a live
    price outranks one without (conviction is unmeasurable against a number).
    Without the priced-first separator, a 70%-confident unpriced row's key could
    beat a +20%-EV priced row and the CALL would read wrong.

    Public so the renderer sorts THE CALL into the same order it was selected
    — otherwise the right picks are chosen but shown in scan order, which reads
    as if the ranking failed.

    No tier component: the unified pool ranks every league equally."""
    ev = getattr(c, "best_mes_ev", None)
    if ev is not None:
        return (0, -ev)          # priced first
    return (1, -_confidence(c))  # unpriced after


def build_deploy_shortlist(candidates: list) -> list:
    """The deploy shortlist over the unified pool: every market-gate-cleared
    fixture, ranked by call_key, NO cap.

    The ID405 MARKET GATE is enforced at this boundary as a structural
    backstop: a fixture whose headlined market is blocked (mkt.blocked) is
    excluded even though every league is deploy-eligible. The gate is open
    today (BLOCKED is empty), so nothing is excluded — but the check stays so
    the gate cannot silently widen later without going through engine/markets.py.
    """
    from engine import markets as mkt
    eligible = [c for c in candidates
                if not (getattr(c, "best_market_key", None)
                     and mkt.blocked(c.best_market_key))]
    return sorted(eligible, key=call_key)
