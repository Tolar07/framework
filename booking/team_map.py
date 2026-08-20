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
    "Ath Madrid": "Atletico Madrid",          # common short form -> canonical
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
    # Newly promoted 2026/27 - identity mappings (HR35: never guess across clubs)
    "Malaga CF": "Malaga CF",
    "Malaga": "Malaga CF",
    "Levante": "Levante",
    "Racing Santander": "Racing Santander",
    "Elche CF": "Elche CF",
    "Elche": "Elche CF",
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
    # Champions League / Europa League. The board's model keys are the
    # football-data.co.uk spellings ("Bodo/Glimt", "Sparta Praha",
    # "Olympiakos Piraeus", "Fenerbahçe"); SportyBet's league page uses
    # "Bodoe/Glimt", "Sparta Prague", "Olympiacos", "Fenerbahce Istanbul".
    # These entries make the reverse resolver produce model keys that MATCH the
    # board, so the SportyBet-price join and the booking-code driver both
    # resolve (the old cache silently stored SportyBet spellings as model keys
    # — e.g. "Sparta Rotterdam" for the board's "Sparta Praha" — and every
    # acca leg reported 'fixture not found').
    "Fenerbahce": "Fenerbahce Istanbul",
    "Fenerbahçe": "Fenerbahce Istanbul",   # board/ç variant -> same SportyBet
    "Sturm Graz": "SK Sturm Graz",
    "Bodo/Glimt": "Bodoe/Glimt",           # football-data key -> SportyBet
    "Bodoe/Glimt": "Bodoe/Glimt",          # legacy alias (reverse prefers Bodo/Glimt)
    "Sparta Praha": "Sparta Prague",
    "Olympiakos Piraeus": "Olympiacos",
    "AGF Aarhus": "AGF Aarhus",
    # UEFA qualifiers (2026-08-11 board). Without these the fuzzy matcher in
    # resolve_team attached WRONG clubs (Celje -> Chelsea, Iberia 1999 ->
    # Hibernian FC, Larne -> Levante, SK Brann -> SC Braga) — a real price on
    # the wrong team. With the exact entry the exact match wins (HR35); the
    # reverse table also picks up these SportyBet spellings, so the next cache
    # build stores model keys that match the board directly.
    "Celje": "NK Celje",
    "Ararat-Armenia": "FC Ararat-Armenia",
    "Hapoel Be'er Sheva": "Hapoel Be`er Sheva FC",  # SportyBet spells it with a backtick
    "Mjällby": "Mjallby AIF",
    "Mjallby": "Mjallby AIF",
    "Kairat Almaty": "FC Kairat Almaty",
    "Levski Sofia": "PFC Levski Sofia",
    "Kauno Žalgiris": "FK Kauno Zalgiris",
    "Kauno Zalgiris": "FK Kauno Zalgiris",
    "Dinamo Zagreb": "GNK Dinamo Zagreb",
    "Sabah Baku": "Sabah Masazir",      # SportyBet's spelling of the Baku club (Masazir)
    "Aarhus": "AGF Aarhus",             # CL-qualifier board key; AGF's Danish pool key is "Aarhus"
    "FK Crvena Zvezda": "Crvena Zvezda",
    "Iberia 1999": "FC Iberia 1999",
    "Larne": "Larne FC",
    "SK Brann": "SK Brann",             # identity — blocks the fuzzy guess "SC Braga"
    "Slovan Bratislava": "Slovan Bratislava",   # identity
    "Panathinaikos": "Panathinaikos",           # identity
    "FC CSKA 1948": "FC CSKA 1948",             # identity
    "Apollon Limassol": "Apollon Limassol",     # identity
    # Champions League qualifiers - LASK Linz mapping
    "LASK Linz": "LASK Linz",              # SportyBet spelling (uppercase)
    "Lask Linz": "LASK Linz",              # board key (capitalized) -> SportyBet
    "Linz": "LASK Linz",                   # short form
    # Conference/Europa League qualifiers - ensure board model keys resolve to
    # SportyBet cache names so odds lookup succeeds (no cross-club guessing;
    # each target is the verified same club).
    "FC ST. Gallen": "FC St. Gallen 1879",  # board model key -> SportyBet cache name
    "FC St. Gallen": "FC St. Gallen 1879",  # normalized variant
    "Borac Banja Luka": "FK Borac Banja Luka",  # board model key -> SportyBet (FK prefix)
    "Egnatia": "KF Egnatia Rrogozhine",     # board model key -> SportyBet cache name
    "Lillestroem": "Lillestroem SK",        # board model key -> SportyBet cache name
    "Lillestrøm": "Lillestroem SK",         # diacritic variant
    "Lillestrom": "Lillestroem SK",         # normalized variant (board key)
    "Omonia Nicosia": "AC Omonia Nicosia",  # board model key -> SportyBet cache name
    "Vikingur Reykjavik": "Vikingur Reykjavik",  # already matches; identity for clarity
    "St Truiden": "St. Truidense VV",       # board model key -> SportyBet cache name
    # Additional Conference/Europa League name variants found in cache
    "Sp Braga": "Braga",                     # board model key -> SportyBet cache name
    "Rīgas FS": "Riga FC",                   # board diacritic variant -> SportyBet cache name
    "Rigas FS": "Rigas FS",                   # normalized variant (SportyBet cache uses "Rigas FS")
    "Rakow": "Rakow Czestochowa",            # board model key -> SportyBet cache name
    # --- Armenian Premier League (2026-08-18): TheSportsDB fixture feed -> SportyBet spellings
    # Verified from TheSportsDB feed names; SportyBet uses same spellings for these clubs.
    "Noah": "FC Noah",
    "Alashkert": "FC Alashkert",
    "Ararat-Armenia": "FC Ararat-Armenia",
    "Urartu": "FC Urartu",
    "Shirak": "Shirak Gyumri",
    "Ararat": "Ararat Yerevan",
    # --- Maltese Premier League (2026-08-18): TheSportsDB fixture feed -> SportyBet spellings
    # Verified from TheSportsDB feed names; SportyBet uses same spellings for these clubs.
    "Birkirkara": "Birkirkara",
    "Gzira United": "Gzira United",
    "Hamrun Spartans": "Hamrun Spartans",
    "Mosta": "Mosta",
    "Balzan": "Balzan FC",
    "Floriana": "Floriana",
    "Valletta": "Valletta",
    "Zabbar St. Patrick": "Zabbar St. Patrick",
    "Birzebbuga St. Peter": "Birzebbuga St. Peter",
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
    # Remove common prefixes/suffixes. "sk " / "fk " are Scandinavian club
    # prefixes ("SK Sturm Graz", "FK Kauno Zalgiris") — without them the
    # reverse resolver can't match "SK Sturm Graz" back to model key "Sturm
    # Graz", and the cache stores the SportyBet spelling as the model key.
    for prefix in ("fc ", "sc ", "ac ", "cd ", "cf ", "rk ", "ss ", "sk ", "fk "):
        if name.startswith(prefix):
            name = name[len(prefix):]
    for suffix in (" fc", " sc", " ac", " cf", " if", " bk", " fk", " sk"):
        if name.endswith(suffix):
            name = name[:-len(suffix)]
    # Remove diacritics (basic). ç matters for "Fenerbahçe" — without it the
    # board's football-data key never normalizes equal to SportyBet's plain
    # "Fenerbahce", so the leg silently no-matches.
    replacements = {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u",
                    "ä": "a", "ö": "o", "ü": "u", "ñ": "n", "ø": "o",
                    "æ": "ae", "ß": "ss", "ç": "c", "ž": "z", "ī": "i",
                    "ș": "s", "ț": "t", "ğ": "g", "ş": "s", "ü": "u",
                    "ő": "o", "ű": "u", "ğ": "g", "ö": "o", "ş": "s",
                    "č": "c", "š": "s", "ř": "r", "ď": "d", "ť": "t",
                    "ń": "n", "ľ": "l"}
    for old, new in replacements.items():
        name = name.replace(old, new)
    return name.strip()


