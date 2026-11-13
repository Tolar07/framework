"""Offline test of backtest/nba_secondary_value.py (framework #569). No network."""
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "backtest")]

import nba_secondary_value as sv  # noqa: E402

sharp = {"ml_home": 1.5, "ml_away": 2.6, "spread": -5.5, "total": 226.5}


def look(at, o, u, event="e1"):
    return {"event_id": event, "at": at, "tip": "2026-10-14T00:00:00Z", "sharp": sharp,
            "markets": [{"id": "225", "spec": "total=226.5", "open": True,
                         "outcomes": [["Over 226.5", o], ["Under 226.5", u]]}]}


first, last = look("2026-10-13T18:00:00Z", 2.10, 1.75), look("2026-10-13T23:50:00Z", 1.95, 1.90)
late = look("2026-10-14T00:20:00Z", 1.0, 1.0)
assert sv.first_looks([last, late, first])[0]["at"] == first["at"], "first look BEFORE tip-off"
game = SimpleNamespace(hs=120, as_=110, q_home=[30, 30, 30, 30], q_away=[28, 27, 28, 27])   # total 230: over
b = sv.bets(first, last, game)
over = next(x for x in b if x["price"] == 2.10)
assert over["won"] == 1 and over["clv"] is not None and over["clv"] > 0, "beat the close: positive CLV"
assert all(1.60 <= x["price"] <= 2.60 for x in b)
assert sv.bets({**first, "sharp": {}}, last, game) == [], "no sharp line: nothing priced (PENDING)"
assert abs(sv._stats([{"price": 2.0, "p": .5, "won": 1, "clv": None}])["ret"] - 1.0) < 1e-9
assert sv.status({"n": 10}).startswith("COLLECTING (10 of 200")
assert sv.status({"n": 300, "ret": 0.2, "se": 0.05}).startswith("FOR THE ARCHITECT")
assert sv.status({"n": 300, "ret": -0.1, "se": 0.05}) == "no steady edge"
text = sv.build([first, last], {"e1": game})
assert "Games graded: 1" in text and "Total points (incl. OT)" in text, text
assert "NO DATA — PENDING" in sv.build([], {}), "no graded game: PENDING"
print("nba secondary value: OK")
