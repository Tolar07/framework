"""Candidate inputs (2026-10-28): H2H venue-aware + time-decayed, form split, xG form — no leakage."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest import inputs_study as st  # noqa: E402
from engine import inputs as ip  # noqa: E402

ms = [{"date": "2020-01-01", "home": "A", "away": "B", "hg": 0, "ag": 3},   # old, same venue
      {"date": "2025-09-01", "home": "B", "away": "A", "hg": 1, "ag": 1},   # reverse venue
      {"date": "2026-03-01", "home": "A", "away": "B", "hg": 2, "ag": 0},   # recent, same venue
      {"date": "2026-10-28", "home": "A", "away": "B", "hg": 9, "ag": 0}]   # the day itself: never read
H = ip.History(ms)
h = ip.h2h(H, "A", "B", "2026-10-28")
assert h["n"] == 2 and 0 < h["gd"] < 2, h   # 2020 is past H2H_MAX_YEARS; the 2-0 at home outweighs the away draw
assert ip.h2h(H, "A", "B", "2020-01-01") is None, "nothing before the first meeting"
assert ip.h2h(H, "A", "B", "2025-12-01")["n"] == 2, "within six years the 2020 meeting counts"
assert ip.h2h(H, "A", "C", "2026-10-28") is None
for i, (hg, ag) in enumerate([(2, 0), (1, 1), (0, 1), (3, 0), (2, 2), (1, 0), (0, 0)]):
    ms.append({"date": f"2026-0{1 + i % 8}-1{i}", "home": "A" if i % 2 == 0 else "C",
               "away": "C" if i % 2 == 0 else "A", "hg": hg, "ag": ag})
H = ip.History(ms)
f = ip.form(H, "A", "2026-10-01")
assert f and f["n"] == 6, f
assert ip.form(H, "A", "2026-10-01", "home")["n"] >= 3
assert ip.fixture_features(H, "A", "B", "2026-10-28")["h2h_gd"] is not None
print("h2h venue-aware + decayed, form split, before-the-day only: OK")

rows = [(f"2026-01-{1 + i // 10:02d}", 0.5, i % 2, float(i % 2), None) for i in range(400)]
s, scored = st.wf_preds(rows)
assert s["brier_gain"] > 0 and s["verdict"] == "ADDS INFORMATION", s
assert all(d > "2026-01-01" for d, *_ in scored), "the first days only train"
noise = [(f"2026-01-{1 + i // 10:02d}", 0.5, i % 2, float((i * 7) % 3), None) for i in range(400)]
assert st.wf_preds(noise)[0]["verdict"] != "ADDS INFORMATION"
print("walk-forward input test: a real signal passes, noise does not: OK")
