"""engine/sport_calendar.py (Architect 2026-11-08: understand every sport's calendar and prepare for it). Offline:
ESPN and Flashscore stubbed. An international break is found when the club top flights stop while national-team
fixtures appear; a sport with no fixture listed is off-season; a thin board in a break is EXPECTED; a failed source
is PENDING, never an invented date or a 0."""
import json
import sys
import tempfile
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from engine import sport_calendar as SC  # noqa: E402
from monitor import bot_grader as BG  # noqa: E402
from monitor import supervisor as SV  # noqa: E402

TODAY = date(2026, 11, 9)
NOW = datetime(2026, 11, 9, 6, 0, tzinfo=UTC)


def ymd(d: date) -> str:
    return d.strftime("%Y%m%d")


def day(k: int) -> date:
    return TODAY + timedelta(days=k)


def ev(i: str, d: date, home: str, away: str, hour: int = 15) -> dict:
    return {"id": i, "date": f"{d.isoformat()}T{hour:02d}:00Z", "name": f"{away} at {home}",
            "competitions": [{"competitors": [{"homeAway": "home", "team": {"displayName": home}},
                                              {"homeAway": "away", "team": {"displayName": away}}],
                              "status": {"type": {"name": "STATUS_SCHEDULED"}}}]}


# club leagues: games on 8 Nov, then none until 21 Nov (an international break); Nations League 12-17 Nov
CLUB_DAYS = [day(-1), day(12), day(13), day(19), day(20)]
CLUB_CAL = CLUB_DAYS + [day(20 + 4 * k) for k in range(1, 20)]     # the season goes on past the horizon
NATIONAL_DAYS = [day(3), day(4), day(5), day(6), day(7), day(8)]


def fake_espn(url: str) -> dict:
    path = url.split("/sports/")[1].split("/scoreboard")[0]
    when = url.split("dates=")[1][:8]
    if path.startswith("soccer/") and path.split("/")[1] in ("eng.1", "esp.1", "ger.1", "ita.1"):
        cal = [f"{d.isoformat()}T07:00Z" for d in CLUB_CAL]
        evs = [ev(f"{path}{when}{k}", d, f"Club{k}", f"Club{k + 10}") for d in CLUB_DAYS if ymd(d) == when
               for k in range(5)]
        return {"leagues": [{"calendar": cal, "season": {"displayName": "2026-27"}}], "events": evs}
    if path == "soccer/uefa.nations":
        cal = [{"label": "UEFA Nations League", "entries": [
            {"label": "League Phase", "detail": "Sep 24-Nov 17", "startDate": "2026-09-24T07:00Z",
             "endDate": "2026-11-17T07:59Z"}]}]
        evs = [ev(f"n{when}{k}", d, f"Nation{k}", f"Nation{k + 20}", 19) for d in NATIONAL_DAYS if ymd(d) == when
               for k in range(4)]
        return {"leagues": [{"calendar": cal, "season": {}}], "events": evs}
    if path == "basketball/nba":
        cal = [f"{(TODAY + timedelta(days=k)).isoformat()}T07:00Z" for k in range(-1, 30)]
        evs = []
        if when == ymd(day(1)):
            evs = [ev("b1", day(1), "New York Knicks", "Boston Celtics", 0)]
        if when == ymd(day(2)):
            evs = [ev("b2", day(2), "Boston Celtics", "Miami Heat", 0)]
        return {"leagues": [{"calendar": cal, "season": {}}], "events": evs}
    if path == "baseball/mlb":           # the season is over: no game day left
        return {"leagues": [{"calendar": ["2026-10-30T07:00Z"], "season": {"displayName": "2026"}}], "events": []}
    return {"leagues": [{"calendar": [], "season": {}}], "events": []}


def fs_feed(sport: str):
    def get(off: int) -> str:
        d = TODAY + timedelta(days=off)
        ts = int(datetime(d.year, d.month, d.day, 18, tzinfo=UTC).timestamp())
        if sport == "football" and d in NATIONAL_DAYS:
            return f"~ZA÷EUROPE: UEFA Nations League - League A¬~AA÷x{off}¬AD÷{ts}¬AE÷A¬AF÷B¬"
        if sport == "snooker":
            return f"~ZA÷WORLD: Champion of Champions¬~AA÷s{off}¬AD÷{ts}¬AE÷P¬AF÷Q¬"
        return ""
    return get


doc = SC.build(TODAY, get=fake_espn, fs_get=fs_feed, now=NOW,
               sports=("football", "basketball", "baseball", "snooker", "darts"))

# ── football: the club leagues stop while national-team fixtures appear = international break ──
fb = doc["sports"]["football"]
brk = [w for w in fb["windows"] if w["kind"] == "international break"]
assert len(brk) == 1, fb["windows"]
w = brk[0]
assert w["start"] == day(0).isoformat() and w["end"] == day(11).isoformat(), w
assert w["confidence"] == "high" and w["national_fixtures"] >= 10 and len(w["leagues_paused"]) == 4
assert "espn" in w["source"]
nl = [e for e in fb["events"] if e["name"].startswith("UEFA Nations League (")]
assert nl and nl[0]["start"] == day(3).isoformat() and nl[0]["end"] == day(8).isoformat(), fb["events"]
assert any(e.get("phase") and e["end"] == "2026-11-17" for e in fb["events"])

# ── expected volume: an empty board inside the break is EXPECTED; after it is NOT ──
v = SC.expected_volume(doc, "football", day(1).isoformat())
assert v["level"] == "none" and "international break" in v["reason"], v
ok, text = SC.board_label(doc, "football", day(1).isoformat(), 0)
assert ok and text.startswith("0 picks — expected (international break"), text
ok, text = SC.board_label(doc, "football", day(12).isoformat(), 0)
assert not ok and "NOT expected" in text, text

