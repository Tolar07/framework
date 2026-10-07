"""
Offline test of the paper book (engine/paper_book.py, backtest/paper_book_study.py):
rules fire on the FIRST price, bets settle from the real result, CLV against
the last price (and none when a basketball line moved), the verdict bar, and
the study written.
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "backtest"))

from engine import paper_book as pb
from engine import universe as uv


def fb(first, last, h, a, covered=False):
    return {"sport": "football", "home": "A", "away": "B", "comp": "X", "covered": covered,
            "first": {"p": first}, "last": {"p": last}, "result": {"h": h, "a": a, "after_90": False}}


g = fb({"1x2": [1.40, 4.5, 7.0], "ou2.5": [1.70, 2.10], "dc": [1.10, 1.25, 2.60]},
       {"1x2": [1.30, 5.0, 9.0], "ou2.5": [1.80, 2.00], "dc": [1.08, 1.20, 2.90]}, 2, 0)
bs = {b["strategy"]: b for b in pb.bets(g)}
assert set(bs) == {"F1 short favourite", "F5 over 2.5 when favoured"}, set(bs)   # dc 1.10 is below 1.20
f1 = bs["F1 short favourite"]
assert f1["price"] == 1.40 and f1["won"] == 1 and abs(f1["pnl"] - 0.40) < 1e-9
assert abs(f1["clv"] - (1.40 / 1.30 - 1)) < 1e-9, "bet at 1.40, it closed 1.30: +7.7% CLV"
assert bs["F5 over 2.5 when favoured"]["won"] == 0, "2-0 is not over 2.5"
assert pb.bets({**g, "result": {"h": 1, "a": 1, "after_90": True}}) == [], "never a 90' bet from extra time"
assert pb.bets({**g, "result": None}) == []
print("rules fire on the first price, settle, CLV vs the last price: OK")

b = {"sport": "basketball", "home": "H", "away": "V", "comp": "NBA", "covered": True,
     "first": {"p": {"win": [1.40, 3.00], "total": [220.5, 1.90, 1.90]}},
     "last": {"p": {"win": [1.35, 3.20], "total": [224.5, 1.90, 1.90]}}, "result": {"h": 110, "a": 100}}
bb = {x["strategy"]: x for x in pb.bets(b)}
assert bb["B1 home favourite"]["won"] == 1 and bb["B3 main total under"]["won"] == 1      # 210 < 220.5
assert bb["B3 main total under"]["clv"] is None, "the line moved 220.5 -> 224.5: no CLV"
print("basketball rules (moved line gives no CLV): OK")

s = pb.Score()
for _ in range(120):                                   # +40% a bet, CLV positive
    s.add({"won": 1, "pnl": 0.40, "clv": 0.02})
assert s.verdict() == "READY TO PROPOSE"
s2 = pb.Score()
for _ in range(50):
    s2.add({"won": 1, "pnl": 0.4, "clv": 0.02})
assert s2.verdict().startswith("learning")
s3 = pb.Score()
for i in range(120):
    s3.add({"won": i % 2, "pnl": 0.9 if i % 2 else -1.0, "clv": -0.01})
assert s3.verdict() in ("no edge shown", "losing — avoid")
print("verdict bar (100+ bets, 2 se, positive CLV): OK")

d = Path(tempfile.mkdtemp())
uv.archive([g, {**g, "covered": True}], d)
import paper_book_study as pbs  # noqa: E402

_orig = uv.load_graded
pbs.uv.load_graded = lambda folder=None: _orig(d)
pbs.OUT = d / "PAPER_BOOK.md"
pbs.main()
txt = pbs.OUT.read_text(encoding="utf-8")
assert "2 graded games so far" in txt and "| F1 short favourite | 1X2 favourite at 1.20–1.50 | 2 | 100% |" in txt
assert "+40.0% / +40.0%" in txt and "**Ready to propose:** none yet" in txt
print("study written: OK")

print("ALL PAPER-BOOK TESTS PASSED")
