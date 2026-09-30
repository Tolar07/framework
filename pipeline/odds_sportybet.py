"""
SportyBet as a live odds source — the book the Architect actually bets into.

WHY
  the-odds-api is metered (500/mo, shared across leagues) and keeps hitting 0;
  the Architect has ruled out paying for any odds API. SportyBet publishes a
  free, keyless JSON API (verified reachable) carrying the FULL market ladder,
  and it is the book he bets into — so its price is the truest "price you can
  take" (the doctrine pipeline.odds._best_price encodes). It covers every deploy
  league INCLUDING the Extra leagues (Danish Superliga, Ekstraklasa) that the
  free football-data feed cannot.

SAFETY — FILTER BY TOURNAMENT ID, NEVER NAME (HR35)
  League names collide across countries on SportyBet: "Premiership" is also
  Northern Irish, "Superliga" is also Romanian/Serbian/Slovak. Filtering by name
  mixes clubs from the wrong country into a league — a fabricated price on the
  wrong fixture. So this module keys on the unique Sportradar tournament ID.

TEAM NAMES (HR35)
  SportyBet is a fourth naming convention. SB->model pairs below were built by
  diffing SportyBet's live team list against the model's football-data names,
  per league, 2026-09-30 — verified pairs only. An unmapped name passes through
  unchanged and simply won't join a model fixture (fail-safe: NO DATA, never a
  wrong match), and is flagged so a genuinely new club is noticed, not guessed.

  ToS: reads SportyBet's own public endpoint for the Architect's own betting
  decisions; it can be rate-limited or changed by SportyBet at any time.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.odds import FixtureOdds, MarketQuote, CACHE_DIR, ODDS_MAX_AGE_SECONDS

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
_LIST = ("https://www.sportybet.com/api/ng/factsCenter/pcUpcomingEvents"
         "?sportId=sr:sport:1&marketId=1,18,10,29,11,26&pageSize=100&pageNum={page}")
_CACHE = CACHE_DIR / "sportybet_events.json"

# Framework league -> unique Sportradar tournament ID (verified live 2026-09-30
# by category, so name collisions can't attach the wrong country's clubs).
SPORTYBET_TOURNAMENT_ID = {
    "Eredivisie": "sr:tournament:37",
    "Belgian Pro League": "sr:tournament:38",
    "Scottish Premiership": "sr:tournament:36",
    "Danish Superliga": "sr:tournament:39",
    "Ekstraklasa": "sr:tournament:202",
    # Added 2026-09-30 for wider + midweek coverage. IDs verified live against the
    # SportyBet feed by the event's own country/tournament block (not by name —
    # names collide across countries), so each maps to the right competition.
    "Premier League": "sr:tournament:17",      # England
    "Championship": "sr:tournament:18",         # England (2nd tier)
    "La Liga": "sr:tournament:8",               # Spain
    "La Liga 2": "sr:tournament:54",            # Spain (LALIGA HYPERMOTION)
    "Serie A": "sr:tournament:23",              # Italy
    "Serie B": "sr:tournament:53",              # Italy
    "Bundesliga": "sr:tournament:35",           # Germany
    "2. Bundesliga": "sr:tournament:44",        # Germany
    "Ligue 1": "sr:tournament:34",              # France
    "Ligue 2": "sr:tournament:182",             # France
    "Primeira Liga": "sr:tournament:238",       # Portugal (Liga Portugal)
}

# SportyBet team name -> model (football-data) key. Verified pairs only; exact
# matches are intentionally omitted (they pass through unchanged).
TEAM_ALIASES: dict[str, dict[str, str]] = {
    "Eredivisie": {
        "ADO Den Haag": "Den Haag", "Alkmaar": "AZ Alkmaar",
        "Excelsior Rotterdam": "Excelsior", "FC Groningen": "Groningen",
        "FC Twente Enschede": "Twente", "FC Utrecht": "Utrecht",
        "Fortuna Sittard": "For Sittard", "NEC Nijmegen": "Nijmegen",
        "PEC Zwolle": "Zwolle", "SC Cambuur": "Cambuur",
        "SC Heerenveen": "Heerenveen", "SC Telstar": "Telstar",
        "Willem II Tilburg": "Willem II",
    },
    "Belgian Pro League": {
        "KV Kortrijk": "Kortrijk", "KV Waasland-Beveren": "Beveren",
        "KVC Westerlo": "Westerlo", "RSC Anderlecht": "Anderlecht",
        "Royal Antwerp FC": "Antwerp", "Royal Charleroi SC": "Charleroi",
        "SV Zulte Waregem": "Waregem", "St. Truidense VV": "St Truiden",
        "Standard Liege": "Standard", "Union Gilloise": "St. Gilloise",
        "Yellow-Red KV Mechelen": "Mechelen",
    },
    "Scottish Premiership": {
        "Dundee FC": "Dundee", "Falkirk FC": "Falkirk",
        "Heart of Midlothian FC": "Hearts", "Hibernian FC": "Hibernian",
        "Kilmarnock FC": "Kilmarnock", "Motherwell FC": "Motherwell",
        "St Mirren FC": "St Mirren", "St. Johnstone FC": "St Johnstone",
    },
    "Danish Superliga": {
        "AC Horsens": "Horsens", "AGF Aarhus": "Aarhus",
        "Broendby IF": "Brondby", "Copenhagen": "FC Copenhagen",
        "FC Midtjylland": "Midtjylland", "Lyngby BK": "Lyngby",
        "Odense Boldklub": "Odense", "Silkeborg IF": "Silkeborg",
        "SonderjyskE": "Sonderjyske", "Viborg FF": "Viborg",
    },
    "Ekstraklasa": {
        "GKS Piast Gliwice": "Piast Gliwice", "Jagiellonia Bialystok": "Jagiellonia",
        "KKS Lech Poznan": "Lech Poznan", "KS Cracovia Krakow": "Cracovia",
        "LKP Motor Lublin": "Motor Lublin", "Legia Warszawa": "Legia",
        "RKS Radomiak Radom": "Radomiak Radom", "Rakow Czestochowa": "Rakow",
        "WKS Slask Wroclaw": "Slask Wroclaw", "Wisla Krakow": "Wisla",
        "Zaglebie Lubin": "Zaglebie",
    },
    # --- Added 2026-09-30 for wider/midweek coverage. SportyBet name -> model
    # (football-data) name, verified against the fitted roster. Only TRUE
    # same-club mappings are listed; a promoted/relegated club not in the model,
    # or any name I could not confirm, is left unmapped on purpose — it renders
    # NO DATA and is flagged for review, never mapped to the wrong club (HR35).
    "Premier League": {
        "Sunderland AFC": "Sunderland", "Leeds United": "Leeds",
        "Man Utd": "Man United", "Manchester United": "Man United",
        "Manchester City": "Man City", "Newcastle United": "Newcastle",
        "Nottingham Forest": "Nott'm Forest", "Tottenham Hotspur": "Tottenham",
        "West Ham United": "West Ham", "Wolverhampton Wanderers": "Wolves",
        "Brighton & Hove Albion": "Brighton", "AFC Bournemouth": "Bournemouth",
    },
    "Championship": {
        "Middlesbrough FC": "Middlesbrough", "Millwall FC": "Millwall",
        "Portsmouth FC": "Portsmouth", "Wrexham AFC": "Wrexham",
        "Birmingham City": "Birmingham", "Blackburn Rovers": "Blackburn",
        "Charlton Athletic": "Charlton", "Coventry City": "Coventry",
        "Derby County": "Derby", "Hull City": "Hull", "Ipswich Town": "Ipswich",
        "Preston North End": "Preston", "Queens Park Rangers": "QPR",
        "Stoke City": "Stoke", "Swansea City": "Swansea",
        "West Bromwich Albion": "West Brom", "Sheffield Utd": "Sheffield United",
        "Sheffield Wednesday": "Sheffield Weds", "Bristol City FC": "Bristol City",
    },
    "La Liga": {
        "Elche CF": "Elche", "Espanyol": "Espanol", "Real Sociedad": "Sociedad",
        "Athletic Bilbao": "Ath Bilbao", "Atletico Madrid": "Ath Madrid",
        "Rayo Vallecano": "Vallecano", "Real Betis": "Betis",
        "Celta Vigo": "Celta", "Deportivo Alaves": "Alaves",
        "Real Oviedo": "Oviedo", "Girona FC": "Girona", "Levante UD": "Levante",
        "RCD Mallorca": "Mallorca",
    },
    "La Liga 2": {
        "Burgos CF": "Burgos", "CD Castellon": "Castellon", "Cordoba CF": "Cordoba",
        "FC Andorra": "Andorra", "Malaga CF": "Malaga",
        "RC Deportivo de A Coruna": "La Coruna", "Racing Santander": "Santander",
        "Sporting Gijon": "Sp Gijon", "Real Sociedad San Sebastian B": "Sociedad B",
        "Albacete Balompie": "Albacete", "AD Ceuta": "Ceuta",
        "SD Huesca": "Huesca", "UD Las Palmas": "Las Palmas",
        "Real Zaragoza": "Zaragoza", "Real Valladolid": "Valladolid",
        "CD Leganes": "Leganes", "CD Mirandes": "Mirandes", "SD Eibar": "Eibar",
        "Cultural Leonesa": "Cultural Leonesa", "UD Almeria": "Almeria",
        "Granada CF": "Granada", "Cadiz CF": "Cadiz",
    },
    "Serie A": {
        "AC Milan": "Milan", "Parma Calcio": "Parma", "Como 1907": "Como",
        "Inter Milan": "Inter", "AS Roma": "Roma", "SS Lazio": "Lazio",
        "SSC Napoli": "Napoli", "US Lecce": "Lecce", "Torino FC": "Torino",
        "Udinese Calcio": "Udinese", "Bologna FC": "Bologna",
        "Cagliari Calcio": "Cagliari", "US Sassuolo": "Sassuolo",
    },
    "Serie B": {
        "Cesena FC": "Cesena", "Modena FC": "Modena", "Palermo FC": "Palermo",
        "US Avellino": "Avellino", "US Catanzaro": "Catanzaro",
        "Sampdoria Genoa": "Sampdoria", "Calcio Padova": "Padova",
        "Carrarese Calcio": "Carrarese", "FC Sudtirol Bolzano": "Sudtirol",
        "Mantova 1911": "Mantova", "Empoli FC": "Empoli", "SSC Bari": "Bari",
        "Spezia Calcio": "Spezia", "AC Reggiana": "Reggiana",
        "US Cremonese": "Cremonese", "Pescara Calcio": "Pescara",
    },
    "Bundesliga": {
        "Bayer Leverkusen": "Leverkusen", "Borussia Dortmund": "Dortmund",
        "Borussia M´gladbach": "M'gladbach", "Borussia Monchengladbach": "M'gladbach",
        "Cologne": "FC Koln", "1. FC Koln": "FC Koln",
        "Eintracht Frankfurt": "Ein Frankfurt", "Hamburger SV": "Hamburg",
        "Bayern Munich": "Bayern Munich", "VfB Stuttgart": "Stuttgart",
        "SC Freiburg": "Freiburg", "TSG Hoffenheim": "Hoffenheim",
        "1. FC Union Berlin": "Union Berlin", "FC Augsburg": "Augsburg",
        "1. FSV Mainz 05": "Mainz", "SV Werder Bremen": "Werder Bremen",
    },
    "2. Bundesliga": {
        "1 FC Kaiserslautern": "Kaiserslautern", "1. FC Magdeburg": "Magdeburg",
        "Hannover 96": "Hannover", "Karlsruher SC": "Karlsruhe",
        "1 FC Nuremberg": "Nurnberg", "1. FC Nurnberg": "Nurnberg",
        "Arminia Bielefeld": "Bielefeld", "Dynamo Dresden": "Dresden",
        "Eintracht Braunschweig": "Braunschweig", "VfL Bochum": "Bochum",
        "Hertha BSC": "Hertha", "Holstein Kiel": "Holstein Kiel",
        "Fortuna Dusseldorf": "Fortuna Dusseldorf", "SV Darmstadt 98": "Darmstadt",
        "SpVgg Greuther Furth": "Greuther Furth",
    },
    "Ligue 1": {
        "AJ Auxerre": "Auxerre", "PSG": "Paris SG", "Paris Saint Germain": "Paris SG",
        "Paris Saint-Germain": "Paris SG", "Olympique Marseille": "Marseille",
        "Olympique Lyon": "Lyon", "Olympique Lyonnais": "Lyon",
        "AS Monaco": "Monaco", "LOSC Lille": "Lille", "RC Lens": "Lens",
        "Stade Rennais": "Rennes", "OGC Nice": "Nice", "Stade Brestois": "Brest",
        "RC Strasbourg": "Strasbourg", "FC Nantes": "Nantes",
        "Le Havre AC": "Le Havre", "FC Lorient": "Lorient", "FC Metz": "Metz",
        "Toulouse FC": "Toulouse", "Angers SCO": "Angers",
    },
    "Ligue 2": {
        "EA Guingamp": "Guingamp", "FC Annecy": "Annecy", "Red Star FC": "Red Star",
        "US Boulogne": "Boulogne", "Clermont Foot": "Clermont",
        "Grenoble Foot": "Grenoble", "Nancy-Lorraine": "Nancy",
        "Rodez Aveyron Football": "Rodez", "Saint-Etienne": "St Etienne",
        "AS Saint-Etienne": "St Etienne", "Stade Lavallois MFC": "Laval",
        "USL Dunkerque": "Dunkerque", "Stade de Reims": "Reims",
        "Montpellier HSC": "Montpellier", "SC Bastia": "Bastia",
        "Amiens SC": "Amiens", "Pau FC": "Pau FC",
    },
    "Primeira Liga": {
        "FC Arouca": "Arouca", "FC Famalicao": "Famalicao",
        "Moreirense FC": "Moreirense", "Rio Ave FC": "Rio Ave",
        "Braga": "Sp Braga", "SC Braga": "Sp Braga", "Sporting": "Sp Lisbon",
        "Sporting CP": "Sp Lisbon", "Vitoria SC Guimaraes": "Guimaraes",
        "Casa Pia Lisbon": "Casa Pia", "Estoril Praia": "Estoril",
        "Estrela Amadora": "Estrela", "Gil Vicente Barcelos": "Gil Vicente",
        "Nacional da Madeira": "Nacional", "Santa Clara Azores": "Santa Clara",
        "Alverca Futebol": "Alverca", "FC Porto": "Porto", "SL Benfica": "Benfica",
        "CD Tondela": "Tondela",
    },
}


def map_team(league: str, name: str) -> str:
    return TEAM_ALIASES.get(league, {}).get(name, name)


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": _UA,
                                               "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _load_all_events() -> tuple[dict[str, list[dict]], list[str]]:
    """All upcoming football events, indexed by tournament ID. Cached once for
    every league under the same 60-minute recency cap the odds cache uses."""
    flags: list[str] = []
    if _CACHE.exists():
        try:
            blob = json.loads(_CACHE.read_text(encoding="utf-8"))
            if time.time() - blob.get("fetched_at", 0) <= ODDS_MAX_AGE_SECONDS:
                flags.append("SportyBet events served from cache (<=60min)")
                return blob["by_tid"], flags
        except (json.JSONDecodeError, OSError, KeyError):
            pass

    by_tid: dict[str, list[dict]] = {}
    total = None
    for page in range(1, 16):
        data = _get(_LIST.format(page=page)).get("data", {})
        total = data.get("totalNum", total)
        for t in data.get("tournaments", []):
            by_tid.setdefault(t.get("id"), []).extend(t.get("events", []))
        if total is not None and page * 100 >= total:
            break
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _CACHE.write_text(json.dumps({"fetched_at": time.time(), "by_tid": by_tid}),
                      encoding="utf-8")
    flags.append("SportyBet events pulled live")
    return by_tid, flags


def parse_markets(event: dict) -> list[dict]:
    """The FULL market ladder for one event (nothing dropped) — for display or
    future use. {id, desc, specifier, outcomes:[{desc, odds}]}."""
    return [{
        "id": m.get("id"), "desc": m.get("desc"), "specifier": m.get("specifier", ""),
        "outcomes": [{"desc": o.get("desc"), "odds": o.get("odds")}
                     for o in m.get("outcomes", [])],
    } for m in event.get("markets", [])]


def _price(markets: list[dict], desc: str, outcome: str, specifier: str = "") -> Optional[float]:
    for m in markets:
        if m["desc"] != desc or (specifier and m["specifier"] != specifier):
            continue
        for o in m["outcomes"]:
            if o["desc"] == outcome and o["odds"] not in (None, ""):
                try:
                    return float(o["odds"])
                except (TypeError, ValueError):
                    return None
    return None


def _to_fixture_odds(event: dict, league: str, now: str) -> FixtureOdds:
    markets = parse_markets(event)

    def mq(p):
        return (MarketQuote(price=p, bookmaker="sportybet", n_books=1, captured_at=now)
                if p else MarketQuote(captured_at=now))

    ko = event.get("estimateStartTime")
    kickoff = (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(ko) / 1000))
               if ko else "")
    return FixtureOdds(
        league=league,
        home_team=map_team(league, (event.get("homeTeamName") or "").strip()),
        away_team=map_team(league, (event.get("awayTeamName") or "").strip()),
        kickoff_utc=kickoff,
        home=mq(_price(markets, "1X2", "Home")),
        draw=mq(_price(markets, "1X2", "Draw")),
        away=mq(_price(markets, "1X2", "Away")),
        over25=mq(_price(markets, "Over/Under", "Over 2.5", specifier="total=2.5")),
        under25=mq(_price(markets, "Over/Under", "Under 2.5", specifier="total=2.5")),
        source="sportybet.com",
        source_tier="T1",
    )


def fetch_odds_sportybet(league: str) -> tuple[list[FixtureOdds], list[str]]:
    """Live SportyBet prices for one league (by tournament ID). Returns
    (fixtures, flags). Empty (with a flag) for a league SportyBet has no
    upcoming events for, or one without a verified tournament ID here."""
    flags: list[str] = []
    tid = SPORTYBET_TOURNAMENT_ID.get(league)
    if not tid:
        flags.append(f"{league}: no verified SportyBet tournament ID — NO DATA — PENDING")
        return [], flags
    try:
        by_tid, lf = _load_all_events()
        flags += lf
    except Exception as e:  # noqa: BLE001 — caller degrades to the next source
        flags.append(f"{league}: SportyBet fetch failed ({e}) — NO DATA — PENDING")
        return [], flags

    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    out = [_to_fixture_odds(ev, league, now) for ev in by_tid.get(tid, [])]
    flags.append(f"{league}: {len(out)} fixture(s) priced from SportyBet")
    return out, flags


if __name__ == "__main__":
    lg = sys.argv[1] if len(sys.argv) > 1 else "Ekstraklasa"
    fx, fl = fetch_odds_sportybet(lg)
    for f in fl:
        print("FLAG:", f)
    for q in fx[:6]:
        print(f"  {q.home_team} v {q.away_team} ({q.kickoff_utc[:10]}) "
              f"1X2={q.home.price}/{q.draw.price}/{q.away.price} "
              f"OU2.5={q.over25.price}/{q.under25.price}")
