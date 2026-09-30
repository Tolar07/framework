"""
Offline tests for data/international_source.py (UEFA Nations League history).
Seeds a fresh cache file so no network is touched. Checks: UEFA-only pool,
neutral-venue matches excluded, pre-window and unplayed (NA) rows handled,
result codes correct, and non-international leagues refused.
"""
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from data import international_source as intl

CSV = """date,home_team,away_team,home_score,away_score,tournament,city,country,neutral
2019-09-06,Germany,Netherlands,2,4,UEFA Euro qualification,Hamburg,Germany,FALSE
2019-09-06,Serbia,Portugal,2,4,UEFA Euro qualification,Belgrade,Serbia,FALSE
2019-09-06,Brazil,Peru,1,0,Friendly,Rio,Brazil,FALSE
2021-06-01,Germany,Serbia,3,0,Friendly,Berlin,Germany,FALSE
2023-03-25,Germany,Serbia,2,1,Friendly,Berlin,Germany,FALSE
2023-06-20,Netherlands,Portugal,1,1,UEFA Nations League,Rotterdam,Netherlands,FALSE
2024-06-20,Germany,Portugal,0,2,UEFA Euro,Munich,Germany,TRUE
2024-09-01,Germany,Brazil,1,1,Friendly,Berlin,Germany,FALSE
2026-10-01,Germany,Serbia,NA,NA,UEFA Nations League,Berlin,Germany,FALSE
"""

with tempfile.TemporaryDirectory() as d:
    (Path(d) / "international_results.csv").write_text(CSV, encoding="utf-8")
    res, skipped, flags = intl.load_results("UEFA Nations League", cache_dir=d)

got = [(r.date, r.home_team, r.away_team, r.fthg, r.ftag, r.ftr) for r in res]
# 2021 row is before HISTORY_SINCE; Euro 2024 row is neutral; Germany v Brazil
# and Brazil v Peru involve a non-UEFA side; the 2026 row is unplayed (NA).
assert got == [("2023-03-25", "Germany", "Serbia", 2, 1, "H"),
               ("2023-06-20", "Netherlands", "Portugal", 1, 1, "D")], got
assert len(skipped) == 1 and skipped[0]["date"] == "2026-10-01", "NA score is skipped, never guessed"
assert all(r.league == "UEFA Nations League" for r in res)
assert any("CLV stays NO DATA" in f for f in flags), "must flag that CLV can't be measured"
print("UEFA-only pool, neutral excluded, window + NA handled: OK")

try:
    intl.load_results("Premier League")
    raise AssertionError("a club league must be refused")
except ValueError:
    pass
print("Non-international league refused: OK")

print("\n✅ ALL INTERNATIONAL SOURCE TESTS PASSED")
