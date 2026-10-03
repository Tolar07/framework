"""Ad-hoc check: parse every cached football-data CSV through the new
validation layer and report how many rows survive / are dropped and why."""
import glob
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.football_data_source as fds

total = 0
skipped_total = 0
for f in glob.glob(str(Path(__file__).parent.parent / "data" / "cache" / "*.csv")):
    name = Path(f).name
    league = name.split("_")[0]
    text = Path(f).read_text(encoding="utf-8", errors="replace")
    try:
        results, skipped = fds.parse_csv_text(league, text, season="2526")
    except ValueError as e:
        print(f"{league} ({name}): SCHEMA ERROR {e}")
        continue
    total += len(results)
    skipped_total += len(skipped)
    reasons: dict[str, int] = {}
    for s in skipped:
        r = s["reason"]
        reasons[r] = reasons.get(r, 0) + 1
    if reasons:
        print(f"{league} ({name}): {len(results)} results, {len(skipped)} skipped:")
        for r, n in reasons.items():
            print(f"    {n}x {r}")

print(f"\nTOTAL: {total} results parsed, {skipped_total} rows skipped")
