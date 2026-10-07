"""
NBA TEAMS — one table for every source the NBA board reads (order 41).

    key       the NBA's own three-letter code; also NBA_Betting's games.home_team
    espn      ESPN team id + abbreviation (scoreboard / odds feeds)
    name      ESPN display name ("LA Clippers")
    sr_id     SportyBet's Sportradar competitor id (homeTeamId / awayTeamId)
    bet365    how bet365 lists the team (DRAFT — see BET365_CONFIRMED)

SportyBet ids were read from SportyBet's own NBA feed on 2026-10-07 for the
27 teams it listed that day. LA Clippers (3425), Sacramento Kings (3413) and
Toronto Raptors (3433) had no game listed; their ids come from Sportradar's
public stats service (stats_team_info), which named all 27 feed ids exactly
as SportyBet does. Nothing is guessed (HR59): an id that disagrees with its
name is flagged and the game is skipped, as football's name matching does;
a team ever left without an id matches by name and its first id is flagged.

bet365 has no free feed (order 27: no paid API), so the bet365 names and
market labels are a draft until the Architect checks them against the app,
exactly like the football bet365 board's menu (order 29, MENU_CONFIRMED).
"""
from __future__ import annotations

import math
import re
import unicodedata
from typing import NamedTuple

# Flip to True once the Architect has checked the bet365 NBA names in the app.
BET365_CONFIRMED = False


class Team(NamedTuple):
    key: str
    espn_id: str
    espn_abbr: str
    name: str
    sr_id: str | None
    bet365: str


TEAMS = (
    Team("ATL", "1", "ATL", "Atlanta Hawks", "sr:competitor:3423", "ATL Hawks"),
    Team("BOS", "2", "BOS", "Boston Celtics", "sr:competitor:3422", "BOS Celtics"),
    Team("BKN", "17", "BKN", "Brooklyn Nets", "sr:competitor:3436", "BKN Nets"),
    Team("CHA", "30", "CHA", "Charlotte Hornets", "sr:competitor:3430", "CHA Hornets"),
    Team("CHI", "4", "CHI", "Chicago Bulls", "sr:competitor:3409", "CHI Bulls"),
    Team("CLE", "5", "CLE", "Cleveland Cavaliers", "sr:competitor:3432", "CLE Cavaliers"),
    Team("DAL", "6", "DAL", "Dallas Mavericks", "sr:competitor:3411", "DAL Mavericks"),
    Team("DEN", "7", "DEN", "Denver Nuggets", "sr:competitor:3417", "DEN Nuggets"),
    Team("DET", "8", "DET", "Detroit Pistons", "sr:competitor:3424", "DET Pistons"),
    Team("GSW", "9", "GS", "Golden State Warriors", "sr:competitor:3428", "GS Warriors"),
    Team("HOU", "10", "HOU", "Houston Rockets", "sr:competitor:3412", "HOU Rockets"),
    Team("IND", "11", "IND", "Indiana Pacers", "sr:competitor:3419", "IND Pacers"),
    Team("LAC", "12", "LAC", "LA Clippers", "sr:competitor:3425", "LA Clippers"),
    Team("LAL", "13", "LAL", "Los Angeles Lakers", "sr:competitor:3427", "LA Lakers"),
    Team("MEM", "29", "MEM", "Memphis Grizzlies", "sr:competitor:3415", "MEM Grizzlies"),
    Team("MIA", "14", "MIA", "Miami Heat", "sr:competitor:3435", "MIA Heat"),
    Team("MIL", "15", "MIL", "Milwaukee Bucks", "sr:competitor:3410", "MIL Bucks"),
    Team("MIN", "16", "MIN", "Minnesota Timberwolves", "sr:competitor:3426", "MIN Timberwolves"),
    Team("NOP", "3", "NO", "New Orleans Pelicans", "sr:competitor:5539", "NO Pelicans"),
    Team("NYK", "18", "NY", "New York Knicks", "sr:competitor:3421", "NY Knicks"),
    Team("OKC", "25", "OKC", "Oklahoma City Thunder", "sr:competitor:3418", "OKC Thunder"),
    Team("ORL", "19", "ORL", "Orlando Magic", "sr:competitor:3437", "ORL Magic"),
    Team("PHI", "20", "PHI", "Philadelphia 76ers", "sr:competitor:3420", "PHI 76ers"),
    Team("PHX", "21", "PHX", "Phoenix Suns", "sr:competitor:3416", "PHX Suns"),
    Team("POR", "22", "POR", "Portland Trail Blazers", "sr:competitor:3414", "POR Trail Blazers"),
    Team("SAC", "23", "SAC", "Sacramento Kings", "sr:competitor:3413", "SAC Kings"),
    Team("SAS", "24", "SA", "San Antonio Spurs", "sr:competitor:3429", "SA Spurs"),
    Team("TOR", "28", "TOR", "Toronto Raptors", "sr:competitor:3433", "TOR Raptors"),
    Team("UTA", "26", "UTAH", "Utah Jazz", "sr:competitor:3434", "UTA Jazz"),
    Team("WAS", "27", "WSH", "Washington Wizards", "sr:competitor:3431", "WAS Wizards"),
)

