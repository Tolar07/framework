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
    "Bundesliga":          BookmakerLeague("Germany", "Bundesliga"),
    "Ligue 1":             BookmakerLeague("France", "Ligue 1"),
    "Europa League":       BookmakerLeague("International Clubs", "UEFA Europa League"),
    "Conference League":   BookmakerLeague("International Clubs", "UEFA Conference League"),
    "Primeira Liga":       BookmakerLeague("Portugal", "Liga Portugal"),
    "Premier League":      BookmakerLeague("England", "Premier League"),
    "La Liga":             BookmakerLeague("Spain", "LaLiga"),
    "Champions League":    BookmakerLeague("International Clubs", "UEFA Champions League"),
    "Austrian Bundesliga": BookmakerLeague("Austria", "Bundesliga"),
    "EFL Cup":             BookmakerLeague("England", "EFL Cup"),
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
    "Primeira Liga":       BookmakerLeague("Portugal", "Liga Portugal"),
    "Premier League":      BookmakerLeague("England", "Premier League"),
    "La Liga":             BookmakerLeague("Spain", "La Liga"),
    "Champions League":    BookmakerLeague("International", "Champions League"),
    "Austrian Bundesliga": BookmakerLeague("Austria", "Bundesliga"),
    "EFL Cup":             BookmakerLeague("England", "League Cup"),
}


def resolve_bookmaker(olp_league: str, bookmaker: str = "sportybet") -> Optional[BookmakerLeague]:
    """Resolve an OLP XDV league name to a bookmaker's country + league names.
    
    Returns None if the league is not mapped (unknown league for this bookmaker).
    """
    mapping = SPORTYBET_LEAGUES if bookmaker == "sportybet" else BET365_LEAGUES
    return mapping.get(olp_league)
