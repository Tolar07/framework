"""Unit tests for fixtures_agent.py — date filtering, source pipeline, verification stamp."""

from __future__ import annotations

import json
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import fixtures_agent as fa


def test_flashscore_line_to_date_resolves_year_against_requested_date():
    """_flashscore_line_to_date should resolve year against the requested date,
    not datetime.now(), so arbitrary dates work."""
    # "21.08. 20:00" with target 2026-08-21 -> should resolve to 2026-08-21
    result = fa._flashscore_line_to_date("21.08. 20:00", target_date="2026-08-21")
    assert result == "2026-08-21", f"expected 2026-08-21, got {result!r}"
    # Wrong month/day should return empty (can't resolve)
    result_bad = fa._flashscore_line_to_date("21.08. 20:00", target_date="2026-09-05")
    assert result_bad == "", f"expected empty for non-matching date, got {result_bad!r}"


def test_flashscore_fetch_filters_to_requested_date():
    """fetch_flashscore should only return fixtures for the requested date."""
    with tempfile.TemporaryDirectory() as td:
        feed_dir = Path(td) / "data" / "live_odds"
        feed_dir.mkdir(parents=True)
        feed = feed_dir / "flashscore_odds_20260812_120000.jsonl"
        # Write fixtures for different dates
        feed.write_text(
            json.dumps({"type": "match_1x2", "home_team": "Arsenal", "away_team": "Coventry", "match_datetime": "21.08. 20:00"}) + "\n" +
            json.dumps({"type": "match_1x2", "home_team": "Chelsea", "away_team": "Liverpool", "match_datetime": "22.08. 15:00"}) + "\n" +
            json.dumps({"type": "match_1x2", "home_team": "ManUtd", "away_team": "Tottenham", "match_datetime": "23.08. 17:30"}) + "\n",
            encoding="utf-8"
        )

        with patch.object(fa, "_find_flashscore_feed", return_value=feed_dir):
            # Request 2026-08-21 — should only get Arsenal vs Coventry
            rows = fa.fetch_flashscore("2026-08-21")

        assert len(rows) == 1, f"expected 1 row for 2026-08-21, got {len(rows)}"
        assert rows[0]["home"] == "Arsenal"
        assert rows[0]["away"] == "Coventry"
        assert rows[0]["kickoff_date"] == "2026-08-21"


def test_sportinglife_returns_empty():
    """fetch_sportinglife currently returns [] — dead code (pipeline calls removed)."""
    rows = fa.fetch_sportinglife("2026-08-21")
    assert rows == [], "Sporting Life should return empty (dead code)"


def test_apply_verification_requires_two_sources():
    """Rows should only be marked verified when >=2 sources agree on (home, away, date)."""
    all_rows = [
        {"home": "Arsenal", "away": "Coventry", "league": "Premier League", "kickoff": "20:00", "source": "FlashScore", "kickoff_date": "2026-08-21"},
        {"home": "Arsenal", "away": "Coventry", "league": "Premier League", "kickoff": "20:00", "source": "SportyBet cache", "kickoff_date": "2026-08-21", "odds_1": 2.0, "odds_x": 3.5, "odds_2": 3.8},
        {"home": "Chelsea", "away": "Liverpool", "league": "Premier League", "kickoff": "15:00", "source": "FlashScore", "kickoff_date": "2026-08-21"},
    ]
    fa._apply_verification(all_rows)
    # Arsenal vs Coventry: 2 sources -> verified
    assert all_rows[0]["verified"] is True
    assert all_rows[1]["verified"] is True
    # Chelsea vs Liverpool: 1 source -> not verified
    assert all_rows[2]["verified"] is False


def test_calendar_uses_date_objects_not_strings():
    """check_league_calendar and verify_league_fixture should use date objects for comparison."""
    active, not_started = fa.check_league_calendar("2026-08-10")
    # "2026-08-10" < "2026-08-14" (many leagues start) should correctly identify not_started
    assert "Premier League" in not_started, "Premier League starts 2026-08-21, must be not_started on 2026-08-10"
    assert isinstance(active, set)
    assert isinstance(not_started, set)
    # verify_league_fixture should flag pre-season
    ok, reason = fa.verify_league_fixture("Premier League", "2026-08-10")
    assert ok is False, "Premier League fixture on 2026-08-10 must be implausible"


if __name__ == "__main__":
    test_flashscore_line_to_date_resolves_year_against_requested_date()
    print("test_flashscore_line_to_date_resolves_year_against_requested_date: OK")

    test_flashscore_fetch_filters_to_requested_date()
    print("test_flashscore_fetch_filters_to_requested_date: OK")

    test_sportinglife_returns_empty()
    print("test_sportinglife_returns_empty: OK")

    test_apply_verification_requires_two_sources()
    print("test_apply_verification_requires_two_sources: OK")

    test_calendar_uses_date_objects_not_strings()
    print("test_calendar_uses_date_objects_not_strings: OK")

    print("\n[OK] ALL FIXTURES AGENT TESTS PASSED")