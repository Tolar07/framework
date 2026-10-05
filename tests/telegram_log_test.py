"""
Offline test of the /log command (output/telegram_commands.py): a logged leg
must be gradeable — pinned to one match (league + date from a recent board,
or a date the Architect adds) with a market that has a settlement rule.
Before 2026-10-04 every /log leg had no match date and was never graded.
"""
import json
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import clv.clv_logger as cl  # noqa: E402
from engine import markets as mkt  # noqa: E402
from engine import picks_ledger as pl  # noqa: E402
from output import telegram_commands as tc  # noqa: E402

tomorrow = (datetime.now(UTC).date() + timedelta(days=1)).isoformat()
with tempfile.TemporaryDirectory() as d:
    pl.LEDGER_DIR = Path(d)
    (Path(d) / f"picks_{tomorrow}.json").write_text(json.dumps({
        "date": tomorrow,
        "rated": [{"fixture": "Hearts v Dundee United", "league": "Scottish Premiership",
                   "home": "Hearts", "away": "Dundee United", "kickoff": tomorrow}],
        "singles": [{"fixture": "Hearts v Dundee United", "pick": "Hearts or Dundee United",
                     "market": "SB:10||Home or Away"}]}))
    log_path = Path(d) / "clv_log.json"
    tc.CLVLog = lambda: cl.CLVLog(log_path)  # type: ignore[assignment,misc]

    def legs() -> list:
        return cl.CLVLog(log_path).legs

    out = tc.cmd_log("Hearts v Dundee United | Over 1.5 goals | 1.42")
    assert out.startswith("Logged as a PAPER leg") and f"({tomorrow})" in out, out
    leg = legs()[-1]
    assert (leg.league, leg.match_date, leg.market) == \
        ("Scottish Premiership", tomorrow, mkt.OVER_15), "found on the board: league, date, key"

    assert tc.cmd_log("hearts v dundee united | Hearts or Dundee United | 1.30").startswith("Logged")
    assert legs()[-1].market == "SB:10||Home or Away", "the board's own pick wording is understood"
    for text, key in (("Hearts to win", mkt.HOME), ("Draw", mkt.DRAW), ("BTTS no", mkt.BTTS_NO),
                      ("Dundee United or Draw", mkt.DC_X2), ("Under 2.5", mkt.UNDER_25)):
        assert tc.cmd_log(f"Hearts v Dundee United | {text} | 1.5").startswith("Logged"), text
        assert legs()[-1].market == key and mkt.settle(key, 1, 0) is not None, text

    n = len(legs())
    refused = tc.cmd_log("Hearts v Dundee United | correct score 2-1 | 9")
    assert "can't settle" in refused and "Nothing logged" in refused and len(legs()) == n
    unknown = tc.cmd_log("Arsenal v Spurs | Over 2.5 | 1.8")
    assert "Add its date" in unknown and "Nothing logged" in unknown and len(legs()) == n, \
        "a match on no recent board is never logged ungradeable"
    assert "not a date" in tc.cmd_log("Arsenal v Spurs | Over 2.5 | 1.8 | 5 Oct")
    assert tc.cmd_log("Arsenal v Spurs | Over 2.5 | 1.8 | 2026-10-05").startswith("Logged")
    assert (legs()[-1].league, legs()[-1].match_date) == ("ARCHITECT-FED", "2026-10-05"), \
        "a date the Architect adds is used; grading then goes through Flashscore"
    assert all(lg.match_date and lg.stake is None for lg in legs()), "never a stake"

# Honest replies
_src = Path(tc.__file__).read_text(encoding="utf-8")
assert "not applied automatically" in _src and "is applied automatically" not in _src, \
    "/note must not claim corrections are applied (the heartbeat only lists them)"
assert "Capital is disabled" not in _src, \
    "capital is enabled at Phase 3; the refusal must not say otherwise"
print("✅ /log legs are gradeable: OK")
