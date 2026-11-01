"""No forced picks + short 3-leg slips (Architect 2026-11-01, plan point 3)."""
import sys
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from engine import short_legs as sl  # noqa: E402

q = lambda p: NS(price=p)  # noqa: E731
assert sl.is_short_price(1.15) and not sl.is_short_price(1.20) and not sl.is_short_price(1.03)

# option 1: the safest outcome is Over 1.5 @1.12 (90%); the fallbacks need 5 pts over break-even
short = [(0.90, "SB:18|total=1.5|Over 1.5", 1.12)]
cands = [(0.86, 0.0, "SB:18|total=4.5|Under 4.5", 0.86, 0.85, q(1.22)),   # 0.86 - 0.820 = 4.0 pts: out
         (0.80, 0.0, "SB:10||Home or Away", 0.80, 0.78, q(1.33))]         # 0.80 - 0.752 = 4.8 pts: out
assert sl.safest_is_short(short, cands)
assert sl.with_edge(cands) == []
good = (0.88, 0.0, "SB:16|hcp=-0.5|Home (-0.5)", 0.88, 0.80, q(1.25))      # 0.88 - 0.80 = 8 pts: kept
assert sl.with_edge(cands + [good]) == [good]
assert not sl.safest_is_short([(0.80, "x", 1.10)], cands), "a short leg weaker than the pick: no gate"

# option 3: three short legs in one window -> one slip, odds >= 1.30
def bf(i, ch, price, ko="2026-11-02T15:00:00Z"):
    return NS(fixture=f"H{i} v A{i} (Serie A)", probs=NS(home_team=f"H{i}", away_team=f"A{i}"),
              kickoff_utc=ko, kickoff_date="2026-11-02",
              short_legs=[(ch, "SB:18|total=1.5|Over 1.5", price), (0.70, "SB:18|total=0.5|Over 0.5", 1.06)])
board = [bf(0, 0.95, 1.12), bf(1, 0.94, 1.10), bf(2, 0.93, 1.11), bf(3, 0.84, 1.10),   # 3: under LEG_MIN
         bf(4, 0.95, 1.18, ko="2026-11-02T20:00:00Z")]                                 # alone in its window
slips = sl.build(board)
assert len(slips) == 1, slips
name, legs, chance = slips[0]
assert name == "Short-3 #1" and [l[0].fixture[:2] for l in legs] == ["H0", "H1", "H2"]
odds = legs[0][4] * legs[1][4] * legs[2][4]
assert odds >= sl.SLIP_MIN_ODDS and abs(chance - 0.95 * 0.94 * 0.93) < 1e-9
assert all(l[3] == "SB:18|total=1.5|Over 1.5" for l in legs)
src = (ROOT / "run_daily.py").read_text(encoding="utf-8")
assert "sl.safest_is_short" in src and "sl.with_edge" in src and 'extra_codes["short3"]' in src
led = (ROOT / "engine" / "picks_ledger.py").read_text(encoding="utf-8")
assert '"short3": list(' in led and 'doc.get("short3", [])' in led
print("short_legs_test: OK")
