"""engine/squad_depth.py + its use in engine/team_news.assess (Architect 2026-11-04: rotated or
long-absent players with good cover must not read as a weakened team)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine import squad_depth as sd  # noqa: E402
from engine import team_news as tn  # noqa: E402

PLAYERS = [
    {"id": 1, "name": "Long Out", "value": 60e6, "group": "ATT", "injured": True},
    {"id": 2, "name": "Rotated Mid", "value": 80e6, "group": "MID", "injured": False},
    {"id": 3, "name": "Bench Mid", "value": 90e6, "group": "MID", "injured": False},
    {"id": 4, "name": "Key Keeper", "value": 40e6, "group": "GK", "injured": False},
    {"id": 5, "name": "Starter Mid", "value": 120e6, "group": "MID", "injured": False},
]
RECENT = [{2, 4, 5}, {2, 4, 5}, {4, 5}, {2, 4, 5}, {4, 5}]       # newest last


def test_already_out_rotation_and_cover():
    missing = [{"id": 1, "name": "Long Out", "value": 60e6}, {"id": 2, "name": "Rotated Mid", "value": 80e6}]
    r = sd.assess(missing, 500e6, PLAYERS, RECENT, xi_ids={4, 5})
    rows = {p["name"]: p for p in r["players"]}
    assert rows["Long Out"]["weight"] == 0 and "priced in" in rows["Long Out"]["reason"]
    assert rows["Rotated Mid"]["cover"] == "Bench Mid" and rows["Rotated Mid"]["weight"] == 0
    assert r["adjusted_share"] == 0


def test_regular_without_cover_counts_in_full():
    missing = [{"id": 4, "name": "Key Keeper", "value": 40e6}]
    r = sd.assess(missing, 400e6, PLAYERS, RECENT, xi_ids={5})
    assert r["players"][0]["weight"] == 1.0 and abs(r["adjusted_share"] - 40 / 440) < 1e-9


def test_cover_never_a_starter_and_used_once():
    missing = [{"id": 2, "name": "Rotated Mid", "value": 80e6}]
    r = sd.assess(missing, 500e6, PLAYERS, RECENT, xi_ids={3, 4, 5})      # the bench mid starts tonight
    assert r["players"][0]["cover"] is None and r["adjusted_share"] > 0


def test_team_news_reads_the_adjusted_share():
    side = {"name": "Madrid", "missing_share": 0.25, "adjusted_share": 0.05, "xi_value": 1,
            "missing": [{"name": "Rodrygo"}], "depth": {"players": [{"name": "Rodrygo", "reason": "already out"}]}}
    news = {"lineup_type": "confirmed", "home": {"name": "AEK", "missing_share": 0.0, "missing": []}, "away": side}
    r = tn.assess("SB:37|total=1.5|Away & Over 1.5", news)
    assert r["level"] == "OK" and "after squad depth" in r["note"]
    side["adjusted_share"] = None
    assert tn.assess("SB:37|total=1.5|Away & Over 1.5", news)["level"] == "RISK"   # no depth read: raw rules


def test_fotmob_parsers():
    team = {"squad": {"squad": [{"title": "coach", "members": [{"id": 9}]},
                                {"title": "midfielders", "members": [{"id": 2, "name": "A", "transferValue": 5,
                                                                      "positionIdsDesc": "CM,DM", "injury": None}]}]},
            "fixtures": {"allFixtures": {"fixtures": [{"id": i, "status": {"finished": i < 7}} for i in range(10)]}}}
    assert sd.squad(team) == [{"id": 2, "name": "A", "value": 5, "group": "MID", "injured": False}]
    assert sd.recent_match_ids(team) == [2, 3, 4, 5, 6]
    det = {"content": {"lineup": {"homeTeam": {"id": 7, "starters": [{"id": 1}]}, "awayTeam": {"id": 8}}}}
    assert sd.starters_of(det, 7) == {1} and sd.starters_of(det, 8) == set()


def main() -> None:
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("squad_depth_test OK")


if __name__ == "__main__":
    main()
