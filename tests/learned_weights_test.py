"""engine/learned_weights.py — step 3 of the bot-training plan (2026-11-01). Recorded only."""
from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine import learned_weights as LW  # noqa: E402


def _hist(n: int, member_good: bool, seed: int = 7) -> list[dict]:
    """Rows where the truth is the anchor shifted by a hidden factor that only 'nvidia' sees."""
    rnd = random.Random(seed)
    out = []
    for i in range(n):
        a = rnd.uniform(0.35, 0.8)
        hidden = rnd.choice([-0.15, 0.15])
        truth = min(max(a + hidden, 0.02), 0.98)
        won = rnd.random() < truth
        nv = truth if member_good else min(max(a - hidden, 0.02), 0.98)
        day = f"2026-10-{1 + i // 20:02d}"
        out.append({"id": f"football|{day}|T{i} v U{i}|SB:1||Home|board", "date": day, "anchor": a,
                    "members": {"nvidia": nv}, "won": won, "stage": "board", "panel_prob": a})
    return out


def test_thin_record_keeps_every_weight_at_zero():
    r = LW.build(_hist(10, True), {})
    assert r["weights"] == {} and r["walk_forward"]["n"] == 0
    assert "stays 0" in LW.summary_line(r)


def test_a_member_that_sees_the_truth_earns_weight_and_beats_the_market():
    r = LW.build(_hist(400, True), {})
    assert r["weights"]["member:nvidia"]["w"] > 0.3
    assert r["walk_forward"]["beats_market"] is True
    assert r["walk_forward"]["learned_brier"] < r["walk_forward"]["market_brier"]


def test_a_member_that_points_the_wrong_way_gets_negative_or_no_weight():
    r = LW.build(_hist(400, False), {})
    assert r["weights"]["member:nvidia"]["w"] < 0.05


def test_facts_are_joined_by_date_fixture_market():
    h = _hist(60, True)
    facts = {("2026-10-01", "T0 v U0", "SB:1||Home"): {"key_absences": -0.6}}
    rs = LW.rows(h, facts)
    assert rs[0]["facts"] == {"key_absences": -0.6}
    assert LW._split_id("football|2026-10-01|A v B|SB:18|total=2.5|Over 2.5|board")[3] == "SB:18|total=2.5|Over 2.5"


def main() -> None:
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("learned_weights_test OK")


if __name__ == "__main__":
    main()
