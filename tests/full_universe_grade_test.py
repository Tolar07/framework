"""monitor/full_universe_grade.py (#534): every ladder side of a finished game graded; extra time pending; offline."""
import gzip
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from monitor import full_universe_grade as fg  # noqa: E402

lad = {"SB:1||Home": 2.0, "SB:1||Away": 3.0, "SB:18|total=2.5|Over 2.5": 1.8, "SB:18|total=2.5|Under 2.5": 2.0,
       "SB:18|total=3|Under 3": 1.5, "SB:10||Home or Draw": 1.2, "SB:14|hcp=0:1|Home (0:1)": 2.6,
       "SB:16|hcp=-2.5|Away (+2.5)": 1.9, "SB:29||No": 2.1, "SB:999|x=1|Weird": 5.0}
g = {"sport": "football", "id": "sr:match:1", "ko": "2026-11-09T15:00Z", "home": "A", "away": "B",
     "result": {"h": 2, "a": 1, "ht": [1, 0], "after_90": False}, "last": {"p": {"ladder": lad}}}
doc, c = fg.grade_game(g)
s = doc["sides"]
assert s["SB:1||Home"][1] == "w" and s["SB:1||Away"][1] == "l"
assert s["SB:18|total=2.5|Over 2.5"][1] == "w" and s["SB:18|total=2.5|Under 2.5"][1] == "l"
assert s["SB:18|total=3|Under 3"][1] == "v" and s["SB:29||No"][1] == "l" and s["SB:10||Home or Draw"][1] == "w"
assert "SB:999|x=1|Weird" not in s and c["unknown"] == 1, "an unknown market is counted, never guessed"
assert fg.grade_game({**g, "result": {"h": 1, "a": 1, "after_90": True}})[0] is None, "extra time reads PENDING"
assert fg.grade_game({**g, "sport": "basketball"})[0] is None
assert fg.grade_game({**g, "result": None})[0] is None

tmp = Path(tempfile.mkdtemp())
uni = tmp / "u"
uni.mkdir()
with gzip.open(uni / "graded_2026-11-10_0100.jsonl.gz", "wt", encoding="utf-8") as f:
    f.write(json.dumps(g) + "\n")
summ = fg.run("2026-11-01", folder=uni, out_dir=tmp / "full")
assert summ["games"] == 1 and summ["entries"] == 9 and summ["unknown"] == 1 and summ["reject"] is True, summ
out = json.loads(gzip.open(tmp / "full" / "2026-11-09_full.json.gz", "rt", encoding="utf-8").read())
assert out["games"][0]["score"] == [2, 1]
dry = tmp / "dry"
fg.run("2026-11-01", folder=uni, out_dir=dry, dry=True)
assert not dry.exists(), "--dry-run writes nothing"
print("full_universe_grade_test OK")
