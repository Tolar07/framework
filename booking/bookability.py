"""What the booking driver can actually put on a SportyBet slip.

WHY THIS EXISTS (Architect directive 2026-09-19)
------------------------------------------------
Selection and booking had no shared notion of what is bookable, so the board
could spend its best edges on legs that die at the betslip. On the 2026-09-19
board 6 of 20 acca legs could not be driven and 3 of 4 accas therefore produced
no booking code — the work was done, priced and published, and then could not
be placed.

The Architect's instruction was to build from the pool we can actually book.
The first instinct was to narrow the competition universe to the top 20-30
leagues, on the theory that obscure clubs are the hard ones to find. The
measured data says otherwise:

    Totals            13 booked / 0 failed   (incl. Latvia, Croatia, Serbia)
    1X2                1 booked / 0 failed   (Israel)
    Draw No Bet        0 booked / 4 failed   (incl. ITALY SERIE A, 2. BUNDESLIGA)
    Double Chance      0 booked / 2 failed   (incl. Romania)

Competition prestige predicted nothing; market family predicted everything.
A top-30 filter would have kept both mainstream failures and discarded 13 legs
that booked without complaint. So the gate keys on what is measured to work:
the competition must be in the booking registry, and the market must have a
drive path that has been proven against the live site.

This module is the single source of truth for that question. It lives in the
booking layer because the booking layer is what knows; the acca builder asks.
"""

from __future__ import annotations

from typing import Optional, Tuple

from booking.league_map import SPORTYBET_LEAGUES
from booking.rebuild_cache import SPORTYBET_CATEGORY_TOURNAMENT

# Market families whose drive path has been verified against the live site.
# A key absent here is NOT assumed broken — it is assumed UNPROVEN, which for
# selection purposes is the same decision (do not spend an edge on it) but a
# different claim (HR35). Move a family in only after observing it land on a
# real slip, and say in the commit what run proved it.
#
# Totals: league-page row plus match-page fallback for off-featured lines.
#   Proven 13/13 on 2026-09-19.
# 1X2: league-page row. Proven 1/1 on 2026-09-19 (Hapoel Beer Sheva).
# DNB / DC: match page, exact market header + rendered outcome label.
#   Proven 3/3 in isolation on 2026-09-19 (sr:match:71945284) — the league-page
#   path never worked because _MARKET_UI_MAP held glyph codes ("1X", "1") that
#   SportyBet renders nowhere.
_DRIVABLE_MARKETS = frozenset({
    "OVER_0_5", "UNDER_0_5",
    "OVER_1_5", "UNDER_1_5",
    "OVER_2_5", "UNDER_2_5",
    "OVER_3_5", "UNDER_3_5",
    "1X2_HOME", "1X2_DRAW", "1X2_AWAY",
    "DNB_HOME", "DNB_AWAY",
    "DC_1X", "DC_12", "DC_X2",
})

# Families deliberately held OUT until someone watches them land. Listed
# explicitly so the gap is visible in code review rather than implied by
# absence: BTTS drives through a league-page inline control that was not
# exercised on 2026-09-19, and Correct Score / HT-FT have never been observed
# to produce a code.
_UNPROVEN_MARKETS = frozenset({"BTTS_YES", "BTTS_NO"})


def market_is_drivable(market_key: Optional[str]) -> bool:
    """True when the booking driver has a proven path for this market."""
    return bool(market_key) and market_key in _DRIVABLE_MARKETS


def competition_is_bookable(league: Optional[str]) -> bool:
    """True when the league can be navigated AND has a resolved tournament id.

    BOTH are required and they are separate maps: league_map supplies the
    country/league names the driver navigates by, SPORTYBET_CATEGORY_TOURNAMENT
    supplies the (category, tournament) ids the match-page URL is built from.
    A competition in one but not the other is not bookable — Taça de Portugal
    was missing from both and silently contributed 11 unbookable fixtures.
    """
    if not league:
        return False
    if league not in SPORTYBET_LEAGUES:
        return False
    ids = SPORTYBET_CATEGORY_TOURNAMENT.get(league)
    return bool(ids) and tuple(ids)[:2] != (0, 0)


def leg_is_bookable(league: Optional[str],
                    market_key: Optional[str]) -> Tuple[bool, str]:
    """(ok, reason). `reason` is empty when ok, else names what is missing.

    The reason is returned rather than logged so the caller can put it on the
    board: a leg withheld for an unbookable reason is reported, never dropped
    silently (HR35).
    """
    if not competition_is_bookable(league):
        return False, f"competition not bookable on SportyBet: {league or 'unknown'}"
    if not market_is_drivable(market_key):
        if market_key in _UNPROVEN_MARKETS:
            return False, f"market drive path unproven: {market_key}"
        return False, f"market not drivable: {market_key or 'unknown'}"
    return True, ""