# ── rotation flag + calendar note on the first club games after the break (call-ups PENDING) ──
rf = fb["rotation_flags"]
assert rf and rf[0]["day"] == day(12).isoformat() and rf[0]["call_ups"].startswith("PENDING")
note = SC.note_for(doc, "football", "Premier League", f"{day(12).isoformat()}T15:00:00Z", "Club1 v Club11")
assert note and note.startswith("first club game after the international break"), note
note = SC.note_for(doc, "football", "UEFA Nations League", f"{day(8).isoformat()}T19:45:00Z", "Nation1 v Nation21")
assert note and "Nations League final league-phase matchday" in note, note
assert SC.note_for(doc, "football", "Premier League", f"{day(20).isoformat()}T15:00:00Z", "A v B") is None

# ── basketball: back-to-back from the fetched games; WNBA-style single-league windows don't empty the sport ──
note = SC.note_for(doc, "basketball", "NBA", f"{day(2).isoformat()}T00:00:00Z", home="Boston Celtics",
                   away="Miami Heat")
assert note and "Boston Celtics: second night of a back-to-back" in note, note

# ── baseball: no game day left in the season = off-season (data, not a typed date) ──
bb = doc["sports"]["baseball"]
off = [w for w in bb["windows"] if w["kind"] == "off-season"]
assert off and off[0]["league"] == "MLB" and off[0]["end"] is None and "PENDING" in off[0]["source"], bb["windows"]

# ── darts: every source answered, none lists a fixture = off-season; snooker lists its event ──
dw = doc["sports"]["darts"]["windows"]
assert dw and dw[0]["kind"] == "off-season", dw
assert SC.board_label(doc, "darts", day(2).isoformat(), 0)[0]
sn = doc["sports"]["snooker"]["events"]
assert sn and sn[0]["name"] == "WORLD: Champion of Champions" and sn[0]["major"] and sn[0]["source"] == "flashscore"

# ── a failed source: nothing invented, PENDING ──
def down(url: str) -> dict:
    raise OSError("network down")


def fs_down(sport: str):
    def get(off: int) -> str:
        raise OSError("blocked")
    return get


bad = SC.build(TODAY, get=down, fs_get=fs_down, now=NOW, sports=("football", "snooker"))
assert all(not s["ok"] and s["error"] for s in bad["sources"]), bad["sources"]
for sport in ("football", "snooker"):
    s = bad["sports"][sport]
    assert s["windows"] == [] and s["events"] == [], s["windows"]
    assert all(r["all"] is None and r["tracked"] is None for r in s["days"].values()), "a failed day is None, not 0"
    assert SC.expected_volume(bad, sport, day(1).isoformat())["level"] == "PENDING"
    assert not SC.board_label(bad, sport, day(1).isoformat(), 0)[0]
assert SC.expected_volume(None, "football", "2026-11-10")["level"] == "PENDING"
assert SC.note_for(None, "football", "Premier League", "2026-11-21T15:00:00Z", "A v B") is None
assert SC.coming_up_lines(None, "2026-11-09") == ["calendar PENDING (no calendar file)"]
assert all("PENDING" in line for line in SC.coming_up_lines(bad, "2026-11-09"))

# ── one ESPN day failing: that day is PENDING (None), the others still counted ──
def flaky(url: str) -> dict:
    if f"dates={ymd(day(12))}" in url:
        raise OSError("timeout")
    return fake_espn(url)


fl = SC.fetch_espn("soccer/eng.1", "Premier League", "club", TODAY, flaky, NOW)
assert fl["days"][day(12).isoformat()]["n"] is None and fl["days"][day(13).isoformat()]["n"] == 5
assert fl["failed_days"] == [day(12).isoformat()]

# ── files, the 23:02 report section, the supervisor line ──
with tempfile.TemporaryDirectory() as t:
    out = Path(t)
    SC.save(doc, out)
    assert SC.load_latest("2026-11-10", out)["date"] == "2026-11-09"
    assert SC.load_latest("2026-11-20", out) is None, "a stale calendar is not used"
    assert SC.load_latest("2026-11-08", out) is None
    lines = SC.coming_up_lines(doc, "2026-11-09", 14)
    assert lines[0].startswith("football: international break 9 Nov-20 Nov"), lines
    assert any(x.startswith("baseball: off-season MLB") for x in lines), lines
    saved = SC.OUT_DIR
    SC.OUT_DIR = out
    try:
        orig = SC.load_latest
        SC.load_latest = lambda day=None, out_dir=out, max_age_days=3: orig(day, out_dir, max_age_days)  # type: ignore
        sec = BG.coming_up("2026-11-09")
        assert sec[1] == "COMING UP (next 14 days, sport calendar)" and sec[2].startswith("football:"), sec
        lab = SV._volume("2026-11-10", {"picks": 0})
        assert lab and lab[0] and "international break" in lab[1], lab
    finally:
        SC.OUT_DIR = saved
        SC.load_latest = orig
    text = SV.report("2026-11-10", "morning", "success", {"board": False}, {}, {}, volume=(True, "0 picks — expected"))
    assert "✓ calendar: 0 picks — expected" in text
    text = SV.report("2026-11-10", "morning", "success", {"board": False}, {}, {}, volume=(False, "0 picks — NOT"))
    assert "⚠ calendar: 0 picks — NOT" in text

# the report never breaks on a broken calendar
orig_cu = SC.coming_up_lines
SC.coming_up_lines = lambda *a, **k: (_ for _ in ()).throw(ValueError("bad"))  # type: ignore
assert BG.coming_up("2026-11-09") == []
SC.coming_up_lines = orig_cu

json.dumps(doc)       # the file is plain JSON

if __name__ == "__main__":
    print("sport_calendar_test: OK")
