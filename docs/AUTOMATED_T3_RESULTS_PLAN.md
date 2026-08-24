# Automated T3 Current-Season Results Source — Implementation Plan

**Status:** DRAFT — awaiting Architect approval  
**Created:** 2026-08-24  
**Context:** Reduce 27 pending legs (Aug 23) from lower-tier leagues by adding automated current-season results source

---

## 1. Problem Statement

**Aug 23 verification results:** 35 total legs, 8 settled (6W/2L), **27 PENDING**

**Root cause:** T1 (football-data.co.uk) empty/headers-only for all leagues; T2 (ESPN) covered 29/35 fixtures — misses lower tiers.

**Pending legs by league (from verification log):**
| League | Pending Legs | Coverage Gap |
|--------|--------------|--------------|
| La Liga 2 | ~4 | Not in football-data.co.uk, not in football-data.org free tier |
| Ligue 2 | ~3 | Not in football-data.co.uk, not in football-data.org free tier |
| Swiss Super League | ~3 | Not in football-data.co.uk |
| Eredivisie (early fixtures) | ~2 | football-data.org covers but fixtures not yet played |
| Turkish Super Lig | ~3 | Not in football-data.co.uk |
| Russian Premier League | ~2 | Not in football-data.co.uk |
| Serie B | ~3 | Not in football-data.co.uk |
| Primeira Liga | ~2 | Not in football-data.org free tier |
| Belgian Pro League | ~2 | Not in football-data.org free tier |
| Scottish Premiership | ~2 | Not in football-data.org free tier |

**Total affected:** ~24 of 27 pending legs are from leagues without T1/T2 current-season results coverage.

---

## 2. Current Results Fabric Architecture (Recap)

```
┌─────────────────────────────────────────────────────────────────┐
│                    MULTI-SOURCE FABRIC                          │
├─────────────────┬─────────────────┬─────────────────┬───────────┤
│  HISTORICAL     │  CURRENT SEASON │  LIVE SCORES    │  FIXTURES │
│  RESULTS        │  RESULTS        │  (in-play)      │           │
├─────────────────┼─────────────────┼─────────────────┼───────────┤
│ 1. FD.co.uk T1  │ 1. FD.co.uk     │ 1. ESPN T1      │ 1. API-Football│
│ 2. FD.org T1*   │ 2. FD.org T1    │ 2. API-Football │ 2. TheSportsDB │
│ 3. API-Football │ 3. API-Football │ 3. (reserved)   │ 3. ESPN        │
│ 4. TheSportsDB  │ 4. ESPN T2      │                 │ 4. Odds API    │
└─────────────────┴─────────────────┴─────────────────┴───────────┘
* football-data.org free tier: 12 competitions only (PL, ELC, PD, SA, BL1, FL1, DED, PPL, CL)
```

**Results Ingestion Flow (`data/results_ingestion.py`):**
1. Load acca JSON → extract fixtures by league
2. Try football-data.co.uk (T1) for current + previous season
3. Fallback: ESPN for missing fixtures
4. Last resort: Manual verification file
5. Settle legs → write verification log + update CLV log

---

## 3. Options Analysis

### Option A: Upgrade to Paid API-Football Plan (Recommended Primary)

| Aspect | Assessment |
|--------|------------|
| **Coverage** | All 61 whitelisted leagues + continental competitions (current season) |
| **Data quality** | Official API, structured JSON, includes scores + lineups + stats |
| **Odds** | Free tier odds (today±1) + paid plan wider window + more markets |
| **Cost** | ~$10-20/mo for Standard/Pro plan (Architect to confirm budget) |
| **Integration effort** | LOW — `APIFootballResultsSource` already exists in multi-source, `api_football_plan.is_paid_plan()` gate already built |
| **Timeline** | Minutes after key upgrade (7-day cache TTL in `api_football_plan.py`) |
| **Reliability** | High — official API with SLA |

**How it works:**
- Current `data/api_football_results.py:126` checks `api_football_plan.is_paid_plan()`
- Free plan: raises `SourceNoData` for seasons > 2024
- Paid plan: returns current-season (2025-26) results
- Already registered in `build_results_multi_source()` at priority 15
- `data/api_football_plan.py` caches plan status for 7 days

**Coverage for pending leagues:** ✅ All 61 whitelisted leagues including La Liga 2, Ligue 2, Serie B, Swiss, Turkish, Russian, Primeira, Belgian, Scottish, Eredivisie, etc.

---

### Option B: FlashScore Results Scraper (Recommended Secondary/Redundancy)

