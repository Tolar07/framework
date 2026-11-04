"""
Offline test of the soft-close shadow (engine/soft_close_shadow.py, issue #251 / H003): too few rows
read PENDING, a gap that really predicts Over 2.5 earns a positive out-of-sample gain and a lean in
the right direction, a missing gap gives no shadow chance (HR35), the pre-registered reject rule
fires, and the record is written with recorded_only set.
"""
import json
import random
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from engine import soft_close_shadow as S  # noqa: E402


def synthetic(n_days=40, per_day=10, informative=True, seed=3):
    rng = random.Random(seed)  # noqa: S311 — seeded test data
    rows = []
    for d in range(n_days):
        for _ in range(per_day):
            p = rng.uniform(0.35, 0.65)
            true = min(max(p + rng.uniform(-0.15, 0.15), 0.02), 0.98)
            gap = (true - p) if informative else rng.uniform(-0.15, 0.15)
            y = int(rng.random() < true)
            rows.append((f"2026-09-{1 + d // 2:02d}-{d:03d}", p, y, gap))
    return rows


def test_pending_when_thin():
    rec = S.build(synthetic(1, 5))
    assert rec["verdict"] == "PENDING" and rec["fit"] is None
    assert "PENDING" in S.summary_line(rec)
    assert S.shadow_p(0.5, 0.1, None) is None


def test_informative_gap_gains_and_leans_the_right_way():
    rows = synthetic()
    rec = S.build(rows)
    assert rec["recorded_only"] is True
    assert rec["walk_forward"]["scored"] > 100 and rec["walk_forward"]["gain"] > 0
    fit = S.fit_lean(rows)
    assert S.shadow_p(0.5, 0.15, fit) > 0.5 > S.shadow_p(0.5, -0.15, fit)
    assert S.shadow_p(0.5, None, fit) is None
    assert rec["tagged"]["n"] > 0 and "PENDING" in rec["clv"]


def test_noise_gap_never_promotes():
    rec = S.build(synthetic(informative=False))
    assert not rec["verdict"].startswith("PROMOTION")


def test_reject_rule():
    assert S.verdict({"scored": 1200, "gain": 0.0004, "se": 0.001}).startswith("REJECT")
    assert S.verdict({"scored": 300, "gain": 0.0004, "se": 0.001}) == "KEEP WATCHING"
    assert S.verdict({"scored": 658, "gain": 0.0038, "se": 0.00165}).startswith("PROMOTION")
    assert S.verdict({"scored": 0, "gain": 0.0, "se": 0.0}) == "PENDING"


def test_run_writes_record():
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "rec.json"
        from backtest import features_study as fs
        fs.collect = lambda *a, **k: []          # no graded fixtures: must read PENDING, not crash
        line = S.run(out)
        assert "PENDING" in line
        assert json.loads(out.read_text(encoding="utf-8"))["recorded_only"] is True


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
