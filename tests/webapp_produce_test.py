"""Date-filter unit test for webapp.produce.search_fixtures.

The admin "produce for that day" flow narrows the fetched window to exactly
the chosen day. get_fixtures is mocked so this stays offline and deterministic."""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from webapp.produce import search_fixtures

_FIXTURES = {
    "fixtures": [("Nijmegen", "Telstar"), ("Zwolle", "Ajax"), ("Sparta", "Feyenoord")],
    "dates": {
        ("Nijmegen", "Telstar"): "2026-08-09",
        ("Zwolle", "Ajax"): "2026-08-10",
        ("Sparta", "Feyenoord"): "2026-08-09",
    },
}


def _fake_get_fixtures(league, fixtures_season, days_ahead=14, api_football_season=None):
    return _FIXTURES


with patch("data.multi_source_concrete.get_fixtures", side_effect=_fake_get_fixtures):
    # Whole window (no date) keeps every fixture
    res = search_fixtures(league="Eredivisie")
    assert res["ok"], res
    fixtures = res["leagues"][0]["fixtures"]
    assert len(fixtures) == 3
    print("1. whole window (no date) keeps all fixtures: OK")

    # A chosen day keeps only that day's fixtures
    res = search_fixtures(league="Eredivisie", date="2026-08-09")
    fixtures = res["leagues"][0]["fixtures"]
    assert {f["home"] for f in fixtures} == {"Nijmegen", "Sparta"}, fixtures
    assert all(f["date"] == "2026-08-09" for f in fixtures)
    print("2. date filter keeps only that day's fixtures: OK")

    # A day with no fixtures returns an empty leagues list (honest, never guessed)
    res = search_fixtures(league="Eredivisie", date="2026-08-11")
    assert res["ok"] and res["leagues"] == [], res
    print("3. empty day -> no leagues (honest, not guessed): OK")

    # Search query + date combine
    res = search_fixtures(league="Eredivisie", date="2026-08-09", query="Sparta")
    fixtures = res["leagues"][0]["fixtures"]
    assert [f["home"] for f in fixtures] == ["Sparta"], fixtures
    print("4. query + date combine: OK")

print("\n[OK] ALL PRODUCE DATE-FILTER TESTS PASSED")
