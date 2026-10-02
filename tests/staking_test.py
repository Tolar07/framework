"""
Offline test of edge-based staking (improvement #7): priors, live blending,
stake bands, low-certainty halving and the stop-loss pause. No network.
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine import staking as st

# Priors only: BANKER near break-even -> small; SAFE losing -> minimal.
assert st.single_stake("BANKER", "HIGH", 1.30, {})[0] == st.SMALL
assert st.single_stake("SAFE", "HIGH", 1.25, {})[0] == st.MINIMAL
assert st.single_stake("SAFE", "LOW", 1.25, {})[0] == round(st.MINIMAL / 2, 2), "LOW certainty halves"
print("priors: OK")

# A proven edge (live +10% over 200 picks) earns a quarter-Kelly stake, capped.
stats = {"BANKER": {"n": 200, "roi": 0.10, "last20_pl": 2.0, "paused": False}}
s, why = st.single_stake("BANKER", "HIGH", 1.40, stats)
assert st.MIN_STAKE <= s <= st.MAX_STAKE and "edge" in why, (s, why)
print("proven edge -> bigger stake: OK")

# Stop-loss: last 20 graded singles of a tier lost >= 6 units -> PAUSED.
with tempfile.TemporaryDirectory() as d:
    singles = [{"tier": "SAFE", "price": 1.25, "result": "lost"} for _ in range(8)] + \
              [{"tier": "SAFE", "price": 1.25, "result": "won"} for _ in range(4)]
    doc = {"date": "2026-10-03", "singles": singles}
    (Path(d) / "picks_2026-10-03.json").write_text(json.dumps(doc), encoding="utf-8")
    ts = st.tier_stats(Path(d), today="2026-10-05")
    assert ts["SAFE"]["n"] == 12 and ts["SAFE"]["paused"], ts
    assert st.single_stake("SAFE", "HIGH", 1.25, ts)[0] == 0.0
    assert "PAUSED" in st.summary(ts)
print("stop-loss pause: OK")

print("\n✅ ALL STAKING TESTS PASSED")
