"""News move (Architect 2026-11-09 plan, step 4): prices stamped at confirmed lineups, scored on the edge scoreboard."""
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine import edge_book as eb  # noqa: E402
from monitor import edge_scoreboard as sb  # noqa: E402

now = datetime(2026, 11, 10, 18, 0, tzinfo=UTC)
ev = {"sport": "football", "home": "Arsenal", "away": "Chelsea", "ko": "2026-11-10T19:30:00Z",
      "k": {"SB:1||Home": {"s0": 2.1, "p0": 0.47, "s1": 2.1, "p1": 0.48},
            "SB:1||Away": {"s0": 3.6, "p0": 0.27, "s1": 3.6, "p1": 0.26}}}
docs = {"2026-11-10": {"day": "2026-11-10", "events": {"e1": ev}}}
news = {"Arsenal v Chelsea": {"lineup_type": "predicted", "home_missing_share": 0.0, "away_missing_share": 0.2}}
assert eb.mark_news(docs, news, now) == 0, "a predicted lineup is not the news"
news["Arsenal v Chelsea"]["lineup_type"] = "confirmed"
assert eb.mark_news(docs, news, now) == 1
c = ev["k"]["SB:1||Home"]["c"]
assert c["s"] == 2.1 and c["p"] == 0.48 and c["me"] == 0.2 and c["h"] == 1.5, c
assert eb.mark_news(docs, news, now) == 0, "stamped once: the first confirmed look only"
late = datetime(2026, 11, 10, 20, 0, tzinfo=UTC)
ev2 = {"sport": "football", "home": "Arsenal", "away": "Chelsea", "ko": "2026-11-10T19:30:00Z",
       "k": {"SB:1||Home": {"s1": 2.0, "p1": 0.5}}}
assert eb.mark_news({"d": {"events": {"e": ev2}}}, news, late) == 0, "nothing after kick-off"
print("news move: stamped at the first confirmed lineup, once, before kick-off only: OK")

ev["k"]["SB:1||Home"]["p1"] = 0.52           # the exchange close moved toward the side the lineups favoured
obs = {"2026-11-10": docs["2026-11-10"]}
res = {"e1": {"SB:1||Home": 1, "SB:1||Away": 0}}
orig = sb._won
sb._won = lambda results, eid, key: results.get(eid, {}).get(key)
try:
    out = sb.collect(obs, res, picks_dir=Path("/nonexistent"))
finally:
    sb._won = orig
g = {x["name"]: x for x in out["groups"]}
fav = g["news move: side the lineups favour (missing edge 10%+)"]
assert fav["n"] == 1 and fav["clv"] > 0, fav       # 2.1 x 0.52 - 1 = +9.2%
assert g["news move: every side at confirmed lineups"]["n"] == 2
print("news move groups on the edge scoreboard (favoured side, every side, over the exchange): OK")
