"""Fixture/odds caching tests — each cache is hit on the second call, so warm
runs pay no network. Mocked: no real keys, no real requests. The caches under
test are what took the daily run from ~52s to ~3s warm."""
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).parent.parent))

_tmp = Path(tempfile.mkdtemp(prefix="olp_xdv_fx_cache_test_"))


def _count_get(target, payload):
    """Patch requests.get under `target`; count real network calls; return
    (getter, n_network_calls_after_calls)."""
    calls = {"n": 0}

    class R:
        def raise_for_status(self):
            pass

        def json(self):
            return payload

    def fake_get(*a, **k):
        calls["n"] += 1
        return R()

    return patch(f"{target}.requests.get", side_effect=fake_get), calls


# --- 1. thesportsdb fixture cache (6h TTL) ---------------------------------
from data import thesportsdb_fixtures as tsdb
tsdb.CACHE_DIR = _tmp / "tsdb"
_p, _calls = _count_get("data.thesportsdb_fixtures", {"events": [
    {"strHomeTeam": "AAA", "strAwayTeam": "BBB",
     "dateEvent": "2026-08-05T19:00:00Z"}]})
with _p, patch.object(tsdb, "_get_key", return_value="fake"):
    f1, _ = tsdb.fetch_upcoming("Eredivisie", "2627", days_ahead=14)
    f2, _ = tsdb.fetch_upcoming("Eredivisie", "2627", days_ahead=14)
assert _calls["n"] == 1, "thesportsdb cache must serve the 2nd call"
assert f1 == f2, "cached fixtures must equal network fixtures"
print("1. thesportsdb fixture cache (2nd call free): OK")

# --- 2. fixtures-from-odds derived cache (6h TTL) ---------------------------
import pipeline.odds as odds
odds.FIXTURES_DIR = _tmp / "fio"
from data.football_data_source import MatchResult
fake_fx = [odds.FixtureOdds(
    league="Eredivisie", home_team="AAA", away_team="BBB",
    kickoff_utc="2026-08-05T19:00:00Z",
    home=odds.MarketQuote(2.0, "B1", 1, None), draw=odds.MarketQuote(3.5, "B1", 1, None),
    away=odds.MarketQuote(3.8, "B1", 1, None),
    over25=odds.MarketQuote(1.9, "B1", 1, None), under25=odds.MarketQuote(1.9, "B1", 1, None))]
_p, _calls = _count_get("pipeline.odds", {})
with _p, patch.object(odds, "fetch_odds", return_value=(fake_fx, [])):
    p1, d1, fl1 = odds.fixtures_from_odds("Eredivisie", days_ahead=14)
    p2, d2, fl2 = odds.fixtures_from_odds("Eredivisie", days_ahead=14)
assert _calls["n"] == 0, "derived list must come from cache, no network"
assert p1 == p2 == [("AAA", "BBB")], "derived pairs must be deduped + stable"
print("2. fixtures-from-odds derived cache (2nd call free): OK")

# --- 3. api-football plan-error cache (7d TTL for a deterministic failure) --
from data import fixtures_source as fsrc
fsrc.CACHE_DIR = _tmp / "af"
_p, _calls = _count_get("data.fixtures_source",
                        {"errors": {"plan": "Free plans are limited to seasons 2022-2024"}})
with _p, patch.object(fsrc, "_get_key", return_value="fake"), \
        patch.object(fsrc, "resolve_league_id", return_value=179):
    for _ in range(2):
        try:
            fsrc.fetch_upcoming("Eredivisie", 2026, days_ahead=0)
            raise AssertionError("plan-restricted call must raise")
        except RuntimeError:
            pass
assert _calls["n"] == 1, "plan error must be cached after the first call"
# a success cache also works
_p, _calls = _count_get("data.fixtures_source",
                        {"response": [{"fixture": {"date": "2026-08-05T19:00:00Z"},
                                       "teams": {"home": {"name": "AAA"},
                                                 "away": {"name": "BBB"}}}]})
with _p, patch.object(fsrc, "_get_key", return_value="fake"), \
        patch.object(fsrc, "resolve_league_id", return_value=179):
    f3 = fsrc.fetch_upcoming("Eredivisie", 2026, days_ahead=1)
    f4 = fsrc.fetch_upcoming("Eredivisie", 2026, days_ahead=1)
assert _calls["n"] == 1 and len(f3) == 1 and f3[0].home_team == "AAA"
assert f3 == f4
print("3. api-football plan-error + success cache (2nd call free): OK")

# --- 4. football-data results freshness (the Phase-3-gate critical fix) -----
import os
import time as _time
import data.football_data_source as fds

assert fds._season_is_live("2627") is True, "current season must be live"
assert fds._season_is_live("2526") is False, "completed season must be stable"
print("4a. live vs completed season detection: OK")

_cd = _tmp / "fd"
_cd.mkdir()
_old = _time.time() - 12 * 3600  # 12h old > 6h live-season TTL
_f = _cd / "AA_2627.csv"
_f.write_text("Date,HomeTeam,AwayTeam,FTHG,FTAG,FTR\n", encoding="utf-8")
os.utime(_f, (_old, _old))
_fetch_calls = {"n": 0}

def _new_fetch(league, season):
    _fetch_calls["n"] += 1
    return "Date,HomeTeam,AwayTeam,FTHG,FTAG,FTR\n05/08/2026,AAA,BBB,2,1,H\n"

with patch.object(fds, "fetch_csv_text", side_effect=_new_fetch):
    _res, _ = fds.load_league("AA", "2627", cache_dir=_cd)
assert _fetch_calls["n"] == 1, "stale live-season cache must refresh"
assert any(r.fthg == 2 for r in _res), "new result must be parsed"
print("4b. stale live-season cache refreshes + new result parsed: OK")

# a failed refresh must KEEP the stale snapshot, never lose data
_f2 = _cd / "BB_2627.csv"
_f2.write_text("Date,HomeTeam,AwayTeam,FTHG,FTAG,FTR\n", encoding="utf-8")
os.utime(_f2, (_old, _old))

def _fail_fetch(league, season):
    raise RuntimeError("404 — file removed between seasons")

with patch.object(fds, "fetch_csv_text", side_effect=_fail_fetch):
    _res2, _ = fds.load_league("BB", "2627", cache_dir=_cd)
assert _f2.exists(), "failed refresh must keep the stale snapshot"
print("4c. failed refresh keeps the stale snapshot (no data loss): OK")

# completed seasons keep their cache (30-day TTL) — the run stays fast
_fetch_calls["n"] = 0
_f3 = _cd / "CC_2526.csv"
_f3.write_text("Date,HomeTeam,AwayTeam,FTHG,FTAG,FTR\n", encoding="utf-8")
os.utime(_f3, (_old, _old))
with patch.object(fds, "fetch_csv_text", side_effect=_new_fetch):
    fds.load_league("CC", "2526", cache_dir=_cd)
assert _fetch_calls["n"] == 0, "completed-season cache must NOT refresh"
print("4d. completed-season cache stays cached (speed preserved): OK")

print("\n✅ ALL FIXTURE CACHE TESTS PASSED")
