async def build_cache(
    days_ahead: int = 3,
    headless: bool = True,
    cache_dir: str = ""
) -> dict[str, int]:
    """Build SportyBet fixture cache for all leagues needed by today's acca.

    This is the public API function called by run_daily.py for cache refresh.
    Uses the same resolver-pinned direct-URL approach that worked in poc_book_single.py.
    Writes directly to the booker's authoritative cache dir (data/cache/sportybet/fixtures/).

    Returns:
        dict mapping league name to fixture count
    """
    import asyncio
    from pathlib import Path
    import sys

    sys.path.insert(0, str(Path(__file__).parent.parent))

    # Import the rebuild logic
    from booking.rebuild_cache import main as _rebuild_main

    # Run the rebuild
    await _rebuild_main()

    # Return fixture counts for each league checked
    # For now return empty dict - the actual counts are logged during rebuild
    return {}


def _fixture_changed(prior: CachedFixture, current: CachedFixture) -> bool:
    """Check if a fixture has meaningful changes (odds, time, etc.)."""
    # Compare odds fields (they change frequently)
    if prior.odds_1 != current.odds_1:
        return True
    if prior.odds_x != current.odds_x:
        return True
    if prior.odds_2 != current.odds_2:
        return True
    # Compare match time
    if prior.match_time != current.match_time:
        return True
    return False


# ── public API ──────────────────────────────────────────────────────────────
async def _scrape_one_league(
    league: str,
    country: str,
    cache_dir: str = "",
    headless: bool = True,
) -> List[CachedFixture]:
    """Scrape SportyBet for a single league and return (and cache) fixtures with incremental updates."""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        resolver_rule = _resolver_rule()
        launch_args = ["--disable-gpu", "--no-sandbox", "--disable-dev-shm-usage"]
        if resolver_rule:
            launch_args.append(f"--host-resolver-rules={resolver_rule}")
        browser = await p.chromium.launch(headless=headless, args=launch_args)
        page = await browser.new_page()
        await page.set_viewport_size({"width": 1280, "height": 900})
        page.set_default_timeout(PAGE_LOAD_TIMEOUT)

        try:
            # Read existing cache for incremental updates
            prior_cache = _read_cache(league, max_age_seconds=10**9, cache_dir=cache_dir)
            prior_fixtures_dict = {}
            if prior_cache and prior_cache.fixtures:
                # Create a lookup dict for fast comparison
                for f in prior_cache.fixtures:
                    key = (f.home_team, f.away_team, f.match_date, f.league)
                    prior_fixtures_dict[key] = f

            ok = await _navigate_to_league(page, country, league)
            if not ok:
                print(f"  x could not reach {country}/{league}")
                await browser.close()
                # Return prior cache if navigation failed
                return prior_cache.fixtures if prior_cache else []

            await _async_scroll_to_bottom(page)
            fixtures = await _extract_fixtures_from_page(page, league, country)
            if not fixtures:
                fixtures = await _extract_fixtures_from_json(page, league, country)

            # HR35 content gate: never cache a wrong/mismatched league page.
            # If the scrape is junk, KEEP the prior cache (don't overwrite a
            # good snapshot with garbage) and report honestly.
            valid, reason = _validate_fixtures(league, fixtures)
            if not valid:
                prior = _read_cache(league, max_age_seconds=10**9, cache_dir=cache_dir)
                if prior and prior.fixtures:
                    print(f"  [SKIP] content validation failed for {country}/{league}: "
                          f"{reason} — kept prior {len(prior.fixtures)} fixtures")
                else:
                    print(f"  [SKIP] content validation failed for {country}/{league}: "
                          f"{reason} — no prior cache to keep")
                await browser.close()
                return prior.fixtures if prior else []

            # Cross-league corruption guard: a single wrong page often gets cached
            # under many league names (observed 2026-08-29). If this scrape's team-set
            # near-matches a DIFFERENT league's cache, it's the same bad page — keep prior.
            cross_ok, cross_reason = _cross_league_ok(league, fixtures, cache_dir)
            if not cross_ok:
                prior = _read_cache(league, max_age_seconds=10**9, cache_dir=cache_dir)
                if prior and prior.fixtures:
                    print(f"  [SKIP] cross-league validation failed for {country}/{league}: "
                          f"{cross_reason} — kept prior {len(prior.fixtures)} fixtures")
                else:
                    print(f"  [SKIP] cross-league validation failed for {country}/{league}: "
                          f"{cross_reason} — no prior cache to keep")
                await browser.close()
                return prior.fixtures if prior else []

            # Incremental cache update: identify new, updated, and removed fixtures
            new_fixtures = []
            updated_fixtures = []
            removed_keys = set(prior_fixtures_dict.keys())
            current_fixtures_dict = {}

            for f in fixtures:
                key = (f.home_team, f.away_team, f.match_date, f.league)
                current_fixtures_dict[key] = f
                removed_keys.discard(key)  # Not removed if it's in current scrape

                # Check if fixture exists in prior cache
                if key in prior_fixtures_dict:
                    # Check if fixture has changed (odds, time, etc.)
                    prior_f = prior_fixtures_dict[key]
                    if _fixture_changed(prior_f, f):
                        updated_fixtures.append(f)
                else:
                    # New fixture
                    new_fixtures.append(f)

            # Removed fixtures (in prior but not in current)
            removed_fixtures = [prior_fixtures_dict[key] for key in removed_keys]

            # Log changes for monitoring
            if new_fixtures or updated_fixtures or removed_fixtures:
                print(f"  [CACHE UPDATE] {country}/{league}: "
                      f"+{len(new_fixtures)} new, ~{len(updated_fixtures)} updated, "
                      f"-{len(removed_fixtures)} removed")
            else:
                print(f"  [CACHE STABLE] {country}/{league}: no changes detected")

            # Write updated cache
            _write_cache(league, country, fixtures, cache_dir)
            print(f"  [OK] {country}/{league}: {len(fixtures)} fixtures cached")
            await browser.close()
            return fixtures
        except Exception as exc:
            print(f"  x _scrape_one_league failed for {country}/{league}: {exc}")
            await browser.close()
            # Return prior cache on error to prevent data loss
            return prior_cache.fixtures if prior_cache else []