"""
The SportyBet evidence summary: real bets joined to the board's grading, by
section, at the odds taken — and nothing private (this repo is public).
"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from monitor import sportybet_ledger as sl  # noqa: E402

PICKS = {"accas": [{"code": "AAA111", "result": "won"}, {"code": "BBB222", "result": "lost"}],
         "megas": [{"code": "MMM999", "result": None}],
         "safe3": [{"code": "SSS333", "result": "won"}]}
PLACED = {"date": "2026-10-21", "bets": [
    {"code": "AAA111", "section": "accas", "status": "placed", "legs": 3, "odds": 2.1, "units": 1},
    {"code": "BBB222", "section": "accas", "status": "placed", "legs": 4, "odds": 2.5, "units": 1},
    {"code": "MMM999", "section": "megas", "status": "placed", "legs": 9, "odds": 40.0, "units": 0.1},
    {"code": "SSS333", "section": "safe3", "status": "skipped", "reason": "closed leg: Wolves v X"}]}


def _run():
    d = Path(tempfile.mkdtemp())
    (d / "data").mkdir(), (d / "picks").mkdir()
    (d / "data" / "placed_2026-10-21.json").write_text(json.dumps(PLACED))
    (d / "picks" / "picks_2026-10-21.json").write_text(json.dumps(PICKS))
    return sl.summarise(d / "data", d / "picks"), d


def test_sections_graded_at_odds_taken():
    s, _ = _run()
    acc = s["sections"]["accas"]
    assert (acc["placed"], acc["settled"], acc["won"]) == (2, 2, 1)
    assert acc["return"] == round(2.1 / 2 - 1, 4)          # 1 unit back at 2.10 on 2 units staked
    assert s["sections"]["megas"]["settled"] == 0           # still open: counted, not graded
    assert s["skipped"] == {"closed leg": 1}
    assert "safe3" not in s["sections"]                     # skipped, never placed


def test_lines_and_no_private_fields():
    s, d = _run()
    p = d / "summary.json"
    p.write_text(json.dumps(s))
    text = "\n".join(sl.lines(p))
    assert "accas: 2 placed, 1/2 landed" in text
    blob = json.dumps(s).lower()
    for word in ("naira", "ngn", "balance", "bet_id"):
        assert word not in blob


def test_pending_when_nothing_placed():
    assert "PENDING" in sl.lines(Path(tempfile.mkdtemp()) / "none.json")[0]
