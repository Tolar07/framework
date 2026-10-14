"""
Offline test of data/team_profiles.py: a FotMob team page parsed into a
profile (squad, coach, formation, stats per match), style tiers computed from
the league's own values (conceded stats: lower is better), and the fixture
profile read. No network.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data import team_profiles as tp

page = {"details": {"id": 1, "name": "Attack FC", "shortName": "Attack", "country": "ENG"},
        "overview": {"lastLineupStats": {"formation": "4-3-3", "starters": [{"name": "A. Keeper", "usualPlayingPositionId": 0, "marketValue": 5}]},
                     "teamForm": [{"resultString": "W"}, {"resultString": "L"}]},
        "squad": {"squad": [{"title": "coach", "members": [{"name": "The Coach"}]},
                            {"title": "keepers", "members": [{"name": "A. Keeper", "positionIdsDesc": "GK", "age": 30, "injury": None}]},
                            {"title": "attackers", "members": [{"name": "B. Striker", "positionIdsDesc": "ST", "age": 24, "goals": 5, "injury": {"x": 1}}]}]},
        "stats": {"teams": [{"header": "Expected goals", "participant": {"value": 20.0, "rank": 1}},
                            {"header": "xG conceded", "participant": {"value": 15.0, "rank": 9}},
                            {"header": "Goals per match", "participant": {"value": 2.1, "rank": 1}},
                            {"header": "Something new", "participant": {"value": 3}}]}}
p = tp.parse_team(page, fallback_played=99)
assert p["played"] == 99, "no domestic table on the page: fall back to the competition's count"
page_ucl = {**page, "stats": {**page["stats"], "primaryLeagueId": 47},
            "table": [{"data": {"leagueId": 47, "table": {"all": [{"id": 1, "played": 10}]}}}]}
p = tp.parse_team(page_ucl, fallback_played=2)
assert p["played"] == 10, "per-match stats divide by DOMESTIC games (the stats are domestic totals)"
assert (p["coach"], p["formation"], p["form"]) == ("The Coach", "4-3-3", ["W", "L"])
assert [s["name"] for s in p["squad"]] == ["A. Keeper", "B. Striker"] and p["squad"][1]["injured"]
assert p["stats"]["xg_pm"]["value"] == 2.0 and p["stats"]["xga_pm"]["value"] == 1.5
assert "Something new" not in str(p["stats"]), "only known stats kept"
print("team page parsed: OK")


def team(name, xg, xga):
    return {"name": name, "stats": {"xg_pm": {"value": xg}, "xga_pm": {"value": xga}}}


league = [team("Leaky", 1.9, 2.0), team("Solid", 0.9, 0.7), team("Mid", 1.3, 1.3),
          team("Mid2", 1.4, 1.2), team("Low", 0.8, 1.6), team("Top", 2.1, 1.0)]
s = {t["name"]: tp.style(t, league) for t in league}
assert s["Solid"]["defence"] == "strong" and s["Leaky"]["defence"] == "weak", "conceding less is better"
assert s["Top"]["attack"] == "strong" and s["Low"]["attack"] == "weak"
assert s["Solid"]["possession"] == "PENDING", "an absent stat is PENDING, never guessed"
print("style tiers from the league's own values: OK")

for t in league:
    t["style"] = s[t["name"]]
by = {t["name"]: t for t in league}
assert tp.profile_read(by["Top"], by["Leaky"])["lean"].startswith("BTTS yes")
assert tp.profile_read(by["Solid"], by["Low"])["lean"].startswith("Under")
assert tp.profile_read({"stats": {}, "style": {}}, by["Top"])["lean"].startswith("PENDING")
print("fixture profile read: OK")


# ── the universe sweep's attach: every game gets a profile before kick-off ──
import tempfile  # noqa: E402
from datetime import UTC, datetime, timedelta  # noqa: E402

now = datetime(2026, 10, 14, 9, 0, tzinfo=UTC)
cache = tp.TeamCache(Path(tempfile.mkdtemp()) / "c.json.gz", budget=0)   # budget 0: never fetch
for i, t in enumerate(league):
    cache.data[str(i + 1)] = {"at": now.isoformat(), "profile": {
        "id": i + 1, "name": t["name"], "league": 47,
        "stats": {"xg_pm": t["stats"]["xg_pm"]["value"], "xga_pm": t["stats"]["xga_pm"]["value"]}}}
g = tp.game_profile(cache, 6, 1, now)                          # Top v Leaky
assert g["read"]["lean"].startswith("BTTS yes") and g["home"]["style"]["attack"] == "strong"
assert tp.game_profile(cache, 6, 99, now) is None, "an unknown team: no profile, never a guess"

ko = (now + timedelta(hours=10)).strftime("%Y-%m-%dT%H:%MZ")
late = (now + timedelta(hours=60)).strftime("%Y-%m-%dT%H:%MZ")
pending = {"a": {"sport": "football", "ko": ko, "home": "Top", "away": "Leaky"},
           "b": {"sport": "football", "ko": ko, "home": "Nobody", "away": "Else"},
           "c": {"sport": "football", "ko": late, "home": "Top", "away": "Leaky"},
           "d": {"sport": "basketball", "ko": ko, "home": "Top", "away": "Leaky"}}
fixtures = [{"home": "Top", "away": "Leaky", "home_id": 6, "away_id": 1, "league": "Premier League",
             "kickoff_utc": ko[:-1] + ":00.000Z"}]
real = tp.fm.matches_on
tp.fm.matches_on = lambda day: fixtures
try:
    note = tp.attach(pending, now, cache=cache)
finally:
    tp.fm.matches_on = real
assert pending["a"]["profile"]["read"]["lean"].startswith("BTTS yes")
assert "profile" not in pending["b"], "not matched on FotMob: no profile"
assert "profile" not in pending["c"] and "profile" not in pending["d"], "too far off / not football"
assert "1 games profiled, 1 not matched" in note, note
print("sweep attach + game profile: OK")

# the profile matcher: kick-off and men's / youth / women's kind must agree;
# one exact name is enough when it is the only such fixture at that time
fx = [{"home": "Manchester City", "away": "Paris Saint-Germain", "league": "Champions League",
       "kickoff_utc": "2026-10-14T19:00:00.000Z", "home_id": 1, "away_id": 2},
      {"home": "Manchester City U19", "away": "Paris Saint-Germain U19", "league": "UEFA Youth League",
       "kickoff_utc": "2026-10-14T19:00:00.000Z", "home_id": 3, "away_id": 4},
      {"home": "Strømmen", "away": "Åsane", "league": "1. Divisjon", "kickoff_utc": "2026-10-14T13:00:00.000Z",
       "home_id": 5, "away_id": 6}]
g = {"ko": "2026-10-14T19:00Z", "comp": "UEFA Champions League"}
assert tp.match_game(fx, {**g, "home": "Man City", "away": "PSG"})["home_id"] == 1, "youth fixture kept apart"
assert tp.match_game(fx, {**g, "comp": "UEFA Youth League", "home": "Man City U19", "away": "PSG U19"})["home_id"] == 3
assert tp.match_game(fx, {**g, "ko": "2026-10-14T21:00Z", "home": "Man City", "away": "PSG"}) is None, "kick-off differs"
assert tp.match_game(fx, {"ko": "2026-10-14T13:00Z", "comp": "1st Division",
                          "home": "Stroemmen IF", "away": "Aasane Fotball"})["home_id"] == 5, "Nordic letters"
print("profile matcher: OK")

# ── the paper book's profile rules read the stored profile ──
from engine import paper_book as pb  # noqa: E402

prices = {"p": {"btts": [1.70, 2.05], "ou2.5": [1.80, 1.95], "ou3.5": [3.0, 1.35]}}
row = {"sport": "football", "ko": "2026-10-14T19:00Z", "home": "Top", "away": "Leaky", "first": prices, "last": prices,
       "result": {"h": 2, "a": 1}, "profile": pending["a"]["profile"]}
names = str(pb.bets(row))
assert "btts:yes" in names and "o/u2.5:over" in names, names
assert "o/u3.5:under" in names, "P5 tests the board's habit: short Under 3.5 against a BTTS-yes profile"
assert "btts:yes" not in str(pb.bets({**row, "profile": None})), "no profile: no P bet"
assert "btts:yes" not in str(pb.bets({**row, "ko": "2026-10-12T19:00Z"})), "P rules start 2026-10-13"
print("paper book profile rules: OK")

# ── the profile study ──
sys.path.insert(0, str(Path(__file__).parent.parent / "backtest"))
import profile_study as ps  # noqa: E402

graded = [row] * 3
text = ps.build(graded)
assert "Profiled graded games: **3**" in text and "| BTTS yes / Over 2.5 *(too few)* | 3 | 3.00 |" in text, text
assert "NO DATA — PENDING" in ps.build([]), "no profiled games: PENDING, never an empty table"
print("profile study: OK")

# order 43: a fixture's read by team names; a shootout drops match Unders up to 4.5
db = {"leagues": {"L": {"teams": [{**team("Top", 2.1, 1.0), "name": "Top FC", "stats_league": 47, "style": s["Top"]},
                                  {**team("Leaky", 1.9, 2.0), "name": "Leaky Town", "stats_league": 47,
                                   "style": s["Leaky"]}]}}}
r = tp.fixture_read("Top FC", "Leaky Town", db, {})
assert tp.is_shootout(r), r
assert tp.fixture_read("Top FC", "Nobody United", db, {}) is None, "a team not in the database: no read, no guess"
sys.path.insert(0, str(Path(__file__).parent.parent))
import run_daily as rd  # noqa: E402

assert rd._shootout_under("SB:18|total=3.5|Under 3.5") and rd._shootout_under("UNDER_3_5")
assert not rd._shootout_under("SB:18|total=2.5|Over 2.5") and not rd._shootout_under("SB:18|total=5.5|Under 5.5")
assert not rd._shootout_under("SB:20|total=1.5|Under 1.5"), "team totals are not touched by order 43"
print("order 43 shootout gate: OK")

print("ALL TEAM PROFILE TESTS PASSED")
