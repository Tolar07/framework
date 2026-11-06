"""Decision layer (standing order 51): inside the caps, logged, undone when it fails, all off with one switch."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import decisions as D  # noqa: E402

NOW = datetime(2026, 11, 20, 23, 30, tzinfo=UTC)


def bets(group, n, roi, day="2026-11-10"):
    return [{"group": group, "stake_gbp": 1.0, "profit_gbp": roi, "date": day} for _ in range(n)]


def paths(td):
    return {"state_path": Path(td) / "s.json", "log_path": Path(td) / "l.jsonl"}


def test_group_of():
    assert D.group_of("SB:18|total=2.5|Over 2.5", "matchbook") == "matchbook | SB:18 Over N"
    assert D.group_of("NBA:223|hcp=-3.5|Home (-3.5)") == "NBA:223 Home (N)"
    assert D.group_of("tennis:186||Home", "betfair") == "betfair | tennis:186 Home"


def test_stake_up_one_step_then_cooldown_and_caps():
    os.environ.pop("DECISIONS_AUTO", None)
    with tempfile.TemporaryDirectory() as td:
        g = "matchbook | SB:18 Over N"
        r = D.run(bets(g, 40, 0.10), [], {}, {}, NOW, **paths(td))
        assert [(d["kind"], d["from"], d["to"]) for d in r["made"]] == [("stake_multiplier", 1.0, 1.25)]
        r = D.run(bets(g, 40, 0.10), [], {}, {}, NOW + timedelta(days=1), **paths(td))
        assert r["made"] == [], "7-day cool-down"
        st = r["state"]
        for k in range(5):
            r = D.run(bets(g, 40, 0.10), [], {}, {}, NOW + timedelta(days=8 * (k + 1)), **paths(td))
            st = r["state"]
        assert st["stake_mult"][g] == 1.5, "never above x1.5"
        assert D.stake_mult({"auto": True, "stake_mult": {g: 9}}, g) == 1.5


def test_losing_side_to_paper_and_back():
    with tempfile.TemporaryDirectory() as td:
        g = "betfair | SB:1 Away"
        r = D.run(bets(g, 35, -0.20), [], {}, {}, NOW, **paths(td))
        assert g in r["state"]["paper_groups"]
        r = D.run([], bets("SB:1 Away", 40, 0.08), {}, {}, NOW + timedelta(days=8), **paths(td))
        assert g not in r["state"]["paper_groups"], "back to real on the board's paper record"


def test_undo_when_it_fails_after():
    with tempfile.TemporaryDirectory() as td:
        g = "sportybet | SB:29 Yes"
        D.run(bets(g, 40, 0.10), [], {}, {}, NOW, **paths(td))
        after = bets(g, 40, 0.10) + bets(g, 25, -0.5, day="2026-11-22")
        r = D.run(after, [], {}, {}, NOW + timedelta(days=3), **paths(td))
        assert r["undone"] and r["undone"][0]["to"] == 1.0 and r["state"]["stake_mult"][g] == 1.0
        log = [json.loads(x) for x in (Path(td) / "l.jsonl").read_text(encoding="utf-8").splitlines()]
        assert any(d["status"] == "undone" for d in log) and any(d.get("undoes") for d in log)


def test_value_bar_inside_band():
    with tempfile.TemporaryDirectory() as td:
        # low-value sides lose, high-value sides win: the bar rises to where the profit is
        sides = {"tennis|186": [(0.016, 0, 1.9)] * 40 + [(0.045, 1, 1.9)] * 40 + [(0.045, 0, 1.9)] * 20}
        r = D.run([], [], sides, {"tennis|186": 0.03}, NOW, **paths(td))
        assert [(d["key"], d["to"]) for d in r["made"]] == [("tennis|186", 0.04)]
        assert D.value_threshold({"auto": True, "value_threshold": {"tennis|186": 0.001}}, "tennis|186", 0.03) == 0.015


def test_master_switch_undoes_everything():
    with tempfile.TemporaryDirectory() as td:
        g = "matchbook | SB:18 Over N"
        D.run(bets(g, 40, 0.10), [], {}, {}, NOW, **paths(td))
        os.environ["DECISIONS_AUTO"] = "0"
        try:
            r = D.run(bets(g, 40, 0.10), [], {}, {}, NOW + timedelta(days=9), **paths(td))
        finally:
            os.environ.pop("DECISIONS_AUTO")
        assert r["off"] and r["state"]["stake_mult"] == {} and D.stake_mult(r["state"], g) == 1.0
        assert "OFF" in D.report_line(r)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("decisions_test: OK")
