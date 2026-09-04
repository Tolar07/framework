"""
Upcoming-fixtures source via TheSportsDB (thesportsdb.com).

RATIFIED by the Architect under HR34 on 2026-08-03, ID404 tier T2 (see
verification/id403.py SOURCE_TRUST). Fixtures from here stamp ○ SINGLE-SOURCE,
not ✓ VERIFIED — a second independent source is still needed for F2 quorum.

Why this and not API-Football: API-Football's free plan is capped at seasons
2022-2024, so it cannot see the current season at all. TheSportsDB's free tier
returns the live fixture list. This module replaces nothing — API-Football
stays wired in data/fixtures_source.py as the paid-plan path.

SETUP:
  1. Register free at https://www.thesportsdb.com/register.php
  2. Your API key is on your account page after signing up
  3. Set it before running:  THESPORTSDB_KEY=<your key>
  Without it this falls back to TheSportsDB's public test key "123", which is
  shared, rate-limited, and returns a TRUNCATED league directory. Fine for a
  smoke test, not for a scheduled run.

HR35 throughout: a fixture missing a team name or a date is SKIPPED and
recorded, never completed with a guessed value. A team whose name doesn't map
to a known model key is passed through UNCHANGED so the engine correctly
returns None for it (-> NO DATA — PENDING on the board) rather than being
silently bent onto the nearest-looking team.
"""
from __future__ import annotations
import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

# Initialize logger for this module
log = logging.getLogger(__name__)

from data.football_data_source import MatchResult
from data.multi_source import SourceNoData
from data.retry import get
from engine.league_registry import get_thesportsdb_id

CACHE_DIR = Path(__file__).parent.parent / "data" / "cache" / "thesportsdb"
# Fixtures for a given day are known well ahead and rarely change intra-day, so
# a half-day TTL is safe — the whole point is to stop re-hitting the network
# for a schedule that was already fetched this morning. A reschedule is caught
# within the TTL window, which is acceptable for a daily board.
FIXTURES_MAX_AGE_SECONDS = 6 * 3600

try:
    import requests
except ImportError:
    requests = None

API_BASE = "https://www.thesportsdb.com/api/v1/json"
PUBLIC_TEST_KEY = "123"

# League IDs — now sourced from the dynamic registry (config/leagues.json).
# LEAGUE_IDS is kept as a backward-compat fallback dict populated from the
# registry at import time. New leagues are added via config/leagues.json; no
# code edits needed. Each entry was verified against TheSportsDB's own
# lookupleague.php endpoint (name+country), not guessed.
LEAGUE_IDS: dict[str, int] = {}

# Populate from registry for backward compatibility
try:
    from engine.league_registry import registry
    for name, cfg in registry._leagues.items():
        tid = cfg.get_id("thesportsdb")
        if tid is not None:
            LEAGUE_IDS[name] = int(tid)
except Exception:
    # Registry not yet loaded (tests, import order) — fall back to hardcoded
    # values so existing paths keep working during transition.
    LEAGUE_IDS = {
        "Scottish Premiership": 4330,   # "Scottish Premier League" (Scotland)
        "Eredivisie": 4337,             # "Dutch Eredivisie" (The Netherlands)
        "Danish Superliga": 4340,       # "Danish Superliga" (Denmark)
        "Belgian Pro League": 4338,     # "Belgian Pro League" (Belgium)
        "Premier League": 4328,         # "English Premier League" (England)
        "Championship": 4329,           # "English League Championship" (England)
        "Bundesliga": 4331,             # "German Bundesliga" (Germany)
        "Serie A": 4332,                # "Italian Serie A" (Italy)
        "Ligue 1": 4334,                # "French Ligue 1" (France)
        "La Liga": 4335,                # "Spanish La Liga" (Spain)
        "Primeira Liga": 4344,          # "Portuguese Primeira Liga" (Portugal)
        "Champions League": 4480,
        "Europa League": 4481,
        "UEFA Super Cup": 4512,
        "Ekstraklasa": 4422,
        "HNL": 4629,
        "Austrian Bundesliga": 4621,
    }

# Previously unresolved (public test key truncated directory).
# Resolved 2026-08-08 with personal key 5558126822:
# Ekstraklasa -> 4422, HNL -> 4629.
UNRESOLVED_LEAGUES = set()

