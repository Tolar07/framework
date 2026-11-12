"""
engine/match_facts.py: Flashscore's stats by period, form and head-to-head for every sport's board games.
Offline: real feed text saved on 2026-11-12 (tests/fixtures/match_facts/), no network. Also checks the run
writes only its own two folders (record only).
"""
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from engine import match_facts as mf  # noqa: E402

FX = Path(__file__).parent / "fixtures" / "match_facts"
NOW = datetime(2026, 11, 12, 10, 0, tzinfo=timezone.utc)


def fx(name):
    return (FX / name).read_text(encoding="utf-8")


# the day feed: the game's id, names, state and score by period
day = mf.parse_day(fx("day_basketball.txt"))
assert len(day) == 1 and day[0]["id"] == "n1FCfmzA" and day[0]["home"] == "Adelaide", day
assert "NBL" in day[0]["league"] and len(day[0]["periods"]) >= 3 and day[0]["state"] in ("in", "post")

# the STATS tab: periods, groups, rows, in Flashscore's order and wording
bb = mf.parse_stats(fx("st_basketball.txt"))
assert [p["period"] for p in bb] == ["Match", "1st Quarter"], [p["period"] for p in bb]
assert [g["name"] for g in bb[0]["groups"]] == ["Scoring", "Rebounds", "Other"]
rows = {r[0]: r for g in bb[0]["groups"] for r in g["rows"]}
assert rows["Field goals %"][1].endswith("%") and "Total rebounds" in rows and "Turnovers" in rows
tn = mf.parse_stats(fx("st_tennis.txt"))
assert [p["period"] for p in tn] == ["Match", "Set 1"]
trow = {r[0]: r for g in tn[1]["groups"] for r in g["rows"]}
assert trow["Aces"][1:] == ["1", "0"] and trow["Double Faults"][1:] == ["3", "0"]          # the Architect's screenshot
assert trow["1st serve points won"][1:] == ["84% (16/19)", "63% (10/16)"]
assert trow["Break Points Saved"][1:] == ["0/1", "5/7"]
ih = mf.parse_stats(fx("st_hockey.txt"))
hrow = {r[0]: r for g in ih[0]["groups"] for r in g["rows"]}
assert hrow["Shots on Goal"][1:] == ["28", "17"] and hrow["Penalties"][1:] == ["1", "4"]      # the screenshot too
assert mf.parse_stats("") == [] and mf.parse_stats("A1÷abc¬~") == []

# values as numbers, for a model
assert mf.number("48.48%") == {"v": 48.48, "pct": True}
assert mf.number("84% (16/19)") == {"v": 84.0, "pct": True, "made": 16, "of": 19}
assert mf.number("5/7") == {"made": 5, "of": 7}
assert mf.number("28") == {"v": 28.0} and mf.number("") is None and mf.number("-") is None
flat = mf.flat_stats(tn)
assert flat["Set 1"]["Aces"] == [{"v": 1.0}, {"v": 0.0}] and flat["Match"]["Break Points Saved"][0] == {"made": 3, "of": 6}

# form and head-to-head: first tab only, newest first, capped
hh = mf.parse_h2h(fx("hh_basketball.txt"))
assert len(hh["home_last"]) == mf.LAST_N and len(hh["away_last"]) == mf.LAST_N and hh["h2h"]
assert hh["home_last"][0]["home"] == "Adelaide" and hh["home_last"][0]["score"] == "106:78" and hh["home_last"][0]["res"] == "w"
assert mf.parse_h2h("KA÷Overall¬~KB÷Last matches: A¬~KC÷1794033000¬KJ÷*A¬KK÷B¬KL÷3:2¬WIS÷wo¬~")["home_last"][0]["res"] == "w"
assert all(r["home"] != "X" for k in hh for r in hh[k])                     # the venue tabs are not read
assert mf.form_line(hh["home_last"])[:2] == "WL" and set(mf.form_line(hh["home_last"])) <= set("WLD?")
assert hh["home_last"][0]["date"] >= hh["home_last"][1]["date"]

# one run over a board: matched game gets form before, stats while on, archived once when finished
game = {"key": "basketball:sr:match:1", "sport": "basketball", "id": "sr:match:1", "home": "Adelaide 36ers",
        "away": "Melbourne United", "ko": day[0]["kickoff_utc"], "comp": "NBL", "picked": True}
other = {"key": "basketball:sr:match:2", "sport": "basketball", "id": "sr:match:2", "home": "Nowhere Town",
         "away": "Someone Else", "ko": day[0]["kickoff_utc"], "comp": "X", "picked": False}
calls = []


def fetch(feed, eid):
    calls.append((feed, eid))
    return fx("hh_basketball.txt") if feed == "df_hh_1_" else fx("st_basketball.txt")


