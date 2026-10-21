"""monitor/nba_live.py — the NBA board's games followed live. No network: ESPN is faked."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from monitor import nba_live as NL  # noqa: E402

PICK_H1 = {"home": "Detroit Pistons", "away": "Boston Celtics", "tip": "2026-10-20T19:00:00+00:00",
           "espn_id": "401909088", "espn_date": "2026-10-20", "market_id": "68", "specifier": "total=114.5",
           "outcome": "Under 114.5", "pick": "1st half Under 114.5 points"}
PICK_ML = {**PICK_H1, "market_id": "219", "specifier": "", "outcome": "Away", "pick": "Celtics to win"}


def ev(state: str, period: int, name: str, qh: list[int], qa: list[int]) -> dict:
    return {"id": "401909088", "status": {"period": period, "displayClock": "0.0",
                                          "type": {"state": state, "name": name, "shortDetail": name}},
            "competitions": [{"competitors": [
                {"homeAway": "home", "score": str(sum(qh)), "linescores": [{"value": x} for x in qh]},
                {"homeAway": "away", "score": str(sum(qa)), "linescores": [{"value": x} for x in qa]}]}]}


NIGHT = [
    ev("pre", 0, "STATUS_SCHEDULED", [], []),
    ev("in", 1, "STATUS_IN_PROGRESS", [12], [10]),
    ev("in", 1, "STATUS_END_PERIOD", [28], [26]),
    ev("in", 2, "STATUS_IN_PROGRESS", [28, 10], [26, 9]),
    ev("in", 2, "STATUS_HALFTIME", [28, 27], [26, 28]),      # half: 55 + 54 = 109 < 114.5 -> Under WON
    ev("in", 3, "STATUS_IN_PROGRESS", [28, 27, 5], [26, 28, 8]),
    ev("post", 4, "STATUS_FINAL", [28, 27, 25, 30], [26, 28, 30, 29]),   # 110 - 113: Celtics win
]


def test_board_games_from_the_nba_ledger():
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "nba_2026-10-21.json").write_text(json.dumps({"date": "2026-10-21", "picks": [PICK_H1, PICK_ML]}))
        games = NL.board_games("2026-10-21", Path(d))
        assert NL.board_games("2026-10-22", Path(d)) == []
    assert len(games) == 1 and len(games[0]["picks"]) == 2
    assert games[0]["espn_days"] == ["20261019", "20261020"], "ESPN files a late tip under the US date"


def test_a_night_from_tip_to_final():
    g = {"espn_id": "401909088", "home": "DET", "away": "BOS", "espn_days": ["20261020"],
         "picks": [PICK_H1, PICK_ML]}
    seen: dict = {}
    said: list[list[str]] = []
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "live.jsonl"
        for e in NIGHT:
            lines, still = NL.round_once([g], seen, out, get=lambda _u, e=e: {"events": [e]})
            said.append(lines)
        assert len(out.read_text().splitlines()) == len(NIGHT), "every look is recorded"
    assert said[0] == [] and not any("TIP" in x for x in said[0])
    assert said[1][0] == "TIP-OFF BOS @ DET" and "running — 1st half Under 114.5 points: 22 so far" in said[1][1]
    assert said[2][0] == "END Q1 BOS @ DET 26-28"
    assert said[3] == [], "a quarter is announced once"
    assert said[4][0] == "HALF TIME BOS @ DET 54-55" and "  WON — 1st half Under 114.5 points" in said[4]
    assert said[5] == [], "half time is not announced again when Q3 starts"
    # a jump straight to the final: only FINAL (an "END Q3" line could only show the wrong score)
    assert said[6][0] == "FINAL BOS @ DET 113-110" and "  WON — Celtics to win" in said[6]
    assert still is False


def test_espn_silent_keeps_waiting_quietly():
    g = {"espn_id": "x", "home": "A", "away": "B", "espn_days": ["20261020"], "picks": [PICK_ML]}
    with tempfile.TemporaryDirectory() as d:
        lines, still = NL.round_once([g], {}, Path(d) / "l.jsonl", get=lambda _u: None)
    assert lines == [] and still is True


def test_a_handed_off_run_does_not_repeat_what_was_said():
    """21 Oct: the 23:51 hand-off re-sent a finished game's TIP-OFF and FINAL."""
    g = {"espn_id": "401909088", "home": "DET", "away": "BOS", "espn_days": ["20261020"], "picks": [PICK_H1]}
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "live.jsonl"
        seen: dict = {}
        for e in NIGHT[:3]:                                   # first run: tip-off, end of Q1
            NL.round_once([g], seen, out, get=lambda _u, e=e: {"events": [e]})
        out.write_text(out.read_text() + "not json\n")
        resumed = NL.resume(out)                              # the next run starts here
        lines, _ = NL.round_once([g], resumed, out, get=lambda _u: {"events": [NIGHT[3]]})
        assert lines == [], "nothing new since the last run's look"
        lines, _ = NL.round_once([g], resumed, out, get=lambda _u: {"events": [NIGHT[4]]})
        assert lines[0].startswith("HALF TIME") and not any("TIP" in x or "END Q1" in x for x in lines)
        assert NL.resume(Path(d) / "missing.jsonl") == {}


def test_snapshots_are_not_git_ignored():
    """The blanket *.jsonl ignore made the first night's saves silently save nothing."""
    import subprocess
    root = Path(__file__).parent.parent
    r = subprocess.run(["git", "check-ignore", "-q", "data/study/nba/2026-10-21/live.jsonl"], cwd=root)
    assert r.returncode == 1, "data/study/nba/<board>/live.jsonl must be tracked (see .gitignore)"

if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("nba_live_test OK")
