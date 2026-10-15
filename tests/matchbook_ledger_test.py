"""
The Matchbook evidence summary: right counts and CLV, and nothing private.

This repo is public; the agent's ledger holds stakes, £ P&L, offer and
lineage ids. The summary must carry counts and rates only.
"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from monitor import matchbook_ledger as ml  # noqa: E402

ROWS = [
    {"status": "WON", "source": "framework", "fw_pool": False, "market_name": "Total", "oracle_p": 0.6,
     "avg_odds": 2.1, "close_back": 2.0, "cost_gbp": 3.0, "pnl_gbp": 3.17, "offer_id": 991, "lineage_id": "mb_x"},
    {"status": "LOST", "source": "framework", "fw_pool": True, "market_name": "Total", "oracle_p": 0.55,
     "avg_odds": 1.9, "close_back": 2.0, "cost_gbp": 2.0, "pnl_gbp": -2.04, "offer_id": 992, "lineage_id": "mb_x"},
    {"status": "OPEN", "source": "oracle", "market_name": "Match Odds", "oracle_p": 0.7,
     "avg_odds": 2.5, "cost_gbp": 1.0, "offer_id": 993, "lineage_id": "mb_y"},
    {"status": "VOID", "source": "oracle", "market_name": "Match Odds", "cost_gbp": 0.0},
]


def test_counts_and_clv():
    s = ml.summarise(ROWS)
    t = s["family: Over/Under"]
    assert (t["bets"], t["settled"], t["won"], t["lost"]) == (2, 2, 1, 1), t
    assert t["expected_wins"] == 1.15, t
    assert abs(t["mean_clv"] - 0.0) < 1e-9 and t["clv_n"] == 2, t      # +5% and -5%
    assert s["source: framework pick"]["won"] == 1
    assert s["source: framework rated market"]["lost"] == 1
    assert s["family: 1X2"]["bets"] == 1 and s["family: 1X2"]["mean_clv"] is None   # open, void skipped
    assert s["all"]["bets"] == 3


def test_nothing_private_in_the_public_file():
    with tempfile.TemporaryDirectory() as d:
        led, out = Path(d) / "ledger.jsonl", Path(d) / "summary.json"
        led.write_text("".join(json.dumps(r) + "\n" for r in ROWS), encoding="utf-8")
        assert ml.main(["x", str(led), str(out)]) == 0
        text = out.read_text(encoding="utf-8")
    for private in ("gbp", "£", "offer", "lineage", "991", "3.17", "balance", "stake"):
        assert private not in text.lower(), private


def test_missing_ledger_reads_pending():
    assert "PENDING" in ml.lines(Path("does/not/exist.json"))[0]


if __name__ == "__main__":
    test_counts_and_clv()
    test_nothing_private_in_the_public_file()
    test_missing_ledger_reads_pending()
    print("matchbook_ledger_test: OK")