pre = [{**day[0], "state": "pre", "periods": [], "final": [0, 0]}]
doc, used, arch = mf.update_day("2026-11-12", [game, other], {"basketball": pre}, fetch, NOW)
e = doc["games"]["basketball:sr:match:1"]
assert used == 1 and calls == [("df_hh_1_", "n1FCfmzA")] and e["form"]["home_form"] and "stats" not in e and not arch
assert e["score"] is None and e["state"] == "pre"
assert "pending" in doc["games"]["basketball:sr:match:2"] and "fs_id" not in doc["games"]["basketball:sr:match:2"]
live = [{**day[0], "state": "in"}]
doc, used, arch = mf.update_day("2026-11-12", [game, other], {"basketball": live}, fetch, NOW, doc)
assert used == 1 and calls[-1][0] == "df_st_1_" and doc["games"][game["key"]]["stats"][0]["period"] == "Match" and not arch
done = [{**day[0], "state": "post"}]
doc, used, arch = mf.update_day("2026-11-12", [game, other], {"basketball": done}, fetch, NOW, doc)
assert used == 1 and len(arch) == 1 and arch[0]["stats"]["Match"]["Turnovers"] and arch[0]["sport"] == "basketball"
n = len(calls)
doc, used, arch = mf.update_day("2026-11-12", [game, other], {"basketball": done}, fetch, NOW, doc)
assert used == 0 and len(calls) == n and not arch                          # finished + archived: never read again
assert doc["counts"] == {"games": 2, "matched": 1, "with_stats": 1, "with_form": 1}, doc["counts"]
# no budget: nothing read, nothing lost
d2, used, _ = mf.update_day("2026-11-12", [game], {"basketball": live}, fetch, NOW, None, budget=0)
assert used == 0 and "stats" not in d2["games"][game["key"]]

# which games: every pick, plus a few rated games, from every sport's board; football is not among them
with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    (root / "output" / "ice_hockey").mkdir(parents=True)
    (root / "output" / "multisport" / "tennis").mkdir(parents=True)
    (root / "output" / "picks").mkdir(parents=True)
    (root / "output" / "world_basketball").mkdir(parents=True)
    games = {f"sr:match:{i}": {"home": f"H{i}", "away": f"A{i}", "ko": "2026-11-12T19:00:00Z", "comp": "NHL",
                               "matchbook": i % 2 == 0} for i in range(40)}
    (root / "output" / "ice_hockey" / "ih_2026-11-12.json").write_text(json.dumps(
        {"picks": [{"sb_event_id": "sr:match:39", "home": "H39", "away": "A39", "ko": "2026-11-12T19:00:00Z"}],
         "games": games}))
    (root / "output" / "multisport" / "tennis" / "ms_2026-11-12.json").write_text(json.dumps(
        {"picks": [{"sb_event_id": "t1", "home": "Hewitt, Cruz", "away": "Santillan, Akira", "ko": "2026-11-12T00:00:00Z"}]}))
    (root / "output" / "picks" / "nba_2026-11-12.json").write_text(json.dumps(
        {"picks": [], "study": [{"event_id": "n1", "home": "Indiana Pacers", "away": "Washington Wizards",
                                 "tip": "2026-11-12T00:00:00+00:00"}]}))
    (root / "output" / "picks" / "picks_2026-11-12.json").write_text(json.dumps(
        {"rated": [{"home": "Arsenal", "away": "Chelsea"}]}))
    (root / "output" / "world_basketball" / "wb_2026-11-12.json").write_text(json.dumps(
        {"picks": [{"sb_event_id": "w1", "home": "North Texas", "away": "Santa Clara", "ko": "2026-11-12T01:00:00Z",
                    "comp": "NCAA"}]}))
    bg = mf.board_games("2026-11-12", root)
    by = {}
    for g in bg:
        by.setdefault(g["sport"], []).append(g)
    assert set(by) == {"ice_hockey", "tennis", "basketball"}, set(by)
    assert len(by["ice_hockey"]) == 1 + mf.EXTRA_PER_SPORT and any(g["picked"] for g in by["ice_hockey"])
    assert sum(1 for g in by["ice_hockey"] if not g["picked"] and int(g["id"].split(":")[-1]) % 2 == 0) == mf.EXTRA_PER_SPORT
    assert {g["id"] for g in by["basketball"]} == {"n1", "w1"} and by["basketball"][0]["ko"].endswith("Z")

    # a whole run: writes only output/match_facts and data/match_facts
    before = {p for p in root.rglob("*") if p.is_file()}

    def get(path):
        if path.startswith("f_3_0"):
            return fx("day_basketball.txt")
        if path.startswith("f_"):
            return ""
        return fx("hh_basketball.txt") if path.startswith("df_hh") else fx("st_basketball.txt")
    line = mf.run(NOW, root, get)
    assert line.startswith("match facts: 2026-11-12:"), line
    new = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()} - {p.relative_to(root).as_posix() for p in before}
    assert new and all(p.startswith(("output/match_facts/", "data/match_facts/")) for p in new), new
    out = json.loads((root / "output" / "match_facts" / "mf_2026-11-12.json").read_text())
    assert out["counts"]["games"] == 12 and all("pending" in g or g.get("fs_id") for g in out["games"].values())

print("match_facts_test OK")
