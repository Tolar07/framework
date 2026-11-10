"""Edge bucket study (framework #533): buckets by price, walk-forward halves, PENDING with no data."""
import random
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backtest"))

import edge_bucket_study as eb  # noqa: E402

assert any("PENDING" in x for x in eb.report([])), "no data reads PENDING"
assert [eb.bucket_of(p) for p in (1.2, 1.5, 1.99, 2.0, 3.5, 5.0, 9)] == \
    ["<1.5", "1.5-2.0", "1.5-2.0", "2.0-3.0", "3.0-5.0", "5.0+", "5.0+"]

random.seed(2)


def mk(day, win_p, price):
    return {"date": f"2026-10-{day:02d}", "chance": 0.55, "price": price, "won": int(random.random() < win_p)}


# a 3.0-5.0 bucket that truly wins 40% at price 3.5 (ROI +40%) in both halves; 1.5-2.0 is fair
recs = [mk(d, 0.40, 3.5) for d in range(1, 21) for _ in range(10)]
recs += [mk(d, 0.55, 1 / 0.55) for d in range(1, 21) for _ in range(10)]
res = eb.analyse(recs)
assert res["verdict"].startswith("VALID") and "3.0-5.0" in res["valid_buckets"], res["verdict"]
assert res["train_days"] == 10 and res["test_days"] == 10, "time-ordered halves, no overlap"
tr, te = eb.split(recs)
assert max(r["date"] for r in tr) < min(r["date"] for r in te), "no look-ahead"

# an edge that exists only in the train half is NOT valid (the test half is what counts)
late_fail = [mk(d, 0.60 if d <= 10 else 0.20, 3.5) for d in range(1, 21) for _ in range(10)]
assert not eb.analyse(late_fail)["valid_buckets"], "train-only edge is not valid"

# fair-priced sides only -> nothing actionable
fair = [{**mk(d, 0, 1 / 0.55), "won": int(i < 11)} for d in range(1, 21) for i in range(20)]
assert not eb.analyse(fair)["valid_buckets"]
print("edge_bucket_study_test: OK")
