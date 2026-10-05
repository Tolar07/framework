"""Losing-market watch, knowledge file and proposals (standing order 39). Offline."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine import loss_watch as lw  # noqa: E402

DOG = "SB:16|hcp=-2.5|Away (+2.5)"
FAV = "SB:16|hcp=-1.5|Home (-1.5)"
DC = "SB:10||Home or Draw"


def _ledger(tmp: Path, day: str, singles: list) -> None:
    (tmp / f"picks_{day}.json").write_text(json.dumps({"date": day, "singles": singles}),
                                           encoding="utf-8")


def _s(key, league, won, price=1.22, chance=0.80, day="2026-10-03"):
    return {"fixture": f"A v B ({league})", "league": league, "market": key, "price": price,
            "chance": chance, "result": "won" if won else "lost", "kickoff": day}


def _setup(tmp: Path) -> None:
    # FA Cup underdog handicaps: 8 won, 6 lost at 1.22 -> -4.24u, 57% vs 82% needed
    rows = [_s(DOG, "FA Cup", i < 8) for i in range(14)]
    rows += [_s(DC, "FA Cup", True) for _ in range(10)]               # winning
    rows += [_s(FAV, "League Two", i < 9) for i in range(10)]          # 1 loss: fine
    _ledger(tmp, "2026-10-03", rows)
    _ledger(tmp, "2026-09-01", [_s(DOG, "FA Cup", False, day="2026-09-01")] * 20)  # too old


def test_segment() -> None:
    assert lw.segment(DOG) == "Asian handicap (underdog)"
    assert lw.segment(FAV) == "Asian handicap (favourite)"
    assert lw.segment("SB:14|hcp=0:2|Away (0:2)") == "European handicap (underdog)"
    assert lw.segment(DC) == "Double chance"


def test_watch_flags_and_proposes() -> None:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        _setup(tmp)
        w = lw.watch(tmp, today="2026-10-05")
        assert w["graded"] == 34, "the 1 Sep ledger is outside the window"
        flagged = {(s["segment"], s["league"]) for s in w["flags"]}
        assert ("Asian handicap (underdog)", "FA Cup") in flagged
        assert ("Asian handicap (underdog)", "all") in flagged
        assert not any(s == "Double chance" or lg == "League Two" for s, lg in flagged)
        props_path = tmp / "proposals.json"
        new = lw.propose(w, path=props_path)
        assert {(p["segment"], p["league"]) for p in new} == {
            ("Asian handicap (underdog)", "FA Cup"), ("Asian handicap (underdog)", "all")}
        assert all(p["status"] == "open" for p in new)
        assert lw.propose(w, path=props_path) == [], "an open proposal is not raised twice"
        assert lw.blocks(props_path) == [], "nothing applies before the Architect approves"
        pid = next(p["id"] for p in new if p["league"] == "FA Cup")
        assert "APPROVED" in lw.decide(pid, True, today="2026-10-05", path=props_path)
        blk = lw.blocks(props_path)
        assert blk == [("Asian handicap (underdog)", "FA Cup")]
        assert lw.blocked(DOG, "FA Cup", blk) and not lw.blocked(DOG, "League Two", blk)
        assert not lw.blocked(FAV, "FA Cup", blk) and not lw.blocked(DC, "FA Cup", blk)
        assert "LIFTED" in lw.decide(pid, False, today="2026-10-06", path=props_path)
        assert lw.blocks(props_path) == []
        other = next(p["id"] for p in new if p["league"] == "all")
        assert "REJECTED" in lw.decide(other, False, today="2026-10-05", path=props_path)
        assert lw.propose(lw.watch(tmp, today="2026-10-07"), path=props_path) == [], \
            "a rejected proposal stays quiet for two weeks"
        assert "No proposal" in lw.decide("P99", True, path=props_path)


def test_remember_and_summary() -> None:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        _setup(tmp)
        saved = lw.PROPOSALS_FILE
        lw.PROPOSALS_FILE = tmp / "proposals.json"
        try:
            w = lw.watch(tmp, today="2026-10-05")
            lw.propose(w)
            k = lw.remember(w, {"family": {"Double chance": {"shift": 0.02}}},
                            path=tmp / "knowledge.json")
            assert k["updated"] == "2026-10-05" and k["learning"] == {"family:Double chance": 0.02}
            assert k["history"][-1]["flags"], "the day's flags are kept in the history"
            lw.remember(w, None, path=tmp / "knowledge.json")
            assert len(json.loads((tmp / "knowledge.json").read_text())["history"]) == 1
            text = lw.summary(w)
            assert "Asian handicap (underdog) · FA Cup" in text and "/approve" in text
        finally:
            lw.PROPOSALS_FILE = saved


def test_notes() -> None:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "corrections.csv"
        p.write_text("logged_at,source,note,actioned\n2026-08-03T20:39,telegram,model wrong,no\n"
                     "2026-08-04T10:00,telegram,fixed one,yes\n", encoding="utf-8")
        notes = lw.open_notes(p)
        assert [n["note"] for n in notes] == ["model wrong"]
        assert "model wrong" in lw.notes_line(notes)
        assert lw.open_notes(Path(d) / "missing.csv") == [] and lw.notes_line([]) is None


def test_telegram_decisions_fail_closed() -> None:
    import os

    from output import telegram_commands as tc
    saved = os.environ.get("TELEGRAM_CHAT_ID")
    os.environ.pop("TELEGRAM_CHAT_ID", None)
    try:
        assert tc.handle("/approve P1", "123").startswith("REFUSED"), "no chat configured"
        os.environ["TELEGRAM_CHAT_ID"] = "123"
        assert tc.handle("/approve P1", "999").startswith("REFUSED"), "not the Architect"
        assert tc.handle("/approve P1").startswith("REFUSED"), "no chat id"
        assert "/approve" in tc.handle("/help")
    finally:
        if saved is None:
            os.environ.pop("TELEGRAM_CHAT_ID", None)
        else:
            os.environ["TELEGRAM_CHAT_ID"] = saved


def test_supervisor_checks_knowledge() -> None:
    from monitor import supervisor
    base = dict(day="2026-10-06", slot="evening", run_conclusion="success",
                facts={"board": True, "run_id": True, "bet365": True, "no_data": 0},
                stats={}, runs={})
    stale = supervisor.report(**base, knowledge={"updated": "2026-10-04", "today": "2026-10-05"})
    assert "knowledge file NOT updated" in stale
    fresh = supervisor.report(**base, knowledge={"updated": "2026-10-05", "today": "2026-10-05",
                                                 "open": 2})
    assert "ALL CLEAR" in fresh and "2 proposal(s) waiting" in fresh
    nolog = supervisor.report(**base, knowledge={"updated": "2026-10-05", "today": "2026-10-05",
                                                 "last_run": {"target": "2026-10-05"}})
    assert "run log has no record for 2026-10-06" in nolog
    logged = supervisor.report(**base, knowledge={"updated": "2026-10-05", "today": "2026-10-05",
                                                  "last_run": {"target": "2026-10-06",
                                                               "run_id": "OLPXDV-x"}})
    assert "ALL CLEAR" in logged and "OLPXDV-x" in logged


def test_run_log() -> None:
    from monitor import json_log
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "runs.jsonl"
        assert json_log.read_runs(p) == []
        json_log.record_run(p, run_id="OLPXDV-1", target="2026-10-06", slot="evening", picks=3)
        json_log.record_run(p, run_id="OLPXDV-2", target="2026-10-06", slot="morning", picks=3)
        runs = json_log.read_runs(p)
        assert [r["run_id"] for r in runs] == ["OLPXDV-1", "OLPXDV-2"]
        assert runs[-1]["event"] == "board_run" and runs[-1]["picks"] == 3
        import logging
        for h in list(logging.getLogger("olp.json").handlers):
            if getattr(h, "baseFilename", "") == str(p):
                h.close()
                logging.getLogger("olp.json").removeHandler(h)


if __name__ == "__main__":
    test_segment()
    test_watch_flags_and_proposes()
    test_remember_and_summary()
    test_notes()
    test_telegram_decisions_fail_closed()
    test_supervisor_checks_knowledge()
    test_run_log()
    print("loss watch: OK")
