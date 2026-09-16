"""cache_refresh_scheduler.py — keeps the SportyBet cache fresh on a
regular cadence, and makes staleness a CHECKABLE FACT instead of a
silent assumption. This is what would have caught the Aug 31-Sep 2
stale cache before it caused a verification-gate failure days later.

Two separate things, on purpose:
  1. refresh_cache() — actually re-fetches, using the resilient TLS-
     ladder fetcher so the refresh job itself doesn't die on the same
     redirect-loop bug SportyBet scraping already has.
  2. cache_age_minutes() / is_cache_fresh() — a freshness CHECK any
     other code (the verification gate, produce_bet) can call before
     trusting the cache, rather than trusting it blindly.

Run this on a schedule (Task Scheduler, every 12h or every 60 min,
your call) SEPARATELY from the main pipeline — refreshing shouldn't
depend on a board being generated, and a board being generated
shouldn't have to wait on a live scrape if a recent cache already exists.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Add the olp_xdv directory to the path so we can import from olp_xdv_reliability
sys.path.insert(0, str(Path(__file__).parent))

# NOTE: olp_xdv_reliability has never been committed to this repository -- no
# commit in history adds it, and it is not gitignored, so it exists only as an
# untracked directory on whichever machine wrote refresh_cache(). Its two names
# are used ONLY inside refresh_cache(); the staleness helpers below
# (cache_age_minutes / is_cache_fresh) do not touch them.
#
# Importing it at module scope therefore broke an unrelated consumer:
# booking/verify_fixtures.py imports only cache_age_minutes and is_cache_fresh
# from here, and was dying on an import it never needed. The import now lives
# in refresh_cache(), which genuinely cannot work without it and says so
# plainly when it is absent.

# Legacy single-file cache. Kept as the first place we look so an older
# deployment that really does write it keeps working -- but nothing in this
# repository writes it. Searched 2026-09-16: "sportybet_cache.json" appears
# exactly once, on this line, and the `cache/` directory does not exist.
CACHE_PATH = Path(__file__).resolve().parent / "cache" / "sportybet_cache.json"

# Where the cache ACTUALLY lives: one file per league, written by
# booking/rebuild_cache.py and booking/sportybet_discovery.py, each carrying a
# `fetched_at` epoch float.
#
# cache_age_minutes() only ever read CACHE_PATH, so it always returned None,
# so is_cache_fresh() always returned False, so the verification gate has
# never once been able to count SportyBet as a corroborating source -- the
# Architect's own betting venue, and the ground truth for CLV. Every fixture
# fell through to Tier-1-alone corroboration, which is the documented safe
# behaviour but means fixtures that should read VERIFIED read SINGLE_SOURCE.
LEAGUE_CACHE_DIR = (Path(__file__).resolve().parent / "data" / "cache"
                    / "sportybet" / "fixtures")

DEFAULT_MAX_AGE_MINUTES = 60  # matches the existing "60-minute V2 recency cap" already in use


def refresh_cache(url: str, fallback_fns: list[tuple[str, callable]] | None = None) -> bool:
    """
    Refreshes the cache using SportyBet first, with optional fallbacks
    (e.g. an API-Football pull for the same data) so a scrape failure
    doesn't leave the cache stuck at whatever age it was.

    Writes the fetch timestamp INTO the cache file itself — this is
    the piece that was missing. A cache with no recorded fetch time
    can't be checked for staleness; it can only be trusted or not.
    """
    try:
        from olp_xdv_reliability.providers import ProviderChain, fetch_sportybet_page
    except ModuleNotFoundError as exc:
        print(
            "cache_refresh: olp_xdv_reliability is not installed in this "
            f"checkout ({exc}); the cache was NOT refreshed. Its age is "
            "whatever it already was -- do not read this as 'fresh'.",
            file=sys.stderr,
        )
        return False

    chain_providers = [("sportybet", lambda: fetch_sportybet_page(url))]
    if fallback_fns:
        chain_providers.extend(fallback_fns)

    chain = ProviderChain(chain_providers)
    try:
        result = chain.call()
    except Exception as exc:  # noqa: BLE001
        print(f"cache_refresh: ALL providers failed, cache NOT updated: {exc}", file=sys.stderr)
        return False

    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_used": result.provider_used,
        "degraded": result.degraded,
        "data": result.value if isinstance(result.value, (dict, list, str)) else str(result.value),
    }
    CACHE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"cache_refresh: updated via '{result.provider_used}' "
          f"({'degraded — fallback used' if result.degraded else 'primary source'})")
    return True


def cache_age_minutes() -> float | None:
    """Minutes since the SportyBet cache was last built, or None if unknown.

    None means 'too stale to trust', never 'fine'.

    Checks the legacy single-file cache first, then the per-league directory
    that the builders actually write. The age reported is that of the MOST
    RECENT league file: rebuild_cache writes every mapped league in one pass,
    so the newest timestamp is when that pass ran. An older file alongside it
    is a league that had no fixtures in the last window, which is a normal
    quiet competition rather than a stale read.
    """
    if CACHE_PATH.exists():
        try:
            payload = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
            fetched_at = datetime.fromisoformat(payload["fetched_at_utc"])
            age = datetime.now(timezone.utc) - fetched_at
            return age.total_seconds() / 60
        except (json.JSONDecodeError, KeyError, ValueError):
            pass  # fall through to the per-league cache

    if not LEAGUE_CACHE_DIR.is_dir():
        return None

    newest = None
    for path in LEAGUE_CACHE_DIR.glob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            fetched_at = float(payload["fetched_at"])
        except (json.JSONDecodeError, KeyError, ValueError, TypeError, OSError):
            continue      # a damaged file is not evidence of freshness
        if newest is None or fetched_at > newest:
            newest = fetched_at

    if newest is None:
        return None
    return max(0.0, (time.time() - newest) / 60)


def is_cache_fresh(max_age_minutes: int = DEFAULT_MAX_AGE_MINUTES) -> bool:
    """
    THE function the verification gate should call. If this returns
    False, the gate should NOT hard-fail the whole pipeline — it should
    fall through to Tier-1-alone corroboration, per the framework's own
    rule that a single Tier-1 source can satisfy verification without
    SportyBet at all.
    """
    age = cache_age_minutes()
    if age is None:
        print("cache freshness check: no valid cache timestamp found — treating as stale.", file=sys.stderr)
        return False
    fresh = age <= max_age_minutes
    if not fresh:
        print(f"cache freshness check: cache is {age:.0f} min old "
              f"(limit {max_age_minutes} min) — STALE.", file=sys.stderr)
    return fresh


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="https://sportybet.com.ng/ng/sport/football")
    parser.add_argument("--check-only", action="store_true", help="Just report current cache age, don't refresh")
    args = parser.parse_args()

    if args.check_only:
        age = cache_age_minutes()
        if age is None:
            print("No valid cache found.")
        else:
            print(f"Cache age: {age:.0f} minutes (fresh: {is_cache_fresh()})")
    else:
        refresh_cache(args.url)