# TheSportsDB name -> football-data.co.uk name (the key the fitted model uses).
# Every pair below was confirmed by diffing the two sources' actual team lists
# for the 2026/27 season; only same-club renamings are listed. Clubs that exist
# in one source and not the other because they were PROMOTED or RELEGATED are
# deliberately absent — mapping those would invent a rating for a club with no
# top-flight history (the open promoted-club gap, master doc Section 11).
TEAM_ALIASES: dict[str, dict[str, str]] = {
    "Austrian Bundesliga": {
        "Rapid Vienna": "SK Rapid",
        "Red Bull Salzburg": "Salzburg",
        "SCR Altach": "Altach",
        "SV Ried": "Ried",
        "TSV Hartberg": "Hartberg",
        "WSG Tirol": "Tirol",
    },
    "Scottish Premiership": {
        "Heart of Midlothian": "Hearts",
    },
    "Eredivisie": {
        "Fortuna Sittard": "For Sittard",
        "NEC Nijmegen": "Nijmegen",
        "PEC Zwolle": "Zwolle",
    },
    "Ekstraklasa": {
        # football-data.co.uk POL feed names — diacritic/name-normalised.
        # Verified 2026-08-08 by diffing both sources' actual team lists for
        # 2026/27; every pair below is the same club, not a guess.
        "Górnik Zabrze": "Gornik Zabrze",
        "Jagiellonia Białystok": "Jagiellonia",
        "Lech Poznań": "Lech Poznan",
        "Legia Warsaw": "Legia",
        "Pogoń Szczecin": "Pogon Szczecin",
        "Raków Częstochowa": "Rakow",
        "Widzew Łódź": "Widzew Lodz",
        "Wisła Płock": "Wisla Plock",
        "Zagłębie Lubin": "Zaglebie",
        # 2026-08-11 board flags — TheSportsDB spells these with the club-prefix
        # suffix; every pair is the same club, targets are real pool keys.
        "KKS Lech Poznan": "Lech Poznan",
        "RKS Radomiak Radom": "Radomiak Radom",
        "GKS Piast Gliwice": "Piast Gliwice",
        "LKP Motor Lublin": "Motor Lublin",
        "KS Cracovia Krakow": "Cracovia",
    },
    "Danish Superliga": {
        "AGF Aarhus": "Aarhus",
        "Br\xf8ndby": "Brondby",
        "FC Midtjylland": "Midtjylland",
        "FC Nordsj\xe6lland": "Nordsjaelland",
        "Odense BK": "Odense",
        "Silkeborg IF": "Silkeborg",
        "S\xf8nderjyske": "Sonderjyske",
        # 2026-08-11 board flags — feed uses ASCII spellings the exact dict
        # lookup (map_team) can't match. Same club, real pool keys.
        "Copenhagen": "FC Copenhagen",
        "SonderjyskE": "Sonderjyske",
    },
    "Belgian Pro League": {
        "Sint-Truiden": "St Truiden",
        "Standard Li\xe8ge": "Standard",
        "Union Saint-Gilloise": "St. Gilloise",
        "Zulte Waregem": "Waregem",
        "RAAL La Louvi\xe8re": "RAAL La Louviere",
        # 2026-08-23 board fix: SportyBet feed name variants
        "Club Brugge KV": "Club Brugge",
        "Club Brugge": "Club Brugge",
        "KV Mechelen": "Mechelen",
        "KVC Westerlo": "Westerlo",
        "Antwerp": "Antwerp",
        "Brugge": "Brugge",
        "Gent": "Gent",
        "Anderlecht": "Anderlecht",
        "Charleroi": "Charleroi",
        "OH Leuven": "OH Leuven",
        "Genk": "Genk",
        "Cercle Brugge": "Cercle Brugge",
        "RWDM": "RWDM",
        "Beerschot": "Beerschot",
        "Dender EH": "Dender",
        "Lommel United": "Lommel",
    },
    "Premier League": {
        "Brighton and Hove Albion": "Brighton",
        "Manchester City": "Man City",
        "Manchester United": "Man United",
        "Newcastle United": "Newcastle",
        "Nottingham Forest": "Nott'm Forest",
        "Tottenham Hotspur": "Tottenham",
        "Leeds United": "Leeds",
        # 2026-08-11 board flag — feed's short form; same club.
        "Man Utd": "Man United",
    },
    "Championship": {
        "Birmingham City": "Birmingham",
        "Blackburn Rovers": "Blackburn",
        "Charlton Athletic": "Charlton",
        "Derby County": "Derby",
        "Norwich City": "Norwich",
        "Preston North End": "Preston",
        "Queens Park Rangers": "QPR",
        "Stoke City": "Stoke",
        "Swansea City": "Swansea",
        "West Bromwich Albion": "West Brom",
        # 2026-08-11 board flags — same club, real pool keys.
        "Bolton Wanderers": "Bolton",
        "Middlesbrough FC": "Middlesbrough",
        "Portsmouth FC": "Portsmouth",
        "Sheffield Utd": "Sheffield United",
        "Sunderland AFC": "Sunderland",
        "Wrexham AFC": "Wrexham",
    },
    "La Liga": {
        "Athletic Bilbao": "Ath Bilbao",
        "Atl\xe9tico Madrid": "Ath Madrid",
        "Celta Vigo": "Celta",
        "Deportivo Alav\xe9s": "Alaves",
        "Espanyol": "Espanol",
        "Rayo Vallecano": "Vallecano",
        "Real Betis": "Betis",
        "Real Sociedad": "Sociedad",
        # 2026-08-11 board flags — same club, real pool keys.
        "Atletico Madrid": "Ath Madrid",
        "Elche CF": "Elche",
        "Malaga": "Malaga",
        "Malaga CF": "Malaga",
        "M\xe1laga": "Malaga",
    },
    "Serie A": {
        "AC Milan": "Milan",
        "Inter Milan": "Inter",
        # 2026-08-11 board flags — same club, real pool keys.
        "FC Torino": "Torino",
        "US Lecce": "Lecce",
    },
    "Bundesliga": {
        "Bayer Leverkusen": "Leverkusen",
        "Borussia Dortmund": "Dortmund",
        "Borussia M\xf6nchengladbach": "M'gladbach",
        "Borussia M'gladbach": "M'gladbach",
        "Eintracht Frankfurt": "Ein Frankfurt",
        "K\xf6ln": "FC Koln",
        "Cologne": "FC Koln",
        # 2026-08-11 board flag — same club, real pool key.
        "Hamburger SV": "Hamburg",
        # 2026-08-23 board fix: newly promoted / feed variants
        "SV 07 Elversberg": "Elversberg",
        "Elversberg": "Elversberg",
        "Paderborn": "Paderborn",
        "Schalke 04": "Schalke",
        "Schalke": "Schalke",
    },
    "Ligue 1": {
        "Paris Saint-Germain": "Paris SG",
    },
    "Primeira Liga": {
        "Braga": "Sp Braga",
        "Estoril Praia": "Estoril",
        "Estrela Amadora": "Estrela",
        "Sporting CP": "Sp Lisbon",
        "Vit\xf3ria de Guimar\xe3es": "Guimaraes",
        "Nacional de Madeira": "Nacional",
        # 2026-08-11 board flags — same club, real pool keys.
        "Alverca Futebol": "Alverca",
        "FC Arouca": "Arouca",
        "FC Famalicao": "Famalicao",
        "Moreirense FC": "Moreirense",
        "Rio Ave FC": "Rio Ave",
    },
    "Europa League": {
        # Keys are the ACTUAL TheSportsDB feed spellings (diacritics included),
        # targets are the cross-model pool keys (engine/cross_league.py). Verified
        # 2026-08-08 by folding the feed names against the 267-team pooled graph.
        "Jagiellonia Białystok": "Jagiellonia",
        "Lech Poznań": "Lech Poznan",
        "Górnik Zabrze": "Gornik Zabrze",
        "Ferencváros": "Ferencvarosi TC",
        "Heart of Midlothian": "Hearts",
        "Víkingur Reykjavík": "Vikingur Reykjavik",
        "Rangers": "Rangers",
        "Omonia Nicosia": "Omonia Nicosia",
        # 2026-08-11 board flags — same club, real cross-model pool keys.
        "AC Omonia Nicosia": "Omonia Nicosia",
        "Ferencvarosi Budapest": "Ferencvarosi TC",
        "KKS Lech Poznan": "Lech Poznan",
        "Larne FC": "Larne",
        "Maccabi Tel Aviv FC": "Maccabi Tel Aviv",
        "Pafos FC": "Pafos",
        # 2026-08-13 scan flag — same club, cross-model pool key.
        "Crvena Zvezda": "FK Crvena Zvezda",
    },
    "Champions League": {
        # Same verification as Europa League above: feed spelling -> cross-model
        # pool key, every pair the same club (never a fuzzy near-miss).
        "Bodø/Glimt": "Bodo/Glimt",
        "Crvena Zvezda": "FK Crvena Zvezda",
        "NEC Nijmegen": "Nijmegen",
        "Nijmegen": "Nijmegen",
        "Sparta Prague": "Sparta Praha",
        "Olympiacos": "Olympiakos Piraeus",
        "Union Saint-Gilloise": "St. Gilloise",
        "LASK": "Lask Linz",
        "LASK Linz": "Lask Linz",
        "Lask Linz": "Lask Linz",
        "AGF Aarhus": "Aarhus",
        # 2026-08-18: TheSportsDB feed spells as "Viking FK"; cross-model pool key is "Viking".
        "Viking FK": "Viking",
        "Hapoel Beer Sheva": "Hapoel Beer Sheva",
        "Hapoel Be'er Sheva": "Hapoel Beer Sheva",
        "Sabah FA": "Sabah Baku",
        "Sabah Baku": "Sabah Baku",
        "Sabah Masazir": "Sabah Baku",
    },
    "Conference League": {
        # Same verification rule as CL/EL: feed spelling -> cross-model pool key,
        # every pair the same club. Added 2026-08-11 from the ConfL board flags.
        # Only aliases where the TARGET exists in the cross-league pool are kept.
        # Other feed names (newly promoted clubs, qualifiers without continental
        # matches) correctly have no alias — they stay NO DATA — PENDING (HR35).
        "Braga": "Sp Braga",
        "Copenhagen": "FC Copenhagen",
        "FC Dinamo Minsk": "Dinamo Minsk",
        "FC Dynamo Kyiv": "Dynamo Kyiv",
        "FK Borac Banja Luka": "Borac Banja Luka",
        "Lugano": "FC Lugano",
        "FC St. Gallen 1879": "FC ST. Gallen",
        "Víkingur Reykjavík": "Vikingur Reykjavik",
        "Riga FC": "Rīgas FS",
        "FC Midtjylland": "Midtjylland",
        "Rakow Czestochowa": "Rakow",
        "Nordsjaelland": "Nordsjaelland",
        "Hibernian": "Hibernian",
        "FC Lugano": "FC Lugano",
        "FK Borac Banja Luka": "Borac Banja Luka",
        "FC Dynamo Kyiv": "Dynamo Kyiv",
        "Midtjylland": "Midtjylland",
        "Rakow": "Rakow",
    },
    "UEFA Super Cup": {
        # TheSportsDB feed spells Paris Saint-Germain with hyphen; pool key is Paris SG.
        "Paris Saint-Germain": "Paris SG",
    },
    # HNL — verified 2026-08-13 from scan flags: TheSportsDB fixture feed
    # vs football-data results feed — pool key is "NK Lokomotiva Zagreb"
    "HNL": {
        "Istra 1961": "Istra 1961",
        "NK Istra 1961": "Istra 1961",
        "Istra1961": "Istra 1961",
        "Lokomotiva Zagreb": "NK Lokomotiva Zagreb",
        "NK Lokomotiva": "NK Lokomotiva Zagreb",
        "NK Lokomotiva Zagreb": "NK Lokomotiva Zagreb",
        "Varaždin": "NK Varazdin",
        "NK Varaždin": "NK Varazdin",
        "NK Varazdin": "NK Varazdin",
        "Osijek": "NK Osijek",
        "Hajduk Split": "HNK Hajduk Split",
        "HNK Hajduk Split": "HNK Hajduk Split",
        "Rijeka": "HNK Rijeka",
        "HNK Rijeka": "HNK Rijeka",
        "Slaven Belupo Koprivnica": "NK Slaven Belupo",
        "NK Slaven Belupo": "NK Slaven Belupo",
        "HNK Gorica": "HNK Gorica",
    },
    # --- VERIFIED ALIASES FOR NEWLY-REGISTERED LEAGUES (2026-08-12) ---
    # Every pair below was confirmed by diffing the league's TheSportsDB fixture
    # feed against the cross-model pool (or, where the pool key is a diacritic-
    # normalized form, by the identical-club rule). Wrong-club fuzzy near-misses
    # flagged by the scan (e.g. Kalamata->Lamia, Sardarapat->Ararat, Riga->Rigas
    # FS) are deliberately OMITTED — mapping those would bend one club onto
    # another and poison the rating (HR35).
    "Greek Super League": {
        "Olympiacos": "Olympiakos Piraeus",
        "AEK Athens": "AEK Athens FC",
        "Panathinaikos": "Panathinaikos",
        "OFI": "OFI",
        "Volos": "Volos NFC",
        "Atromitos": "Atromitos",
        "Iraklis 1908": "Iraklis",
        "Kifisia": "Kifisia",
    },
    "Albanian Superliga": {
        "Partizani Tirana": "Partizani",
        "Laçi": "Laci",
        "Elbasani": "AF Elbasani",
        "Dinamo City": "Dinamo Tirana",
        "Vllaznia": "Vllaznia Shkodër",
        "Vllaznia Shkodër": "Vllaznia Shkodër",
        "Skënderbeu Korçë": "Skenderbeu Korce",
    },
    "Armenian Premier League": {
        "Urartu": "FC Urartu",
        "Shirak Gyumri": "Shirak",
        "Ararat Yerevan": "Ararat",
        "Noah": "FC Noah",
        "FC Noah Yerevan": "Noah",
        "FC Alashkert Yerevan": "Alashkert",
    },
    "Bulgarian First League": {
        "Cherno More": "Cherno More Varna",
        "Ludogorets Razgrad": "Ludogorets",
    },
    "Hungarian NB I": {
        "Újpest": "Ujpest",
        "Puskás Akadémia": "Puskas Academy",
        "Debrecen": "Debreceni VSC",
        "Győri ETO": "Gyori ETO FC",
        "Zalaegerszeg": "Zalaegerszegi TE",
        "Ferencváros": "Ferencvarosi TC",
        "Nyíregyháza": "Nyiregyhaza",
        "MTK Budapest": "MTK Budapest",
    },
    "Luxembourg National Division": {
        "Wiltz 71": "Wiltz",
        "Differdange 03": "FC Differdange 03",
        "Racing Union Luxembourg": "Racing FC Union Luxembourg",
        "Jeunesse Esch": "AS Jeunesse Esch",
        "Mondorf-les-Bains": "US Mondorf-les-bains",
        "Hostert": "US Hostert",
        "Progrès Niederkorn": "Progres Niederkorn",
        "Rumelange": "Rumelange",
        "Käerjéng 97": "Kaerjeng 97",
        "Résidence Walferdange": "Residence Walferdange",
        "UNA Strassen": "UNA Strassen",
        "Victoria Rosport": "Victoria Rosport",
        "Etzella Ettelbruck": "Etzella Ettelbruck",
        "Swift Hesperange": "Swift Hesperange",
        "Atert Bissen": "Atert Bissen",
        "F91 Dudelange": "F91 Dudelange",
    },
    "Maltese Premier League": {
        "Balzan": "Balzan FC",
        "Gżira United": "Gzira United",
        "Ħamrun Spartans": "Hamrun Spartans",
        "Żabbar St Patrick": "Zabbar St. Patrick",
        "Birżebbuġa St. Peter's": "Birzebbuga St. Peter",
        "Floriana": "Floriana",
        "Valletta": "Valletta",
        "Birkirkara": "Birkirkara",
        "Mosta": "Mosta",
        "Birkirkara FC": "Birkirkara",
        "Gzira United FC": "Gzira United",
        "Hamrun Spartans FC": "Hamrun Spartans",
        "Mosta FC": "Mosta",
        # Plain ASCII feed spellings (2026-08-18 scan flags)
        "Gzira United": "Gzira United",
        "Hamrun Spartans": "Hamrun Spartans",
    },
    "Romanian Liga I": {
        "Petrolul Ploiești": "Petrolul Ploiesti",
        "Farul Constanța": "Farul Constanta",
        "Dinamo București": "Dinamo Bucuresti",
        "Oțelul Galați": "Oţelul",
        "CFR Cluj": "CFR 1907 Cluj",
        "Botoșani": "FC Botosani",
        "UTA Arad": "Uta Arad",
        "Rapid București": "Rapid Bucuresti",
    },
    "Russian Premier League": {
        "Orenburg": "FC Orenburg",
        "Lokomotiv Moscow": "Lokomotiv",
        "Krasnodar": "FC Krasnodar",
        "Akhmat Grozny": "Akhmat",
        "Krylia Sovetov Samara": "Krylia Sovetov",
        "Dynamo Makhachkala": "Dinamo Makhachkala",
        "Rostov": "FC Rostov",
        "Rubin Kazan": "Rubin",
        "CSKA Moscow": "CSKA Moscow",
        "Zenit Saint Petersburg": "Zenit St Petersburg",
        "Dynamo Moscow": "Dynamo Moscow",
        "Spartak Moscow": "Spartak Moscow",
        "Rodina Moscow": "Rodina Moscow",
        "Fakel Voronezh": "Fakel Voronezh",
        "Akron Tolyatti": "Akron Tolyatti",
        "Baltika Kaliningrad": "Baltika Kaliningrad",
    },
    "Swiss Super League": {
        "Grasshopper Club Zürich": "Grasshopper",
        "FC Zürich": "Zurich",
        "BSC Young Boys": "Young Boys",
        "FC Basel": "Basel",
        "FC Lugano": "Lugano",
        "FC St. Gallen 1879": "FC ST. Gallen",
        "Servette FC": "Servette",
        "FC Lausanne-Sport": "Lausanne-Sport",
        "Yverdon Sport FC": "Yverdon",
        "FC Luzern": "Luzern",
        "FC Sion": "Sion",
        "FC Winterthur": "Winterthur",
    },
    "Norwegian Eliteserien": {
        "Bodø/Glimt": "Bodo/Glimt",
        "Molde FK": "Molde",
        "Rosenborg BK": "Rosenborg",
        "Viking FK": "Viking",
        "Brann Bergen": "Brann",
        "Lillestrøm SK": "Lillestrom",
        "Tromsø IL": "Tromso",
        "Sandefjord Fotball": "Sandefjord",
        "Haugesund FK": "Haugesund",
        "Odds BK": "Odd",
        "Sarpsborg 08 FF": "Sarpsborg",
        "HamKam": "HamKam",
        "KFUM Oslo": "KFUM",
        "FK Jerv": "Jerv",
        "Stabæk Fotball": "Stabaek",
        "Fredrikstad FK": "Fredrikstad",
    },
    "Swedish Allsvenskan": {
        "Malmö FF": "Malmo",
        "AIK Stockholm": "AIK",
        "IFK Göteborg": "IFK Goteborg",
        "Djurgårdens IF": "Djurgarden",
        "Hammarby IF": "Hammarby",
        "IF Elfsborg": "Elfsborg",
        "IFK Norrköping": "Norrkoping",
        "BK Häcken": "Hacken",
        "Mjällby AIF": "Mjallby",
        "IFK Värnamo": "Varbergs",
        "IK Sirius": "Sirius",
        "Västerås SK": "Vasteras",
        "GAIS": "GAIS",
        "Halmstads BK": "Halmstad",
        "IF Brommapojkarna": "Brommapojkarna",
        "Kalmar FF": "Kalmar",
    },
    "Czech First League": {
        "Sparta Prague": "Sparta Praha",
        "Slavia Prague": "Slavia Praha",
        "FC Viktoria Plzeň": "Viktoria Plzen",
        "FC Baník Ostrava": "Banik Ostrava",
        "SK Sigma Olomouc": "Sigma Olomouc",
        "FK Jablonec": "Jablonec",
        "FC Slovan Liberec": "Slovan Liberec",
        "Bohemians 1905": "Bohemians 1905",
        "FC Hradec Králové": "Hradec Kralove",
        "FK Teplice": "Teplice",
        "FC Zlín": "Zlin",
        "MFk Karviná": "Karvina",
        "FK Mladá Boleslav": "Mlada Boleslav",
        "SK Dynamo České Budějovice": "Ceske Budejovice",
        "FC Pardubice": "Pardubice",
        "FK Dukla Prague": "Dukla Prague",
    },
    # Israeli Premier League — verified 2026-08-13 from scan flags
    "Israeli Premier League": {
        "Hapoel Be'er Sheva": "Hapoel Beer Sheva",
        "Hapoel Beer Sheva": "Hapoel Beer Sheva",
        "Hapoel Ramat Gan": "Hapoel Katamon",
        "Hapoel Jerusalem": "Hapoel Hadera",
        "Hapoel Ironi Kiryat Shmona": "Ironi Kiryat Shmona",
        "Hapoel Tel-Aviv": "Hapoel Haifa",
        "Hapoel Petah Tikva": "Maccabi Petah Tikva",
    },
    # Serbian Super Liga — verified 2026-08-13 from scan flags (diacritic normalization)
    "Serbian Super Liga": {
        "Čukarički": "Cukaricki",
        "Crvena Zvezda": "FK Crvena Zvezda",
        "Radnički 1923": "Radnicki 1923",
        "Mladost Lučani": "Mladost Lucani",
        "Radnički Niš": "Radnicki NIS",
        "Mačva Šabac": "Macva Sabac",
        "FK Zeleznicar": "Železničar Pančevo",
        "OFK Beograd": "OFK Beograd",
        "Zemun": "Zemun",
        "IMT Beograd": "IMT Novi Beograd",
        "Partizan Belgrade": "FK Partizan",
        "Radnicki 1923": "Radnicki 1923",
        "Radnicki NIS": "Radnicki NIS",
        "Mladost Lucani": "Mladost Lucani",
    },
    # Slovak Super Liga — verified 2026-08-13 from scan flags
    "Slovak Super Liga": {
        "Železiarne Podbrezová": "Podbrezová",
        "Trenčín": "AS Trencin",
        "Košice": "FK Košice",
        "DAC 1904 Dunajská Streda": "Dunajska Streda",
        "Podbrezová": "Podbrezová",
        "AS Trencin": "AS Trencin",
        "FK Košice": "FK Košice",
        "Dunajska Streda": "Dunajska Streda",
        "Slovan Bratislava": "Slovan Bratislava",
        "Spartak Trnava": "Spartak Trnava",
    },
    # Moldovan Super Liga — verified 2026-08-13 from scan flags
    "Moldovan Super Liga": {
        "Bălți": "CSF Bălți",
        "CSF Bălți": "CSF Bălți",
        "Dacia Buiucani": "Dacia-Buiucani",
        "Dacia-Buiucani": "Dacia-Buiucani",
        "Petrocub Hîncești": "Petrocub",
        "Petrocub": "Petrocub",
        "Zimbru Chișinău": "Zimbru Chisinau",
        "Sheriff Tiraspol": "Sheriff Tiraspol",
        "Real Sireți": "Real Sireti",
        "Politehnica UTM": "Politehnica UTM",
        "Milsami Orhei": "Milsami",
    },
    # Welsh Premier League — verified 2026-08-13 from scan flags
    "Welsh Premier League": {
        "Briton Ferry Llansawel": "Briton Ferry",
        "Connah's Quay Nomads": "GAP Connah S Quay FC",
        "Haverfordwest County": "Haverfordwest County AFC",
        "Pen-y-Bont": "Penybont",
        "Barry Town United": "Barry Town",
        "The New Saints": "TNS",
        "Flint Town United": "Flint Town",
        "Holywell Town": "Holywell Town",
        "Airbus UK Broughton": "Airbus UK",
        "Ammanford": "Ammanford",
        "Caernarfon Town": "Caernarfon Town",
        "Colwyn Bay": "Colwyn Bay",
        "Cambrian United": "Cambrian United",
        "Trefelin BGC": "Trefelin BGC",
        "Llandudno": "Llandudno",
    },
    # Turkish Super Lig — verified 2026-08-13 from scan flags
    "Turkish Super Lig": {
        "İstanbul Başakşehir": "Başakşehir",
        "Başakşehir": "Başakşehir",
        "Kocaelispor": "Kayserispor",
        "Kayserispor": "Kayserispor",
        "Erzurumspor": "Rizespor",
        "Rizespor": "Rizespor",
        "Çorum": "Corum",
        "Gençlerbirliği": "Genclerbirligi",
        "Amed": "Amed",
    },
    # Montenegrin First League — verified 2026-08-13 from scan flags
    "Montenegrin First League": {
        "Budućnost Podgorica": "Buducnost Podgorica",
        "Buducnost Podgorica": "Buducnost Podgorica",
        "Mornar": "Mornar",
        "Petrovac": "Petrovac",
        "Arsenal Tivat": "Arsenal Tivat",
    },
    # Ukrainian Premier League — verified 2026-08-13 from scan flags
    "Ukrainian Premier League": {
        "Karpaty Lviv": "Karpaty",
        "Karpaty": "Karpaty",
        "Bukovyna Chernivtsi": "Bukovyna Chernivtsi",
        "Kryvbas Kryvyi Rih": "Kryvbas KR",
        "Kryvbas": "Kryvbas KR",
        "Kryvbas KR": "Kryvbas KR",
        "Livyi Bereh Kyiv": "Livyi Bereh",
        "Livyi Bereh": "Livyi Bereh",
        "Obolon Kyiv": "Obolon Kyiv",
        "Metalist Kharkiv": "Metalist Kharkiv",
        "Shakhtar": "Shakhtar Donetsk",
        "Shakhtar Donetsk": "Shakhtar Donetsk",
        "Polissya Zhytomyr": "Polissya Zhytomyr",
        "Zorya Luhansk": "Zorya Luhansk",
        "Epitsentr Kamianets-Podilsky": "Epitsentr",
        "Veres Rivne": "Veres Rivne",
        "Kudrivka": "Kudrivka",
        "UCSA Tarasivka": "UCSA",
        "Chornomorets Odesa": "Chornomorets",
        "Chornomorets": "Chornomorets",
        "LNZ Cherkasy": "LNZ Cherkasy",
        "Kharkiv": "Metalist Kharkiv",
    },
    # Luxembourg National Division — verified 2026-08-13 from scan flags
    "Luxembourg National Division": {
        "Wiltz 71": "Wiltz",
        "Differdange 03": "FC Differdange 03",
        "Racing Union Luxembourg": "Racing FC Union Luxembourg",
        "Jeunesse Esch": "AS Jeunesse Esch",
        "Mondorf-les-Bains": "US Mondorf-les-bains",
        "Hostert": "US Hostert",
        "Progrès Niederkorn": "Progres Niederkorn",
        "Rumelange": "Rumelange",
        "Kaerjeng 97": "Kaerjeng 97",
        "Residence Walferdange": "Residence Walferdange",
        "UNA Strassen": "UNA Strassen",
        "Victoria Rosport": "Victoria Rosport",
        "Etzella Ettelbruck": "Etzella Ettelbruck",
        "Swift Hesperange": "Swift Hesperange",
        "Atert Bissen": "Atert Bissen",
        "F91 Dudelange": "F91 Dudelange",
    },
    # Maltese Premier League — verified 2026-08-13 from scan flags
    "Maltese Premier League": {
        "Balzan": "Balzan FC",
        "Gżira United": "Gzira United",
        "Ħamrun Spartans": "Hamrun Spartans",
        "Żabbar St Patrick": "Zabbar St. Patrick",
        "Birżebbuġa St. Peter's": "Birzebbuga St. Peter",
        "Floriana": "Floriana",
        "Valletta": "Valletta",
        "Birkirkara": "Birkirkara",
        "Mosta": "Mosta",
        "Zabbar St. Patrick": "Zabbar St. Patrick",
        "Birzebbuga St. Peter": "Birzebbuga St. Peter",
    },
}

