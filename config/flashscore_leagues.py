"""
FlashScore league → URL slug mapping (RATIFIED 2026-08-16).

Every slug below was empirically verified against flashscore.com (HTTP 200) on
2026-08-16 by probing the live site — NOT guessed. HR35: we never fabricate a
URL we have not confirmed resolves. If FlashScore changes a slug, the affected
league simply falls back to the double-outage path in booking/verify_fixtures.py
(fixture kept-but-warned), never a fabricated negative.

Format: OLP XDV league name (== config/leagues.json "name") -> "country/slug"
which composes to https://www.flashscore.com/football/<country>/<slug>/

This is the SINGLE source of truth for FlashScore league URLs. The scraper
(scrape_live_odds_v3.py) and the verification gate both import FLASHSCORE_LEAGUES.
"""
from __future__ import annotations

from typing import Dict

FLASHSCORE_LEAGUES: Dict[str, str] = {
    "Premier League": "england/premier-league",
    "La Liga": "spain/laliga",
    "Serie A": "italy/serie-a",
    "Bundesliga": "germany/bundesliga",
    "Ligue 1": "france/ligue-1",
    "Champions League": "europe/champions-league",
    "Europa League": "europe/europa-league",
    "Conference League": "europe/conference-league",
    "UEFA Super Cup": "europe/uefa-super-cup",
    "Scottish Premiership": "scotland/premiership",
    "Belgian Pro League": "belgium/jupiler-pro-league",
    "Eredivisie": "netherlands/eredivisie",
    "Championship": "england/championship",
    "Primeira Liga": "portugal/liga-portugal",
    "Danish Superliga": "denmark/superliga",
    "Ekstraklasa": "poland/ekstraklasa",
    "HNL": "croatia/hnl",
    "Austrian Bundesliga": "austria/bundesliga",
    "EFL Cup": "england/efl-cup",
    "Turkish Super Lig": "turkey/super-lig",
    "Russian Premier League": "russia/premier-league",
    "Swiss Super League": "switzerland/super-league",
    "Greek Super League": "greece/super-league",
    "Czech First League": "czech-republic/chance-liga",
    "Romanian Liga I": "romania/superliga",
    "Ukrainian Premier League": "ukraine/premier-league",
    "Serbian Super Liga": "serbia/mozzart-bet-super-liga",
    "Norwegian Eliteserien": "norway/eliteserien",
    "Swedish Allsvenskan": "sweden/allsvenskan",
    "Finnish Veikkausliiga": "finland/veikkausliiga",
    "Hungarian NB I": "hungary/nb-i",
    "Slovak Super Liga": "slovakia/nike-liga",
    "Slovenian PrvaLiga": "slovenia/prva-liga",
    "Bulgarian First League": "bulgaria/efbet-league",
    "Israeli Premier League": "israel/ligat-ha-al",
    "Cypriot First Division": "cyprus/cyprus-league",
    "Albanian Superliga": "albania/abissnet-superiore",
    "Armenian Premier League": "armenia/premier-league",
    "Azerbaijani Premyer Liqa": "azerbaijan/premier-league",
    "Belarusian Premier League": "belarus/premier-league",
    "Kazakhstan Premier League": "kazakhstan/premier-league",
    "Kosovan Superliga": "kosovo/superliga",
    "Latvian Virsliga": "latvia/virsliga",
    "Lithuanian A Lyga": "lithuania/toplyga",
    "Luxembourg National Division": "luxembourg/bgl-ligue",
    "Maltese Premier League": "malta/premier-league",
    "Moldovan Super Liga": "moldova/super-liga",
    "Montenegrin First League": "montenegro/prva-crnogorska-liga",
    "Estonian Meistriliiga": "estonia/meistriliiga",
    "Georgian Erovnuli Liga": "georgia/crystalbet-erovnuli-liga",
    "Northern Irish Premiership": "northern-ireland/nifl-premiership",
    "Welsh Premier League": "wales/cymru-premier",
    "Republic of Ireland Premier Division": "ireland/premier-division",
    "Icelandic Urvalsdeild": "iceland/besta-deild-karla",
    "Faroe Islands Premier League": "faroe-islands/premier-league",
    "North Macedonian First League": "north-macedonia/1-mfl",
    "Bosnian Premier League": "bosnia-and-herzegovina/wwin-liga-bih",
    "Gibraltarian National League": "gibraltar/national-league",
    "Andorran Primera Divisió": "andorra/primera-divisio",
    "Sanmarinese Campionato": "san-marino/campionato-sammarinese",
    "Liechtensteiner Cup": "liechtenstein/liechtenstein-cup",
}

BASE_URL = "https://www.flashscore.com/football/{slug}/"
