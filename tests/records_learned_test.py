"""engine/records ensemble + drift_alarm (to-do #7 ideas 7 and 9): learned only from earlier boards."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.records import _common, drift_alarm, ensemble  # noqa: E402


def _boards(folder: Path) -> None:
    for d in range(1, 13):
        singles = []
        for i in range(20):      # the sharp market is right (lands 60%), the model says 80%
            singles.append({"market": "SB:18|total=1.5|Over 1.5", "price": 1.6, "chance": 0.8,
                            "sharp_p": 0.6, "result": "won" if i % 5 < 3 else "lost"})
        (folder / f"picks_2026-10-{d:02d}.json").write_text(json.dumps({"singles": singles}), encoding="utf-8")
    (folder / "picks_2026-10-20.json").write_text(json.dumps({"singles": [
        {"market": "SB:18|total=1.5|Over 1.5", "chance": 0.8, "sharp_p": 0.6, "price": 1.6, "result": "lost"}]}),
        encoding="utf-8")


def test_learned_from_the_past_only():
    with tempfile.TemporaryDirectory() as t:
        folder = Path(t)
        _boards(folder)
        rows = _common.graded_singles("2026-10-13", folder)
        assert len(rows) == 240 and all(r["date"] < "2026-10-13" for r in rows)
        w, n = ensemble.fit(rows)
        assert n == 240 and w is not None and w <= 0.1          # the market wins the blend
        assert ensemble.fit(rows[:50]) == (None, 50)
        st = drift_alarm.states(rows)
        fam = next(iter(st.values()))
        assert fam["alarm"] == "down" and fam["up"] < fam["down"]
        orig = _common.PICKS_DIR
        try:
            ensemble.graded_singles = lambda b: _common.graded_singles(b, folder)  # type: ignore[assignment]
            drift_alarm.graded_singles = lambda b: _common.graded_singles(b, folder)  # type: ignore[assignment]
            doc = {"singles": [{"market": "SB:18|total=1.5|Over 1.5", "chance": 0.8, "sharp_p": 0.6}]}
            ensemble.annotate_doc(doc, "2026-10-13")
            drift_alarm.annotate_doc(doc, "2026-10-13")
            b = doc["singles"][0]["blend"]
            assert abs(b["yes"] + b["no"] - 1) < 1e-9 and b["yes"] < 0.7
            assert doc["singles"][0]["drift"]["alarm"] == "down" and doc["drift"]
        finally:
            _common.PICKS_DIR = orig


if __name__ == "__main__":
    test_learned_from_the_past_only()
    print("records_learned_test OK")
