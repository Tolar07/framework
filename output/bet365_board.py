"""Render the Bet365 section of the nightly Telegram message.

ARCHITECT DIRECTIVE 2026-09-19
"Although Bet365 does not have a booking code, but at least if I see
everything in the list and the leagues, the name of the leagues, the country
and the time, I can easily go and book that."

So this renders for a HUMAN NAVIGATING A MENU, not for a paste box. Every leg
carries country, competition, kickoff and market because those four are what
you need to find a fixture in Bet365's sidebar. There is no code and this
never claims one — a "Booking code: PENDING" line here would imply one is
coming, and none is (HR35).

Scope is booking.bet365_scope (top-flight European), narrower than SportyBet's
by directive: Bet365's coverage is genuinely thinner outside the major
European markets, and every Bet365 selection is placed by hand, so a fixture
the Architect cannot find in the menu is a real cost rather than a
theoretical one.
"""

from __future__ import annotations

from typing import Iterable, Optional

from booking.bet365_scope import in_bet365_scope

# Flags for the countries the Bet365 scope can produce. A country absent here
# renders without a flag rather than with a wrong one.
_FLAG = {
    "England": "🇬🇧", "Spain": "🇪🇸", "Italy": "🇮🇹", "Germany": "🇩🇪",
    "France": "🇫🇷", "Portugal": "🇵🇹", "Netherlands": "🇳🇱",
    "Belgium": "🇧🇪", "Scotland": "🏴󠁧󠁢󠁳󠁣󠁴󠁿", "Turkey": "🇹🇷", "Greece": "🇬🇷",
    "Austria": "🇦🇹", "Switzerland": "🇨🇭", "Denmark": "🇩🇰",
    "Norway": "🇳🇴", "Sweden": "🇸🇪", "Czech Republic": "🇨🇿",
    "Czechia": "🇨🇿", "Poland": "🇵🇱", "Ukraine": "🇺🇦", "Russia": "🇷🇺",
    "International Clubs": "🇪🇺",
}


def _country_for(league: str) -> str:
    """Country as the booking registry records it, or PENDING."""
    try:
        from booking.league_map import SPORTYBET_LEAGUES
        m = SPORTYBET_LEAGUES.get(league)
        return m.country if m else "PENDING"
    except Exception:
        return "PENDING"


def filter_to_scope(legs: Iterable) -> list:
    """Legs whose competition the Bet365 route may select from."""
    return [l for l in legs if in_bet365_scope(_league_of(l))]


def build_bet365_accas(board: list, board_date: str, **kwargs) -> list:
    """Build Bet365 accas FROM the in-scope pool — separate production.

    NOT a filtered copy of the SportyBet accas. Filtering them produced 2-leg
    remnants of 5-leg bets on the 2026-09-19 board: a different, weaker bet
    wearing the same label. The Architect asked for Bet365 production to be
    made separately over the competitions Bet365 actually carries, which is
    what this does — the acca builder runs again over the scoped board and
    fills a full route from it.

    Returns the same ProductionBets-derived acca list the SportyBet route
    uses, so both sides of the nightly message are built by identical logic
    and differ only in their fixture pool.
    """
    from engine.acca import build_production_bets
    from pipeline.production_stage_b import _build_acca_route

    scoped = [bf for bf in board
              if in_bet365_scope(_league_from_fixture(bf))]
    if not scoped:
        return []
    bets = build_production_bets(scoped, today=board_date, odds_index=None,
                                 **kwargs)
    route = _build_acca_route(bets)
    return list(getattr(route, "accas", []) or [])


def _league_from_fixture(bf) -> Optional[str]:
    """League of a BoardFixture, whose name carries it as a suffix."""
    lg = getattr(bf, "league", None)
    if lg:
        return lg
    name = getattr(bf, "fixture", "") or ""
    if name.endswith(")") and " (" in name:
        return name.rsplit(" (", 1)[1][:-1]
    return None


def _league_of(leg) -> Optional[str]:
    if isinstance(leg, dict):
        return leg.get("league")
    return getattr(leg, "league", None)


def _field(leg, name: str, default=None):
    if isinstance(leg, dict):
        return leg.get(name, default)
    return getattr(leg, name, default)


def render_bet365_section(accas: list, heartbeats: Optional[list] = None,
                          board_date: str = "") -> str:
    """The Bet365 block of the nightly message.

    `accas` is a list of {label, legs[...]} (dicts or objects). Legs outside
    the Bet365 scope are dropped and COUNTED — an acca that loses legs is
    reported as reduced, never silently shortened, because a 5-leg acca
    quietly rendered as 3 legs is a different bet.
    """
    out: list[str] = []
    out.append("=" * 34)
    out.append("BET365 — top-flight European only")
    out.append("No booking code on Bet365. Build these by")
    out.append("hand; country, league and kickoff are listed")
    out.append("so each one is findable in the menu.")
    out.append("")

    any_content = False
    for acca in accas or []:
        label = _field(acca, "label", "Acca")
        legs = _field(acca, "legs", []) or []
        kept = filter_to_scope(legs)
        dropped = len(legs) - len(kept)
        if not kept:
            out.append(f"▸ {label} — NOT PLAYABLE on Bet365")
            out.append(f"   all {len(legs)} legs outside top-flight European scope")
            out.append("")
            continue
        any_content = True
        combined = 1.0
        for l in kept:
            combined *= (_field(l, "price") or 1.0)
        out.append("-" * 34)
        header = f"▸ {label} — {len(kept)} legs"
        if dropped:
            header += f"  (REDUCED from {len(legs)})"
        out.append(header)
        if dropped:
            out.append(f"   {dropped} leg(s) dropped: outside Bet365 scope.")
            out.append("   This is NOT the same bet as the SportyBet acca.")
        for i, l in enumerate(kept, 1):
            lg = _league_of(l) or "PENDING"
            country = _country_for(lg)
            flag = _FLAG.get(country, "")
            ko = _field(l, "kickoff_utc") or "??:??"
            out.append(f"{i}. {ko}  {_field(l, 'fixture', '?')}")
            out.append(f"      {flag} {country} · {lg}".rstrip())
            out.append(f"      {_field(l, 'market_name', '?')} @ "
                       f"{_field(l, 'price', '?')}")
        out.append(f"   Combined odds ............... {combined:.2f}")
        out.append("")

    for hb in heartbeats or []:
        lg = _league_of(hb) or "PENDING"
        if not in_bet365_scope(lg):
            continue
        any_content = True
        country = _country_for(lg)
        flag = _FLAG.get(country, "")
        out.append(f"▸ HEARTBEAT {_field(hb, 'lineage_id', '')}")
        out.append(f"   {_field(hb, 'kickoff_utc') or '??:??'}  "
                   f"{_field(hb, 'fixture', '?')}")
        out.append(f"      {flag} {country} · {lg}".rstrip())
        out.append(f"      {_field(hb, 'market_name', '?')} @ "
                   f"{_field(hb, 'price', '?')}")
        out.append("")

    if not any_content:
        out.append("Nothing in scope for Bet365 on this board.")
        out.append("Reported rather than omitted (HR35).")
        out.append("")

    out.append("Prices shown are SPORTYBET's. Bet365 will")
    out.append("differ — check its price before staking.")
    return "\n".join(out)
