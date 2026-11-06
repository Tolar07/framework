"""Betfair check (Architect 2026-11-06): closing price per sport, wins vs prices per market. No network."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from monitor import betfair_check as C  # noqa: E402


def bet(i, sport, mt, won, price=1.30, close=None):
    b = {"code": f"C{i}", "mode": "live", "sport": sport, "market_type": mt, "result": "WON" if won else "LOST",
         "size_matched": 1.0, "avg_price": price, "price": price, "chance": 0.78,
         "pnl": round((price - 1) * 0.95, 2) if won else -1.0}
    if close:
        b["liq_close"] = {"price": close}
    return b


def test_flags_markets_far_below_their_prices_and_negative_clv():
    bets = [bet(i, "football", "DOUBLE_CHANCE", i % 2 == 0) for i in range(36)]          # 18/36 at 1.30
    bets += [bet(100 + i, "tennis", "MATCH_ODDS", True, 1.8, close=1.9) for i in range(25)]  # worse than close
    bets += [bet(200, "tennis", "MATCH_ODDS", True)] + [dict(bet(300, "nba", "X", True), code="G/X")]
    with tempfile.TemporaryDirectory() as t:
        (Path(t) / "paper_2026-11-12.json").write_text(json.dumps({"bets": bets}), encoding="utf-8")
        res = C.check(C.settled(Path(t)))
    assert res["bets"] == 62, "the exit leg (code with /) is not a bet of its own"
    dc = res["markets"]["football|DOUBLE_CHANCE"]
    assert dc["won"] == 18 and dc["exp_price"] == 27.7 and dc["z"] < -3
    assert any("football double chance: won 18 of 36" in f for f in res["flags"])
    assert any(f.startswith("tennis: losing to the closing price (-5.3% on 25 bets)") for f in res["flags"])
    text = "\n".join(C.lines(res))
    assert "nothing is stopped automatically" in text and "⚠" in text


def test_too_few_and_empty():
    res = C.check([bet(1, "darts", "MATCH_ODDS", True, close=1.2)])
    assert not res["flags"] and "CLV too few yet (1 of 20)" in "\n".join(C.lines(res))
    assert C.lines(C.check([])) == ["No settled live Betfair bets yet — PENDING."]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("betfair_check_test: OK")