| Aspect | Assessment |
|--------|------------|
| **Coverage** | 92 leagues mapped in `config/flashscore_leagues.py` (ALL whitelisted + more) |
| **Data quality** | Web-scraped, requires Playwright, team name normalization needed |
| **Odds** | Not reliable (odds regex buggy per `verify_fixtures.py`) — results only |
| **Cost** | Free (no API key) but compute-heavy (Playwright) |
| **Integration effort** | MEDIUM — new module `data/flashscore_results.py` + registration |
| **Timeline** | 1-2 days development |
| **Reliability** | Medium — site structure changes break scraper; needs monitoring |

**Technical approach:**
1. Create `data/flashscore_results.py` with `FlashScoreResultsSource` class
2. Scrape completed matches from FlashScore league pages for target date
3. Parse: home/away teams, scores, status (FT), match time
4. Normalize team names to football-data.co.uk canonical (use `_norm()` from `verify_fixtures.py`)
4. Return `MatchResult` objects compatible with pipeline
5. Register in `multi_source_concrete.py:build_results_multi_source()` at priority ~18 (after ESPN)
6. Use same Playwright patterns as `scripts/scrape_live_odds_v3.py`

**FlashScore URL pattern for results:**
- Fixtures: `https://www.flashscore.com/football/{country}/{slug}/` (already working)
- Results: `https://www.flashscore.com/football/{country}/{slug}/results/` (needs investigation)

---

### Option C: Alternative Current-Season Results APIs

| Source | Coverage | Free Tier | Effort | Notes |
|--------|----------|-----------|--------|-------|
| **football-data.org** | 12 comps free, more paid | 10 req/min, 100/day | Already integrated | Already in fabric as T1 (priority 12); paid plan would expand |
| **API-Sports (v3)** | All major leagues | Free: 2022-2024 only | Already integrated | Same as API-Football (same company) |
| **Sportmonks** | 2000+ leagues | Trial only | High | Requires paid plan |
| **RapidAPI football** | Various | Freemium | High | Multiple providers, inconsistent |
| **TheSportsDB** | Many leagues | Free (rate limited) | Already integrated | Already in fabric as T2 (priority 20); current season works |

**TheSportsDB current-season results:** Already in fabric at priority 20! Check if it covers the missing leagues.

---

## 4. Recommended Strategy: Layered Approach

### Phase 1 (Immediate — Minutes): Enable Paid API-Football
- Architect provides paid API-Football key → paste into `.env` as `API_FOOTBALL_KEY`
- `api_football_plan.py` detects paid plan within 7 days (or force refresh cache)
- Current-season results auto-enable for ALL 61 whitelisted leagues
- **Expected impact:** ~20-24 of 27 pending legs resolved

### Phase 2 (1-2 days): Add FlashScore Results Scraper (Redundancy)
- Build `data/flashscore_results.py` as new DataSource
- Register in multi-source at priority 18 (after ESPN T2)
- Provides independent T2 verification for fixture verification gate + results ingestion
- **Expected impact:** Covers any leagues API-Football misses + redundancy

### Phase 3 (Future): Expand football-data.org to Paid Tier
- If football-data.org paid plan covers more competitions
- Already integrated, just need paid key and expanded `COMPETITION_CODES`

---

## 5. Implementation Details

### 5.1 Phase 1: Paid API-Football Activation (Zero Code Changes)

**Files that already handle this:**
- `data/api_football_plan.py` — plan probe, 7-day cache
- `data/api_football_results.py:126` — `is_paid_plan()` gate
- `data/multi_source_concrete.py:269` — already registered

**Action required:**
1. Obtain paid API-Football key (Standard or Pro plan)
2. Update `.env`: `API_FOOTBALL_KEY=<paid-key>`
3. Clear plan cache: `rm data/cache/api_football/plan.json`
4. Run verification — current-season results will flow

**Verification:**
```bash
python -c "from data.api_football_plan import is_paid_plan; print(is_paid_plan())"
# Should return True
```

---

### 5.2 Phase 2: FlashScore Results Scraper (New Module)

**New file: `data/flashscore_results.py`**