# Other spellings seen for a team, folded (see _fold). City + nickname of every
# team is added automatically; these are the ones that aren't.
ALIASES = {
    "los angeles clippers": "LAC", "la lakers": "LAL", "l a lakers": "LAL",
    "l a clippers": "LAC", "philadelphia sixers": "PHI", "portland blazers": "POR",
}

BY_KEY = {t.key: t for t in TEAMS}
BY_ESPN_ABBR = {t.espn_abbr: t for t in TEAMS}
BY_SR = {t.sr_id: t for t in TEAMS if t.sr_id}


def _fold(name: str) -> str:
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    return " ".join(re.split(r"[^a-z0-9]+", s)).strip()


def _nickname(t: Team) -> str:
    """The team's nickname: the last word, except the one two-word nickname."""
    return "trail blazers" if t.key == "POR" else _fold(t.name).split()[-1]


_BY_NAME = {_fold(t.name): t for t in TEAMS}
_BY_NAME.update({a: BY_KEY[k] for a, k in ALIASES.items()})
_BY_NICK = {_nickname(t): t for t in TEAMS}


def by_name(name: str) -> Team | None:
    """A team from any source's name: full name, a known alias, or its nickname
    ("Trail Blazers", "76ers") — each nickname belongs to exactly one team."""
    f = _fold(name)
    if not f:
        return None
    if f in _BY_NAME:
        return _BY_NAME[f]
    for nick, t in _BY_NICK.items():
        if f == nick or f.endswith(" " + nick):
            return t
    return None


def by_espn(abbr: str) -> Team | None:
    return BY_ESPN_ABBR.get((abbr or "").strip().upper())


def sportybet(name: str, sr_id: str | None) -> tuple[Team | None, str | None]:
    """(team, mapping note) for one SportyBet side. The id decides when it is on
    file; a name the id contradicts is never trusted."""
    named = by_name(name)
    if sr_id and sr_id in BY_SR:
        t = BY_SR[sr_id]
        if named is not None and named != t:
            return None, (f"mapping: SportyBet id {sr_id} is {t.name} on file but the feed "
                          f"calls it '{name}' — skipped, check engine/nba_teams.py")
        return t, None
    if named is None:
        return None, f"mapping: SportyBet team '{name}' ({sr_id}) is not in engine/nba_teams.py — skipped"
    if sr_id and named.sr_id is None:
        return named, (f"mapping: new SportyBet id {sr_id} for {named.name} — matched by name; "
                       f"add it to engine/nba_teams.py")
    if sr_id and named.sr_id != sr_id:
        return None, (f"mapping: SportyBet '{name}' has id {sr_id}, file says {named.sr_id} — "
                      f"skipped, check engine/nba_teams.py")
    return named, None


# ── bet365 (draft names, order 29 pattern) ───────────────────────────────────
BET365_MARKETS = {
    "219": "Game Lines › Money Line",
    "223": "Game Lines › Spread",
    "225": "Game Lines › Total",
    "68": "1st Half › Total",
    "236": "1st Quarter › Total",
    "227": "Team Totals",
    "228": "Team Totals",
    "66": "1st Half › Spread",
    "303": "Quarter › Spread",
}
# No bet365 line for SportyBet's regulation-time total (18): bet365's game
# total includes overtime, so it is a different bet.
_QUARTER = {"1": "1st Quarter", "2": "2nd Quarter", "3": "3rd Quarter"}


def bet365_pick(row: dict, home: Team, away: Team) -> str | None:
    """How a SportyBet NBA pick reads on bet365, or None when it has no match.
    Full-game lines include overtime on both books; half/quarter lines never do."""
    mid, o = str(row.get("market_id")), (row.get("outcome") or "").strip()
    market = BET365_MARKETS.get(mid)
    if market is None or not o:
        return None
    side = o.split()[0]
    if mid == "219":
        team = {"Home": home, "Away": away}.get(side)
        return f"{market}: {team.bet365}" if team else None
    if mid in ("223", "66", "303"):
        m = re.search(r"\(([-+]?\d+(?:\.\d+)?)\)", o)
        team = {"Home": home, "Away": away}.get(side)
        if mid == "303":
            q = re.search(r"quarternr=(\d)", row.get("specifier") or "")
            if not q or q.group(1) not in _QUARTER:
                return None
            market = f"{_QUARTER[q.group(1)]} › Spread"
        return f"{market}: {team.bet365} {float(m.group(1)):+g}" if team and m else None
    if mid in ("227", "228"):
        m = re.match(r"(Over|Under)\s+(\d+(?:\.\d+)?)$", o)
        team = home if mid == "227" else away
        return f"{market}: {team.bet365} {m.group(1)} {m.group(2)}" if m else None
    m = re.match(r"(Over|Under)\s+(\d+(?:\.\d+)?)$", o)
    return f"{market}: {m.group(1)} {m.group(2)}" if m else None


def bet365_take_at(row: dict, min_ev: float, floor: float) -> float:
    """Lowest bet365 price that still clears the board's own value bar for this
    pick's fair chance (rounded UP to 0.01, never below the band floor)."""
    return max(floor, math.ceil(100.0 * (1 + min_ev) / row["chance"] - 1e-9) / 100.0)
