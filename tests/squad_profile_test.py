"""engine/squad_profile.py: player roles from recent line-ups and the manager's rotation habit."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine import squad_profile as sp  # noqa: E402


def _match(xi: list[int], subs: dict[int, int] | None = None, off: dict[int, int] | None = None, tid: int = 7):
    starters = [{"id": i, "performance": {"rating": 7.0, "substitutionEvents":
                 ([{"type": "subOut", "time": off[i]}] if off and i in off else [])}} for i in xi]
    bench = [{"id": i, "performance": {"rating": 6.5, "substitutionEvents": [{"type": "subIn", "time": t}]}}
             for i, t in (subs or {}).items()]
    return {"content": {"lineup": {"homeTeam": {"id": tid, "starters": starters, "subs": bench}}}}


def test_minutes_roles_and_rotation():
    team = {"details": {"id": 7, "name": "Club"},
            "squad": {"squad": [{"title": "coach", "members": [{"name": "Boss"}]},
                                {"title": "mid", "members": [
                                    {"id": i, "name": f"P{i}", "transferValue": 10, "positionIdsDesc": "CM"}
                                    for i in range(1, 6)] + [{"id": 6, "name": "Hurt", "transferValue": 9,
                                                              "positionIdsDesc": "ST", "injury": {"x": 1}}]}]}}
    ms = [("2026-10-01T19:00:00Z", sp.match_lines(_match([1, 2, 3], {4: 60}, {1: 75}), 7)),
          ("2026-10-04T15:00:00Z", sp.match_lines(_match([1, 2, 4]), 7)),
          ("2026-10-11T15:00:00Z", sp.match_lines(_match([1, 3, 4]), 7))]
    p = sp.profile(team, ms)
    rows = {r["name"]: r for r in p["players"]}
    assert rows["P1"]["role"] == "regular" and rows["P1"]["minutes"] == 75 + 90 + 90
    assert rows["P4"]["starts"] == 2 and rows["P4"]["sub_apps"] == 1 and rows["P4"]["minutes"] == 30 + 180
    assert rows["P5"]["role"] == "unused" and rows["Hurt"]["role"] == "out"
    assert p["coach"] == "Boss" and p["rotation"]["avg_changes"] == 1.0
    assert p["rotation"]["n_short"] == 1 and p["rotation"]["n_long"] == 1
    assert sp.match_lines(_match([1]), 99) is None


def main() -> None:
    test_minutes_roles_and_rotation()
    print("squad_profile_test OK")


if __name__ == "__main__":
    main()
