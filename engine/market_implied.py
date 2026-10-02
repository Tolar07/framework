"""
MARKET-IMPLIED probabilities — for a fixture the model cannot rate.

Architect 2026-10-02: every fixture gets production; nothing is dropped. Where
the Dixon-Coles model has no history for a team (FA Cup non-league sides, newly
promoted clubs), the fixture is priced from SportyBet's own odds with the
bookmaker margin removed (each two- or three-way market normalised to 100%).

This is NOT a model opinion and is labelled as such everywhere it appears:
  * it carries no edge by construction — EV against the same book is roughly
    minus the margin;
  * it never invents a number: every probability comes from a live quoted price
    (HR35). All of 1X2, Over/Under 1.5 / 2.5 / 3.5 and BTTS must be priced.
"""
from __future__ import annotations

from typing import Optional

from engine.dixon_coles import FixtureProbabilities


def _pair(a, b) -> Optional[float]:
    """De-vigged probability of the FIRST side of a two-way market."""
    pa, pb = getattr(a, "price", None), getattr(b, "price", None)
    if not pa or not pb:
        return None
    ia, ib = 1 / pa, 1 / pb
    return ia / (ia + ib)


def implied_probs(fx) -> Optional[FixtureProbabilities]:
    """FixtureProbabilities from a FixtureOdds' live prices, or None when any of
    the required markets is unpriced."""
    if fx is None:
        return None
    h, d, a = (getattr(fx, k).price for k in ("home", "draw", "away"))
    if not (h and d and a):
        return None
    ih, id_, ia = 1 / h, 1 / d, 1 / a
    tot = ih + id_ + ia
    p_over_25 = _pair(fx.over25, fx.under25)
    if p_over_25 is None:
        return None
    p_over_15 = _pair(getattr(fx, "over15", None), getattr(fx, "under15", None))
    p_over_35 = _pair(getattr(fx, "over35", None), getattr(fx, "under35", None))
    p_btts = _pair(getattr(fx, "btts_yes", None), getattr(fx, "btts_no", None))
    if None in (p_over_15, p_over_35, p_btts):
        return None          # a missing line is never filled with a guess (HR35)
    return FixtureProbabilities(
        home_team=fx.home_team, away_team=fx.away_team,
        lambda_home=None, lambda_away=None,          # no goals model behind these
        p_home=ih / tot, p_draw=id_ / tot, p_away=ia / tot,
        p_over_15=p_over_15, p_over_25=p_over_25, p_over_35=p_over_35,
        p_btts_yes=p_btts,
    )