```python
"""
FlashScore completed match results scraper.
Provides current-season results for 92 leagues as T2 redundancy.
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.football_data_source import MatchResult
from data.multi_source import SourceNoData
from config.flashscore_leagues import FLASHSCORE_LEAGUES, BASE_URL

try:
    from playwright.async_api import async_playwright
except ImportError:
    async_playwright = None

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
        """Fetch completed matches for a specific date."""
        if async_playwright is None:
            raise RuntimeError("playwright not installed")

        # Check cache first
        cached = self._load_cache(target_date)
        if cached is not None:
            return cached

        # FlashScore results page: /football/{country}/{slug}/results/
        results_url = BASE_URL.format(slug=self.slug).rstrip("/") + "/results/"

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.set_viewport_size({"width": 1280, "height": 900})

            try:
                await page.goto(results_url, wait_until="domcontentloaded", timeout=60000)
                await page.wait_for_timeout(5000)

                # Find completed match rows
                match_elements = await page.query_selector_all("[class*='event__match']")
                results = []

                for el in match_elements:
                    try:
                        match = await self._parse_match_element(el, target_date)
                        if match:
                            results.append(match)
                    except Exception:
                        continue

                if results:
                    self._save_cache(target_date, results)

                return results

            finally:
                await browser.close()

    async def _parse_match_element(self, el, target_date: str) -> Optional[MatchResult]:
        """Parse a single match row from FlashScore results page."""
        # Extract home/away from participant elements
        home_el = await el.query_selector(".event__homeParticipant")
        away_el = await el.query_selector(".event__awayParticipant")
        score_el = await el.query_selector(".event__score, [class*='event__score']")
        time_el = await el.query_selector(".event__time, .event__stageTime")
        status_el = await el.query_selector(".event__status, [class*='event__status']")

        if not home_el or not away_el:
            return None

        home_team = (await home_el.text_content() or "").strip()
        away_team = (await away_el.text_content() or "").strip()

        # Get team name from image alt if available
        img_h = await home_el.query_selector("img")
        if img_h:
            home_team = await img_h.get_attribute("alt") or home_team
        img_a = await away_el.query_selector("img")
        if img_a:
            away_team = await img_a.get_attribute("alt") or away_team

        # Parse score
        score_text = (await score_el.text_content() or "").strip() if score_el else ""
        score_match = re.match(r"(\d+)\s*[-:]\s*(\d+)", score_text)
        if not score_match:
            return None
        home_score, away_score = int(score_match.group(1)), int(score_match.group(2))

        # Parse status (should be FT for completed)
        status_text = (await status_el.text_content() or "").strip() if status_el else ""
        if "FT" not in status_text and "Finished" not in status_text:
            return None  # Only completed matches

        # Parse date
        match_date = self._parse_flashscore_date((await time_el.text_content() or "").strip(), target_date)
        if match_date != target_date:
            return None

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
        # Formats: "21.08. 20:00" or "12:30" (today) or "Yesterday 20:00"
        if not match_datetime:
            return target_date

        from datetime import datetime as _dt
        now = _dt.now()

        # Try DD.MM. HH:MM
        m = re.match(r"(\d{1,2})\.(\d{1,2})\.\s*(\d{1,2}):(\d{2})", match_datetime)
        if m:
            day, mon, hh, mm = (int(x) for x in m.groups())
            for year in (now.year, now.year + 1):
                try:
                    cand = _dt(year, mon, day)
                    if 0 <= (cand - now).days <= 400:
                        return cand.strftime("%Y-%m-%d")
                except ValueError:
                    continue

        # Try HH:MM only (today)
        m = re.match(r"^(\d{1,2}):(\d{2})$", match_datetime.strip())
        if m:
            return now.strftime("%Y-%m-%d")

        return target_date

    def _cache_path(self, target_date: str) -> Path:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        safe_league = self.league.replace(" ", "_").replace("/", "_")
        return CACHE_DIR / f"{safe_league}_{target_date}.json"

    def _load_cache(self, target_date: str) -> Optional[List[MatchResult]]:
        path = self._cache_path(target_date)
        if not path.exists():
            return None
        import time
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
                "league": r.league, "date": r.date, "home_team": r.home_team,
                "away_team": r.away_team, "fthg": r.fthg, "ftag": r.ftag,
                "ftr": r.ftr, "source": r.source, "source_tier": r.source_tier,
            }
            for r in results
        ]
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


async def fetch_flashscore_results(league: str, target_date: str) -> List[MatchResult]:
    """Convenience function for multi-source integration."""
    source = FlashScoreResultsSource(league)
    return await source.fetch_results_for_date(target_date)
```

---

**Registration in `data/multi_source_concrete.py`:**

```python
# Add to imports
# from data.flashscore_results import fetch_flashscore_results

class FlashScoreResultsSource(DataSource):
    """FlashScore completed match results (T2 redundancy)."""

    def __init__(self):
        super().__init__("flashscore_results", priority=18, timeout=60.0)

    def fetch(self, **kwargs) -> list:
        league = kwargs["league"]
        target_date = kwargs.get("target_date") or kwargs.get("date")
        if not target_date:
            raise SourceNoData("flashscore_results: target_date required")
        # Run async fetch in sync context
        results = asyncio.run(fetch_flashscore_results(league, target_date))
        if not results:
            raise SourceNoData(f"flashscore_results: no results for {league} on {target_date}")
        return {"results": results, "source": "flashscore_results"}


# In build_results_multi_source(), add:
# (FlashScoreResultsSource().fetch, "flashscore_results", 18),
```

---

### 5.3 Integration with Results Ingestion

**Modify `data/results_ingestion.py:fetch_results_for_fixtures()`:**

After ESPN fallback (line 206), add:

