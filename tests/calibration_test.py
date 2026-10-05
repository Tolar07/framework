"""BTTS calibration (engine/calibration.py, backtest/BTTS_STUDY.md). Offline."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine import calibration as cal  # noqa: E402


def test_btts_calibration() -> None:
    # the model under-rates BTTS at the low end and over-spreads at the top
    assert abs(cal.btts_yes(0.45) - 0.525) < 0.005
    assert abs(cal.btts_yes(0.75) - 0.661) < 0.005
    assert cal.btts_yes(0.35) > 0.35 and cal.btts_yes(0.75) < 0.75
    # monotonic: a higher raw chance never gives a lower calibrated one
    xs = [i / 100 for i in range(1, 100)]
    ys = [cal.btts_yes(x) for x in xs]
    assert all(b >= a for a, b in zip(ys, ys[1:], strict=False))
    assert cal.btts_yes(None) is None


def test_keys_and_complement() -> None:
    assert cal.is_btts_key("BTTS_YES") is True and cal.is_btts_key("BTTS_NO") is False
    assert cal.is_btts_key("SB:29||Yes") is True and cal.is_btts_key("SB:29||No") is False
    for k in ("OVER_3_5", "DC_1X", "SB:18|total=3.5|Over 3.5", "SB:19|total=1.5|Over 1.5",
              "SB:546||Home/Draw & Yes"):
        assert cal.is_btts_key(k) is None
        assert cal.model_prob(k, 0.6) == 0.6          # other markets unchanged
    yes, no = cal.model_prob("BTTS_YES", 0.45), cal.model_prob("BTTS_NO", 0.55)
    assert abs(yes + no - 1) < 1e-9                    # yes and no still add to 1
    assert cal.model_prob("SB:29||Yes", 0.45) == yes
    assert cal.model_prob("BTTS_YES", None) is None


def test_goals_lines() -> None:
    # the model under-rates goals: a 50% Over 2.5 becomes ~53%
    assert abs(cal.model_prob("OVER_2_5", 0.5) - 0.532) < 0.002
    for line, raw in ((1.5, 0.75), (2.5, 0.5)):
        o = cal.model_prob(f"SB:18|total={line}|Over {line}", raw)
        u = cal.model_prob(f"SB:18|total={line}|Under {line}", 1 - raw)
        assert abs(o + u - 1) < 1e-9 and o == cal.over(line, raw)
    assert cal.model_prob("UNDER_1_5", 0.25) == 1 - cal.over(1.5, 0.75)
    assert cal.goals_key("SB:18|total=3.5|Over 3.5") is None
    assert cal.over(3.5, 0.3) == 0.3


if __name__ == "__main__":
    test_goals_lines()
    test_btts_calibration()
    test_keys_and_complement()
    print("BTTS calibration: OK")
