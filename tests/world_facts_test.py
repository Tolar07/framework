"""
engine/world_facts.py: every finished football match with its half-time score, team stats by half and goal minutes.
Offline: real feed text saved on 2026-11-12 (tests/fixtures/world_facts/), no network. Also checks that a run
writes only its own folders and never archives a match twice.
"""
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import world_facts as wf  # noqa: E402

FX = Path(__file__).parent / "fixtures" / "world_facts"
NOW = datetime(2026, 11, 12, 18, 0, tzinfo=timezone.utc)


def fx(name):
    return (FX / name).read_text(encoding="utf-8")


day = wf.parse_day(fx("day.txt"))
by = {m["home"]: m for m in day}
# the abandoned match in the fixture (stage 4) is not a result and is left out
assert set(by) == {"Instituto", "Altach U21", "Brighton"}, set(by)
assert by["Instituto"]["ft"] == [2, 2] and by["Instituto"]["ht"] == [1, 0]
assert by["Brighton"]["ft"] == [2, 0] and by["Brighton"]["ht"] == [2, 0]
assert by["Altach U21"]["ht"] == [0, 2] and by["Altach U21"]["league"] == "AUSTRIA: Regionalliga West"

# goal minutes: in order, added time kept apart, and they agree with the half-time score
goals = wf.parse_goals(fx("arg_incidents.txt"), [2, 2])
assert goals == [[7, 0, "h"], [66, 0, "a"], [79, 0, "a"], [90, 3, "h"]], goals
assert sum(1 for g in goals if g[0] <= 45 and g[2] == "h") == by["Instituto"]["ht"][0]
assert wf.parse_goals(fx("eng_incidents.txt"), [2, 0]) == [[15, 0, "h"], [42, 0, "h"]]
# a part list is never kept: goals that do not add up to the score read None (HR35)
assert wf.parse_goals(fx("arg_incidents.txt"), [3, 2]) is None
assert wf.parse_goals(fx("small_incidents.txt"), [0, 3]) is None
assert wf.parse_goals("", [0, 0]) == []

# team stats for the match and each half; a stat repeated in the tab is taken once
st = wf.parse_stats(fx("arg_stats.txt"))
assert set(st) == {"match", "h1", "h2"}, set(st)
assert st["match"]["corners"] == [1.0, 3.0] and st["h1"]["corners"] == [0.0, 2.0] and st["h2"]["corners"] == [1.0, 1.0]
assert st["match"]["xg"] == [1.44, 1.02] and st["match"]["poss"] == [50.0, 50.0]
assert wf.parse_stats(fx("eng_stats.txt"))["h1"]["red"] == [0.0, 1.0]
assert wf.parse_stats(fx("small_stats.txt")) is None

row = wf.detail_row(by["Altach U21"], fx("small_stats.txt"), fx("small_incidents.txt"))
assert row["stats"] is None and row["goals"] is None and row["ft"] == [0, 3]

# a whole run, twice: writes only its own folders, archives each match once, reads detail once
with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    calls = []

    def get(path):
        calls.append(path)
        if path.startswith("f_1_-1"):
            return fx("day.txt")
        if path.startswith("f_"):
            return ""
        key = {"vo2HLBqC": "arg", "M109CYgU": "eng", "d4YzCh3d": "small"}[path.split("_")[-1]]
        return fx(f"{key}_stats.txt") if path.startswith("df_st") else fx(f"{key}_incidents.txt")

    line = wf.run(NOW, root, get)
    assert line.startswith("world facts: 3 finished matches in the feeds, 3 new archived (3 with half-time); "
                           "detail read for 3 (2 with stats, 2 with goal minutes), 0 still to read"), line
    files = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    assert files == {"data/world_facts/2026-11.jsonl", "data/world_facts_detail/2026-11.jsonl",
                     "output/world_facts/latest.json"}, files
    n_calls = len(calls)
    line2 = wf.run(NOW, root, get)
    assert "0 new archived" in line2 and "detail read for 0" in line2, line2
    assert len(calls) == n_calls + len(wf.DAYS_BACK), "the second run reads the day feeds only"
    base = [json.loads(x) for x in (root / "data" / "world_facts" / "2026-11.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(base) == 3 and len({r["id"] for r in base}) == 3
    doc = json.loads((root / "output" / "world_facts" / "latest.json").read_text())
    assert (doc["matches"], doc["with_half_time"], doc["competitions"], doc["with_corners"], doc["with_goal_minutes"]) == (3, 3, 3, 2, 2), doc

    # one polite pass: the per-run limit is kept and the rest waits for the next run
    root2 = Path(tmp) / "second"
    line3 = wf.run(NOW, root2, get, detail_per_run=1)
    assert "detail read for 1" in line3 and "2 still to read" in line3, line3

print("world_facts_test OK")