```python
# 3. Fallback: FlashScore for still-missing fixtures
still_missing = [(h, a) for h, a in pairs
                 if f"{league}|{h} v {a}" not in results_by_key]
if still_missing:
    try:
        from data.flashscore_results import fetch_flashscore_results
        fs_results = await fetch_flashscore_results(league, target_date)
        for result in fs_results:
            key = f"{result.league}|{result.home_team} v {result.away_team}"
            if key not in results_by_key:
                # Convert MatchResult -> FDMatchResult
                fd_result = FDMatchResult(
                    league=result.league,
                    date=result.date,
                    home_team=result.home_team,
                    away_team=result.away_team,
                    fthg=result.fthg,
                    ftag=result.ftag,
                    ftr=result.ftr,
                    closing_home_odds=None,
                    closing_draw_odds=None,
                    closing_away_odds=None,
                    source="flashscore",
                    source_tier="T2",
                    odds=None,
                    kickoff_time=None,
                )
                results_by_key[key] = fd_result
        if any(f"{league}|{h} v {a}" in results_by_key for h, a in still_missing):
            print(f"[results_ingestion] FlashScore: matched fixtures for {league}")
    except Exception as e:
        print(f"[results_ingestion] FlashScore fallback error for {league}: {e}")
```

**Note:** Since `fetch_results_for_fixtures` is sync, the FlashScore call would need `asyncio.run()` wrapper or the function made async. Alternative: create a sync wrapper in `flashscore_results.py`.

---

## 6. Testing Plan

### Unit Tests
- [ ] `data/flashscore_results.py` — mock Playwright, test parsing logic
- [ ] Team name normalization against known FlashScore → football-data.co.uk mappings
- [ ] Date parsing for various FlashScore formats
- [ ] Cache read/write

### Integration Tests
- [ ] Run `results_ingestion.py` for a known date with FlashScore results
- [ ] Verify multi-source chain: FD.co.uk → FD.org → ESPN → FlashScore → Manual
- [ ] Test with leagues currently pending: La Liga 2, Ligue 2, Swiss, Turkish, etc.

### End-to-End
- [ ] Run full pipeline for a match day
- [ ] Verify verification log shows reduced PENDING count
- [ ] Check CLV log integration works with FlashScore results

---

## 7. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| FlashScore HTML structure changes | Medium | High | Versioned selectors, alert on parse failures, fallback to other sources |
| Playwright/bot detection | Low-Medium | Medium | Stealth mode, reasonable delays, user-agent rotation |
| Team name normalization gaps | Medium | Medium | Extend `_norm()` with league-specific mappings; log unmatched |
| API-Football paid key not available | Low | High | FlashScore scraper as backup; TheSportsDB already in chain |
| Rate limiting on FlashScore | Low | Low | Cache results (6h TTL), scrape once per day per league |

---

## 8. Dependencies

- `playwright` (already in `scripts/scrape_live_odds_v3.py`)
- `playwright-stealth` (optional, already tried in v3)
- `config/flashscore_leagues.py` (already exists, 92 leagues mapped)
- `booking/verify_fixtures.py:_norm()` (already exists, team normalization)

---

## 9. Files to Create/Modify

| File | Action | Phase |
|------|--------|-------|
| `.env` | Add paid `API_FOOTBALL_KEY` | 1 |
| `data/flashscore_results.py` | Create new module | 2 |
| `data/multi_source_concrete.py` | Register FlashScoreResultsSource | 2 |
| `data/results_ingestion.py` | Add FlashScore fallback | 2 |
| `tests/flashscore_results_test.py` | Unit tests | 2 |

---

## 10. Success Criteria

1. **Phase 1 (Paid API-Football):**
   - `is_paid_plan()` returns `True`
   - Aug 24 verification: pending legs reduced from 27 → ≤7
   - All top-20 leagues have current-season results coverage

2. **Phase 2 (FlashScore scraper):**
   - Scraper runs without errors for test leagues
   - Results match known scores for completed matches
   - Integration test: verification log shows FlashScore as source for ≥5 previously-pending legs
   - No regression in existing T1/T2 sources

---

## 11. Architect Decision Required

| Decision | Options | Recommendation |
|----------|---------|----------------|
| **Approve Phase 1 (Paid API-Football)?** | Yes / No / Defer | **Yes** — zero code risk, immediate impact |
| **Approve Phase 2 (FlashScore scraper)?** | Yes / No / Defer | **Yes** — redundancy, covers edge cases |
| **Budget for API-Football paid plan?** | $10-20/mo | Confirm budget availability |
| **Priority order in multi-source?** | API-Football (paid) → FD.org → ESPN → FlashScore → TheSportsDB | As designed (FlashScore at 18) |

---

*Plan complete. Awaiting Architect go/no-go on Phase 1 and Phase 2.*