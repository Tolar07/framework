"""engine/records/shadow_kelly.py (to-do #7 idea 6)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.records import shadow_kelly as sk  # noqa: E402


def test_shrinks_with_disagreement():
    agree = sk.record({"chance": 0.62, "sharp_p": 0.61, "price": 1.80})
    apart = sk.record({"chance": 0.62, "sharp_p": 0.55, "price": 1.80})
    assert agree["full"] == apart["full"] > 0
    assert agree["shrunk"] > apart["shrunk"] > 0 and apart["disagree"] == 0.07
    assert sk.record({"chance": 0.62, "sharp_p": 0.45, "price": 1.80})["shrunk"] == 0
    assert sk.record({"chance": 0.50, "sharp_p": 0.60, "price": 1.80})["no_edge"] > 0   # model prefers the other side
    assert sk.record({"chance": 0.4, "price": 1.5})["full"] == 0 and sk.record({})["full"] is None


if __name__ == "__main__":
    test_shrinks_with_disagreement()
    print("records_shadow_kelly_test OK")
