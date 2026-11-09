"""
EUROPEAN FIXTURES (Architect 2026-11-09 plan, step 2: motivation across competitions).

football-data.co.uk has league matches only, so a European midweek was invisible
to the rest study (backtest/REST_STUDY.md). This reads the European club
competitions from openfootball/champions-league (public domain, CC0): Champions
League from 2018-19, Europa and Conference League from 2020-21 / 2021-22.
Each game has a date and both clubs with a country code; `club_dates` turns
them into {football-data club name: [dates]} for one league season.

Strict matching (HR59 spirit): a European club is linked to a league club only
when exactly one club of that league matches (normalised tokens or the ALIAS
table); anything else is left out and counted, never guessed.

    python data/euro_fixtures.py 2425 "Premier League"     show the matches + misses
"""
from __future__ import annotations

import re
import sys
import unicodedata
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "cache" / "euro"
URL = "https://raw.githubusercontent.com/openfootball/champions-league/master/{season}/{comp}.txt"
COMPS = ("cl", "el", "conf")
COUNTRY = {"Premier League": "ENG", "La Liga": "ESP", "Serie A": "ITA", "Bundesliga": "GER", "Ligue 1": "FRA",
           "Eredivisie": "NED", "Primeira Liga": "POR", "Scottish Premiership": "SCO",
           "Belgian Pro League": "BEL"}
MONTHS = {m: i for i, m in enumerate(("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct",
                                      "Nov", "Dec"), 1)}
DROP = {"fc", "cf", "ac", "sc", "afc", "kv", "kaa", "krc", "rsc", "sv", "vfb", "vfl", "tsg", "bv", "bsc", "ssc",
        "as", "ss", "us", "of", "29", "ogc", "rc", "losc", "sl", "cd", "ud", "rcd", "club", "de", "da", "do", "and", "the",
        "1899", "1900", "1901", "1904", "1907", "1909", "1913", "04", "05", "09", "1846", "1848", "1860"}
# European name (normalised) -> football-data name, where tokens alone can't tell
ALIAS = {
    "manchester city": "Man City", "manchester united": "Man United", "tottenham hotspur": "Tottenham",
    "newcastle united": "Newcastle", "wolverhampton wanderers": "Wolves", "west ham united": "West Ham",
    "nottingham forest": "Nott'm Forest", "brighton hove albion": "Brighton",
    "atletico madrid": "Ath Madrid", "club atletico madrid": "Ath Madrid", "athletic club": "Ath Bilbao",
    "real betis balompie": "Betis", "real betis": "Betis", "real sociedad": "Sociedad",
    "villarreal": "Villarreal", "sevilla": "Sevilla", "rayo vallecano": "Vallecano",
    "internazionale milano": "Inter", "inter": "Inter", "milan": "Milan", "ss lazio": "Lazio", "roma": "Roma",
    "napoli": "Napoli", "atalanta": "Atalanta", "fiorentina": "Fiorentina", "juventus": "Juventus",
    "bayern munchen": "Bayern Munich", "bayer leverkusen": "Leverkusen", "borussia dortmund": "Dortmund",
    "borussia monchengladbach": "M'gladbach", "eintracht frankfurt": "Ein Frankfurt", "rb leipzig": "RB Leipzig",
    "union berlin": "Union Berlin", "1 union berlin": "Union Berlin", "koln": "FC Koln", "1 koln": "FC Koln",
    "hoffenheim": "Hoffenheim", "wolfsburg": "Wolfsburg", "freiburg": "Freiburg", "stuttgart": "Stuttgart",
    "mainz": "Mainz", "1 mainz": "Mainz", "heidenheim": "Heidenheim", "1 heidenheim": "Heidenheim",
    "paris saint germain": "Paris SG", "olympique lyonnais": "Lyon", "olympique marseille": "Marseille",
    "olympique de marseille": "Marseille", "lille": "Lille", "lille osc": "Lille", "monaco": "Monaco",
    "stade rennais": "Rennes", "rennais": "Rennes", "nice": "Nice", "lens": "Lens", "racing lens": "Lens",
    "stade brestois": "Brest", "brestois": "Brest", "nantes": "Nantes", "strasbourg": "Strasbourg",
    "psv": "PSV Eindhoven", "psv eindhoven": "PSV Eindhoven", "ajax": "Ajax", "feyenoord": "Feyenoord",
    "feyenoord rotterdam": "Feyenoord", "az alkmaar": "AZ Alkmaar", "az": "AZ Alkmaar", "twente": "Twente",
    "utrecht": "Utrecht", "vitesse": "Vitesse",
    "benfica": "Benfica", "sport lisboa benfica": "Benfica", "sporting clube portugal": "Sp Lisbon",
    "sporting cp": "Sp Lisbon", "porto": "Porto", "sporting braga": "Sp Braga", "braga": "Sp Braga",
    "vitoria guimaraes": "Guimaraes", "gil vicente": "Gil Vicente",
    "lazio roma": "Lazio", "lazio": "Lazio", "bor monchengladbach": "M'gladbach", "athletic": "Ath Bilbao",
    "sporting clube braga": "Sp Braga", "sporting": "Sp Lisbon",
    "celtic": "Celtic", "rangers": "Rangers", "aberdeen": "Aberdeen", "heart midlothian": "Hearts",
    "hibernian": "Hibernian", "dundee united": "Dundee United", "kilmarnock": "Kilmarnock",
    "club brugge": "Club Brugge", "anderlecht": "Anderlecht", "genk": "Genk", "racing genk": "Genk",
    "royal antwerp": "Antwerp", "antwerp": "Antwerp", "gent": "Gent", "aa gent": "Gent", "union saint gilloise": "St. Gilloise",
    "royale union saint gilloise": "St. Gilloise", "standard liege": "Standard", "cercle brugge": "Cercle Brugge",
}


