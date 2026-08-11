"""Team name mapping — OLP XDV short names to SportyBet/Bet365 official names.

OLP XDV uses football-data.co.uk short names (e.g. "For Sittard", "Nijmegen").
SportyBet uses official/registered names (e.g. "Fortuna Sittard", "NEC Nijmegen").
Bet365 uses yet another set of names.

Strategy: exact match first, then fuzzy prefix/substring match.
The TEAM_ALIASES tables in pipeline/odds.py and data/thesportsdb_fixtures.py
document known name differences — this module consolidates them.
"""
from __future__ import annotations
import re
from difflib import SequenceMatcher
from typing import Optional


# --- SportyBet team names (verified live 2026-08-08) ---
SPORTYBET_TEAMS: dict[str, str] = {
    # Eredivisie — values are the SportyBet league-page spellings (verified from
    # the 2026-08-11 cache); the keys are the football-data model keys.
    "Nijmegen": "NEC Nijmegen",
    "Telstar": "SC Telstar",           # Eerste Divisie, not on SportyBet Eredivisie
    "Go Ahead Eagles": "Go Ahead Eagles",
    "Willem II": "Willem II Tilburg",
    "PSV Eindhoven": "PSV Eindhoven",
    "For Sittard": "Fortuna Sittard",
    "Groningen": "FC Groningen",
    "Utrecht": "FC Utrecht",
    "Heerenveen": "SC Heerenveen",
    "Twente": "FC Twente Enschede",
    "Sparta Rotterdam": "Sparta Rotterdam",
    "Feyenoord": "Feyenoord",
    "Ajax": "Ajax",
    "Zwolle": "PEC Zwolle",
    "AZ Alkmaar": "Alkmaar",           # SportyBet league page spells AZ "Alkmaar"
    "Alkmaar": "Alkmaar",              # legacy alias; reverse picks "AZ Alkmaar" (first)
    "Excelsior": "Excelsior Rotterdam",
    # Danish Superliga
    "Randers FC": "Randers FC",
    "Lyngby": "Lyngby BK",
    "AC Horsens": "AC Horsens",
    "Brondby": "Broendby IF",
    "Silkeborg": "Silkeborg IF",
    "Odense": "Odense Boldklub",
    "AGF Aarhus": "AGF Aarhus",
    "Viborg": "Viborg FF",
    "Nordsjaelland": "Nordsjaelland",
    "Midtjylland": "FC Midtjylland",
    "SonderjyskE": "SonderjyskE",
    "Copenhagen": "Copenhagen",
    # Scottish Premiership — values are the SportyBet league-page spellings
    # (2026-08-11 cache): SportyBet appends "FC" to most SPFL names.
    "Celtic": "Celtic",
    "Rangers": "Rangers",
    "Hearts": "Heart of Midlothian FC",
    "Aberdeen": "Aberdeen",
    "Hibernian": "Hibernian FC",
    "Dundee": "Dundee",
    "Dundee United": "Dundee United",
    "Motherwell": "Motherwell FC",
    "St Mirren": "St Mirren FC",
    "Kilmarnock": "Kilmarnock FC",
    "Falkirk": "Falkirk FC",
    "St Johnstone": "St Johnstone",
    # Belgian Pro League — values are the SportyBet league-page spellings
    # (2026-08-11 cache). "Club Brugge" and "Kortrijk" were previously missing
    # entirely, so the fuzzy matcher attached them to the WRONG clubs ("Club
    # Brugge" -> Cercle Brugge). The no-fuzzy reverse resolver prevents that
    # class of corruption.
    "Standard": "Standard Liege",
    "Cercle Brugge": "Cercle Brugge",
    "Club Brugge": "Club Brugge",
    "Westerlo": "KVC Westerlo",
    "St. Gilloise": "Union Gilloise",
    "St Truiden": "St. Truidense VV",
    "Lommel": "Lommel SK",
    "Kortrijk": "KV Kortrijk",
    "Charleroi": "Royal Charleroi SC",
    "Oud-Heverlee Leuven": "Oud-Heverlee Leuven",
    "Gent": "Gent",
    "Mechelen": "Yellow-Red KV Mechelen",
    "Waregem": "SV Zulte Waregem",
    "Genk": "Genk",
    "Anderlecht": "RSC Anderlecht",
    "Antwerp": "Royal Antwerp FC",
    "Beveren": "KV Waasland-Beveren",
    # Ekstraklasa (2026-08-11) — model keys from odds.py aliases. Other clubs in
    # the division are NOT mapped: they pass through unchanged (NO DATA — PENDING)
    # rather than risk a wrong map (HR35).
    "Legia": "Legia Warszawa",
    "Jagiellonia": "Jagiellonia Bialystok",
    "Pogon Szczecin": "Pogon Szczecin",
    "Zaglebie": "Zaglebie Lubin",
    # Premier League
    "Arsenal": "Arsenal",
    "Man City": "Man City",
    "Liverpool": "Liverpool",
    "Chelsea": "Chelsea",
    "Man Utd": "Man Utd",
    "Tottenham": "Tottenham",
    "Newcastle": "Newcastle",
    "Aston Villa": "Aston Villa",
    "Brighton": "Brighton",
    "Bournemouth": "Bournemouth",
    "West Ham": "West Ham",
    "Brentford": "Brentford",
    "Crystal Palace": "Crystal Palace",
    "Wolves": "Wolves",
    "Fulham": "Fulham",
    "Everton": "Everton",
    "Nottm Forest": "Nottm Forest",
    "Ipswich Town": "Ipswich Town",
    "Leicester": "Leicester",
    "Leeds United": "Leeds United",
    "Sunderland AFC": "Sunderland AFC",
    "Burnley": "Burnley",
    "Sheffield Utd": "Sheffield United",
    "Sheffield United": "Sheffield United",
    # Newly promoted for 2026/27 — unrated by the model, but explicitly
    # mapped to itself so the fuzzy matcher never guesses a WRONG club
    # (e.g. "Coventry City" must not match "Exeter City"). The "new to this
    # division" check then recognises it instead of reporting a mis-map.
    "Coventry City": "Coventry City",
    # EFL Cup / Championship
    "Mansfield Town": "Mansfield Town",
    "Plymouth Argyle": "Plymouth Argyle",
    "Exeter City": "Exeter City",
    "Millwall": "Millwall FC",
    # La Liga — SportyBet uses standard names that match OLP keys.
    # Add as identity mappings so reverse lookup (SportyBet -> OLP) works.
    "Real Madrid": "Real Madrid",
    "Barcelona": "Barcelona",
    "Atletico Madrid": "Atletico Madrid",
    "Alaves": "Alaves",
    "Getafe": "Getafe",
    "Sevilla": "Sevilla",
    "Rayo Vallecano": "Rayo Vallecano",
    "Villarreal": "Villarreal",
    "Espanyol": "Espanyol",
    "Levante": "Levante",
    "Celta": "Celta",
    "Osasuna": "Osasuna",
    "Racing Santander": "Racing Santander",
    "Valencia": "Valencia",
    "Athletic Bilbao": "Athletic Bilbao",
    "Real Sociedad": "Real Sociedad",
    "Betis": "Real Betis",
    "Mallorca": "Mallorca",
    "Girona": "Girona",
    "Las Palmas": "Las Palmas",
    "Leganes": "Leganes",
    # Serie A
    "Inter": "Inter Milan",
    "AC Milan": "AC Milan",
    "Juventus": "Juventus",
    "Napoli": "Napoli",
    "Roma": "Roma",
    "Lazio": "Lazio",
    # Bundesliga
    "Bayern Munich": "Bayern Munich",
    "Dortmund": "Borussia Dortmund",
    "RB Leipzig": "RB Leipzig",
    "Bayer Leverkusen": "Bayer Leverkusen",
    "Eintracht Frankfurt": "Eintracht Frankfurt",
    # Ligue 1 — SportyBet uses standard names that match OLP keys.
    # Add as identity mappings so reverse lookup (SportyBet -> OLP) works.
    "PSG": "Paris Saint-Germain",
    "Monaco": "Monaco",
    "Lille": "Lille",
    "Lyon": "Lyon",
    "Marseille": "Marseille",
    "Nice": "Nice",
    "Rennes": "Rennes",
    "Toulouse": "Toulouse",
    "Lorient": "Lorient",
    "Troyes": "Troyes",
    "Paris FC": "Paris FC",
    "Le Havre": "Le Havre",
    "Angers": "Angers",
    "Strasbourg": "Strasbourg",
    "Auxerre": "AJ Auxerre",
    "Brest": "Brest",
    "Lens": "RC Lens",
    "Reims": "Reims",
    "Montpellier": "Montpellier",
    "Nantes": "Nantes",
    "Saint Etienne": "Saint-Etienne",
    "Le Mans FC": "Le Mans FC",
    # Primeira Liga
    "Porto": "FC Porto",
    "Benfica": "Benfica",
    "Sp Lisbon": "Sporting CP",
    "Braga": "SC Braga",
    "Guimaraes": "Vitoria de Guimaraes",
    # Champions League / Europa League
    "Fenerbahce": "Fenerbahce Istanbul",
    "Sturm Graz": "SK Sturm Graz",
    "Bodoe/Glimt": "Bodoe/Glimt",
    "AGF Aarhus": "AGF Aarhus",
}


