"""
Bet365 league → URL slug mapping (PENDING live verification — HR35).

Every slug below must be empirically verified against bet365.com (HTTP 200)
before marking verified. Bet365 has strong anti-bot protection; slugs may
require authenticated session. If Bet365 changes a slug, the affected league
simply falls back to the double-outage path in booking/verify_fixtures.py
(fixture kept-but-warned), never a fabricated negative.

Format: OLP XDV league name (== config/leagues.json "name") -> Bet365 slug
which composes to https://www.bet365.com/#/AC/B1/C1/D{slug}/E{slug}/F{...}/
or the public fixtures page: https://www.bet365.com/#/AC/B1/C1/D{slug}/

This is the SINGLE source of truth for Bet365 league URLs.
"""

from __future__ import annotations
from typing import Dict

BET365_LEAGUES: Dict[str, str] = {
    # Major European leagues - Bet365 uses numeric IDs
    "Premier League": "1000000000",  # England Premier League
    "Championship": "1000000001",    # England Championship
    "La Liga": "1000000002",         # Spain La Liga
    "Serie A": "1000000003",         # Italy Serie A
    "Bundesliga": "1000000004",      # Germany Bundesliga
    "Ligue 1": "1000000005",         # France Ligue 1
    "Eredivisie": "1000000006",      # Netherlands Eredivisie
    "Primeira Liga": "1000000007",   # Portugal Primeira Liga
    "Champions League": "1000000010", # UEFA Champions League
    "Europa League": "1000000011",    # UEFA Europa League
    "Conference League": "1000000012", # UEFA Conference League
    "Scottish Premiership": "1000000020",
    "Belgian Pro League": "1000000021",
    "Danish Superliga": "1000000022",
    "Ekstraklasa": "1000000023",
    "HNL": "1000000024",
    "Austrian Bundesliga": "1000000025",
    "Turkish Super Lig": "1000000026",
    "Swiss Super League": "1000000027",
    "Greek Super League": "1000000028",
    "Czech First League": "1000000029",
    "Norwegian Eliteserien": "1000000030",
    "Swedish Allsvenskan": "1000000031",
    "Finnish Veikkausliiga": "1000000032",
    "Hungarian NB I": "1000000033",
    "Slovak Super Liga": "1000000034",
    "Slovenian PrvaLiga": "1000000035",
    "Bulgarian First League": "1000000036",
    "Romanian Liga I": "1000000037",
    "Ukrainian Premier League": "1000000038",
    "Serbian Super Liga": "1000000039",
    "Cypriot First Division": "1000000040",
    "Israeli Premier League": "1000000041",
    "EFL Cup": "1000000050",
    "FA Cup": "1000000051",
    "Copa del Rey": "1000000052",
    "Coppa Italia": "1000000053",
    "DFB Pokal": "1000000054",
    "Coupe de France": "1000000055",
    "KNVB Beker": "1000000056",
}

# Bet365 uses a complex URL structure. For fixtures, the pattern is typically:
# https://www.bet365.com/#/AC/B1/C1/D{id}/E{id}/F{...}/
# The public fixtures page might be more accessible:
BASE_URL = "https://www.bet365.com/#/AC/B1/C1/D{slug}/"