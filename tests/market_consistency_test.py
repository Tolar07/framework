"""engine/market_consistency.py — joint grid recovers the rates, flags a soft side, keeps both sides."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine import market_consistency as xm  # noqa: E402


def _book(lh: float, la: float, rho: float = -0.05, margin: float = 1.05) -> dict:
    m = xm.grid(lh, la, rho)
    price = lambda q: round(1 / (q * margin), 3)  # noqa: E731
    h, d, a = (xm._stat(m, n) for n in ("home", "draw", "away"))
    p = {"1x2": [price(h), price(d), price(a)]}
    for line in xm.OU_LINES:
        o = xm._stat(m, f"over{line}")
        p[f"ou{line}"] = [price(o), price(1 - o)]
    bt = xm._stat(m, "btts")
    p["btts"] = [price(bt), price(1 - bt)]
    p["dc"] = [price(h + d), price(h + a), price(d + a)]
    return p


def test_recovers_rates():
    f = xm.fit(_book(1.7, 0.9))
    assert f is not None
    assert abs(f["lh"] - 1.7) < 0.05 and abs(f["la"] - 0.9) < 0.05, f
    assert f["rmse"] < 0.005


def test_soft_side_and_its_other_side():
    p = _book(1.5, 1.2)
    fair_over = p["ou2.5"][0]
    p["ou2.5"][0] = round(fair_over * 1.12, 3)       # one soft line, the rest consistent
    s = xm.summary(p)
    over, under = s["sides"]["ou2.5:over"], s["sides"]["ou2.5:under"]
    assert over[2] > 0.03, over                     # soft vs the book's own other markets
    assert under[2] < 0, under                      # its other side is recorded and is not
    assert all(v[2] < 0.01 for k, v in s["sides"].items() if not k.startswith("ou2.5")), s["sides"]
    assert set(s["sides"]) >= {"1x2:home", "1x2:draw", "1x2:away", "btts:yes", "btts:no", "dc:12"}


def test_ladder_keeps_whole_line():
    p = _book(1.4, 1.1)
    p["ladder"] = {"SB:16|hcp=-1.5|Home (-1.5)": 9.0, "SB:16|hcp=-1.5|Away (+1.5)": 1.05,
                   "SB:18|total=4.5|Over 4.5": 1.5, "SB:18|total=4.5|Under 4.5": 1.01}
    lad = xm.summary(p)["ladder"]
    assert "SB:16|hcp=-1.5|Home (-1.5)" in lad and "SB:16|hcp=-1.5|Away (+1.5)" in lad
    assert lad["SB:16|hcp=-1.5|Home (-1.5)"][2] > 0 > lad["SB:16|hcp=-1.5|Away (+1.5)"][2]
    assert not any(k.startswith("SB:18|total=4.5") for k in lad) or \
        max(lad[k][2] for k in lad if k.startswith("SB:18")) > 0


def test_missing_markets_and_attach():
    assert xm.fit({"1x2": [2.0, 3.4, 3.6]}) is None          # no goals market -> no fit
    assert xm.summary(None) is None
    rows = [{"sport": "football", "first": {"p": _book(1.3, 1.0)}, "last": {"p": {}}},
            {"sport": "basketball", "first": {"p": {"win": [1.5, 2.5]}}},
            {"sport": "football", "first": {"p": {"1x2": ["x", 0, None]}}}]
    assert xm.attach(rows) == "consistency recorded 1"
    assert rows[0]["xm"]["first"]["sides"] and rows[0]["xm"]["last"] is None
    assert "xm" not in rows[1] and "xm" not in rows[2]
    assert xm.side_of(rows[0]["xm"]["first"], "1x2:home") is not None


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("market_consistency_test OK")
