"""cache_refresh_scheduler staleness helpers — they must read the real cache.

The regression this pins: cache_age_minutes() only ever looked at
`cache/sportybet_cache.json`, a single aggregate file that NOTHING in this
repository writes (searched 2026-09-16: the name appears once, on the line
that reads it, and the `cache/` directory does not exist). So it always
returned None, is_cache_fresh() always returned False, and the verification
gate could never count SportyBet as a corroborating source — the Architect's
own betting venue, and the ground truth for CLV.

That is the documented safe degradation (fall through to Tier-1-alone
corroboration) rather than a wrong answer, but it means fixtures that should
read VERIFIED read SINGLE_SOURCE, permanently.

Plain script, no pytest (repo convention):
    py -3.12 tests/cache_freshness_test.py
"""
from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import cache_refresh_scheduler as crs  # noqa: E402

FAILURES: list[str] = []


def check(label: str, got, want) -> None:
    if got == want:
        print(f"  [OK] {label}")
    else:
        print(f"  [FAIL] {label}: got {got!r}, want {want!r}")
        FAILURES.append(label)


def check_true(label, got):
    check(label, bool(got), True)


def check_false(label, got):
    check(label, bool(got), False)


class _Swap:
    """Point the module at a temp cache for the duration of a test."""

    def __init__(self, league_dir=None, legacy=None):
        self.league_dir = league_dir
        self.legacy = legacy

    def __enter__(self):
        self._old_dir = crs.LEAGUE_CACHE_DIR
        self._old_legacy = crs.CACHE_PATH
        crs.LEAGUE_CACHE_DIR = self.league_dir or Path("/nonexistent-league-dir")
        crs.CACHE_PATH = self.legacy or Path("/nonexistent-legacy.json")
        return self

    def __exit__(self, *a):
        crs.LEAGUE_CACHE_DIR = self._old_dir
        crs.CACHE_PATH = self._old_legacy


def _write_league(dirpath: Path, name: str, fetched_at: float, fixtures=None) -> None:
    dirpath.mkdir(parents=True, exist_ok=True)
    (dirpath / f"{name}.json").write_text(json.dumps({
        "fetched_at": fetched_at,
        "league": name.replace("_", " "),
        "country": "Testland",
        "fixtures": fixtures or [],
    }), encoding="utf-8")


def test_reads_the_per_league_cache() -> None:
    print("\ntest: freshness comes from the cache the builders actually write")

    with tempfile.TemporaryDirectory() as td:
        d = Path(td) / "fixtures"
        _write_league(d, "Test_League", time.time() - 300)   # 5 minutes old
        with _Swap(league_dir=d):
            age = crs.cache_age_minutes()
            check_true("an age is reported at all", age is not None)
            check_true("and it is about five minutes", 4.0 <= age <= 6.0)
            check_true("so the cache reads fresh", crs.is_cache_fresh())


def test_newest_file_defines_the_age() -> None:
    print("\ntest: the most recent build defines the age")

    # rebuild_cache writes every mapped league in one pass, so the newest
    # timestamp is when that pass ran. An older file beside it is a
    # competition that had no fixtures in the window — a quiet league, not a
    # stale read — and must not drag the whole cache to "stale".
    with tempfile.TemporaryDirectory() as td:
        d = Path(td) / "fixtures"
        _write_league(d, "Quiet_League", time.time() - 9 * 3600)   # 9 hours old
        _write_league(d, "Busy_League", time.time() - 120)         # 2 minutes old
        with _Swap(league_dir=d):
            age = crs.cache_age_minutes()
            check_true("age tracks the newest file", age is not None and age < 5.0)
            check_true("cache reads fresh", crs.is_cache_fresh())


def test_staleness_is_still_detected() -> None:
    print("\ntest: a genuinely old cache is still called stale")

    with tempfile.TemporaryDirectory() as td:
        d = Path(td) / "fixtures"
        _write_league(d, "Old_League", time.time() - 6 * 3600)     # 6 hours old
        with _Swap(league_dir=d):
            age = crs.cache_age_minutes()
            check_true("age is reported", age is not None and age > 300)
            check_false("but it is not fresh", crs.is_cache_fresh())


def test_absent_and_damaged_are_not_freshness() -> None:
    print("\ntest: absent or damaged is never read as fresh")

    # None must mean "too stale to trust", never "fine".
    with _Swap():
        check("no cache at all -> None", crs.cache_age_minutes(), None)
        check_false("and not fresh", crs.is_cache_fresh())

    with tempfile.TemporaryDirectory() as td:
        d = Path(td) / "fixtures"
        d.mkdir(parents=True)
        (d / "Broken.json").write_text("{not json", encoding="utf-8")
        with _Swap(league_dir=d):
            check("unparseable file -> None", crs.cache_age_minutes(), None)
            check_false("and not fresh", crs.is_cache_fresh())

    with tempfile.TemporaryDirectory() as td:
        d = Path(td) / "fixtures"
        _write_league(d, "NoStamp", time.time())
        # strip the timestamp
        p = d / "NoStamp.json"
        payload = json.loads(p.read_text(encoding="utf-8"))
        del payload["fetched_at"]
        p.write_text(json.dumps(payload), encoding="utf-8")
        with _Swap(league_dir=d):
            check("file with no fetched_at -> None", crs.cache_age_minutes(), None)

    # A damaged file must not hide a good one.
    with tempfile.TemporaryDirectory() as td:
        d = Path(td) / "fixtures"
        _write_league(d, "Good", time.time() - 60)
        (d / "Broken.json").write_text("{not json", encoding="utf-8")
        with _Swap(league_dir=d):
            age = crs.cache_age_minutes()
            check_true("a good file still counts", age is not None and age < 5.0)


def test_legacy_file_still_wins_when_present() -> None:
    print("\ntest: an older deployment's aggregate file is still honoured")

    from datetime import datetime, timezone
    with tempfile.TemporaryDirectory() as td:
        legacy = Path(td) / "sportybet_cache.json"
        legacy.write_text(json.dumps({
            "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        }), encoding="utf-8")
        d = Path(td) / "fixtures"
        _write_league(d, "Old_League", time.time() - 9 * 3600)
        with _Swap(league_dir=d, legacy=legacy):
            age = crs.cache_age_minutes()
            check_true("legacy timestamp is used", age is not None and age < 5.0)


if __name__ == "__main__":
    test_reads_the_per_league_cache()
    test_newest_file_defines_the_age()
    test_staleness_is_still_detected()
    test_absent_and_damaged_are_not_freshness()
    test_legacy_file_still_wins_when_present()

    print()
    if FAILURES:
        print(f"=== {len(FAILURES)} FAILURE(S) ===")
        for f in FAILURES:
            print(f"  - {f}")
        sys.exit(1)
    print("=== all passed ===")
