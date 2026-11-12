"""
backtest/stat_lines_study.py, framework#601: the ESPN trend claim and the daily paper picks, on a fake ESPN history
and fake graded / pending stat lines in a temp folder. Offline.
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backtest"))
import stat_lines_study as sls  # noqa: E402

OPP = ["Gamma Rovers", "Delta Wanderers", "Epsilon Athletic", "Zeta Albion", "Eta Town", "Theta County"]


def espn(i, date, h, a, hid, aid, ft, corners, cards):
    return {"id": f"e{i}", "date": date, "lid": 1, "league": "Test League", "year": 2026, "hid": hid, "aid": aid,
            "home": h, "away": a, "ft": ft, "corners": corners, "cards": cards, "goals": None, "ht": None}


rows, i = [], 0
for k in range(6):          # Alpha at home: 14 corners and 5 yellows a game; Beta away: the same
    i += 1
    rows.append(espn(i, f"2026-10-{k + 1:02d}T15:00Z", "Alpha United", OPP[k], 10, 20 + k, [1, 0], [8, 6],
                     [[10, 0, "Y"]] * 5))
    i += 1
    rows.append(espn(i, f"2026-10-{k + 1:02d}T17:00Z", OPP[k], "Beta City", 30 + k, 11, [0, 1], [7, 7],
                     [[10, 1, "Y"]] * 5))
# a red-card game must stay out of the yellow trend (cards 9 yellow + 1 red)
i += 1
rows.append(espn(i, "2026-10-08T15:00Z", "Alpha United", "Gamma Rovers", 10, 20, [1, 1], [8, 6],
                 [[5, 0, "Y"]] * 9 + [[6, 0, "R"]]))
target = espn(99, "2026-11-01T15:00Z", "Alpha United", "Beta City", 10, 11, [2, 1], [9, 4], [[3, 0, "Y"]] * 5)
rows.append(target)

# tables / helpers
tab = sls.trend_table([("corners", "10.5"), ("corners", "10"), ("yellow", "4.5")])
assert set(tab) == {"corners over 10.5", "yellow over 4.5"}, set(tab)        # whole line = push, left out
assert sls._yellow_clean({"cards": [[1, 0, "Y"], [2, 1, "R"]]}) is None         # red card: PENDING
assert sls._yellow_clean({"cards": None}) is None and sls._yellow_clean({"cards": [[1, 0, "Y"]]}) == 1.0
assert sls._side(0.7, 0.5, 0.05) == "over" and sls._side(0.3, 0.5, 0.05) == "under" and sls._side(0.52, 0.5, 0.05) is None

with tempfile.TemporaryDirectory() as d:
    root = Path(d)
    (root / "data" / "espn_matches").mkdir(parents=True)
    (root / "data" / "espn_matches" / "2026-10.jsonl").write_text(
        "\n".join(json.dumps(m) for m in rows if m["date"] < "2026-11") + "\n", encoding="utf-8")
    (root / "data" / "espn_matches" / "2026-11.jsonl").write_text(json.dumps(target) + "\n", encoding="utf-8")
    (root / "data" / "world_facts").mkdir(parents=True)
    (root / "data" / "world_facts" / "2026-11.jsonl").write_text(json.dumps(
        {"id": "FS1", "ko": "2026-11-01T15:00Z", "home": "Alpha United", "away": "Beta City", "ft": [2, 1]}) + "\n")
    graded = [{"id": "sr:match:1", "ko": "2026-11-01T15:00Z", "home": "Alpha Utd", "away": "Beta City", "fs_id": "FS1",
               "fs_home": "Alpha United", "fs_away": "Beta City",
               "last": {"lines": {"corners": {"10.5": [1.9, 1.9]}, "bookings": {"4.5": [1.9, 1.9]}}},
               "graded": {"corners": {"10.5": {"over": 1, "under": 0}}, "bookings": {"4.5": {"over": 1, "under": 0}}}}]
    erows = sls.espn_rows(root)
    bets, matched, total = sls.trend_claim(graded, erows, sls._fs_scores(root))
    assert (matched, total) == (1, 1), (matched, total)
    got = {(b["market"], b["side"]): b for b in bets}
    assert ("corners", "over") in got and got[("corners", "over")]["hit"] == 1, bets   # 13 corners > 10.5, trend high
    assert got[("corners", "over")]["p"] > 0.55
    # the target game itself is not in its own history
    assert sls.trend_claim([{**graded[0], "fs_id": "NOPE"}], erows, sls._fs_scores(root))[1] == 0   # no score: PENDING

    # paper picks: a priced game tomorrow, graded after
    (root / "data" / "stat_lines").mkdir(parents=True)
    pend = {"sr:match:2": {"id": "sr:match:2", "ko": "2026-11-13T15:00Z", "home": "Alpha United", "away": "Beta City",
                           "last": {"lines": {"corners": {"10.5": [1.9, 1.9]}, "bookings": {"4.5": [1.9, 1.9]}}}},
            "sr:match:3": {"id": "sr:match:3", "ko": "2026-11-13T15:00Z", "home": "Nobody FC", "away": "Beta City",
                           "last": {"lines": {"corners": {"10.5": [1.9, 1.9]}}}}}
    (root / "data" / "stat_lines" / "pending.json").write_text(json.dumps(pend), encoding="utf-8")
    msg = sls.write_paper(root, erows, [], "2026-11-12")
    picks = json.loads((root / "output/stat_lines/paper_2026-11-12.json").read_text())["picks"]
    assert picks and all(p["id"] == "sr:match:2" for p in picks), picks           # unmatched team: not guessed
    assert {p["market"] for p in picks} >= {"corners"} and all(p["result"] is None for p in picks)
    assert "graded to date 0" in msg, msg
    g = [{"id": "sr:match:2", "graded": {"corners": {"10.5": {"over": 1, "under": 0}},
                                         "bookings": {"4.5": {"over": 0, "under": 1}}}}]
    msg = sls.write_paper(root, erows, g, "2026-11-12")
    picks = json.loads((root / "output/stat_lines/paper_2026-11-12.json").read_text())["picks"]
    assert all(p["result"] is not None for p in picks) and "graded to date" in msg, (picks, msg)

    # the whole study runs end to end and reports PENDING below the bar
    gd = root / "data" / "stat_lines" / "graded"
    gd.mkdir()
    (gd / "2026-11.jsonl").write_text(json.dumps(graded[0]) + "\n", encoding="utf-8")
    out = sls.main(root)
    assert "ESPN trend bets" in out, out
    rep = (root / "output/stat_lines/STAT_LINES_STUDY.md").read_text(encoding="utf-8")
    assert "## 3. The ESPN trend vs the line" in rep and "PENDING (too few)" in rep

# no ESPN data at all: PENDING, no crash
with tempfile.TemporaryDirectory() as d:
    assert sls.trend_claim([], [], {}) == ([], 0, 0)
    assert sls.paper_picks(Path(d), [], "2026-11-12") == []
print("stat_lines_trend_test OK")
