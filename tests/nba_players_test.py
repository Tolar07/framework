"""
Offline test of the NBA player data (data/nba_players.py, Architect 2026-10-28 step 1):
box-score rows, the season log and its scan pointer, injuries, expected starters,
season / last-10 averages and the stale-data gate. No network: fake ESPN blobs.
"""
import shutil
import sys
import tempfile
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data import nba_players as npl
from data import nba_source as ns

KEYS = ["minutes", "points", "rebounds"]


def ath(pid, name, mins, pts, starter=True, dnp=False):
    return {"athlete": {"id": pid, "displayName": name}, "starter": starter, "didNotPlay": dnp,
            "stats": [] if dnp else [str(mins), str(pts), "5"]}


def box(home_players, away_players):
    return {"boxscore": {"players": [
        {"team": {"abbreviation": "BOS"}, "statistics": [{"keys": KEYS, "athletes": home_players}]},
        {"team": {"abbreviation": "NYK"}, "statistics": [{"keys": KEYS, "athletes": away_players}]}],
        "teams": [{"team": {"abbreviation": t}, "statistics": [
            {"name": "fieldGoalsMade-fieldGoalsAttempted", "displayValue": "40-90"},
            {"name": "freeThrowsMade-freeThrowsAttempted", "displayValue": "20-25"},
            {"name": "offensiveRebounds", "displayValue": "10"},
            {"name": "totalTurnovers", "displayValue": "14"}]} for t in ("BOS", "NYK")]}}


BOS = [ath("1", "Star", 36, 30), ath("2", "Second", 34, 20), ath("3", "Third", 30, 15),
       ath("4", "Four", 28, 8), ath("5", "Five", 26, 6), ath("6", "Bench", 18, 9, starter=False),
       ath("7", "Unused", 0, 0, starter=False, dnp=True)]
NYK = [ath(str(i), f"K{i}", 30, 20 - i) for i in range(11, 16)]

days = {date(2026, 10, 21): [ns.Game("g1", "2026-10-21", 2027, 2, "BOS", "NYK", 110, 100, True)],
        date(2026, 10, 23): [ns.Game("g2", "2026-10-23", 2027, 2, "NYK", "BOS", 99, 105, True)],
        date(2026, 10, 24): [ns.Game("g3", "2026-10-24", 2027, 1, "BOS", "NYK", 90, 80, True)],   # preseason: ignored
        date(2026, 10, 28): [ns.Game("g9", "2026-10-28", 2027, 2, "BOS", "NYK", tip="2026-10-28T23:30Z")]}
calls = []


def scoreboard(d, use_cache=True):
    return days.get(d, [])


def fetch(url):
    calls.append(url)
    e = url.split("event=")[1]
    if e == "g9":
        return {"injuries": [{"team": {"abbreviation": "BOS"}, "injuries": [
            {"athlete": {"id": "1", "displayName": "Star"}, "status": "Out"},
            {"athlete": {"id": "3", "displayName": "Third"}, "status": "Day-To-Day"}]}]}
    return box(BOS, NYK) if e in ("g1", "g2", "g3") else None