# Reverse table: SportyBet league-page spelling -> OLP XDV model key. Built
# once from SPORTYBET_TEAMS (model key -> SportyBet name). First-wins on
# collisions preserves the canonical key — the table is ordered canonical-
# before-alias, e.g. "AZ Alkmaar" before "Alkmaar" (reverse("Alkmaar") ->
# "AZ Alkmaar") and "Sheffield Utd" before "Sheffield United" (reverse
# ("Sheffield United") -> "Sheffield Utd").
_MODEL_BY_SPORTYBET: dict[str, str] = {}
for _olp_key, _sb_name in SPORTYBET_TEAMS.items():
    _MODEL_BY_SPORTYBET.setdefault(_sb_name, _olp_key)


def _normalize(name: str) -> str:
    """Normalize a team name for comparison."""
    name = name.lower().strip()
    # Remove common prefixes/suffixes
    for prefix in ("fc ", "sc ", "ac ", "cd ", "cf ", "rk ", "ss "):
        if name.startswith(prefix):
            name = name[len(prefix):]
    for suffix in (" fc", " sc", " ac", " cf", " if", " bk", " fk", " sk"):
        if name.endswith(suffix):
            name = name[:-len(suffix)]
    # Remove diacritics (basic)
    replacements = {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u",
                    "ä": "a", "ö": "o", "ü": "u", "ñ": "n", "ø": "o",
                    "æ": "ae", "ß": "ss"}
    for old, new in replacements.items():
        name = name.replace(old, new)
    return name.strip()


