"""
FlashScore completed match results scraper.
Provides current-season results for 92 leagues as T2 redundancy.

Scrapes completed matches from FlashScore league results pages.
Returns MatchResult objects compatible with the results ingestion pipeline.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import re
import sys
import time
from dataclasses import dataclass, asdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.football_data_source import MatchResult
from data.multi_source import SourceNoData

# Import FlashScore league mapping via importlib to avoid config.py/package collision
_REPO_ROOT = Path(__file__).parent.parent
def _load_flashscore_map():
    fallback = ({"Premier League": "england/premier-league"},
                "https://www.flashscore.com/football/{slug}/")
    try:
        from config.flashscore_leagues import FLASHSCORE_LEAGUES, BASE_URL
        return FLASHSCORE_LEAGUES, BASE_URL
    except ImportError:
        pass
    # Direct file load (collision-safe)
    _p = _REPO_ROOT / "config" / "flashscore_leagues.py"
    if not _p.exists():
        return fallback
    _spec = importlib.util.spec_from_file_location("flashscore_leagues", _p)
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    return _mod.FLASHSCORE_LEAGUES, _mod.BASE_URL

FLASHSCORE_LEAGUES, BASE_URL = _load_flashscore_map()

try:
    from playwright.async_api import async_playwright
except ImportError:
    async_playwright = None

# Try to import stealth for anti-bot evasion
try:
    from playwright_stealth import Stealth
    _STEALTH = Stealth()
except ImportError:
    _STEALTH = None

CACHE_DIR = Path(__file__).parent / "cache" / "flashscore_results"
LIVE_SEASON_TTL = 6 * 3600
COMPLETED_SEASON_TTL = 30 * 24 * 3600


@dataclass
class FlashScoreMatch:
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    status: str
    match_date: str


class FlashScoreResultsSource:
    """Scrapes completed match results from FlashScore league results pages."""

    def __init__(self, league: str):
        self.league = league
        self.slug = FLASHSCORE_LEAGUES.get(league)
        if not self.slug:
            raise SourceNoData(f"flashscore_results: league {league!r} not mapped")

    async def fetch_results_for_date(self, target_date: str) -> List[MatchResult]:
        """Completed matches for one date, harvesting the whole page while there.

        The page this loads is the league's SEASON results page: every
        completed match of the season is already in the DOM. It used to be
        parsed, filtered down to `target_date`, and the rest thrown away --
        so reconstructing a season's history meant ~200 loads of the same
        page at ~25s each (60s navigation timeout plus a 15s settle), which
        is what made FlashScore unusable as a history source and left
        Russia, Switzerland and the continental competitions with no model
        unless a PAID API-Football key was present.

        Now one load caches every date it saw, so the second date onwards is
        free. `target_date` still decides what is RETURNED, so every existing
        caller behaves exactly as before.
        """
        if async_playwright is None:
            raise RuntimeError("playwright not installed")

        # Check cache first
        cached = self._load_cache(target_date)
        if cached is not None:
            return cached

        by_date = await self.fetch_season_results(reference_date=target_date)
        return by_date.get(target_date, [])

    async def fetch_season_results(
        self, reference_date: Optional[str] = None
    ) -> dict:
        """Every completed match on the season results page, grouped by date.

        One page load. Each date found is written to that date's cache file,
        so a later fetch_results_for_date for any of them is a file read.

        `reference_date` only supplies the year used to resolve FlashScore's
        year-less "DD.MM." dates; it does not filter anything.
        """
        if async_playwright is None:
            raise RuntimeError("playwright not installed")

        reference_date = reference_date or datetime.now().strftime("%Y-%m-%d")

        # FlashScore results page: /football/{country}/{slug}/results/
        base_url = BASE_URL.format(slug=self.slug).rstrip("/")
        results_url = f"{base_url}/results/"

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            )
            page = await context.new_page()
            await page.set_viewport_size({"width": 1280, "height": 900})

            try:
                await page.goto(results_url, wait_until="domcontentloaded", timeout=60000)
                await page.wait_for_timeout(15000)

                # Find completed match rows — FlashScore uses .event__match--withRowLink for history
                match_elements = await page.query_selector_all("[class*='event__match--withRowLink']")
                # Fall back to broad selector if the above returns nothing unexpectedly
                if not match_elements:
                    match_elements = await page.query_selector_all("[class*='event__match']")
                by_date: dict[str, List[MatchResult]] = {}

                for el in match_elements:
                    try:
                        match = await self._parse_match_element(el, reference_date)
                    except Exception:
                        continue
                    if match:
                        by_date.setdefault(match.date, []).append(match)

                # Cache each date separately so any single-date caller gets a
                # file read rather than another page load.
                for day, day_results in by_date.items():
                    try:
                        self._save_cache(day, day_results)
                    except Exception:
                        # A cache write failure must not lose the data we
                        # already have in hand.
                        continue

                return by_date

            finally:
                await browser.close()

    async def _select_first_leaf(self, parent) -> Optional[str]:
        """Get textContent of the first leaf element whose class contains *name*."""
        # FlashScore uses wcl-name_* classes
        children = await parent.query_selector_all("[class*='wcl-name_']")
        for c in children:
            txt = (await c.text_content() or "").strip()
            if txt:
                return txt
        # fallback: also try generic 'name' class
        children = await parent.query_selector_all("[class*='name']")
        for c in children:
            txt = (await c.text_content() or "").strip()
            if txt:
                return txt
        # fallback: direct text
        return (await parent.text_content() or "").strip() or None

    async def _parse_match_element(self, el, target_date: str) -> Optional[MatchResult]:
        """Parse a single match row from FlashScore results page."""
        # Team names: FlashScore uses wcl-name_* class on leaf elements inside the match row
        # Find all name elements in the match row
        name_els = await el.query_selector_all("[class*='wcl-name_']")
        if len(name_els) < 2:
            return None
        home_team = (await name_els[0].text_content() or "").strip()
        away_team = (await name_els[1].text_content() or "").strip()
        if not home_team or not away_team:
            return None

        # Score: FlashScore uses event__score event__score--home / event__score--away
        home_score_el = await el.query_selector("[class*='event__score'][class*='--home']")
        away_score_el = await el.query_selector("[class*='event__score'][class*='--away']")
        if not home_score_el or not away_score_el:
            return None
        try:
            home_score = int((await home_score_el.text_content() or "").strip())
            away_score = int((await away_score_el.text_content() or "").strip())
        except ValueError:
            return None

        # Date: FlashScore uses wcl-dateContent_* or wcl-stageTime_*
        time_el = await el.query_selector("[class*='wcl-dateContent_'], [class*='wcl-stageTime_']")
        match_raw_date = (await time_el.text_content() or "").strip() if time_el else ""

        match_date = self._parse_flashscore_date(match_raw_date, target_date)
        # NB: no date filter here any more. The caller decides what to keep --
        # see fetch_season_results. `target_date` is still passed because
        # _parse_flashscore_date needs a year to resolve FlashScore's
        # year-less "DD.MM. HH:MM" format against.

        # Normalize team names to football-data.co.uk canonical
        from booking.verify_fixtures import _norm
        home_norm = _norm(home_team)
        away_norm = _norm(away_team)

        return MatchResult(
            league=self.league,
            date=match_date,
            home_team=home_norm,
            away_team=away_norm,
            fthg=home_score,
            ftag=away_score,
            ftr="H" if home_score > away_score else ("D" if home_score == away_score else "A"),
            source="flashscore.com",
            source_tier="T2",
        )

    def _parse_flashscore_date(self, match_datetime: str, target_date: str) -> str:
        """Parse FlashScore date format to ISO date."""
        if not match_datetime:
            return target_date

        # Use target_date year as primary reference (current season context)
        try:
            target_year = int(target_date.split("-")[0])
        except (ValueError, IndexError):
            target_year = datetime.now().year

        now = datetime.now()

        # Try DD.MM. HH:MM
        m = re.match(r"(\d{1,2})\.(\d{1,2})\.\s*(\d{1,2}):(\d{2})", match_datetime)
        if m:
            day, mon, hh, mm = (int(x) for x in m.groups())
            try:
                target_dt = datetime.strptime(target_date, "%Y-%m-%d")
            except ValueError:
                target_dt = now

            # FlashScore omits the year, so the year has to be inferred. These
            # are COMPLETED matches, which means they are in the PAST -- and
            # that is what the previous rule got backwards. Its fallback was
            #     0 <= (cand - now).days <= 400
            # which accepts only FUTURE dates, so a result from 25 July 2026
            # read on 16 September 2026 failed the 2026 candidate (negative
            # delta) and matched 2027 instead. Every result older than the
            # +/-5 day window came back stamped a year late.
            #
            # It stayed invisible while the caller filtered each page down to a
            # single date and discarded the rest; harvesting the whole season
            # exposes it on every row.
            candidates = []
            for year in (target_year, target_year - 1, now.year, now.year - 1):
                try:
                    cand = datetime(year, mon, day)
                except ValueError:
                    continue          # 29 Feb in a non-leap year
                if cand not in candidates:
                    candidates.append(cand)

            # An exact hit near the requested date wins outright: that is the
            # single-date caller asking for a day it already knows about.
            for cand in candidates:
                if abs((cand - target_dt).days) <= 5:
                    return cand.strftime("%Y-%m-%d")

            # Otherwise take the most recent date that has actually happened.
            # A completed match cannot be in the future; allowing one lets a
            # finished result masquerade as an upcoming fixture and skews any
            # time-decay weighting that reads it.
            past = [c for c in candidates if c <= now]
            if past:
                return max(past).strftime("%Y-%m-%d")

        # Try HH:MM only (today)
        m = re.match(r"^(\d{1,2}):(\d{2})$", match_datetime.strip())
        if m:
            return now.strftime("%Y-%m-%d")

        return target_date

    def _date_matches_target(self, match_date: str, target_date: str) -> bool:
        """Check if match date matches target date or target date + 1 (for late evening matches)."""
        if match_date == target_date:
            return True
        # Check if match date is the day after target (late evening matches that finish after midnight)
        from datetime import datetime, timedelta
        try:
            tgt = datetime.strptime(target_date, "%Y-%m-%d")
            match_dt = datetime.strptime(match_date, "%Y-%m-%d")
            if match_dt == tgt + timedelta(days=1):
                return True
        except ValueError:
            pass
        return False

    def _cache_path(self, target_date: str) -> Path:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        safe_league = self.league.replace(" ", "_").replace("/", "_")
        return CACHE_DIR / f"{safe_league}_{target_date}.json"

    def _load_cache(self, target_date: str) -> Optional[List[MatchResult]]:
        path = self._cache_path(target_date)
        if not path.exists():
            return None
        age = time.time() - path.stat().st_mtime
        ttl = COMPLETED_SEASON_TTL  # Results don't change after match
        if age > ttl:
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return [MatchResult(**r) for r in data]
        except Exception:
            return None

    def _save_cache(self, target_date: str, results: List[MatchResult]) -> None:
        path = self._cache_path(target_date)
        data = [
            {
                "league": r.league,
                "date": r.date,
                "home_team": r.home_team,
                "away_team": r.away_team,
                "fthg": r.fthg,
                "ftag": r.ftag,
                "ftr": r.ftr,
                "source": r.source,
                "source_tier": r.source_tier,
            }
            for r in results
        ]
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


async def fetch_flashscore_results(league: str, target_date: str) -> List[MatchResult]:
    """Convenience function for multi-source integration."""
    source = FlashScoreResultsSource(league)
    return await source.fetch_results_for_date(target_date)


def fetch_flashscore_results_sync(league: str, target_date: str) -> List[MatchResult]:
    """Sync wrapper for multi-source fabric integration."""
    return asyncio.run(fetch_flashscore_results(league, target_date))


async def fetch_flashscore_season(league: str,
                                  reference_date: Optional[str] = None) -> dict:
    """Every completed match of the season, grouped by date. One page load."""
    return await FlashScoreResultsSource(league).fetch_season_results(
        reference_date=reference_date)


def fetch_flashscore_season_sync(league: str,
                                 reference_date: Optional[str] = None) -> dict:
    """Sync wrapper around fetch_flashscore_season."""
    return asyncio.run(fetch_flashscore_season(league, reference_date))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="FlashScore Results Scraper")
    parser.add_argument("league", help="League name (e.g., 'La Liga 2')")
    parser.add_argument("date", help="Target date (YYYY-MM-DD)")
    args = parser.parse_args()

    results = fetch_flashscore_results_sync(args.league, args.date)

    print(f"\n{'='*80}")
    print(f"FLASHSCORE RESULTS - {args.league} - {args.date} - {len(results)} matches")
    print(f"{'='*80}\n")

    for r in results:
        print(f"  {r.date}  {r.league}")
        print(f"    {r.home_team} {r.fthg} - {r.ftag} {r.away_team}  ({r.ftr})")
        print()