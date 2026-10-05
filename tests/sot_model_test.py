"""Shots-on-target rating (engine/sot_model.py). Offline."""
from __future__ import annotations

import csv
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine import sot_model  # noqa: E402


def test_rows_and_ratings() -> None:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "X_2526.csv"
        with open(p, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "HST", "AST"])
            for i in range(60):
                day = f"{1 + i % 28:02d}/0{1 + i // 28}/2026"
                # Strong creates 8 shots on target a game, Weak 2
                w.writerow([day, "Strong", "Weak", 2, 0, 8, 2])
                w.writerow([day, "Weak", "Strong", 0, 1, 2, 8])
            w.writerow(["05/01/2026", "Strong", "Weak", 1, 0, "", 3])   # no HST: skipped
        rows = sot_model.rows_from_csv([p, Path(d) / "missing.csv"])
        assert len(rows) == 120 and all(r["hst"] is not None for r in rows)
        sr = sot_model.ratings_from_rows(rows, "2026-12-31")
        m = sr.matrix("Strong", "Weak")
        import numpy as np
        assert abs(m.sum() - 1) < 1e-9 and np.tril(m, -1).sum() > 0.6, "more shots, more wins"
        assert sot_model.ratings_from_rows(rows[:10], "2026-12-31") is None, "too few: no rating"
    assert {"Championship", "Eredivisie"} <= sot_model.SOT_LEAGUES


if __name__ == "__main__":
    test_rows_and_ratings()
    print("shots-on-target rating: OK")
