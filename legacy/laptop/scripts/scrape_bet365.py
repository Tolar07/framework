#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bet365 Fixtures + Odds Scraper — produces structured JSONL feed for the
verification gate and the multi-market odds pipeline.

Bet365 provides football fixtures and odds. This scraper targets the fixtures
pages (which are publicly accessible) to extract home/away/date for F2 quorum
AND the full set of market odds for every football betting market (1X2, Totals
at 0.5/1.5/2.5/3.5, BTTS, Double Chance, Draw No Bet, HT/FT, Correct Score) —
37 canonical markets, the same universe the OLP XDV engine prices on.

IMPORTANT: Bet365 has strong anti-bot protection. This scraper:
- Uses Playwright with stealth settings
- May require manual login cookies for full access
- Falls back to public fixture pages when possible

Architecture: same pattern as FlashScore scraper
- Produces to data/live_odds/bet365_fixtures_*.jsonl (fixtures, type=match_1x2)
- Produces to data/live_odds/bet365_odds_*.jsonl (odds, type=match_odds)
- Each odds entry carries all canonical-market odds found, plus a ZONE flag
  (SAFE / 5050 / WATCH / FLOOR) per market so the production cap (MAX_ODDS_CAP
  = 2.00) and the safe zone (1.20–1.50) are visible at the earliest point.
- Source registered as "bet365_odds" in SOURCE_TRUST = T2 (after verification),
  same tier as the SportyBet cache it parallels.

ODDS ZONES (Architect 2026-08-19 — mirror of engine/acca.py constants):
  FLOOR  : price < 1.20   — rejected (no value in heavy favourites)
  SAFE   : 1.20–1.50      — preferred "safe" deployment sweet spot
  5050   : 1.50–2.00      — admitted only as fallback (the 50/50 zone)
  WATCH  : price > 2.00   — over the hard cap, flagged for review, never capital