with tempfile.TemporaryDirectory() as tmp:
    npl.CACHE = Path(tmp) / "cache"
    log = Path(tmp) / "nba_players" / "player_games.jsonl"
    meta = log.parent / "meta.json"

    # minutes as "MM:SS" or "MM"; DNP kept at 0 minutes
    assert npl._minutes("34:12") == 34.0 and npl._minutes("--") is None
    rows = npl.box_rows(days[date(2026, 10, 21)][0], box(BOS, NYK))
    assert len(rows) == 12 and [r for r in rows if r["p"] == "7"][0]["m"] == 0
    assert all(r["h"] == 1 for r in rows if r["t"] == "BOS") and rows[0]["o"] == "NYK"
    print("box rows: OK")

    # the log takes finished regular-season games once; the pointer stops re-scans
    npl.update_log(date(2026, 10, 25), fetch=fetch, scoreboard=scoreboard, log=log, meta=meta)
    got = npl.load_log(log)
    assert {r["g"] for r in got} == {"g1", "g2"}, "preseason left out"
    assert '"through": "2026-10-24"' in meta.read_text()
    n = len(calls)
    npl.update_log(date(2026, 10, 25), fetch=fetch, scoreboard=scoreboard, log=log, meta=meta)
    assert len(calls) == n and len(npl.load_log(log)) == len(got), "nothing fetched twice"
    teams = npl.load_log(log.parent / "team_games.jsonl")
    assert len(teams) == 4 and teams[0]["poss"] == 90 - 10 + 14 + 0.44 * 25 == 105.0
    assert {(r["t"], r["pts"]) for r in teams if r["g"] == "g1"} == {("BOS", 110), ("NYK", 100)}
    print("season log: OK")

    # team rows backfilled for games logged before the team log existed
    (log.parent / "team_games.jsonl").unlink()
    shutil.rmtree(npl.CACHE)
    summ = {"header": {"competitions": [{"date": "2026-10-21T23:30Z", "competitors": [
        {"homeAway": "home", "score": "110"}, {"homeAway": "away", "score": "100"}]}]}}
    old_fetch = fetch
    back = npl.backfill_teams(log, log.parent / "team_games.jsonl", lambda u: {**old_fetch(u), **summ})
    assert len(back) == 4 and back[0]["tip"] == "2026-10-21T23:30Z", back[:1]
    npl._append(log.parent / "team_games.jsonl", back)
    print("team backfill: OK")

    # last night not finished: stop there and come back next run
    days[date(2026, 10, 25)] = [ns.Game("g4", "2026-10-25", 2027, 2, "BOS", "NYK")]
    npl.update_log(date(2026, 10, 26), fetch=fetch, scoreboard=scoreboard, log=log, meta=meta)
    assert '"through": "2026-10-24"' in meta.read_text()
    # ... but an older unfinished game is a postponement and is passed over
    npl.update_log(date(2026, 10, 27), fetch=fetch, scoreboard=scoreboard, log=log, meta=meta)
    assert '"through": "2026-10-26"' in meta.read_text()
    del days[date(2026, 10, 25)]
    print("unfinished nights: OK")

    # sheets: Star is out (a top-3 scorer), Third doubtful-ish, starters exclude Star
    start = datetime(2026, 10, 28, 10, tzinfo=UTC)
    sheets, _ = npl.night_sheets(start, start + timedelta(hours=24), datetime(2026, 10, 28, 6, tzinfo=UTC),
                                 fetch=fetch, scoreboard=scoreboard, log=log)
    assert len(sheets) == 1
    h, a = sheets[0]["home_sheet"], sheets[0]["away_sheet"]
    assert h["team"] == "BOS" and h["games"] == 2 and h["stale"] == ["newest box score 2026-10-23"], h["stale"]
    assert h["top3_out"] == ["Star"] and [o["name"] for o in h["out"]] == ["Star"]
    assert [d["name"] for d in h["doubtful"]] == ["Third"]
    assert "Star" not in h["starters"] and h["starters"][:4] == ["Second", "Third", "Four", "Five"]
    assert len(h["starters"]) == 5 and h["starters"][4] == "Bench", "next man up by minutes"
    p2 = next(p for p in h["players"] if p["name"] == "Second")
    assert p2["gp"] == 2 and p2["min"] == 34.0 and p2["pts"] == 20.0 and p2["pts10"] == 20.0
    assert next(p for p in h["players"] if p["name"] == "Unused")["gp"] == 0
    assert a["out"] == [] and a["top3_out"] == []
    print("team sheets: OK")

    # stale gate: unreadable injuries, too few games, old box scores
    t = npl.team_sheet(npl.load_log(log), "BOS", None, date(2026, 10, 24))
    assert t["stale"] == ["injury list unreadable"], t["stale"]
    t = npl.team_sheet(npl.load_log(log)[:3], "BOS", [], date(2026, 10, 22))
    assert t["stale"] == ["1 games logged"], t["stale"]
    print("stale gate: OK")

    # a new season starts a new log
    meta.write_text('{"season": "2025-10-01", "through": "2026-06-20"}')
    npl.update_log(date(2026, 10, 22), fetch=fetch, scoreboard=scoreboard, log=log, meta=meta)
    assert {r["g"] for r in npl.load_log(log)} == {"g1"}
    print("new season: OK")

print("nba_players_test: ALL OK")
