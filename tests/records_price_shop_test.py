"""engine/records/price_shop.py (to-do #7 idea 10)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.records import price_shop as ps  # noqa: E402


def test_best_book_both_sides():
    r = ps.record({"price": 1.90, "sharp_p": 0.50})
    assert r["best"] == "matchbook" and r["mb_price"] == 1.98 and r["sb_edge"] < 0 and r["no_mb_price"] == 1.98
    assert ps.record({"price": 2.10, "sharp_p": 0.50})["best"] == "sportybet"
    assert ps.record({"price": 2.1}) is None and ps.record({"price": 2.1, "sharp_p": 1.0}) is None


if __name__ == "__main__":
    test_best_book_both_sides()
    print("records_price_shop_test OK")
