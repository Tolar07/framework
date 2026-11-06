"""TELEGRAM NBA TEST — /board nba, /board basketball, /why nba <n>, NBA block in /status.

Offline, on temp folders. Pins: the NBA board is returned as written; a missing board reads PENDING;
/why nba explains a pick with its blend weight and the market group's shadow record; world
basketball picks show with their code (PENDING when none); the football /board and /why paths are
untouched.
"""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from output import telegram_commands as tc  # noqa: E402
from output import telegram_nba as tn  # noqa: E402

FAILED: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"{'  OK  ' if ok else ' FAIL '} {name}" + (f"  ({detail})" if detail else ""))
    if not ok:
        FAILED.append(name)


PICK = {"home": "Boston Celtics", "away": "Miami Heat", "tip": "2026-11-06T00:30:00+00:00",
        "pick": "1st half total Over 110.5", "price": 1.9, "chance": 0.60, "fair_price": 1.67,
        "ev": 0.14, "market_id": "68", "specifier": "total=110.5", "code": None, "result": None}

with tempfile.TemporaryDirectory() as td:
    d = Path(td)
    boards, ledger, wb, shadow = d / "boards", d / "picks", d / "wb", d / "shadow"
    for x in (boards, ledger, wb, shadow):
        x.mkdir()

    check("board: none yet reads PENDING", "PENDING" in tn.nba_board(boards))
    check("why: none yet reads PENDING", "PENDING" in tn.explain("1", ledger, d / "r.md", boards))

    (boards / "nba_2026-11-05.txt").write_text("NBA BOARD TEXT", encoding="utf-8")
    (ledger / "nba_2026-11-05.json").write_text(json.dumps({"picks": [PICK]}), encoding="utf-8")
    check("board: newest NBA board returned as written", tn.nba_board(boards) == "NBA BOARD TEXT")

    rep = d / "r.md"
    rep.write_text("| Market | graded | won | stated chance | return ± se | status |\n|---|---:|---:|---:|---|---|\n"
                   "| 1st half total | 120 | 57% | 60% | +11.0% ± 8.8% | not yet |\n", encoding="utf-8")
    out = tn.explain("1", ledger, rep, boards)
    check("why: shows the pick, chance and fair price", "Over 110.5" in out and "60%" in out and "1.67" in out, out)
    check("why: shows a blend weight", "Blend weight" in out)
    check("why: shows the shadow record row", "120 graded" in out and "+11.0%" in out, out)
    check("why: code and result read PENDING", out.count("PENDING") >= 2)
    check("why: pick number out of range is said", "has 1" in tn.explain("5", ledger, rep, boards))
    check("why: bad argument gives usage", "Usage" in tn.explain("x", ledger, rep, boards))
    check("record: unknown family reads PENDING", "PENDING" in tn.group_record("Nope", rep))

    check("world: none reads PENDING", "PENDING" in tn.world_board(date(2026, 11, 6), wb))
    (wb / "wb_2026-11-06.json").write_text(json.dumps({"picks": [
        {"home": "Real Madrid", "away": "Barca", "comp": "Euroleague", "ko": "2026-11-06T19:00Z",
         "pick": "Over 160.5", "price": 1.85, "chance": 0.58, "code": None}]}), encoding="utf-8")
    w = tn.world_board(date(2026, 11, 6), wb)
    check("world: pick listed with PENDING code", "Real Madrid" in w and "code PENDING" in w, w)

    st = tn.nba_status(ledger, shadow, wb, d / "live", boards, datetime(2026, 11, 6, tzinfo=timezone.utc))
    check("status: board and world counts", "1 picks" in st and "picks recorded: 1" in st, st)
    check("status: no live snapshot reads PENDING", "PENDING" in st)

check("split: nba", tn.split_sport("nba 2") == ("nba", "2"))
check("split: basketball", tn.split_sport("basketball")[0] == "basketball")
check("split: football number untouched", tn.split_sport("2") == (None, "2"))
check("route: /board nba goes to the NBA board",
      tc.cmd_board("nba") == tn.nba_board(tc.BOARD_DIR))
check("route: /why 2 stays football usage-checked", "Usage" in tc.cmd_why("abc"))
check("route: /why nba abc gives the NBA usage", "nba" in tc.cmd_why("nba abc"))
check("route: /status carries the NBA block", "NBA / BASKETBALL" in tc.cmd_status(""))

print()
if FAILED:
    print(f"FAILED: {len(FAILED)}")
    sys.exit(1)
print("telegram nba: all checks passed")
