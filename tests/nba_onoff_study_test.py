"""Offline test of backtest/nba_onoff_study.py (#296): walk-forward, no look-ahead, PENDING when empty."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest import nba_onoff_study as st


def game(i, star_out, scorer_pts):
    rows = [{"g": f"g{i}", "d": f"2026-11-{i:02d}", "t": "AAA", "p": "scorer", "n": "S", "m": 20.0, "pts": scorer_pts}]
    for p in ("k1", "k2", "k3"):
        if not (star_out and p == "k1"):
            rows.append({"g": f"g{i}", "d": f"2026-11-{i:02d}", "t": "AAA", "p": p, "n": p, "m": 36.0, "pts": 20})
    return rows


def test_adjustment_uses_only_prior_games():
    log = []
    for i in range(1, 13):
        out = i in (6, 7, 9, 11)
        log += game(i, out, 30 if out else 15)
    recs = [r for r in st.evaluate(log) if r["p"] == "scorer" and r["teammate_out"]]
    adj = [r for r in recs if r["adjusted"]]
    assert adj, "adjustment should apply once two prior games without the teammate exist"
    for r in adj:
        assert abs(r["adj"] - r["actual"]) < abs(r["plain"] - r["actual"])
    first = [r for r in recs if r["g"] == "g6"][0]
    assert not first["adjusted"]          # no prior games without him: no look-ahead


def test_empty_reads_pending():
    s = st.summarise([])
    assert s["all"]["n"] == 0 and "PENDING" in st.render(s, 0)


if __name__ == "__main__":
    test_adjustment_uses_only_prior_games()
    test_empty_reads_pending()
    print("ok")