def resolve_team(olp_name: str, bookmaker: str = "sportybet") -> str:
    """Resolve an OLP XDV team name to a bookmaker's official name.

    EXACT + NORMALIZED-EXACT ONLY — deliberately NO fuzzy pass (HR35), mirroring
    resolve_team_to_model. The old fuzzy pass returned a DIFFERENT club when the
    board key wasn't in the table (verified live 2026-08-11: "Celje" -> "Chelsea",
    "Iberia 1999" -> "Hibernian FC", "Larne" -> "Levante", "SK Brann" ->
    "SC Braga"), which would attach one club's real price to the wrong team.
    An unmapped name returns UNCHANGED so the caller reports NO DATA — PENDING
    rather than guess across clubs; add a verified alias instead.

    Returns the bookmaker's official name, or the original OLP name as fallback.
    """
    # 1. Exact match
    if bookmaker == "sportybet":
        if olp_name in SPORTYBET_TEAMS:
            return SPORTYBET_TEAMS[olp_name]
    # (Bet365 teams TBD)

    # 2. Normalized-exact (case/diacritics/prefix/suffix equal) — never fuzzy.
    target = _normalize(olp_name)
    source = SPORTYBET_TEAMS if bookmaker == "sportybet" else {}
    for olp_key, bm_name in source.items():
        if _normalize(olp_key) == target:
            return bm_name

    # 3. Unmapped: return the original — an honest NO DATA, never a guess.
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