def norm(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return " ".join(t for t in s.split() if t not in DROP)


def fetch(season: str, comp: str) -> str | None:
    """season like '2024-25'. Cached; a missing file (404) is None."""
    CACHE.mkdir(parents=True, exist_ok=True)
    p = CACHE / f"{season}_{comp}.txt"
    if p.exists():
        t = p.read_text(encoding="utf-8")
        return t or None
    try:
        with urllib.request.urlopen(URL.format(season=season, comp=comp), timeout=30) as r:  # noqa: S310 - fixed https URL
            t = r.read().decode("utf-8")
    except Exception:  # noqa: BLE001 — a competition absent that season
        t = ""
    p.write_text(t, encoding="utf-8")
    return t or None


_DATE = re.compile(r"^\s*(?:\[)?(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\w*\.?\s+([A-Z][a-z]{2})\w*\s+(\d{1,2})(?:\s+(\d{4}))?")
_GAME = re.compile(r"^\s*(?:\d{1,2}[.:]\d{2}\s+)?(.+?)\s+\(([A-Z]{3})\)\s+v\s+(.+?)\s+\(([A-Z]{3})\)")


def parse(text: str, start_year: int) -> list[dict]:
    """Games {date, home, hc, away, ac}. A date line without a year gets the
    season's: Jul-Dec = start_year, Jan-Jun = start_year + 1."""
    out, cur = [], None
    for line in text.splitlines():
        m = _DATE.match(line)
        if m and m.group(1) in MONTHS:
            mon, day = MONTHS[m.group(1)], int(m.group(2))
            yr = int(m.group(3)) if m.group(3) else (start_year if mon >= 7 else start_year + 1)
            try:
                cur = date(yr, mon, day).isoformat()
            except ValueError:
                cur = None
            rest = line[m.end():]
        else:
            rest = line
        g = _GAME.search(rest)
        if g and cur:
            out.append({"date": cur, "home": g.group(1).strip(), "hc": g.group(2),
                        "away": g.group(3).strip(), "ac": g.group(4)})
    return out


def fd_season(code: str) -> str:
    """'2425' -> '2024-25'."""
    return f"20{code[:2]}-{code[2:]}"


def match_club(euro: str, clubs: list[str]) -> str | None:
    n = norm(euro)
    if n in ALIAS and ALIAS[n] in clubs:
        return ALIAS[n]
    toks = set(n.split())
    hits = [c for c in clubs if (set(norm(c).split()) and set(norm(c).split()) <= toks)]
    return hits[0] if len(hits) == 1 else None


def games(code: str) -> list[dict]:
    """Every European game of one season (football-data season code)."""
    s = fd_season(code)
    out = []
    for comp in COMPS:
        t = fetch(s, comp)
        if t:
            for g in parse(t, int(s[:4])):
                g["comp"] = comp
                out.append(g)
    return out


def club_dates(code: str, league: str, clubs: list[str]) -> tuple[dict[str, list[dict]], list[str]]:
    """{football-data club: [{date, comp, ko}]} for the league's country, and
    the European names of that country left unmatched. ko = a knockout game
    (late in the competition: from February)."""
    cc = COUNTRY.get(league)
    out: dict[str, list[dict]] = {}
    miss: set[str] = set()
    if not cc:
        return out, []
    for g in games(code):
        for side, c in (("home", "hc"), ("away", "ac")):
            if g[c] != cc:
                continue
            club = match_club(g[side], clubs)
            if club is None:
                miss.add(g[side])
                continue
            out.setdefault(club, []).append({"date": g["date"], "comp": g["comp"],
                                             "ko": g["date"][5:7] in ("02", "03", "04", "05")})
    for v in out.values():
        v.sort(key=lambda x: x["date"])
    return out, sorted(miss)


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    from data.football_data_source import load_league
    code, lg = sys.argv[1], sys.argv[2]
    res, _ = load_league(lg, code)
    clubs = sorted({r.home_team for r in res} | {r.away_team for r in res})
    got, miss = club_dates(code, lg, clubs)
    for k, v in sorted(got.items()):
        print(f"{k}: {len(v)} European games")
    print("unmatched:", miss)
