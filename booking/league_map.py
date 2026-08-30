"""League and country mapping — OLP XDV names to SportyBet/Bet365 names.

SportyBet organizes by country (sidebar) then league (sub-item).
Bet365 uses a similar country > league hierarchy.
This module maps OLP XDV's league names to the correct country + league for each bookmaker.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class BookmakerLeague:
    """A league as a bookmaker knows it."""
    country: str          # sidebar country name (e.g. "Netherlands", "England")
    league: str           # sub-league name (e.g. "Eredivisie", "EFL Cup")
    odds_format: str = "decimal"  # "decimal" for SportyBet/Bet365 Nigeria


# --- SportyBet mapping ---
# Verified live 2026-08-08 by navigating the SportyBet Nigeria sidebar.
# "Conference League" (2026-08-10) follows the SAME "International Clubs" /
# UEFA-family pattern as Champions League + Europa League — SportyBet lists all
# three UEFA club comps under that one country node. Flagged for re-verification
# on the next cache build (HR35: a wrong sidebar sub-item silently returns
# another competition's fixtures).
SPORTYBET_LEAGUES: dict[str, BookmakerLeague] = {
    "Eredivisie":          BookmakerLeague("Netherlands", "Eredivisie"),
    "Danish Superliga":    BookmakerLeague("Denmark", "Superliga"),
    "Belgian Pro League":  BookmakerLeague("Belgium", "Pro League"),
    "Scottish Premiership": BookmakerLeague("Scotland", "Premiership"),
    "Ekstraklasa":         BookmakerLeague("Poland", "Ekstraklasa"),
    "HNL":                 BookmakerLeague("Croatia", "HNL"),
    "Championship":        BookmakerLeague("England", "Championship"),
    "Serie A":             BookmakerLeague("Italy", "Serie A"),
    "Serie B":             BookmakerLeague("Italy", "Serie B"),
    "Bundesliga":          BookmakerLeague("Germany", "Bundesliga"),
    "Ligue 1":             BookmakerLeague("France", "Ligue 1"),
    "Ligue 2":             BookmakerLeague("France", "Ligue 2"),
    "Europa League":       BookmakerLeague("International Clubs", "UEFA Europa League"),
    "Conference League":   BookmakerLeague("International Clubs", "UEFA Conference League"),
    "Primeira Liga":       BookmakerLeague("Portugal", "Liga Portugal"),
    "Liga Portugal":       BookmakerLeague("Portugal", "Liga Portugal"),   # acca payload alias
    "Premier League":      BookmakerLeague("England", "Premier League"),
    "La Liga":             BookmakerLeague("Spain", "La Liga"),
    "LaLiga":              BookmakerLeague("Spain", "LaLiga"),   # acca payload alias
    "La Liga 2":           BookmakerLeague("Spain", "LaLiga2"),
    "Champions League":    BookmakerLeague("International Clubs", "UEFA Champions League"),
    "Austrian Bundesliga": BookmakerLeague("Austria", "Bundesliga"),
    "EFL Cup":             BookmakerLeague("England", "EFL Cup"),
    # --- Missing leagues from acca payload (2026-08-23) ---
    "Russian Premier League": BookmakerLeague("Russia", "Premier League"),
    "Swiss Super League":     BookmakerLeague("Switzerland", "Super League"),
    "Super League":           BookmakerLeague("Switzerland", "Super League"),  # acca payload alias
    "Turkish Super Lig":      BookmakerLeague("Turkiye", "Super Lig"),
    # --- Domestic cups & secondary comps (PENDING live SportyBet sidebar
    # --- verification — HR35). The 06/11 below were originally committed with a
    # --- false "verified live 2026-08-16" label; a live browser check on
    # --- 2026-08-16 proved 05/11 were WRONG (the "26/27" season suffix is not
    # --- used by SportyBet's sidebar for these cups -> nav=False, rows=0 ->
    # --- silent wrong-competition contamination). The suffix was stripped from
    # --- the 5 failures; all 11 remain PENDING until a live re-check confirms
    # --- each sub-item resolves to real fixtures. Do NOT mark verified until
    # --- the live browser check returns nav=True for each.
    "FA Cup":              BookmakerLeague("England", "FA Cup"),
    "Community Shield":    BookmakerLeague("England", "Community Shield"),
    "EFL Trophy":          BookmakerLeague("England", "EFL Trophy"),
    "Copa del Rey":        BookmakerLeague("Spain", "Copa del Rey"),
    "Coppa Italia":        BookmakerLeague("Italy", "Coppa Italia"),
    "DFB Pokal":           BookmakerLeague("Germany", "DFB Pokal"),
    "German Super Cup":    BookmakerLeague("Germany", "Super Cup"),
    "Coupe de France":     BookmakerLeague("France", "Coupe de France"),
    "KNVB Beker":          BookmakerLeague("Netherlands", "KNVB beker"),
    "OFB Cup":             BookmakerLeague("Austria", "OFB Cup"),
    "Scottish League Cup": BookmakerLeague("Scotland", "League Cup"),
    # --- NEW 2026-08-12: Require live SportyBet sidebar verification (HR35) ---
    # These mappings are PENDING live verification — wrong sub-item = silent wrong data
    "Süper Lig":           BookmakerLeague("Turkiye", "Super Lig"),
    "Super League Greece": BookmakerLeague("Greece", "Super League"),
    # NOTE: "Swiss Super League" duplicate removed — correct mapping is on line 51 (Country: Switzerland, League: Super League)
    "Eliteserien":         BookmakerLeague("Norway", "Eliteserien"),
    "Allsvenskan":         BookmakerLeague("Sweden", "Allsvenskan"),
    "Czech First League":  BookmakerLeague("Czech Republic", "First League"),
    # --- OLP XDV official name aliases (2026-08-13): same SportyBet league, different OLP key ---
    # Norwegian Eliteserien (OLP) == Eliteserien (SportyBet)
    "Norwegian Eliteserien": BookmakerLeague("Norway", "Eliteserien"),
    # Turkish Super Lig (OLP) == Super Lig (SportyBet) — sidebar uses "Turkiye" + "Super Lig" (no diacritics)
    "Turkish Super Lig":     BookmakerLeague("Turkiye", "Super Lig"),
    # Greek Super League (OLP) == Super League Greece (SportyBet)
    "Greek Super League":    BookmakerLeague("Greece", "Super League"),
    # Swedish Allsvenskan (OLP) == Allsvenskan (SportyBet)
    "Swedish Allsvenskan":   BookmakerLeague("Sweden", "Allsvenskan"),
    # --- ACCA PAYLOAD ALIASES (2026-08-23): keys used in acca_<date>.json payload ---
    # These map directly to SportyBet sidebar names (verified live from SportyBet JSON)
    "LaLiga":                BookmakerLeague("Spain", "LaLiga"),
    "Pro League":            BookmakerLeague("Belgium", "Pro League"),
    "Liga Portugal":         BookmakerLeague("Portugal", "Liga Portugal"),
    "Super League":          BookmakerLeague("Switzerland", "Super League"),
    # --- NEW 2026-08-14: 33 missing whitelisted leagues — HR35 pending live sidebar verification ---
    # These mappings are PENDING live verification — wrong sub-item = silent wrong data
    "Albanian Superliga":         BookmakerLeague("Albania", "Superliga"),
    "Andorran Primera Divisió":   BookmakerLeague("Andorra", "Primera Divisió"),
    "Armenian Premier League":    BookmakerLeague("Armenia", "Premier League"),
    "Azerbaijani Premyer Liqa":   BookmakerLeague("Azerbaijan", "Premyer Liqa"),
    "Belarusian Premier League":  BookmakerLeague("Belarus", "Premier League"),
    "Bosnian Premier League":     BookmakerLeague("Bosnia", "Premier League"),
    "Bulgarian First League":     BookmakerLeague("Bulgaria", "First League"),
    "Cypriot First Division":     BookmakerLeague("Cyprus", "First Division"),
    "Estonian Meistriliiga":      BookmakerLeague("Estonia", "Meistriliiga"),
    "Faroe Islands Premier League": BookmakerLeague("Faroe Islands", "Premier League"),
    "Finnish Veikkausliiga":      BookmakerLeague("Finland", "Veikkausliiga"),
    "Georgian Erovnuli Liga":     BookmakerLeague("Georgia", "Erovnuli Liga"),
    "Gibraltarian National League": BookmakerLeague("Gibraltar", "National League"),
    "Hungarian NB I":             BookmakerLeague("Hungary", "NB I"),
    "Icelandic Urvalsdeild":      BookmakerLeague("Iceland", "Urvalsdeild"),
    "Israeli Premier League":     BookmakerLeague("Israel", "Premier League"),
    "Kazakhstani Premier League": BookmakerLeague("Kazakhstan", "Premier League"),
    "Kosovan Superliga":          BookmakerLeague("Kosovo", "Superliga"),
    "Latvian Virsliga":           BookmakerLeague("Latvia", "Virsliga"),
    "Liechtensteiner Cup":        BookmakerLeague("Liechtenstein", "Cup"),
    "Lithuanian A Lyga":          BookmakerLeague("Lithuania", "A Lyga"),
    "Luxembourg National Division": BookmakerLeague("Luxembourg", "National Division"),
    "Maltese Premier League":     BookmakerLeague("Malta", "Premier League"),
    "Moldovan Super Liga":        BookmakerLeague("Moldova", "Super Liga"),
    "Montenegrin First League":   BookmakerLeague("Montenegro", "First League"),
    "North Macedonian First League": BookmakerLeague("North Macedonia", "First League"),
    "Northern Irish Premiership": BookmakerLeague("Northern Ireland", "Premiership"),
    "Republic of Ireland Premier Division": BookmakerLeague("Republic of Ireland", "Premier Division"),
    "Romanian Liga I":            BookmakerLeague("Romania", "Liga I"),
    # NOTE: "Russian Premier League" duplicate removed — correct mapping is on line 50 (Country: Russia, League: Premier League)
    "Sanmarinese Campionato":     BookmakerLeague("San Marino", "Campionato"),
    "Serbian Super Liga":         BookmakerLeague("Serbia", "Super Liga"),
    "Slovak Super Liga":          BookmakerLeague("Slovakia", "Super Liga"),
    "Slovenian PrvaLiga":         BookmakerLeague("Slovenia", "PrvaLiga"),
    "UEFA Super Cup":             BookmakerLeague("International Clubs", "UEFA Super Cup"),
    "Welsh Premier League":       BookmakerLeague("Wales", "Cymru Premier"),
}

# --- Bet365 mapping ---
# Bet365 uses similar country > league hierarchy.
# TODO: verify live once Bet365 browser automation is tested.
BET365_LEAGUES: dict[str, BookmakerLeague] = {
    "Eredivisie":          BookmakerLeague("Netherlands", "Eredivisie"),
    "Danish Superliga":    BookmakerLeague("Denmark", "Superligaen"),
    "Belgian Pro League":  BookmakerLeague("Belgium", "Pro League"),
    "Scottish Premiership": BookmakerLeague("Scotland", "Premiership"),
    "Ekstraklasa":         BookmakerLeague("Poland", "Ekstraklasa"),
    "HNL":                 BookmakerLeague("Croatia", "1. HNL"),
    "Championship":        BookmakerLeague("England", "Championship"),
    "Serie A":             BookmakerLeague("Italy", "Serie A"),
    "Bundesliga":          BookmakerLeague("Germany", "Bundesliga"),
    "Ligue 1":             BookmakerLeague("France", "Ligue 1"),
    "Europa League":       BookmakerLeague("International", "Europa League"),
    "Conference League":   BookmakerLeague("International", "Conference League"),
    "UEFA Super Cup":      BookmakerLeague("International", "Super Cup"),
    "Primeira Liga":       BookmakerLeague("Portugal", "Liga Portugal"),
    "Premier League":      BookmakerLeague("England", "Premier League"),
    "La Liga":             BookmakerLeague("Spain", "La Liga"),
    "Champions League":    BookmakerLeague("International", "Champions League"),
    "Austrian Bundesliga": BookmakerLeague("Austria", "Bundesliga"),
    "EFL Cup":             BookmakerLeague("England", "League Cup"),
    # --- NEW 2026-08-12: Require live Bet365 verification ---
    "Süper Lig":           BookmakerLeague("Turkiye", "Super Lig"),
    "Super League Greece": BookmakerLeague("Greece", "Super League"),
    "Swiss Super League":  BookmakerLeague("Switzerland", "Super League"),
    "Eliteserien":         BookmakerLeague("Norway", "Eliteserien"),
    "Allsvenskan":         BookmakerLeague("Sweden", "Allsvenskan"),
    "Czech First League":  BookmakerLeague("Czech Republic", "First League"),
}


def resolve_bookmaker(olp_league: str, bookmaker: str = "sportybet") -> Optional[BookmakerLeague]:
    """Resolve an OLP XDV league name to a bookmaker's country + league names.
    
    Returns None if the league is not mapped (unknown league for this bookmaker).
    """
    mapping = SPORTYBET_LEAGUES if bookmaker == "sportybet" else BET365_LEAGUES
    return mapping.get(olp_league)