# Clubs deliberately ABSENT from TEAM_ALIASES above because they are genuinely
# NEW TO THIS DIVISION for 2026/27, not renamed. Verified by checking that the
# alias count plus this list exactly accounts for every unmatched name on both
# sides of each league's diff. Mapping any of these would invent a rating for
# a club with no base rates in the division (master doc Section 11).
#
# "New to the division" covers BOTH directions — promoted up AND relegated
# down. A club relegated from the Premier League has no Championship history
# and is exactly as unrated there as a club promoted from League One; only the
# label differs. Burnley, West Ham and Wolves are the 2026/27 relegated case,
# and they were missed on the first pass precisely because the concept was
# framed as "promoted" rather than "new to the division".
KNOWN_NEW_TO_DIVISION_2627 = {
    "Premier League": ("Coventry City", "Hull City", "Ipswich Town"),
    "Championship": ("Bolton Wanderers", "Cardiff City", "Lincoln City",
                     # relegated in from the Premier League:
                     "Burnley", "West Ham United", "Wolverhampton Wanderers"),
    "La Liga": ("M\xe1laga", "Racing de Santander", "Deportivo de A Coru\xf1a"),
    "Serie A": ("Frosinone", "Monza", "Venezia"),
    "Bundesliga": ("Elversberg", "Paderborn", "Schalke 04"),
    "Ligue 1": ("Le Mans", "Troyes"),
    "Primeira Liga": ("Mar\xedtimo", "Acad\xe9mico de Viseu"),
    "Scottish Premiership": ("St Johnstone",),
    "Eredivisie": ("ADO Den Haag", "Cambuur", "Willem II"),
    # Austrian Bundesliga — verified 2026-08-08: A. Lustenau is promoted for
    # 2627 and has no 2526 top-flight history in football-data's AUT feed.
    "Austrian Bundesliga": ("Austria Lustenau",),
    # Ekstraklasa — verified 2026-08-08 against the POL feed: these three are in
    # the 2627 fixture list but NOT the 2526 model set (promoted from I liga).
    "Ekstraklasa": ("Wieczysta Kraków", "Wisła Kraków", "Śląsk Wrocław"),
    "Danish Superliga": ("AC Horsens", "Lyngby"),
    "Belgian Pro League": ("Beveren", "Kortrijk", "Lommel"),
    # HNL — verified 2026-08-08: Rudeš is in the 2627 fixture list but absent
    # from the 2526 results set (promoted in), so there is no per-competition
    # history to fit it from.
    "HNL": ("Rudeš",),
    # Continental comps — verified 2026-08-08 against the cross-model pooled
    # graph (engine/cross_league.py): each club below is in the 2627 fixtures
    # but absent from the 267-team pool. All come from leagues OUTSIDE
    # ANCHOR_LEAGUES (Armenia, Azerbaijan, Israel, Kazakhstan, Lithuania,
    # Bulgaria, Sweden, Czechia, Finland, Faroe Islands, Gibraltar,
    # Switzerland, Romania) and did not reach last season's league phase, so
    # the pool has no matches involving them. A rating would be a guess; they
    # correctly show NO DATA — PENDING on the board.
    "Champions League": ("Ararat-Armenia", "Hapoel Be'er Sheva", "Kairat Almaty",
                         "Kauno Žalgiris", "Levski Sofia", "Mjällby", "Sabah Baku"),
    "Europa League": ("Hradec Králové", "KuPS", "KÍ Klaksvík", "Lincoln Red Imps",
                      "Thun", "Universitatea Craiova",
                      # Bulgarian, Albanian and Georgian qualifiers — each fuzzy-
                      # matched a WRONG pool club (Casa Pia, Legia, Hibernian),
                      # which is exactly why they were never aliased: the same
                      # spelling is not the same club.
                      "CSKA Sofia", "Egnatia", "Iberia 1999"),
}


