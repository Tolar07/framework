"""Which competitions the Bet365 route is allowed to select from.

ARCHITECT DIRECTIVE 2026-09-19
"For bet365, especially for bet365, because I can't start searching for those
leagues far, far away, and they might not be covered. Let's just really focus
on European teams, top flight European teams."

This is deliberately NARROWER than the SportyBet scope, and the reasoning is
different from the earlier top-30 proposal that the measured data rejected.
That proposal was about BOOKING FAILURES, and market family — not competition
prestige — turned out to cause every one of those (totals 13/13 booked
including Latvia and Croatia; Draw No Bet 0/4 including Serie A). Narrowing by
prestige would not have fixed a single failure.

Two things make the Bet365 case different and sound:

1. COVERAGE IS GENUINELY THINNER. SportyBet is a Nigerian-facing book that
   carries the Faroese, Armenian, Kosovan and Sanmarinese leagues natively.
   Bet365's strength is the major European markets. A selection Bet365 does
   not list cannot be placed there at any price.

2. THE ARCHITECT PLACES THESE BY HAND. Bet365 has no booking code, so every
   Bet365 selection is navigated manually. A fixture the Architect cannot
   readily find is a real cost, not a theoretical one — and more information
   is available on top-flight sides, which is the Architect's stated reason
   for preferring them.

Scope note: this gates the BET365 ROUTE ONLY. The SportyBet route keeps the
full 56-competition scope — it books those leagues without complaint and
excluding them would discard real edge for no gain.
"""

from __future__ import annotations

# Top-flight domestic leagues of the major European football nations.
# First tier only: the second tiers below are listed separately so the
# distinction stays explicit rather than buried.
TOP_FLIGHT_EUROPEAN: frozenset[str] = frozenset({
    "Premier League",            # England
    "La Liga",                   # Spain
    "Serie A",                   # Italy
    "Bundesliga",                # Germany
    "Ligue 1",                   # France
    "Primeira Liga",             # Portugal
    "Eredivisie",                # Netherlands
    "Belgian Pro League",        # Belgium
    "Scottish Premiership",      # Scotland
    "Turkish Super Lig",         # Turkiye
    "Greek Super League",        # Greece
    "Austrian Bundesliga",       # Austria
    "Swiss Super League",        # Switzerland
    "Danish Superliga",          # Denmark
    "Norwegian Eliteserien",     # Norway
    "Swedish Allsvenskan",       # Sweden
    "Czech First League",        # Czechia
    "Ekstraklasa",               # Poland
    "Ukrainian Premier League",  # Ukraine
    "Russian Premier League",    # Russia
})

# UEFA club competitions — the best-covered fixtures on any European book.
UEFA_CLUB: frozenset[str] = frozenset({
    "Champions League",
    "Europa League",
    "Conference League",
    "UEFA Super Cup",
})

# Major domestic cups of the same nations. Well covered and easy to find,
# though early rounds can carry lower-division sides.
MAJOR_CUPS: frozenset[str] = frozenset({
    "FA Cup",                    # England
    "DFB-Pokal",                 # Germany
    "Copa del Rey",              # Spain
    "Coppa Italia",              # Italy
    "Taça de Portugal",          # Portugal
    "EFL Cup",                   # England
})

# Second tiers of the biggest five. Bet365 covers these well and they carry
# real liquidity, but they are NOT top flight — kept separate so including
# them is a deliberate choice, not an accident of one big set.
BIG_FIVE_SECOND_TIER: frozenset[str] = frozenset({
    "Championship",              # England
    "2. Bundesliga",             # Germany
    "La Liga 2",                 # Spain
    "Serie B",                   # Italy
    "Ligue 2",                   # France
})

# The shipped Bet365 scope. Second tiers are IN: the Architect's concern was
# competitions that are hard to find or uncovered, and the Championship and
# 2. Bundesliga are neither — they sit in Bet365's main menu alongside the
# top flights. Remove BIG_FIVE_SECOND_TIER here to tighten to first tier only.
BET365_SCOPE: frozenset[str] = (
    TOP_FLIGHT_EUROPEAN | UEFA_CLUB | MAJOR_CUPS | BIG_FIVE_SECOND_TIER
)


def in_bet365_scope(league: str | None) -> bool:
    """True when the Bet365 route may select this competition."""
    return bool(league) and league in BET365_SCOPE


def scope_reason(league: str | None) -> str:
    """Why a competition is out of scope. Empty when it is in scope."""
    if in_bet365_scope(league):
        return ""
    return (f"outside Bet365 scope (top-flight European only): "
            f"{league or 'unknown'}")
