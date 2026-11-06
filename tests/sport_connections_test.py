"""SPORT CONNECTIONS (Architect 2026-11-06: "Everything inherits everything ... no gaps"):
every sport (football, basketball and every rollout sport) lists every capability; a `done` one
names framework files that exist (and name the sport, outside football's own core files); a
`todo` one names the issue building it and a due date; live-blocking gaps are reported by
monitor/connections_check.py on and after each sport's live date."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

REG = json.loads((ROOT / "config" / "sport_connections.json").read_text(encoding="utf-8"))
ROLL = json.loads((ROOT / "config" / "sport_rollout.json").read_text(encoding="utf-8"))
from engine import multisport as _ms  # noqa: E402

MS_SPORTS = set(_ms.SPORTS)
TOKENS = {"basketball": ("nba", "basketball", "ncaa"), "ice_hockey": ("hockey",)}


def test_every_sport_listed():
    want = {"football", "basketball"}
    for s in ROLL["sports"]:
        want |= set(s.get("covers") or [s["sport"]])
    assert want <= set(REG["sports"]), f"sports without connections: {sorted(want - set(REG['sports']))}"


def test_every_capability_everywhere():
    caps = set(REG["capabilities"])
    for sport, c in REG["sports"].items():
        assert set(c) == caps, f"{sport}: missing {sorted(caps - set(c))}, unknown {sorted(set(c) - caps)}"
    assert set(REG["live_blocking"]) <= caps


def test_entries_are_real():
    for sport, c in REG["sports"].items():
        for cap, v in c.items():
            st = v["status"]
            assert st in ("done", "external", "todo", "n/a"), f"{sport}.{cap}: bad status {st}"
            if st == "n/a":
                assert v.get("reason"), f"{sport}.{cap}: n/a needs a reason"
                continue
            if st == "done":
                assert v.get("paths"), f"{sport}.{cap}: done needs paths"
                for p in v["paths"]:
                    f = ROOT / p
                    assert f.exists(), f"{sport}.{cap}: {p} does not exist"
                    if sport != "football" and f.suffix in (".py", ".yml", ".md"):
                        text = f.read_text(encoding="utf-8").lower()
                        toks = TOKENS.get(sport, (sport, sport.replace("_", " ")))
                        generic = "multisport" in text and sport in MS_SPORTS     # runs every SPORTS entry
                        assert any(t in text for t in toks) or generic, f"{sport}.{cap}: {p} never names {sport}"
            elif st == "external":
                assert v.get("repo", "").startswith("Tolar07/") and v.get("ref"), f"{sport}.{cap}: external needs repo + ref"
            else:
                assert v.get("issue") and v.get("due"), f"{sport}.{cap}: todo needs an issue and a due date"


def test_check_flags_live_gaps():
    from monitor import connections_check as cc
    _lines, blocking = cc.gaps("2026-11-11")
    assert not blocking, "nothing is live before 12 Nov"
    reg = {"live_blocking": ["matchbook_live"], "sports": {"tennis": {"matchbook_live": {"status": "todo", "issue": "x"}}}}
    _l, b = cc.gaps("2026-11-12", reg, {"sports": [{"sport": "tennis", "live_from": "2026-11-12"}]})
    assert b and "tennis" in b[0]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("sport_connections_test: OK")
