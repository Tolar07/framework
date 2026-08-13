"""
Unified league pool (ID401) — the whitelist, with no softness.

The softness A/B/C/D ranking (ID402) and every trace of a "softness tier" were
removed by Architect order (2026-08-10, finished 2026-08-11). There is ONE
pool: every whitelisted league is scan- AND deploy-eligible; a league off the
whitelist (HR34) is neither. No tier priority, no deploy cap, no scan-only
class.

The ID405 MARKET GATE was also opened (2026-08-10, Architect order): every
market may carry capital again. `engine/markets.py` BLOCKED is empty;
`build_deploy_shortlist` still calls `mkt.blocked()` as a structural backstop so
a future market gate would be honoured automatically, but today it never blocks.

The whitelist itself (ID401) remains the single source of truth for league
eligibility — a league on it is deploy-eligible, a league off it is not.

Since 2026-08-12 the whitelist is DRIVEN BY the dynamic registry
(config/leagues.json). WHITELISTED_LEAGUES below is a derived symbol computed
from the registry so all existing importers keep working without changes.
"""
from __future__ import annotations

from engine.league_registry import registry

# WHITELISTED_LEAGUES is now derived from the registry — all deploy-eligible
# leagues, kept sorted for stable ordering. Do NOT edit this list directly;
# add/remove leagues in config/leagues.json instead.
WHITELISTED_LEAGUES: list[str] = registry.WHITELISTED_LEAGUES


def is_deploy_eligible(league: str) -> bool:
    """A whitelisted league is deploy-eligible (unified pool, no tiers). HR34
    still excludes a league that is not on the whitelist at all."""
    return registry.is_eligible(league)


def _confidence(c) -> float:
    """Ranking key: the model's strongest market probability.

    Ranks by model conviction only — what the engine actually knows. Fixtures
    with no probabilities sort last."""
    probs = getattr(c, "probs", None)
    if probs is None:
        return -1.0
    # p_home / p_draw / p_away / 1-p_over_25 are the model's probabilities for
    # the deployable markets. A STRETCH 1X2-only rating (ClubElo fallback) has
    # no goals opinion — its p_over_25 is None, so the goals market is skipped
    # rather than crashing (HR35).
    over25 = probs.p_over_25
    return float(max(probs.p_home, probs.p_draw, probs.p_away,
                     1.0 - over25 if over25 is not None else 0.0))


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
