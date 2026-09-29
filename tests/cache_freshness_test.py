"""
Cache-freshness test for data.football_data_source.load_league.

Regression guard for the Phase 3 gate stalling at 0: a cache file that already
existed was read forever, with no age check, so grade_open_legs() kept settling
against a results table frozen before the latest fixtures were published. The
legs never graded, log_close() never ran, and legs_with_clv stayed 0.

Plain-script style (matches the other tests): no pytest, no network — the
source fetch is stubbed so this is deterministic and offline.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.football_data_source as fds

# A minimal Extra-schema CSV (Poland/POL layout) with one played 2026/2027 row.
FRESH_CSV = (
    "Country,League,Season,Date,Home,Away,HG,AG,Res\n"
    "Poland,Ekstraklasa,2026/2027,11/09/2026,Rakow,Motor Lublin,2,1,H\n"
)
STALE_CSV = (
    "Country,League,Season,Date,Home,Away,HG,AG,Res\n"
    "Poland,Ekstraklasa,2026/2027,01/08/2026,Old,Fixture,0,0,D\n"
)


def _run(tmp: Path) -> None:
    fetches = {"n": 0}

    def fake_fetch(league, season):
        fetches["n"] += 1
        return FRESH_CSV

    fds.fetch_csv_text = fake_fetch  # stub network out
    cache_file = tmp / "Ekstraklasa_all.csv"

    # 1. No cache -> fetches, writes cache, parses the fresh row.
    res, _ = fds.load_league("Ekstraklasa", "2627", cache_dir=tmp)
    assert fetches["n"] == 1, "first load should fetch"
    assert any(r.home_team == "Rakow" for r in res), "fresh row should parse"

    # 2. Fresh cache (just written) -> served from disk, NO refetch.
    res, _ = fds.load_league("Ekstraklasa", "2627", cache_dir=tmp)
    assert fetches["n"] == 1, "fresh cache must not refetch"

    # 3. Stale cache (mtime aged past the TTL) -> refetch replaces it. This is
    #    the exact bug: before the fix, an aged cache was still read verbatim.
    cache_file.write_text(STALE_CSV, encoding="utf-8")
    old = time.time() - (fds.CACHE_MAX_AGE_SECONDS + 60)
    import os
    os.utime(cache_file, (old, old))
    res, _ = fds.load_league("Ekstraklasa", "2627", cache_dir=tmp)
    assert fetches["n"] == 2, "stale cache must refetch"
    assert any(r.home_team == "Rakow" for r in res), "refetch should supersede stale row"
    assert all(r.home_team != "Old" for r in res), "stale row must be gone after refetch"

    # 4. Refetch failure with a stale cache present -> fall back to stale, no raise.
    cache_file.write_text(STALE_CSV, encoding="utf-8")
    os.utime(cache_file, (old, old))

    def boom(league, season):
        fetches["n"] += 1
        raise RuntimeError("network down")

    fds.fetch_csv_text = boom
    res, _ = fds.load_league("Ekstraklasa", "2627", cache_dir=tmp)
    assert any(r.home_team == "Old" for r in res), "must fall back to stale cache on fetch failure"


def main() -> None:
    import tempfile
    orig = fds.fetch_csv_text
    try:
        with tempfile.TemporaryDirectory() as d:
            _run(Path(d))
    finally:
        fds.fetch_csv_text = orig
    print("cache_freshness_test: OK")


if __name__ == "__main__":
    main()
