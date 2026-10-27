"""
Offline test of the NBA team table (engine/nba_teams.py): every ESPN team and
every SportyBet name + id as both feeds listed them on 2026-10-07, the
mapping flags (new id, id/name conflict, unknown team), and the draft bet365
names, market labels and take-at prices.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine import nba_teams as nt

# SportyBet's NBA feed, 2026-10-07 (27 teams listed; LAC, SAC, TOR had no game)
SB = {
    "Atlanta Hawks": "sr:competitor:3423", "Boston Celtics": "sr:competitor:3422",
    "Brooklyn Nets": "sr:competitor:3436", "Charlotte Hornets": "sr:competitor:3430",
    "Chicago Bulls": "sr:competitor:3409", "Cleveland Cavaliers": "sr:competitor:3432",
    "Dallas Mavericks": "sr:competitor:3411", "Denver Nuggets": "sr:competitor:3417",
    "Detroit Pistons": "sr:competitor:3424", "Golden State Warriors": "sr:competitor:3428",
    "Houston Rockets": "sr:competitor:3412", "Indiana Pacers": "sr:competitor:3419",
    "Los Angeles Lakers": "sr:competitor:3427", "Memphis Grizzlies": "sr:competitor:3415",
    "Miami Heat": "sr:competitor:3435", "Milwaukee Bucks": "sr:competitor:3410",
    "Minnesota Timberwolves": "sr:competitor:3426", "New Orleans Pelicans": "sr:competitor:5539",
    "New York Knicks": "sr:competitor:3421", "Oklahoma City Thunder": "sr:competitor:3418",
    "Orlando Magic": "sr:competitor:3437", "Philadelphia 76ers": "sr:competitor:3420",
    "Phoenix Suns": "sr:competitor:3416", "Portland Trail Blazers": "sr:competitor:3414",
    "San Antonio Spurs": "sr:competitor:3429", "Utah Jazz": "sr:competitor:3434",
    "Washington Wizards": "sr:competitor:3431",
}
# ESPN's NBA teams endpoint, 2026-10-07: (abbreviation, id, display name)
ESPN = [
    ("ATL", "1", "Atlanta Hawks"), ("BOS", "2", "Boston Celtics"), ("BKN", "17", "Brooklyn Nets"),
    ("CHA", "30", "Charlotte Hornets"), ("CHI", "4", "Chicago Bulls"),
    ("CLE", "5", "Cleveland Cavaliers"), ("DAL", "6", "Dallas Mavericks"),
    ("DEN", "7", "Denver Nuggets"), ("DET", "8", "Detroit Pistons"),
    ("GS", "9", "Golden State Warriors"), ("HOU", "10", "Houston Rockets"),
    ("IND", "11", "Indiana Pacers"), ("LAC", "12", "LA Clippers"),
    ("LAL", "13", "Los Angeles Lakers"), ("MEM", "29", "Memphis Grizzlies"),
    ("MIA", "14", "Miami Heat"), ("MIL", "15", "Milwaukee Bucks"),
    ("MIN", "16", "Minnesota Timberwolves"), ("NO", "3", "New Orleans Pelicans"),
    ("NY", "18", "New York Knicks"), ("OKC", "25", "Oklahoma City Thunder"),
    ("ORL", "19", "Orlando Magic"), ("PHI", "20", "Philadelphia 76ers"),
    ("PHX", "21", "Phoenix Suns"), ("POR", "22", "Portland Trail Blazers"),
    ("SAC", "23", "Sacramento Kings"), ("SA", "24", "San Antonio Spurs"),
    ("TOR", "28", "Toronto Raptors"), ("UTAH", "26", "Utah Jazz"),
    ("WSH", "27", "Washington Wizards"),
]
# NBA_Betting's VALID_TEAM_ABBREVIATIONS (its games.home_team / away_team)
EXT = {"ATL", "BKN", "BOS", "CHA", "CHI", "CLE", "DAL", "DEN", "DET", "GSW", "HOU", "IND",
       "LAC", "LAL", "MEM", "MIA", "MIL", "MIN", "NOP", "NYK", "OKC", "ORL", "PHI", "PHX",
       "POR", "SAC", "SAS", "TOR", "UTA", "WAS"}

# ── the table itself ─────────────────────────────────────────────────────────
assert len(nt.TEAMS) == 30
for field in ("key", "espn_id", "espn_abbr", "name", "bet365"):
    vals = [getattr(t, field) for t in nt.TEAMS]
    assert len(set(vals)) == 30, f"{field} must be unique"
ids = [t.sr_id for t in nt.TEAMS if t.sr_id]
assert len(ids) == len(set(ids)) == 30
assert {t.key for t in nt.TEAMS} == EXT, "team keys are NBA_Betting's codes"
print("30 teams, unique on every field, keys = NBA_Betting codes: OK")

# ── ESPN ─────────────────────────────────────────────────────────────────────
for abbr, eid, name in ESPN:
    t = nt.by_espn(abbr)
    assert t and t.espn_id == eid and t.name == name, (abbr, t)
    assert nt.by_name(name) == t, name
print("all 30 ESPN teams (id, abbreviation, name): OK")

# ── SportyBet ────────────────────────────────────────────────────────────────
for name, sr in SB.items():
    t, note = nt.sportybet(name, sr)
    assert t and t.sr_id == sr and note is None, (name, t, note)
# The three SportyBet had no game for on 2026-10-07: ids from Sportradar's stats
# service, which named all 27 feed ids above exactly as SportyBet does.
for name, sr in [("Los Angeles Clippers", "sr:competitor:3425"), ("LA Clippers", "sr:competitor:3425"),
                 ("Sacramento Kings", "sr:competitor:3413"), ("Toronto Raptors", "sr:competitor:3433")]:
    t, note = nt.sportybet(name, sr)
    assert t and t.sr_id == sr and note is None, (name, t, note)
print("all 30 SportyBet ids (27 from the feed + 3 from Sportradar stats): OK")

# a team without an id on file matches by name and flags the id it was shown
tor = nt.BY_KEY["TOR"]
nt._BY_NAME["toronto raptors"] = tor._replace(sr_id=None)
try:
    t, note = nt.sportybet("Toronto Raptors", "sr:competitor:9999")
    assert t.key == "TOR" and note.startswith("mapping: new SportyBet id"), note
finally:
    nt._BY_NAME["toronto raptors"] = tor
t, note = nt.sportybet("Toronto Raptors", None)
assert t.key == "TOR" and note is None
t, note = nt.sportybet("Boston Celtics", "sr:competitor:3423")       # Atlanta's id
assert t is None and "skipped" in note, note
t, note = nt.sportybet("Boston Celtics", "sr:competitor:8888")       # id not on file, name has one
assert t is None and "file says sr:competitor:3422" in note, note
t, note = nt.sportybet("Seattle SuperSonics", "sr:competitor:7777")
assert t is None and "not in engine/nba_teams.py" in note
print("mapping flags: new id, id/name conflict, unknown team: OK")

for alias, key in [("LA Lakers", "LAL"), ("LA Clippers", "LAC"), ("Los Angeles Clippers", "LAC"),
                   ("Trail Blazers", "POR"), ("Portland Blazers", "POR"), ("76ers", "PHI"),
                   ("Golden State Warriors", "GSW"), ("Philadelphia Sixers", "PHI")]:
    assert nt.by_name(alias).key == key, alias
assert nt.by_name("Kings") == nt.BY_KEY["SAC"] and nt.by_name("") is None
assert nt.by_name("Los Angeles") is None, "a city alone is two teams — never guessed"
print("aliases and nicknames: OK")

# ── bet365 (draft names) ─────────────────────────────────────────────────────
bos, lal = nt.BY_KEY["BOS"], nt.BY_KEY["LAL"]
assert nt.bet365_pick({"market_id": "219", "outcome": "Away"}, bos, lal) == "Game Lines › Money Line: LA Lakers"
assert nt.bet365_pick({"market_id": "223", "outcome": "Home (-6.5)"}, bos, lal) == "Game Lines › Spread: BOS Celtics -6.5"
assert nt.bet365_pick({"market_id": "223", "outcome": "Away (+11.5)"}, bos, lal) == "Game Lines › Spread: LA Lakers +11.5"
assert nt.bet365_pick({"market_id": "225", "outcome": "Under 231.5"}, bos, lal) == "Game Lines › Total: Under 231.5"
assert nt.bet365_pick({"market_id": "68", "outcome": "Over 112.5"}, bos, lal) == "1st Half › Total: Over 112.5"
assert nt.bet365_pick({"market_id": "236", "outcome": "Over 55.5"}, bos, lal) == "1st Quarter › Total: Over 55.5"
assert nt.bet365_pick({"market_id": "999", "outcome": "Home"}, bos, lal) is None
assert nt.BET365_CONFIRMED is False, "draft until the Architect checks the app"
# take-at: fair chance 0.60 at the line bar of +5% -> 1.05 / 0.60 = 1.75
assert nt.bet365_take_at({"chance": 0.60}, 0.05, 1.20) == 1.75
assert nt.bet365_take_at({"chance": 0.95}, 0.03, 1.20) == 1.20, "never below the band floor"
print("bet365 names, market labels and take-at price: OK")

print("ALL NBA TEAM-MAPPING TESTS PASSED")