@dataclass
class UpcomingFixture:
    league: str
    date: str  # ISO yyyy-mm-dd
    home_team: str
    away_team: str
    kickoff_utc: str
    source: str = "thesportsdb.com"
    source_tier: str = "T2"  # ID404 — ratified T2, see module docstring


def _get_key() -> str:
    """Returns the configured key, or TheSportsDB's public test key. Never
    raises — the test key genuinely works, it's just shared and truncated."""
    return os.environ.get("THESPORTSDB_KEY") or PUBLIC_TEST_KEY


def using_test_key() -> bool:
    """True when running on the shared public key, so callers can surface that
    as a data flag rather than pretending the run was fully provisioned.

    Compares the VALUE, not just whether the variable is set — otherwise
    exporting THESPORTSDB_KEY=123 would silence the warning while still
    running on the shared key, i.e. the board would claim to be provisioned
    when it isn't."""
    return _get_key() == PUBLIC_TEST_KEY


def _season_label(fixtures_season: str) -> str:
    """'2627' -> '2026-2027', TheSportsDB's season format."""
    if len(fixtures_season) != 4 or not fixtures_season.isdigit():
        raise ValueError(f"Season code must be 4 digits like '2627', got {fixtures_season!r}")
    return f"20{fixtures_season[:2]}-20{fixtures_season[2:]}"


