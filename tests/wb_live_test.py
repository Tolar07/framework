"""monitor/wb_live.py - world basketball / NCAA picks followed live. No network: ESPN is faked."""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from monitor import wb_live as WL  # noqa: E402

TIP = "2026-11-10T23:00:00Z"
H1 = {"sb_event_id": "sr:1", "comp": "NCAA", "home": "Duke Blue Devils", "away": "Kansas Jayhawks", "tip": TIP,
      "market_id": "68", "specifier": "total=70.5", "outcome": "Under 70.5", "pick": "1st half Under 70.5 points"}
ML = {**H1, "market_id": "219", "specifier": "", "outcome": "Home", "pick": "Duke Blue Devils to win"}
EU = {"sb_event_id": "sr:2", "comp": "EuroLeague", "home": "Real Madrid", "away": "Olympiacos", "tip": TIP,
      "market_id": "219", "specifier": "", "outcome": "Home", "pick": "Real Madrid to win"}


def ev(state, period, name, qh, qa):
    def team(n, i):
        return {"id": i, "displayName": n, "shortDisplayName": n.split()[0], "location": n.split()[0],
                "name": n.split()[-1], "abbreviation": n[:3].upper()}
    return {"events": [{"id": "9001", "date": "2026-11-10T23:00Z",
                        "status": {"period": period, "displayClock": "0.0",
                                   "type": {"state": state, "name": name, "shortDetail": name}},
                        "competitions": [{"competitors": [
                            {"homeAway": "home", "score": str(sum(qh)), "team": team("Duke Blue Devils", "150"),
                             "linescores": [{"value": x} for x in qh]},
                            {"homeAway": "away", "score": str(sum(qa)), "team": team("Kansas Jayhawks", "2305"),
                             "linescores": [{"value": x} for x in qa]}]}]}]}


NIGHT = [
    ev("pre", 0, "STATUS_SCHEDULED", [], []),
    ev("in", 1, "STATUS_IN_PROGRESS", [20], [15]),
    ev("in", 1, "STATUS_HALFTIME", [35], [30]),               # 65 < 70.5: Under WON at half time
    ev("in", 2, "STATUS_IN_PROGRESS", [35, 10], [30, 12]),
    ev("post", 2, "STATUS_FINAL", [35, 40], [30, 38]),         # Duke 75 - 68
]


def write_picks(d: Path, picks):
    (d / "wb_2026-11-10.json").write_text(json.dumps({"picks": picks}), encoding="utf-8")


def test_night_games_group_and_flag_ncaa():
    with tempfile.TemporaryDirectory() as t:
        write_picks(Path(t), [H1, ML, EU])
        gs = WL.night_games("2026-11-10", Path(t))
        assert len(gs) == 2
        duke = next(g for g in gs if g["ncaa"])
        assert len(duke["picks"]) == 2 and not next(g for g in gs if not g["ncaa"])["ncaa"]


def test_night_outside_window_is_empty():
    with tempfile.TemporaryDirectory() as t:
        write_picks(Path(t), [{**H1, "tip": "2026-11-10T09:00:00Z"}])     # before 12:00 UTC: the previous night
        assert WL.night_games("2026-11-10", Path(t)) == []


def test_a_night_is_followed_once_each():
    with tempfile.TemporaryDirectory() as t:
        write_picks(Path(t), [H1, ML, EU])
        games = WL.night_games("2026-11-10", Path(t))
        out, seen, said = Path(t) / "live.jsonl", {}, []
        for blob in NIGHT:
            lines, still = WL.round_once(games, seen, out, get=lambda url, b=blob: b)
            said += lines
        text = "\n".join(said)
        assert text.count("TIP-OFF") == 1 and text.count("HALF TIME") == 1 and text.count("FINAL") == 1
        assert "WON - 1st half Under 70.5 points" in text          # settled from the 1st half alone
        assert "WON - Duke Blue Devils to win" in text            # final 75-68
        assert text.count("NO LIVE FEED - PENDING") == 1          # EuroLeague: said once, never guessed
        assert not still


def test_silent_espn_says_nothing_and_keeps_waiting():
    with tempfile.TemporaryDirectory() as t:
        write_picks(Path(t), [H1])
        games = WL.night_games("2026-11-10", Path(t))
        lines, still = WL.round_once(games, {}, Path(t) / "l.jsonl", get=lambda url: None)
        assert lines == [] and still


def test_resume_does_not_repeat():
    with tempfile.TemporaryDirectory() as t:
        write_picks(Path(t), [H1])
        games = WL.night_games("2026-11-10", Path(t))
        out = Path(t) / "live.jsonl"
        WL.round_once(games, {}, out, get=lambda url: NIGHT[1])
        seen = WL.resume(out)
        lines, _ = WL.round_once(games, seen, out, get=lambda url: NIGHT[1])
        assert lines == []


def main():
    for k, v in list(globals().items()):
        if k.startswith("test_"):
            v()
    print("wb_live_test OK")


if __name__ == "__main__":
    main()
