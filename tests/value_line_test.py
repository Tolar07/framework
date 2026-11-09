"""Value line (Architect 2026-11-09 plan, step 6): 30-day ROI + CLV of board singles, not hit rate."""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from monitor import value_line as vl  # noqa: E402

with tempfile.TemporaryDirectory() as tmp:
    d = Path(tmp)
    singles = [{"market": "SB:10||Home or Draw", "price": 1.25, "result": "won", "home": "A", "away": "B"}] * 8 \
        + [{"market": "SB:10||Home or Draw", "price": 1.25, "result": "lost", "home": "A", "away": "B"}] * 2
    (d / "picks_2026-11-01.json").write_text(json.dumps({"singles": singles}), encoding="utf-8")
    (d / "picks_2026-09-01.json").write_text(json.dumps({"singles": singles}), encoding="utf-8")   # outside 30 days
    out = vl.build("2026-11-09", picks_dir=d, obs={})
    a = out["groups"]["all"]
    assert a["n"] == 10 and a["hit"] == 0.8 and a["roi"] == 0.0, a      # 80% won at 1.25 = break-even
    assert "judged by price, not hit rate" in out["report_line"] and "CLV PENDING" in out["report_line"]
    assert "Double chance" in out["report_line"], out["report_line"]
    empty = vl.build("2026-11-09", picks_dir=d / "none", obs={})
    assert "PENDING" in empty["report_line"]
print("value line: 30-day window, ROI not hit rate, CLV PENDING without a close: OK")