def resolve_team(olp_name: str, bookmaker: str = "sportybet") -> str:
    """Resolve an OLP XDV team name to a bookmaker's official name.

    Strategy:
    1. Exact match in SPORTYBET_TEAMS / BET365_TEAMS dict
    2. Fuzzy match using normalized names and SequenceMatcher
    3. Return original name if no match found (best effort)

    Returns the bookmaker's official name, or the original OLP name as fallback.
    """
    # 1. Exact match
    if bookmaker == "sportybet":
        if olp_name in SPORTYBET_TEAMS:
            return SPORTYBET_TEAMS[olp_name]
    # (Bet365 teams TBD)

    # 2. Fuzzy match
    target = _normalize(olp_name)
    best_match = None
    best_score = 0.0

    source = SPORTYBET_TEAMS if bookmaker == "sportybet" else {}
    for olp_key, bm_name in source.items():
        bm_norm = _normalize(bm_name)
        # Prefix match (one contains the other)
        if target in bm_norm or bm_norm in target:
            score = 0.9
        else:
            score = SequenceMatcher(None, target, bm_norm).ratio()
        if score > best_score:
            best_score = score
            best_match = bm_name

    if best_score >= 0.6:
        return best_match

    # 3. Fallback: return original
    return olp_name


def resolve_team_to_model(sportybet_name: str) -> str:
    """SportyBet league-page name -> OLP XDV model key (football-data short name).

    The REVERSE of resolve_team, used by the SportyBet cache builder so
    model_home/model_away hold REAL model keys, not SportyBet spellings. The
    old code called resolve_team backwards (SportyBet name -> table of
    SportyBet VALUES), which fuzzy-matched one club against another and could
    return a DIFFERENT team entirely — e.g. "Millwall FC" -> "AC Milan",
    "Club Brugge" -> "Cercle Brugge", "Excelsior Rotterdam" ->
    "Sparta Rotterdam". That attached one club's real price to the wrong model
    team.

    EXACT + NORMALIZED-EXACT ONLY — deliberately NO fuzzy pass (HR35). A name
    that isn't in the reverse table returns UNCHANGED so the caller reports
    NO DATA — PENDING. Attaching a real price to the wrong team is worse than
    an honest gap, so we never guess across clubs.
    """
    if sportybet_name in _MODEL_BY_SPORTYBET:
        return _MODEL_BY_SPORTYBET[sportybet_name]
    target = _normalize(sportybet_name)
    for sb_name, model_key in _MODEL_BY_SPORTYBET.items():
        if _normalize(sb_name) == target:
            return model_key
    return sportybet_name