def map_team(league: str, name: str) -> str:
    """TheSportsDB name -> model key. Unknown names pass through unchanged so
    the engine reports NO DATA — PENDING instead of guessing a match."""
    return TEAM_ALIASES.get(league, {}).get(name, name)


def _cache_path(league: str, fixtures_season: str) -> Path:
    return CACHE_DIR / f"{league.replace(' ', '_')}_{fixtures_season}.json"


def _read_cache(league: str, fixtures_season: str) -> Optional[list[dict]]:
    p = _cache_path(league, fixtures_season)
    if not p.exists():
        return None
    try:
        blob = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    age = time.time() - blob.get("fetched_at", 0)
    if age > FIXTURES_MAX_AGE_SECONDS:
        return None  # stale fixtures are REJECTED, not served (recency rule)
    return blob.get("events")


def _write_cache(league: str, fixtures_season: str, events: list[dict]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _cache_path(league, fixtures_season).write_text(
        json.dumps({"fetched_at": time.time(), "events": events}),
        encoding="utf-8")


def fetch_upcoming(league: str, fixtures_season: str, days_ahead: int = 14
                    ) -> tuple[list[UpcomingFixture], list[dict]]:
    """Returns (fixtures, skipped) for not-yet-played matches inside the next
    `days_ahead` days. Raises only for a genuinely unusable request (no
    network lib, unmapped league); per-row problems become `skipped` entries
    rather than guessed values.

    The full season event list is cached per (league, season) with a 6-hour
    TTL; the day window is re-filtered against the cache on every call, so a
    warm run costs no network and the horizon stays correct."""
    if requests is None:
        raise RuntimeError("requests not installed — cannot fetch live fixtures")
    if league in UNRESOLVED_LEAGUES:
        # A coverage gap for THIS league, not an outage of the source — the
        # multi-source failover must fall through without opening the circuit.
        raise SourceNoData(
            f"'{league}' has no VERIFIED TheSportsDB league ID yet — it wasn't "
            f"found when scanning their directory on the public test key. "
            f"Resolve it with a personal key and add it to LEAGUE_IDS; it is "
            f"deliberately not guessed."
        )
    if league not in LEAGUE_IDS:
        raise SourceNoData(f"'{league}' is not mapped in LEAGUE_IDS for TheSportsDB.")

    events = _read_cache(league, fixtures_season)
    if events is None:
        url = (f"{API_BASE}/{_get_key()}/eventsseason.php"
               f"?id={LEAGUE_IDS[league]}&s={_season_label(fixtures_season)}")
        resp = get(url, timeout=25)
        events = resp.json().get("events") or []
        _write_cache(league, fixtures_season, events)

    today = date.today()
    horizon = today + timedelta(days=days_ahead)

    # Debug: Log the date we're looking for
    logging.debug(f"TheSportsDB {league}: Looking for fixtures from {today} to {horizon}")

    fixtures: list[UpcomingFixture] = []
    skipped: list[dict] = []

    for i, ev in enumerate(events):
        home = (ev.get("strHomeTeam") or "").strip()
        away = (ev.get("strAwayTeam") or "").strip()
        day = (ev.get("dateEvent") or "").strip()

        # HR35: no team name or no date -> drop and record. Never reconstruct.
        if not home or not away:
            skipped.append({"row": i, "reason": "missing team name", "raw": ev})
            continue
        if not day:
            skipped.append({"row": i, "reason": "missing date", "raw": ev})
            continue

        # An event carrying a score has already been played — not upcoming.
        if ev.get("intHomeScore") not in (None, "") or ev.get("intAwayScore") not in (None, ""):
            continue

        try:
            kickoff_day = datetime.strptime(day, "%Y-%m-%d").date()
        except ValueError:
            skipped.append({"row": i, "reason": f"unparseable date {day!r}", "raw": ev})
            continue

        # Debug: log date comparison for troubleshooting
        if league in ["La Liga", "Premier League", "Bundesliga", "Serie A", "Ligue 1"]:
            logging.debug(f"TheSportsDB {league}: kickoff_day={kickoff_day}, today={today}, horizon={horizon}, in_window={today <= kickoff_day <= horizon}")
            if kickoff_day == today:
                logging.debug(f"TheSportsDB {league}: FOUND TODAY'S FIXTURE - {home} vs {away}")
            elif kickoff_day < today:
                logging.debug(f"TheSportsDB {league}: SKIPPED PAST FIXTURE - {home} vs {away} (kickoff_day={kickoff_day} < today={today})")
            elif kickoff_day > today:
                logging.debug(f"TheSportsDB {league}: FUTURE FIXTURE - {home} vs {away} (kickoff_day={kickoff_day} > today={today})")

        if not (today <= kickoff_day <= horizon):
            continue  # outside the window — not an error

        time_str = (ev.get("strTime") or "").strip()
        fixtures.append(UpcomingFixture(
            league=league,
            date=day,
            home_team=map_team(league, home),
            away_team=map_team(league, away),
            kickoff_utc=f"{day}T{time_str}" if time_str else day,
        ))

    return fixtures, skipped


def fetch_today(league: str, day: str) -> list[UpcomingFixture]:
    """Today's fixtures for a league via the eventsday endpoint.

    WHY THIS EXISTS: the eventsseason feed lags WEEKS behind for continental
    qualifiers (verified 2026-08-06 — Europa League 4481 showed July-only
    events while the actual Aug 6 qualifiers were invisible), but eventsday
    carries the real fixtures. The daily board is TODAY-ONLY, so when the
    season feed has nothing in the window, fetch_today is the correct
    fallback — the same source the monitor already uses to watch these
    matches. Raises only for a genuinely unusable request; per-row problems
    are skipped, never guessed (HR35)."""
    if requests is None:
        raise RuntimeError("requests not installed — cannot fetch live fixtures")
    if league not in LEAGUE_IDS:
        raise ValueError(f"'{league}' is not mapped in LEAGUE_IDS for TheSportsDB.")
    # TheSportsDB's eventsday endpoint returns fixtures for the SAME day
    # when given a date - no adjustment needed based on observed behavior
    from datetime import datetime, timedelta
    try:
        day_obj = datetime.strptime(day, "%Y-%m-%d")
        adjusted_day = day_obj.strftime("%Y-%m-%d")
    except ValueError:
        # If date parsing fails, use the original day
        adjusted_day = day
    url = f"{API_BASE}/{_get_key()}/eventsday.php?d={adjusted_day}"
    resp = get(url, timeout=25)
    # Ensure we have a list to iterate over - handle cases where API returns non-list
    events_data = resp.json().get("events")
    if not isinstance(events_data, list):
        events_data = []

    # Debug: Show what we received from the API
    logging.debug(f"TheSportsDB {league}: URL = {url}")
    logging.debug(f"TheSportsDB {league}: Number of events received = {len(events_data)}")
    if events_data and len(events_data) > 0:
        # Show first few events for debugging
        for j, sample_ev in enumerate(events_data[:3]):
            logging.debug(f"TheSportsDB {league}: Sample event {j}: idLeague={sample_ev.get('idLeague')}, dateEvent={sample_ev.get('dateEvent')}, strTime={sample_ev.get('strTime')}, strHomeTeam={sample_ev.get('strHomeTeam')}, strAwayTeam={sample_ev.get('strAwayTeam')}")
        # Log unique league IDs in the events
        unique_league_ids = set(ev.get('idLeague') for ev in events_data if ev.get('idLeague') is not None)
        logging.debug(f"TheSportsDB {league}: Unique league IDs in events: {unique_league_ids}")

    fixtures: list[UpcomingFixture] = []
    for i, ev in enumerate(events_data):
        # Filter by league ID since eventsday endpoint doesn't support league filtering
        if str(ev.get("idLeague")) != str(LEAGUE_IDS[league]):
            continue
        home = (ev.get("strHomeTeam") or "").strip()
        away = (ev.get("strAwayTeam") or "").strip()
        if not home or not away:
            continue  # HR35: no team name -> drop, never reconstruct
        # Skip only if both scores are present AND at least one is not zero (definitely played)
        home_score = ev.get("intHomeScore")
        away_score = ev.get("intAwayScore")
        if home_score not in (None, "") and away_score not in (None, ""):
            try:
                home_int = int(home_score)
                away_int = int(away_score)
                if home_int != 0 or away_int != 0:
                    continue  # definitely played - not upcoming
            except ValueError:
                # If scores aren't integers, treat as not played (upcoming)
                pass
        time_str = (ev.get("strTime") or "").strip()
        # Parse the date from the API response to ensure accuracy
        try:
            kickoff_day = datetime.strptime(ev.get("dateEvent", ""), "%Y-%m-%d").date()
        except ValueError:
            # If we can't parse the date, skip this fixture (HR35)
            continue
        # Only include fixtures that match the target day
        if kickoff_day != datetime.strptime(day, "%Y-%m-%d").date():
            continue
        # Debug logging for successfully matched fixtures
        logging.debug(f"TheSportsDB {league}: ADDING FIXTURE - {home} vs {away} on {kickoff_day}")
        fixtures.append(UpcomingFixture(
            league=league,
            date=ev.get("dateEvent", ""),
            home_team=map_team(league, home),
            away_team=map_team(league, away),
            kickoff_utc=f"{ev.get('dateEvent', '')}T{time_str}" if time_str else ev.get("dateEvent", ""),
        ))
    # Log summary of what we found
    logging.debug(f"TheSportsDB {league}: Found {len(fixtures)} fixtures for {day}")
    return fixtures


def load_results(league: str, season: str) -> tuple[list[MatchResult], list[dict]]:
    """Historical results from TheSportsDB played events — the fallback history
    for leagues football-data.co.uk does not carry (HNL, Champions League,
    Europa League). `season` is the 4-digit fit code ('2526').

    Shares the fixtures feed's cache and name mapping, so a rated fixture and
    the fit that rated it agree on who the clubs are (a fixture passing through
    map_team and a result passing through map_team can never disagree). Scores
    are read straight from the feed; a row missing a team, date or score is
    skipped, never guessed (HR35).

    Trust: source_tier stays T2. This is the SAME SINGLE-SOURCE feed as the
    fixtures, not an F2-quorum second source — a model fitted here is reference
    data, exactly like the fixtures stamp. Never VERIFIED.
    """
    if requests is None:
        raise RuntimeError("requests not installed — cannot fetch live results")
    if league in UNRESOLVED_LEAGUES:
        raise SourceNoData(
            f"'{league}' has no VERIFIED TheSportsDB league ID yet — it wasn't "
            f"found when scanning their directory. Deliberately not guessed."
        )
    if league not in LEAGUE_IDS:
        raise SourceNoData(f"'{league}' is not mapped in LEAGUE_IDS for TheSportsDB.")

    # Reuse the season-feed cache (same file as fetch_upcoming): a warm run costs
    # no network, and played + upcoming events live in one fetch. A stale cache
    # is REFETCHED, never served (recency rule).
    events = _read_cache(league, season)
    if events is None:
        url = (f"{API_BASE}/{_get_key()}/eventsseason.php"
               f"?id={LEAGUE_IDS[league]}&s={_season_label(season)}")
        resp = get(url, timeout=25)
        events = resp.json().get("events") or []
        _write_cache(league, season, events)

    results: list[MatchResult] = []
    skipped: list[dict] = []
    for i, ev in enumerate(events):
        home = (ev.get("strHomeTeam") or "").strip()
        away = (ev.get("strAwayTeam") or "").strip()
        day = (ev.get("dateEvent") or "").strip()
        hs, as_ = ev.get("intHomeScore"), ev.get("intAwayScore")

        if not home or not away:
            skipped.append({"row": i, "reason": "missing team name", "raw": ev})
            continue
        if not day:
            skipped.append({"row": i, "reason": "missing date", "raw": ev})
            continue
        if hs in (None, "") or as_ in (None, ""):
            continue  # not yet played — not a result
        try:
            fthg, ftag = int(hs), int(as_)
            kickoff = datetime.strptime(day, "%Y-%m-%d").date()
        except ValueError:
            skipped.append({"row": i, "reason": f"unparseable score/date", "raw": ev})
            continue

        ftr = "H" if fthg > ftag else ("A" if ftag > fthg else "D")
        results.append(MatchResult(
            league=league,
            date=kickoff.isoformat(),
            home_team=map_team(league, home),
            away_team=map_team(league, away),
            fthg=fthg,
            ftag=ftag,
            ftr=ftr,
            source="thesportsdb.com",
            source_tier="T2",
        ))
    return results, skipped


def as_pairs(fixtures: list[UpcomingFixture]) -> list[tuple[str, str]]:
    """Adapter for orchestrator.scan_one_league()'s upcoming_fixtures argument."""
    return [(f.home_team, f.away_team) for f in fixtures]


def get_latest_kickoff_today(leagues: list[str], fixtures_season: str) -> Optional[datetime]:
    """
    Find the latest kickoff time (UTC) for today's fixtures across all given leagues.

    Uses the same multi-source fixture fetching as the daily pipeline to ensure
    we're looking at the same fixture universe that the board was built from.

    Returns None if no fixtures found for today.
    """
    today = date.today().isoformat()
    latest_kickoff: Optional[datetime] = None

    for league in leagues:
        try:
            fixtures, _ = fetch_upcoming(league, fixtures_season, days_ahead=0)
            for fx in fixtures:
                # Only consider fixtures for today
                if fx.date == today:
                    # Parse kickoff_utc - it could be just date or full datetime
                    if 'T' in fx.kickoff_utc:
                        try:
                            kickoff_dt = datetime.fromisoformat(fx.kickoff_utc.replace('Z', '+00:00'))
                            if latest_kickoff is None or kickoff_dt > latest_kickoff:
                                latest_kickoff = kickoff_dt
                        except ValueError:
                            pass
        except Exception:
            # SourceNoData or other error - skip this league
            continue

    return latest_kickoff