The scraper only READS and LABELS; it never filters (filtering is the engine's
job in engine/acca.py). The zone tag is honest metadata so a downstream
consumer can see, per-market, where each price sits before the engine runs.
"""

import asyncio
import importlib.util
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, List, Dict

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from playwright.async_api import async_playwright

# --- Odds zone thresholds (mirror engine/acca.py so the scraper's labels match
# --- the engine's hard gates exactly). Imported live when possible so the two
# --- can never drift; the literals below are the documented fallback values.
try:
    from engine.acca import MAX_ODDS_CAP, MIN_ODDS_FLOOR, PREFERRED_ODDS_CEILING
except Exception:
    MAX_ODDS_CAP = 2.00
    MIN_ODDS_FLOOR = 1.20
    PREFERRED_ODDS_CEILING = 1.50

# Load config module directly to avoid config.py package collision (HR35)
_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT))
def _load_bet365_map():
    fallback = ({"Premier League": "1000000000"},
                "https://www.bet365.com/#/AC/B1/C1/D{slug}/")
    try:
        spec = importlib.util.spec_from_file_location(
            "bet365_leagues", _REPO_ROOT / "config" / "bet365_leagues.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.BET365_LEAGUES, mod.BASE_URL
    except Exception:
        return fallback

BET365_LEAGUES, BASE_URL = _load_bet365_map()


# --- Canonical market keys the Bet365 scraper will try to surface.
# --- These are the OLP XDV canonical identities from engine/markets.py (the
# --- single source of truth — code compares KEYS, humans read display()). The
# --- scraper maps Bet365's market/outcome cells onto these keys so the odds it
# --- emits join the SAME pipeline the SportyBet cache and api-football feed
# --- feed into. Kept in sync with engine/markets.EDGE_MARKETS.
CANONICAL_MARKETS = (
    "1X2_HOME", "1X2_DRAW", "1X2_AWAY",
    "OVER_0_5", "UNDER_0_5",
    "OVER_1_5", "UNDER_1_5",
    "OVER_2_5", "UNDER_2_5",
    "OVER_3_5", "UNDER_3_5",
    "BTTS_YES", "BTTS_NO",
    "DC_1X", "DC_X2", "DC_12",
    "DNB_HOME", "DNB_AWAY",
    "HT_FT_11", "HT_FT_1X", "HT_FT_12",
    "HT_FT_X1", "HT_FT_XX", "HT_FT_X2",
    "HT_FT_21", "HT_FT_2X", "HT_FT_22",
    "CS_1_0", "CS_0_1", "CS_1_1", "CS_2_0", "CS_0_2",
    "CS_2_1", "CS_1_2", "CS_2_2", "CS_0_0",
    "CS_3_0", "CS_0_3", "CS_3_1", "CS_1_3",
)

# Human-readable market label for each canonical key (mirrors markets.display
# but without team names — used only for the scraper's on-disk metadata).
_MARKET_LABEL = {
    "1X2_HOME": "Home Win", "1X2_DRAW": "Draw", "1X2_AWAY": "Away Win",
    "OVER_0_5": "Over 0.5", "UNDER_0_5": "Under 0.5",
    "OVER_1_5": "Over 1.5", "UNDER_1_5": "Under 1.5",
    "OVER_2_5": "Over 2.5", "UNDER_2_5": "Under 2.5",
    "OVER_3_5": "Over 3.5", "UNDER_3_5": "Under 3.5",
    "BTTS_YES": "BTTS Yes", "BTTS_NO": "BTTS No",
    "DC_1X": "Double Chance 1X", "DC_X2": "Double Chance X2", "DC_12": "Double Chance 12",
    "DNB_HOME": "Draw No Bet Home", "DNB_AWAY": "Draw No Bet Away",
    "HT_FT_11": "HT/FT 1/1", "HT_FT_1X": "HT/FT 1/X", "HT_FT_12": "HT/FT 1/2",
    "HT_FT_X1": "HT/FT X/1", "HT_FT_XX": "HT/FT X/X", "HT_FT_X2": "HT/FT X/2",
    "HT_FT_21": "HT/FT 2/1", "HT_FT_2X": "HT/FT 2/X", "HT_FT_22": "HT/FT 2/2",
    "CS_1_0": "Correct Score 1-0", "CS_0_1": "Correct Score 0-1",
    "CS_1_1": "Correct Score 1-1", "CS_2_0": "Correct Score 2-0",
    "CS_0_2": "Correct Score 0-2", "CS_2_1": "Correct Score 2-1",
    "CS_1_2": "Correct Score 1-2", "CS_2_2": "Correct Score 2-2",
    "CS_0_0": "Correct Score 0-0", "CS_3_0": "Correct Score 3-0",
    "CS_0_3": "Correct Score 0-3", "CS_3_1": "Correct Score 3-1",
    "CS_1_3": "Correct Score 1-3",
}


def classify_zone(price: Optional[float]) -> str:
    """The deployment zone a price sits in (mirrors engine/acca.py gates).

    FLOOR : price < 1.20   — rejected (no value in heavy favourites)
    SAFE  : 1.20–1.50      — preferred "safe" zone
    5050  : 1.50–2.00      — 50/50 fallback zone
    WATCH : price > 2.00   — above MAX_ODDS_CAP, review only (never capital)
    NONE  : no price / degenerate (<=1.0) — honest gap, not a fabrication."""
    if price is None or price <= 1.0:
        return "NONE"
    if price < MIN_ODDS_FLOOR:
        return "FLOOR"
    if price <= PREFERRED_ODDS_CEILING:
        return "SAFE"
    if price <= MAX_ODDS_CAP:
        return "5050"
    return "WATCH"


class Bet365FixturesScraper:
    """Scrapes fixtures and odds from Bet365 for mapped leagues."""

    OUTPUT_DIR = Path(__file__).parent.parent / "data" / "live_odds"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    def __init__(
        self,
        headless: bool = True,
        leagues: Optional[List[str]] = None,
        max_matches_per_league: int = 50,
    ):
        self.headless = headless
        self.leagues = leagues or list(BET365_LEAGUES.keys())
        self.max_matches = max_matches_per_league
        self.browser = None
        self.page = None
        self.playwright = None

    async def __aenter__(self):
        self.playwright = await async_playwright().start()
        # Use stealthier launch args for Bet365
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process",
                "--no-sandbox",
            ]
        )
        context = await self.browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="en-GB",
            timezone_id="Europe/London",
        )
        # Add stealth script
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)
        self.page = await context.new_page()
        return self

    async def __aexit__(self, *args):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    def _parse_fixture_row(self, text: str, league: str) -> Optional[tuple[str, str, str]]:
        """
        Parse a Bet365 fixture row.
        Bet365 format varies; typically "Team A v Team B  21 Aug 20:00"
        Returns (home, away, match_datetime) or None.
        """
        if not text or len(text) < 5:
            return None

        # Pattern 1: "Team A v Team B  21 Aug 20:00"
        m = re.match(r'^(.+?)\s+v\s+(.+?)\s+(\d{1,2}\s+\w{3}\s+\d{1,2}:\d{2})', text.strip())
        if m:
            home, away, dt = m.groups()
            return home.strip(), away.strip(), dt.strip()

        # Pattern 2: "Team A - Team B  21/08/2026 20:00"
        m = re.match(r'^(.+?)\s+-\s+(.+?)\s+(\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2})', text.strip())
        if m:
            home, away, dt = m.groups()
            return home.strip(), away.strip(), dt.strip()

        # Pattern 3: Date prefix "21 Aug 20:00  Team A v Team B"
        m = re.match(r'^(\d{1,2}\s+\w{3}\s+\d{1,2}:\d{2})\s+(.+)', text.strip())
        if m:
            dt, rest = m.groups()
            m2 = re.match(r'^(.+?)\s+v\s+(.+)$', rest.strip())
            if m2:
                home, away = m2.groups()
                return home.strip(), away.strip(), dt.strip()

        return None

    async def scrape_league_fixtures(self, league_name: str) -> List[dict[str, Any]]:
        """Scrape fixtures + odds for a single league from Bet365.

        Returns a list of dicts containing BOTH fixture entries (type=match_1x2)
        and odds entries (type=match_odds). The odds entries carry the full set
        of canonical market odds found on the page, each tagged with its zone
        (SAFE / 5050 / WATCH / FLOOR / NONE) so the production engine's
        MAX_ODDS_CAP / MIN_ODDS_FLOOR / PREFERRED_ODDS_CEILING gates are visible
        at the earliest point in the pipeline. The scraper does NOT filter — it
        labels honestly so downstream consumers see the unvarnished picture.
        """
        slug = BET365_LEAGUES.get(league_name)
        if not slug:
            print(f"  [{datetime.now().isoformat()}] {league_name}: NOT MAPPED in BET365_LEAGUES")
            return []

        url = BASE_URL.format(slug=slug)
        print(f"  [{datetime.now().isoformat()}] {league_name}: fetching {url}")

        try:
            await self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await self.page.wait_for_timeout(5000)
        except Exception as e:
            print(f"  [{datetime.now().isoformat()}] {league_name}: navigation failed: {e}")
            return []

        # Bet365 uses specific classes for fixtures
        # Try multiple selectors
        selectors = [
            "[class*='Fixture']",
            "[class*='fixture']",
            "[class*='Match']",
            "[class*='match']",
            ".gl-Participant",
            ".sip-Participant",
            "tr[class*='Row']",
        ]

        match_elements = []
        for sel in selectors:
            els = await self.page.query_selector_all(sel)
            if els:
                match_elements = els
                print(f"  [{datetime.now().isoformat()}] {league_name}: found {len(els)} with selector '{sel}'")
                break

        if not match_elements:
            print(f"  [{datetime.now().isoformat()}] {league_name}: no fixture elements found")
            return []

        all_results = []
        for idx, el in enumerate(match_elements[:self.max_matches]):
            try:
                text = await el.text_content()
                if not text or len(text.strip()) < 10:
                    continue

                parsed = self._parse_fixture_row(text, league_name)
                if not parsed:
                    continue

                home_team, away_team, match_datetime = parsed

                # Fixture entry (for F2 quorum)
                all_results.append({
                    "type": "match_1x2",
                    "league": league_name,
                    "home_team": home_team,
                    "away_team": away_team,
                    "match_datetime": match_datetime,
                    "market": "match_winner",
                    "source": "bet365_fixtures",
                    "timestamp": datetime.now().isoformat()
                })

                # Odds entry — extract all canonical markets from this match element
                odds_entry = await self._extract_odds_from_element(el, league_name, home_team, away_team, match_datetime)
                if odds_entry:
                    all_results.append(odds_entry)

            except Exception as e:
                print(f"    match {idx} parse error: {e}")
                continue

        print(f"  [{datetime.now().isoformat()}] {league_name}: parsed {len([r for r in all_results if r['type']=='match_1x2'])} fixtures, {len([r for r in all_results if r['type']=='match_odds'])} odds entries")
        return all_results

    async def _extract_odds_from_element(self, el, league_name: str, home_team: str, away_team: str, match_datetime: str) -> Optional[dict]:
        """Extract odds for ALL canonical markets from a single match element.

        Bet365's fixture rows expose multiple market cells. The first is 1X2
        (Home/Draw/Away). Subsequent cells can be Totals (various lines), BTTS,
        Double Chance, Draw No Bet, HT/FT, Correct Score — each rendered as a
        separate market cell with its own outcome odds. We walk the DOM to find
        every market cell and its outcomes, mapping Bet365's labels to our
        canonical keys (engine/markets.py).
        """
        try:
            # Get all market cells in this row
            market_cells = await el.query_selector_all(".gl-MarketGroup, .sip-MarketGroup, [class*='MarketGroup'], [class*='market-group']")
            if not market_cells:
                # Try alternative structure: odds buttons directly in the row
                market_cells = await el.query_selector_all("[class*='Odds'], [class*='odds']")

            markets_data = {}
            for cell in market_cells:
                cell_data = await self._parse_market_cell(cell)
                if cell_data:
                    # cell_data is {canonical_key: {"price": float, "zone": str, "label": str}}
                    markets_data.update(cell_data)

            if not markets_data:
                return None

            # Build the odds entry
            return {
                "type": "match_odds",
                "league": league_name,
                "home_team": home_team,
                "away_team": away_team,
                "match_datetime": match_datetime,
                "markets": markets_data,
                "source": "bet365_odds",
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            print(f"    odds extraction error: {e}")
            return None

    async def _parse_market_cell(self, cell) -> Optional[Dict[str, Dict[str, Any]]]:
        """Parse a single market cell into canonical market odds.

        Returns a dict mapping canonical_key -> {"price": float, "zone": str, "label": str}
        """
        try:
            # Try to find the market header (e.g., "1X2", "Over/Under 2.5", "BTTS")
            header = await cell.query_selector("[class*='MarketName'], [class*='market-name'], [class*='title']")
            market_name = (await header.text_content() or "").strip() if header else "unknown"

            # Find all outcome buttons in this cell
            outcomes = await cell.query_selector_all("[class*='Odds'], [class*='odds'], [class*='Outcome'], [class*='outcome']")

            result = {}
            for out in outcomes:
                out_text = await out.text_content()
                if not out_text:
                    continue
                out_text = out_text.strip()

                # Pattern: "OutcomeName\nPrice" or "OutcomeName Price"
                # Common Bet365 format: the odds value is often in a span
                price_elem = await out.query_selector("[class*='Price'], [class*='price'], [class*='Odd'], [class*='odd']")
                if price_elem:
                    price_text = (await price_elem.text_content() or "").strip()
                else:
                    # Split by whitespace/newline and take the last numeric token
                    parts = re.split(r'\s+', out_text)
                    price_text = parts[-1] if parts else ""

                try:
                    price = float(price_text)
                except ValueError:
                    continue

                # Extract outcome name (everything before the price)
                outcome_name = out_text[:-len(price_text)].strip() if price_text else out_text
                outcome_name = re.sub(r'\s+\d+\.\d+$', '', outcome_name).strip()

                # Map Bet365 outcome name + market_name to canonical key
                canonical = self._map_bet365_to_canonical(market_name, outcome_name)
                if canonical:
                    zone = classify_zone(price)
                    result[canonical] = {
                        "price": price,
                        "zone": zone,
                        "label": _MARKET_LABEL.get(canonical, canonical)
                    }

            return result if result else None
        except Exception:
            return None

    def _map_bet365_to_canonical(self, market_name: str, outcome_name: str) -> Optional[str]:
        """Map Bet365 market name + outcome name to OLP XDV canonical key.

        This is the single place where Bet365's display labels are translated
        into our canonical identity keys. The mapping is intentionally strict —
        if a market/outcome isn't recognized, we return None so it becomes an
        honest NONE zone in the output rather than a fabricated canonical key.
        """
        market_lower = market_name.lower()
        outcome_lower = outcome_name.lower()

        # 1X2 / Match Winner
        if "match" in market_lower and "winner" in market_lower or "1x2" in market_lower:
            if outcome_lower in ("1", "home", "home win"):
                return "1X2_HOME"
            if outcome_lower in ("x", "draw"):
                return "1X2_DRAW"
            if outcome_lower in ("2", "away", "away win"):
                return "1X2_AWAY"

        # Totals (Over/Under at various lines)
        if "over" in market_lower and "under" in market_lower or "total" in market_lower:
            # Extract line from market name (e.g., "Over/Under 2.5" -> 2.5)
            line_match = re.search(r'(\d+\.?\d*)', market_name)
            line = float(line_match.group(1)) if line_match else 2.5

            if outcome_lower in ("over", "o"):
                if line == 0.5: return "OVER_0_5"
                if line == 1.5: return "OVER_1_5"
                if line == 2.5: return "OVER_2_5"
                if line == 3.5: return "OVER_3_5"
            if outcome_lower in ("under", "u"):
                if line == 0.5: return "UNDER_0_5"
                if line == 1.5: return "UNDER_1_5"
                if line == 2.5: return "UNDER_2_5"
                if line == 3.5: return "UNDER_3_5"

        # BTTS (Both Teams To Score)
        if "both" in market_lower and "score" in market_lower or "btts" in market_lower or "gg" in market_lower:
            if outcome_lower in ("yes", "gg", "both teams to score"):
                return "BTTS_YES"
            if outcome_lower in ("no", "ng", "no goal"):
                return "BTTS_NO"

        # Double Chance
        if "double" in market_lower and "chance" in market_lower or "dc" in market_lower:
            if "1x" in outcome_lower or "home/draw" in outcome_lower:
                return "DC_1X"
            if "x2" in outcome_lower or "draw/away" in outcome_lower:
                return "DC_X2"
            if "12" in outcome_lower or "home/away" in outcome_lower:
                return "DC_12"

        # Draw No Bet
        if "draw" in market_lower and "bet" in market_lower or "dnb" in market_lower:
            if "1" in outcome_lower or "home" in outcome_lower:
                return "DNB_HOME"
            if "2" in outcome_lower or "away" in outcome_lower:
                return "DNB_AWAY"

        # HT/FT (Half Time / Full Time)
        if "half" in market_lower and "full" in market_lower or "ht" in market_lower and "ft" in market_lower:
            # Outcome format: "1/1", "1/X", "1/2", "X/1", "X/X", "X/2", "2/1", "2/X", "2/2"
            htft_map = {
                "1/1": "HT_FT_11", "1/x": "HT_FT_1X", "1/2": "HT_FT_12",
                "x/1": "HT_FT_X1", "x/x": "HT_FT_XX", "x/2": "HT_FT_X2",
                "2/1": "HT_FT_21", "2/x": "HT_FT_2X", "2/2": "HT_FT_22",
            }
            return htft_map.get(outcome_lower.replace(" ", ""))

        # Correct Score
        if "correct" in market_lower and "score" in market_lower or "exact" in market_lower:
            # Outcome format: "1:0", "0:1", "1:1", "2:0", "0:2", "2:1", "1:2", "2:2", "0:0", "3:0", "0:3", "3:1", "1:3"
            cs_map = {
                "1:0": "CS_1_0", "0:1": "CS_0_1", "1:1": "CS_1_1",
                "2:0": "CS_2_0", "0:2": "CS_0_2", "2:1": "CS_2_1",
                "1:2": "CS_1_2", "2:2": "CS_2_2", "0:0": "CS_0_0",
                "3:0": "CS_3_0", "0:3": "CS_0_3", "3:1": "CS_3_1",
                "1:3": "CS_1_3",
            }
            key = outcome_lower.replace(" ", "").replace("-", ":")
            return cs_map.get(key)

        return None

    async def scrape_all(self) -> List[dict[str, Any]]:
        all_results: List[dict[str, Any]] = []
        for league in self.leagues:
            try:
                fixtures = await self.scrape_league_fixtures(league)
                all_results.extend(fixtures)
            except Exception as e:
                print(f"  [{datetime.now().isoformat()}] {league}: ERROR {e}")
                continue
        return all_results

    def save_results(self, results: List[dict[str, Any]]) -> Path:
        """Save all results, splitting into fixtures and odds feeds.

        Two files are written:
          - bet365_fixtures_{ts}.jsonl  : type=match_1x2  (for F2 quorum)
          - bet365_odds_{ts}.jsonl      : type=match_odds (all canonical markets, zoned)

        The odds file carries every market odds we found plus its zone label
        (SAFE / 5050 / WATCH / FLOOR / NONE) so downstream consumers can see the
        MAX_ODDS_CAP / MIN_ODDS_FLOOR / PREFERRED_ODDS_CEILING picture natively.
        """
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        fixtures_file = self.OUTPUT_DIR / f"bet365_fixtures_{ts}.jsonl"
        odds_file = self.OUTPUT_DIR / f"bet365_odds_{ts}.jsonl"

        fixtures_count = 0
        odds_count = 0
        markets_found = 0
        zone_counts = {"SAFE": 0, "5050": 0, "WATCH": 0, "FLOOR": 0, "NONE": 0}

        with fixtures_file.open("w", encoding="utf-8") as ff, odds_file.open("w", encoding="utf-8") as of:
            for entry in results:
                if entry.get("type") == "match_1x2":
                    ff.write(json.dumps(entry) + "\n")
                    fixtures_count += 1
                elif entry.get("type") == "match_odds":
                    of.write(json.dumps(entry) + "\n")
                    odds_count += 1
                    for mkt in entry.get("markets", {}).values():
                        markets_found += 1
                        zone = mkt.get("zone", "NONE")
                        if zone in zone_counts:
                            zone_counts[zone] += 1

        print(f"[{datetime.now().isoformat()}] Saved {fixtures_count} fixtures to {fixtures_file}")
        print(f"[{datetime.now().isoformat()}] Saved {odds_count} odds entries ({markets_found} total market-odds) to {odds_file}")
        print(f"[{datetime.now().isoformat()}] Zone breakdown: "
              f"SAFE={zone_counts['SAFE']} 5050={zone_counts['5050']} "
              f"WATCH={zone_counts['WATCH']} FLOOR={zone_counts['FLOOR']} NONE={zone_counts['NONE']}")
        return fixtures_file


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Bet365 fixtures scraper")
    parser.add_argument("--leagues", nargs="*", help="Specific league names to scrape (default: all mapped)")
    parser.add_argument("--headless", action="store_true", default=True)
    parser.add_argument("--max-matches", type=int, default=50, help="Max matches per league")
    args = parser.parse_args()

    async with Bet365FixturesScraper(
        headless=args.headless,
        leagues=args.leagues,
        max_matches_per_league=args.max_matches,
    ) as scraper:
        results = await scraper.scrape_all()
        scraper.save_results(results)

        fixtures = [r for r in results if r.get("type") == "match_1x2"]
        odds_entries = [r for r in results if r.get("type") == "match_odds"]

        print("\n" + "="*60)
        print("📊 BET365 SCRAPING SUMMARY")
        print("="*60)

        by_league: dict[str, int] = {}
        for r in fixtures:
            by_league[r["league"]] = by_league.get(r["league"], 0) + 1

        for lg, cnt in sorted(by_league.items()):
            print(f"  {lg}: {cnt} fixtures")
        print(f"\nTOTAL: {len(fixtures)} fixtures across {len(by_league)} leagues")
        print(f"TOTAL: {len(odds_entries)} odds entries (all canonical markets zoned)")

        # Zone summary across all odds entries
        zone_totals = {"SAFE": 0, "5050": 0, "WATCH": 0, "FLOOR": 0, "NONE": 0}
        for oe in odds_entries:
            for mkt in oe.get("markets", {}).values():
                z = mkt.get("zone", "NONE")
                if z in zone_totals:
                    zone_totals[z] += 1
        print(f"\nODDS ZONE BREAKDOWN (MAX_ODDS_CAP={MAX_ODDS_CAP}, "
              f"PREFERRED_CEILING={PREFERRED_ODDS_CEILING}, FLOOR={MIN_ODDS_FLOOR}):")
        print(f"  SAFE   (1.20-1.50, preferred): {zone_totals['SAFE']}")
        print(f"  5050   (1.50-2.00, fallback) : {zone_totals['5050']}")
        print(f"  WATCH  (>2.00, ID420 watch)  : {zone_totals['WATCH']}")
        print(f"  FLOOR  (<1.20, reject)       : {zone_totals['FLOOR']}")
        print(f"  NONE   (not parsed)          : {zone_totals['NONE']}")


if __name__ == "__main__":
    asyncio.run(main())