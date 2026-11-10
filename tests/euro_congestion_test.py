"""European fixtures + congestion inputs (Architect 2026-11-09, step 2): parse, strict match, flags."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest import euro_congestion_study as st  # noqa: E402
from data import euro_fixtures as ef  # noqa: E402

TXT = """= UEFA Champions League 2024/25
▪ League, Matchday 1
  Tue Sep 17 2024
    18:45  BSC Young Boys (SUI)    v Aston Villa FC (ENG)     0-3 (0-2)
           AC Milan (ITA)          v Liverpool FC (ENG)       1-3 (1-2)
  Wed Sep 18
    21:00  Manchester City FC (ENG) v FC Internazionale Milano (ITA)  0-0
  Tue Mar 4
    21:00  PSV (NED)               v Arsenal FC (ENG)         1-7
"""
g = ef.parse(TXT, 2024)
assert [x["date"] for x in g] == ["2024-09-17", "2024-09-17", "2024-09-18", "2025-03-04"], g
assert g[2]["home"] == "Manchester City FC" and g[2]["hc"] == "ENG" and g[0]["home"] == "BSC Young Boys"
clubs = ["Arsenal", "Aston Villa", "Liverpool", "Man City", "Man United"]
assert ef.match_club("Manchester City FC", clubs) == "Man City"
assert ef.match_club("Aston Villa FC", clubs) == "Aston Villa"
assert ef.match_club("Liverpool FC", clubs) == "Liverpool"
assert ef.match_club("Unknown Rovers", clubs) is None, "no match is left out, never guessed"
print("European fixtures: parse dates (year carried), strict club match: OK")

eu = {"Man City": [{"date": "2024-09-18", "comp": "cl", "ko": False}],
      "Arsenal": [{"date": "2025-03-04", "comp": "cl", "ko": True}]}
f = st.features(eu, "Man City", "Arsenal", "2024-09-21")
assert f["euro_before_gap"] == 1 and f["euro_after_gap"] == 0 and f["euro_any"] == 1, f
f = st.features(eu, "Man City", "Arsenal", "2025-03-01")
assert f["euro_after_gap"] == -1 and f["euro_ko_after_gap"] == -1, f
f = st.features(eu, "Man City", "Arsenal", "2024-09-18")
assert f["euro_before_gap"] == 0 and f["euro_after_gap"] == 0, "a game on the same day is neither before nor after"
assert st.features(eu, "Man City", "Arsenal", "2024-12-01")["euro_any"] == 0
print("European congestion flags: before / after / knockout within 4 days: OK")
