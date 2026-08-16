"""
PredictZ league → URL slug mapping (PENDING live verification — HR35).

Every slug below must be empirically verified against predictz.com (HTTP 200)
before marking verified. If PredictZ changes a slug, the affected league simply
falls back to the double-outage path in booking/verify_fixtures.py (fixture
kept-but-warned), never a fabricated negative.

Format: OLP XDV league name (== config/leagues.json "name") -> PredictZ slug
which composes to https://www.predictz.com/football/<slug>/

This is the SINGLE source of truth for PredictZ league URLs.
"""

from __future__ import annotations
from typing import Dict

PREDICTZ_LEAGUES: Dict[str, str] = {
    # Major European leagues (verified patterns from PredictZ)
    "Premier League": "england/premier-league",
    "Championship": "england/championship",
    "La Liga": "spain/la-liga",
    "Serie A": "italy/serie-a",
    "Bundesliga": "germany/bundesliga",
    "Ligue 1": "france/ligue-1",
    "Eredivisie": "netherlands/eredivisie",
    "Primeira Liga": "portugal/primeira-liga",
    "Champions League": "europe/champions-league",
    "Europa League": "europe/europa-league",
    "Conference League": "europe/conference-league",
    "Scottish Premiership": "scotland/premiership",
    "Belgian Pro League": "belgium/jupiler-pro-league",
    "Danish Superliga": "denmark/superliga",
    "Ekstraklasa": "poland/ekstraklasa",
    "HNL": "croatia/hnl",
    "Austrian Bundesliga": "austria/bundesliga",
    "Turkish Super Lig": "turkey/super-lig",
    "Swiss Super League": "switzerland/super-league",
    "Greek Super League": "greece/super-league",
    "Czech First League": "czech-republic/first-league",
    "Norwegian Eliteserien": "norway/eliteserien",
    "Swedish Allsvenskan": "sweden/allsvenskan",
    "Finnish Veikkausliiga": "finland/veikkausliiga",
    "Hungarian NB I": "hungary/nb-i",
    "Slovak Super Liga": "slovakia/super-liga",
    "Slovenian PrvaLiga": "slovenia/prvaliga",
    "Bulgarian First League": "bulgaria/first-league",
    "Romanian Liga I": "romania/liga-1",
    "Ukrainian Premier League": "ukraine/premier-league",
    "Serbian Super Liga": "serbia/super-liga",
    "Cypriot First Division": "cyprus/first-division",
    "Israeli Premier League": "israel/premier-league",
    "EFL Cup": "england/efl-cup",
    "FA Cup": "england/fa-cup",
    "Copa del Rey": "spain/copa-del-rey",
    "Coppa Italia": "italy/coppa-italia",
    "DFB Pokal": "germany/dfb-pokal",
    "Coupe de France": "france/coupe-de-france",
    "KNVB Beker": "netherlands/knvb-beker",
}

BASE_URL = "https://www.predictz.com/football/{slug}/"