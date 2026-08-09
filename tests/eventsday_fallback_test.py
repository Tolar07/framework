"""Eventsday fallback test — the daily board must READ today's cup qualifiers
even when the TSDB SEASON feed lags weeks behind (verified 2026-08-06: Europa
League 4481 eventsseason showed July-only events while the real Aug 6
qualifiers were invisible). fetch_today pulls the eventsday feed, and the
orchestrator uses it as a fallback when the season feed has nothing in the
TODAY-only window."""
import sys
import tempfile
import datetime
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).parent.parent))

from data import thesportsdb_fixtures as tsdb

_tmp = Path(tempfile.mkdtemp(prefix="olp_xdv_evtday_"))
DAY = "2026-08-06"

EVENTS = {
    "events": [
        {"strHomeTeam": "Jagiellonia Białystok", "strAwayTeam": "Rangers",
         "strTime": "16:00", "strStatus": "NS"},
        {"strHomeTeam": "Lech Poznań", "strAwayTeam": "KÍ Klaksvík",
         "strTime": "17:00", "strStatus": "NS"},
        # already played — must be excluded (not upcoming)
        {"strHomeTeam": "Lincoln Red Imps", "strAwayTeam": "Omonia Nicosia",
         "strTime": "17:00", "strStatus": "FT", "intHomeScore": "1",
         "intAwayScore": "0"},
        # missing team name — skipped, never reconstructed (HR35)
        {"strHomeTeam": "", "strAwayTeam": "Nobody", "strTime": "18:00",
         "strStatus": "NS"},
    ]
}


def _fake_get(*a, **k):
    class R:
        status_code = 200
        def raise_for_status(self):
            pass
        def json(self):
            return EVENTS
    return R()


# --- 1. fetch_today returns only the real upcoming fixtures ------------------
with patch("data.retry.request", side_effect=_fake_get):
    fx = tsdb.fetch_today("Europa League", DAY)
assert len(fx) == 2, f"only 2 upcoming (played + missing-name excluded), got {len(fx)}"
names = {(f.home_team, f.away_team) for f in fx}
# The Europa League aliases normalise the feed spellings to the model keys,
# so the mapped names are what reach the board.
assert ("Jagiellonia", "Rangers") in names, names
assert ("Lech Poznan", "KÍ Klaksvík") in names, names
assert all(f.date == DAY for f in fx)
print("1. fetch_today: upcoming only, played + malformed excluded: OK")

# --- 2. unmapped league raises, never guessed ---------------------------------
try:
    with patch("data.retry.request", side_effect=_fake_get):
        tsdb.fetch_today("Conference League", DAY)
    assert False, "unmapped league must raise (HR35)"
except ValueError:
    pass
print("2. unmapped league raises, never guessed: OK")

# --- 3. orchestrator falls back to eventsday when the season feed lags -------
import orchestrator
from brain.store import Brain

b = Brain(_tmp / "t.db")

# Make the season feed return nothing in the window: patch fetch_upcoming to
# return [], and confirm scan_one_league still lands today's eventsday rows.
with patch("data.retry.request", side_effect=_fake_get), \
     patch("data.thesportsdb_fixtures._read_cache", return_value=[]), \
     patch("data.thesportsdb_fixtures.fetch_today",
           wraps=tsdb.fetch_today) as fetch_today_spy:
    # avoid a real fit: give the scan a cross-league fallback is heavy, so
    # instead verify the fixture-discovery step yields the eventsday pairs.
    from data.thesportsdb_fixtures import as_pairs
    pairs = as_pairs(tsdb.fetch_today("Europa League", DAY))
    assert pairs, "eventsday pairs must be non-empty"

# Prove the orchestrator's fallback block actually calls fetch_today by
# checking it fires when fetch_upcoming is empty and days_ahead==0.
with patch("data.retry.request", side_effect=_fake_get), \
     patch("data.thesportsdb_fixtures.fetch_today", side_effect=_fake_get) if False else patch(
         "data.thesportsdb_fixtures.fetch_today", return_value=tsdb.fetch_today(
             "Europa League", DAY)) as spy:
    with patch("orchestrator.tsdb.fetch_upcoming", return_value=([], [])):
        with patch("orchestrator.tsdb.fetch_today",
                   wraps=tsdb.fetch_today) as orch_spy:
            slice_, flags = orchestrator.scan_one_league(
                "Europa League", "2526", brain=b, stats={}, days_ahead=0)
            assert orch_spy.called, "orchestrator must call fetch_today when season feed is empty"
            assert any("eventsday" in f for f in flags), \
                f"flag must report the eventsday fallback: {flags}"

print("3. orchestrator falls back to eventsday when the season feed lags: OK")

print("\n✅ EVENTSDAY FALLBACK WORKS — today's cup qualifiers reach the board.")
