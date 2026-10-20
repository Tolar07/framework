"""scripts/weekly_review.py — the NBA section (Architect 2026-10-20: NBA treated as football)."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts import weekly_review as W  # noqa: E402


def _p(mid: str, res: str | None, price: float = 2.0, stage: str = "regular") -> dict:
    return {"market_id": mid, "price": price, "result": res, "stage": stage, "close_value": 0.04}


with tempfile.TemporaryDirectory() as d:
    p = Path(d)
    (p / "nba_2026-10-21.json").write_text(json.dumps({"date": "2026-10-21", "picks": [
        _p("68", "won"), _p("68", "lost"), _p("219", "won", 2.5), _p("219", None), _p("225", "won", 1.9, "preseason")]}))
    (p / "nba_2026-10-01.json").write_text(json.dumps({"date": "2026-10-01", "picks": [_p("68", "won")]}))
    sec = W.nba_section(7, "2026-10-22", p)
    assert sec[0].startswith("*NBA board*")
    assert sec[1] == "  All NBA picks: 2/3 won, flat return +50.0%, value v closing line +4.0%", sec[1]
    assert "  NBA 1st half total: 1/2 won, flat return +0.0%, value v closing line +4.0%" in sec
    assert any(x.startswith("  Gemini on NBA:") for x in sec)
    assert W.nba_section(7, "2026-10-30", p)[1].startswith("  no graded regular-season NBA pick")
    # a week with no graded football single still reports the NBA board
    assert "*NBA board*" in W.review(7, "2026-10-22", p)

print("weekly_review_nba_test: OK")
