"""engine/records package + timing (to-do #7 idea 3)."""
from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine import records  # noqa: E402
from engine.records import timing as tm  # noqa: E402

W = datetime(2026, 10, 28, 12, 0, tzinfo=UTC)


def test_signals():
    base = {"kickoff_utc": "2026-10-28T15:00Z", "first_price": 1.80}
    s = tm.timing({**base, "price": 1.70, "sharp_p": 0.62}, W)
    assert s["signal"] == "steam" and s["hours_to_ko"] == 3.0 and not s["after_lineups"]
    assert s["yes"] > 0 > s["no"]
    assert tm.timing({**base, "price": 1.90, "sharp_p": 0.56}, W)["signal"] == "rlm"
    assert tm.timing({**base, "price": 1.90, "sharp_p": 0.50}, W)["signal"] == "fade"
    assert tm.timing({**base, "price": 1.80, "sharp_p": 0.60}, W)["signal"] is None
    lu = tm.timing({**base, "kickoff_utc": "2026-10-28T12:45Z", "price": 1.8}, W)
    assert lu["after_lineups"] and lu["sharp_gap"] is None and lu["signal"] is None


def test_package_runs_every_module_and_never_raises():
    doc = {"generated_at": "2026-10-28T12:00:00Z",
           "singles": [{"price": 1.7, "first_price": 1.8, "sharp_p": 0.62, "kickoff_utc": "2026-10-28T15:00Z"}],
           "study": [{"price": "bad"}]}
    notes = records.annotate_doc(doc, "2026-10-28")
    assert any(n.startswith("timing: timing 2") for n in notes), notes
    assert doc["singles"][0]["timing"]["signal"] == "steam"
    assert doc["study"][0]["timing"]["sb_move"] is None
    assert isinstance(records.annotate_doc({}, "2026-10-28"), list)


if __name__ == "__main__":
    test_signals()
    test_package_runs_every_module_and_never_raises()
    print("records_timing_test OK")
