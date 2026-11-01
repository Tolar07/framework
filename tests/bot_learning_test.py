"""monitor/bot_learning.py — the bots' paper challengers read into the framework (2026-11-01)."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from monitor import bot_learning as BL  # noqa: E402

FAKE = '''
import json
BASELINE = "LIVE"
VARIANTS = ("LIVE", "KO1H")
def load(p):
    return json.loads(p.read_text())
def summary(bets):
    out = {}
    for v in VARIANTS:
        g = [b for b in bets if b["variant"] == v]
        out[v] = {"graded": len(g), "win_rate": 0.5, "clv": 0.01 if v == "KO1H" else 0.0,
                  "roi": 0.1 if v == "KO1H" else 0.0}
    return out
def verdict(ch, lv):
    return "challenger beats live" if ch["roi"] > lv["roi"] else "live ahead"
def report(bets, s):
    return [f"  KO1H vs LIVE: {verdict(s['KO1H'], s['LIVE'])}"]
'''


def test_reads_a_bots_own_challenger_and_writes_ratios_only():
    bots = Path(tempfile.mkdtemp())
    pkg = bots / "betfair-agent" / "betfairfake"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "challenger.py").write_text(FAKE)
    (bots / "betfair-agent" / "ledger").mkdir()
    (bots / "betfair-agent" / "ledger" / "challenger.json").write_text(json.dumps(
        {"bets": [{"variant": "LIVE"}, {"variant": "KO1H"}]}))
    old = BL.BOTS
    BL.BOTS = (("Betfair", "betfair-agent", "betfairfake", "file:ledger/challenger.json"),)
    try:
        rows = BL.collect(bots)
    finally:
        BL.BOTS = old
    assert rows[0]["variants"][0]["verdict"] == "challenger beats live"
    assert "KO1H vs LIVE" in BL.report_block(rows)
    out = Path(tempfile.mkdtemp()) / "learning.json"
    BL.save(rows, out)
    saved = json.loads(out.read_text())
    assert "lines" not in saved["bots"][0]          # the report lines (may carry money) stay out of the file
    assert saved["bots"][0]["variants"][0]["roi"] == 0.1


def test_a_missing_or_broken_bot_never_stops_the_others():
    bots = Path(tempfile.mkdtemp())
    assert BL.collect(bots) == []
    assert BL.report_block([]) == ""
    assert "unreadable" in BL.report_block([{"bot": "X", "error": "ValueError: x", "variants": []}])


def main() -> None:
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("bot_learning_test OK")


if __name__ == "__main__":
    main()
