"""engine/wb_team_news.py — record-only NCAA team news per pick (framework#391). Offline: a fake ESPN."""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine import wb_team_news as wtn  # noqa: E402

NOW = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)
KO = NOW + timedelta(hours=5)
KOS = KO.strftime("%Y-%m-%dT%H:%M:%SZ")


def _box(star_min=30):
    ath = [{"athlete": {"id": "9", "displayName": "Star"}, "stats": [str(star_min), "20"], "starter": True}]
    ath += [{"athlete": {"id": str(i), "displayName": f"P{i}"}, "stats": ["20", "8"]} for i in range(1, 6)]
    return {"boxscore": {"players": [{"team": {"abbreviation": "HOM"},
                                      "statistics": [{"keys": ["minutes", "points"], "athletes": ath}]}]}}


def fake(star_listed: bool, home_roster_ok: bool = True):
    def get(url):
        if "scoreboard" in url:
            return {"events": [{"id": "g1", "date": KO.strftime("%Y-%m-%dT%H:%MZ"), "competitions": [{"competitors": [
                {"homeAway": "home", "team": {"id": "1", "abbreviation": "HOM", "displayName": "Home State",
                                              "shortDisplayName": "Home State", "location": "Home State", "name": "H"}},
                {"homeAway": "away", "team": {"id": "2", "abbreviation": "AWY", "displayName": "Away Tech",
                                              "shortDisplayName": "Away Tech", "location": "Away Tech", "name": "A"}}]}]}]}
        if url.endswith("/teams/1/roster"):
            if not home_roster_ok:
                return None
            inj = [{"status": "Out"}] if star_listed else []
            return {"athletes": [{"id": "9", "displayName": "Star", "injuries": inj}]}
        if url.endswith("/roster"):
            return {"athletes": [{"id": "70", "displayName": "X", "injuries": []}]}
        if "/schedule" in url:
            return {"events": [{"id": f"p{i}", "date": (NOW - timedelta(days=i)).strftime("%Y-%m-%dT%H:%MZ"),
                                "competitions": [{"status": {"type": {"completed": True}}, "competitors": [
                                    {"homeAway": "home", "team": {"abbreviation": "HOM"}},
                                    {"homeAway": "away", "team": {"abbreviation": "ZZZ"}}]}]} for i in range(1, 6)]}
        if "summary" in url:
            return _box()
        return None
    return get


PICK = {"sb_event_id": "sr:1", "comp": "NCAA", "home": "Home State", "away": "Away Tech", "ko": KOS,
        "pick": "Home State to win", "market_id": "219", "outcome": "Home"}


def test_star_out_hurts_the_pick_and_is_recorded():
    with tempfile.TemporaryDirectory() as t:
        out = wtn.update([PICK], NOW, "2026-11-10", Path(t), fake(True))
        assert out[0]["verdict"] == "HURT" and "Star" in out[0]["note"]
        assert (Path(t) / "wb_news_2026-11-10.jsonl").exists()
        assert out[0]["absence"]["home"]["adj_share"] > 0.12


def test_nobody_listed_is_neutral_and_says_coverage_is_thin():
    with tempfile.TemporaryDirectory() as t:
        out = wtn.update([PICK], NOW, "2026-11-10", Path(t), fake(False))
        assert out[0]["verdict"] == "NEUTRAL" and "not proof" in out[0]["note"]


def test_unreadable_roster_is_pending_not_guessed():
    with tempfile.TemporaryDirectory() as t:
        out = wtn.update([PICK], NOW, "2026-11-10", Path(t), fake(False, home_roster_ok=False))
        assert out[0]["verdict"] == "PENDING"


def test_non_ncaa_league_is_pending_no_feed():
    with tempfile.TemporaryDirectory() as t:
        out = wtn.update([{**PICK, "comp": "EuroLeague"}], NOW, "2026-11-10", Path(t), fake(True))
        assert out[0]["verdict"] == "PENDING" and "no injury feed" in out[0]["note"]


def test_started_game_skipped_and_unchanged_not_rerecorded():
    with tempfile.TemporaryDirectory() as t:
        d = Path(t)
        old = {**PICK, "sb_event_id": "sr:2", "ko": (NOW - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")}
        assert len(wtn.update([PICK, old], NOW, "2026-11-10", d, fake(True))) == 1
        assert wtn.update([PICK], NOW, "2026-11-10", d, fake(True)) == []      # same verdict: no new line
        assert len((d / "wb_news_2026-11-10.jsonl").read_text().splitlines()) == 1


def test_run_alerts_once_on_hurt():
    with tempfile.TemporaryDirectory() as t:
        d = Path(t)
        (d / "wb_2026-11-10.json").write_text(json.dumps({"date": "2026-11-10", "picks": [PICK]}), encoding="utf-8")
        first = wtn.run(NOW, d, fake(True))
        assert len(first) == 1 and "NEWS HURT" in first[0]
        assert wtn.run(NOW, d, fake(True)) == []


def main() -> None:
    for n, f in sorted(globals().items()):
        if n.startswith("test_"):
            f()
    print("wb_team_news_test OK")


if __name__ == "__main__":
    main()
