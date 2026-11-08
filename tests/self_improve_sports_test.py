"""Weekly self-improvement loop, section (e) every sport (framework#356): basketball and every rollout
sport (ice hockey + engine/multisport.SPORTS) is asked "what do I need to do better?" from its own graded
record; each gets at most one proposal with one buildable deliverable; too little data is PENDING, never
an issue; issues are opened once by title and an open one is commented on, never duplicated."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import multisport as ms  # noqa: E402
from scripts import self_improve as si  # noqa: E402


def _w(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding="utf-8")


def _root(t: str) -> Path:
    r = Path(t)
    # basketball: 40 graded NBA picks losing to the close
    _w(r / "output" / "picks" / "nba_2026-11-08.json",
       {"picks": [{"price": 1.9, "result": "won" if i % 2 else "lost", "close_value": -0.02, "stage": "regular"}
                  for i in range(40)] + [{"price": 1.9, "result": "won", "close_value": 0.5, "stage": "preseason"}]})
    # tennis: graded sides, no picks -> the gate study
    _w(r / "output" / "multisport" / "tennis" / "ms_2026-11-08.json", {"picks": [], "games": {}})
    _w(r / "data" / "multisport" / "tennis" / "scoreboard.json",
       {"picks": 0, "won": 0, "pnl": 0, "clv_fair_avg": None, "all_sides_by_market": {"186": {"sides": 400}}})
    # darts: a few sides -> PENDING
    _w(r / "output" / "multisport" / "darts" / "ms_2026-11-08.json", {"picks": [], "games": {}})
    _w(r / "data" / "multisport" / "darts" / "scoreboard.json",
       {"picks": 2, "won": 1, "pnl": 0.1, "all_sides_by_market": {"186": {"sides": 20}}})
    # rugby: board files but no scoreboard -> grading fix
    _w(r / "output" / "multisport" / "rugby" / "ms_2026-11-08.json", {"picks": [], "games": {}})
    # volleyball: 50 picks holding value, coin-level Elo over 300 games -> K study
    _w(r / "output" / "multisport" / "volleyball" / "ms_2026-11-08.json", {"picks": [], "games": {}})
    _w(r / "data" / "multisport" / "volleyball" / "scoreboard.json",
       {"picks": 50, "won": 30, "pnl": 2.0, "clv_fair_avg": 0.01, "all_sides_by_market": {"186": {"sides": 900}},
        "elo": {"walk_forward_brier": 0.26, "scored": 300}})
    # ice hockey: a flagged experiment shadow -> Architect decision
    _w(r / "output" / "ice_hockey" / "ih_2026-11-08.json", {"picks": [], "games": {}})
    _w(r / "data" / "ice_hockey" / "scoreboard.json", {"picks": 10, "all_sides_by_market": {"1": {"sides": 500}}})
    _w(r / "memory" / "strategies.json",
       {"flagged": ["IH1 ice hockey: winner only", "S1 HIGH certainty only"],
        "standings": {"IH1 ice hockey: winner only": {"slot": "ice_hockey", "vs_live": "beats live",
                                                       "counted": {"n": 120}},
                      "S1 HIGH certainty only": {"slot": "singles"}}})
    return r


def test_every_sport_is_asked():
    want = {"basketball", "ice_hockey", *ms.SPORTS}
    assert set(si.rollout_sports()) == want
    ro = json.loads((ROOT / "config" / "sport_rollout.json").read_text(encoding="utf-8"))
    assert {c for s in ro["sports"] for c in (s.get("covers") or [s["sport"]])} <= want, "every rollout sport"
    with tempfile.TemporaryDirectory() as t:
        out = si.audit_sports(Path(t))
    assert [q["sport"] for q in out] == si.rollout_sports()
    assert all(q["proposal"] is None and "PENDING" in q["answer"] for q in out), "no data = PENDING, no issue"


def test_answers_and_one_deliverable_each():
    with tempfile.TemporaryDirectory() as t:
        r = _root(t)
        q = {x["sport"]: x for x in si.audit_sports(r)}
    assert q["basketball"]["record"]["picks"] == 40, "NBA preseason is left out"
    assert q["basketball"]["proposal"]["title"].startswith("Basketball: picks lose to the closing price")
    assert "BASKETBALL_CLV_STUDY.md" in q["basketball"]["proposal"]["body"]
    assert "TENNIS_GATE_STUDY.md" in q["tennis"]["proposal"]["body"] and q["tennis"]["proposal"]["kind"] == "study"
    assert q["darts"]["proposal"] is None and "PENDING" in q["darts"]["answer"], "too little graded: no issue"
    assert q["rugby"]["proposal"]["kind"] == "fix" and "scoreboard" in q["rugby"]["proposal"]["title"]
    assert "VOLLEYBALL_K_STUDY.md" in q["volleyball"]["proposal"]["body"]
    assert q["ice_hockey"]["proposal"]["kind"] == "promote" and "IH1" in q["ice_hockey"]["proposal"]["title"]
    for x in q.values():
        p = x["proposal"]
        if p:
            assert "Deliverable:" in p["body"] and "RECORD-ONLY" in p["body"], f"{x['sport']}: one buildable deliverable"
            assert not any(ch.isdigit() for ch in p["title"].replace("IH1", "")), "stable titles (dedupe by title)"
    md = si.render([], [], [], "2026-11-08", None, list(q.values()))
    assert "## (e) Every sport" in md and "| tennis |" in md and "| basketball |" in md
    note = si.architect_note(None, {"loops": [], "inputs": [], "proposals": [], "sports": list(q.values())})
    assert "tennis:" in note and "Sports with something to do better" in note


def test_issues_opened_once_open_ones_commented():
    with tempfile.TemporaryDirectory() as t:
        sports = si.audit_sports(_root(t))
    calls: list[tuple] = []
    tennis = next(q["proposal"]["title"] for q in sports if q["sport"] == "tennis")
    rugby = next(q["proposal"]["title"] for q in sports if q["sport"] == "rugby")

    def fake_gh(*args: str, inp: str | None = None) -> str:
        calls.append(args)
        if args[:2] == ("issue", "list") and "open" in args:
            return json.dumps([{"title": tennis, "number": 900}])
        if args[:2] == ("issue", "list"):
            return json.dumps([{"title": rugby, "stateReason": "NOT_PLANNED"}])
        if args[:2] == ("issue", "create"):
            return f"https://github.com/x/y/issues/{len(calls)}\n"
        return ""
    real = si._gh
    si._gh = fake_gh
    try:
        made = si.open_sport_issues(sports, "2026-11-08")
    finally:
        si._gh = real
    created = [a[a.index("--title") + 1] for a in calls if a[:2] == ("issue", "create")]
    assert tennis not in created and rugby not in created, "never a duplicate, never a re-opened not-planned"
    assert any(a[:3] == ("issue", "comment", "900") for a in calls), "the open one gets this week's numbers"
    assert len(created) == len(made) == 3, created     # basketball, volleyball, ice hockey
    assert all("self-improvement" in a for a in calls if a[:2] == ("issue", "create"))


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("self_improve_sports_test: OK")
