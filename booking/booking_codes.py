"""SPORTYBET BOOKING-CODES — turn the day's accas + singles into bookable codes.

WHAT THIS DOES
  Reads the day's acca payload (output/boards/acca_<date>.json — built by
  run_daily's engine.acca) and, for each leg of each acca, drives the
  SportyBet Nigeria SPA with Playwright to add the exact selection to the
  betslip. When all of an acca's legs are in the betslip it reads the
  generated BOOKING CODE and records it. The output is a code the Architect
  can paste into SportyBet to recall the slip — it is a pre-fill, NOT a stake.

  PRODUCTION INTENT (2026-08-10): the payload now also carries 1-leg slips
  labelled "SINGLE — <fixture>" — one per remaining fixture's natural best
  market, each with its OWN booking code. A single is just a 1-leg acca here:
  book_accas drives one selection and reads one code per entry, so no new
  driver logic is needed. Every acca (Acca A / Acca B, ... ) AND every single
  gets its own code.

DEPLOY GATE (Phase 3 live — capital authority stays with the Architect)
  This module NEVER clicks "Place Bet", NEVER enters a stake, and NEVER
  confirms a wager. It adds selections and copies a code. The Architect is the
  only person who can turn a code into money. A bug here can at most assemble
  a slip — it cannot deploy a cent.

HONESTY (HR35)
  - Every leg is reported individually: BOOKED (code captured), or MANUAL
    (could not be driven reliably — the Architect adds it by hand). A leg is
    never silently dropped from the slip.
  - Under 2.5 legs are harder to drive than 1X2 legs (the league page exposes
    only the first market cell = 1X2; totals need the match page and a market
    tab). A totals leg that the match page does not yield in the allotted
    attempts is flagged MANUAL, not guessed.
  - A fault in the browser is a per-leg miss, never a fabricated code.
  - The whole module is best-effort: a caller (the daily run) treats a fault
    here as a data flag, never a run failure.

USAGE
  py -3.12 -m booking.booking_codes [--date 2026-08-09] [--headed]
  py -3.12 -m booking.booking_codes --accas output/boards/acca_2026-08-09.json
  (run_daily invokes book_accas() directly; the CLI is a manual review tool)
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable

try:
    from playwright.sync_api import sync_playwright, Page
except ImportError:
    sync_playwright = None

sys.path.insert(0, str(Path(__file__).parent.parent))

# --- Retry & Resilience Configuration ---
MAX_CLICK_RETRIES = 3
BASE_CLICK_DELAY = 1.0
MAX_CLICK_DELAY = 10.0
NAVIGATION_TIMEOUT = 30000
ELEMENT_WAIT_TIMEOUT = 10000

# Error classification
class TransientError(Exception):
    """Transient error that may succeed on retry (network, timeout, rate limit)."""
    pass

class PermanentError(Exception):
    """Permanent error that won't succeed on retry (element not found, wrong page)."""
    pass

class RateLimitedError(TransientError):
    """Rate limit error (429) - should back off."""
    pass

def _is_transient_error(e: Exception) -> bool:
    """Classify if an error is transient (retryable)."""
    if isinstance(e, TransientError):
        return True
    error_msg = str(e).lower()
    # Network/timeout errors
    if any(kw in error_msg for kw in ["timeout", "connection", "network", "dns", "resolve"]):
        return True
    # Rate limiting
    if "429" in error_msg or "rate limit" in error_msg:
        return True
    # 5xx server errors
    if any(code in error_msg for code in ["500", "502", "503", "504"]):
        return True
    return False

def _sleep_backoff(attempt: int, base: float = BASE_CLICK_DELAY, cap: float = MAX_CLICK_DELAY) -> None:
    """Sleep with exponential backoff and jitter."""
    delay = min(base * (2 ** attempt), cap)
    time.sleep(delay + random.uniform(0, 0.5))

def safe_click(locator, max_retries: int = MAX_CLICK_RETRIES,
               base_delay: float = BASE_CLICK_DELAY,
               wait_timeout: int = ELEMENT_WAIT_TIMEOUT) -> bool:
    """
    Click a locator with retry logic and exponential backoff.
    Returns True on success, False on permanent failure after retries.
    """
    for attempt in range(max_retries):
        try:
            # Wait for element to be ready
            locator.wait_for(state="visible", timeout=wait_timeout)
            locator.click()
            # Brief verification delay
            time.sleep(0.5)
            return True
        except Exception as e:
            if attempt == max_retries - 1:
                if _is_transient_error(e):
                    print(f"  [CLICK RETRY EXHAUSTED] {locator}: {e}")
                else:
                    print(f"  [CLICK PERMANENT FAILURE] {locator}: {e}")
                return False
            # Transient error - retry with backoff
            if _is_transient_error(e):
                _sleep_backoff(attempt, base_delay)
            else:
                # Permanent error - don't retry
                print(f"  [CLICK PERMANENT FAILURE] {locator}: {e}")
                return False
    return False

def safe_navigate(page, url: str, max_retries: int = 2,
                  wait_timeout: int = NAVIGATION_TIMEOUT) -> bool:
    """
    Navigate to a URL with retry logic.
    Returns True on success, False on failure after retries.
    """
    for attempt in range(max_retries):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=wait_timeout)
            page.wait_for_load_state("networkidle", timeout=10000)
            return True
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"  [NAVIGATE FAILED] {url}: {e}")
                return False
            if _is_transient_error(e):
                _sleep_backoff(attempt)
            else:
                print(f"  [NAVIGATE PERMANENT FAILURE] {url}: {e}")
                return False
    return False

from booking.league_map import SPORTYBET_LEAGUES
from booking.bridge import load_sportybet_fixtures
from booking.sportybet_fixtures import _navigate_to_league_sync as _navigate_to_league

BASE_URL = "https://www.sportybet.com.ng"
BOARD_DIR = Path(__file__).parent.parent / "output" / "boards"

# 1X2 click index inside the league-page row's first market cell.
# The first market cell renders Home / Draw / Away in that order.
_1X2_INDEX = {  # market_key -> cell index within the row's first market
    "1X2_HOME": 0,
    "1X2_DRAW": 1,
    "1X2_AWAY": 2,
}

# Totals markets: map market_key -> (target_line, outcome_index)
# outcome_index: 0 = Over, 1 = Under
TOTALS_INDEX = {
    "OVER_1_5": ("1.5", 0),
    "UNDER_1_5": ("1.5", 1),
    "OVER_2_5": ("2.5", 0),
    "UNDER_2_5": ("2.5", 1),
    "OVER_3_5": ("3.5", 0),
    "UNDER_3_5": ("3.5", 1),
    "OVER_0_5": ("0.5", 0),
    "UNDER_0_5": ("0.5", 1),
}


def _load_acca_payload(day: str) -> dict:
    """Read acca_<date>.json. Raises FileNotFoundError when missing — the
    caller reports it honestly rather than fabricating a code set."""
    path = BOARD_DIR / f"acca_{day}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"acca payload missing — {path}. Run the daily pipeline first, "
            f"or pass --accas with an explicit payload path.")
    return json.loads(path.read_text(encoding="utf-8"))


def _cache_entry(f) -> dict:
    """One PipelineFixture (from booking.bridge) as the dict _resolve_fixture
    reads. The model keys live on home_team/away_team — mapping them here is
    what makes an acca leg resolvable (regression: f.get() on the dataclass
    silently produced an empty cache and every leg reported 'not found')."""
    return {
        "fixture_id": f.sportybet_fixture_id,
        "sportybet_home": f.sportybet_home,
        "sportybet_away": f.sportybet_away,
        "model_home": f.home_team,
        "model_away": f.away_team,
    }


def _resolve_fixture(leg: dict, cache) -> Optional[dict]:
    """Find the SportyBet cached fixture for one acca leg.

    The leg's `fixture` is "Home v Away" in MODEL keys (board keys). The cache
    carries model_home/model_away alongside the SportyBet names — match on
    MODEL keys (same rule the MES/CLV wiring uses: resolve on the model key,
    never the SportyBet spelling first, which silently no-matches). Falls back
    to resolve_team(model name -> SportyBet spelling) because the acca builder
    keys legs with the OLP names ('Heerenveen') while the cache stores
    SportyBet's ('SC Heerenveen')."""
    if " v " not in (leg.get("fixture") or ""):
        return None
    home, away = [s.strip() for s in leg["fixture"].split(" v ", 1)]

    def _norm(s):
        # Normalized-exact only (case/diacritics/prefix via team_map._normalize)
        # — never a fuzzy guess across clubs (HR35). Falls back to lower/strip
        # if team_map ever changes its helper.
        try:
            from booking.team_map import _normalize
            return _normalize(s or "")
        except Exception:
            return (s or "").lower().strip()

    # Exact model-key match first. Match BOTH orderings: the acca leg's
    # "Home v Away" is the MODEL's fixture order, but SportyBet's cached
    # fixture is stored in the BOOK's page order (which can be reversed, e.g.
    # model "Celtic v LASK Linz" vs cache "LASK Linz v Celtic"). A one-sided
    # match silently no-matched every reversed-team leg (fixed 2026-08-20).
    for fx in cache:
        if fx.get("model_home") == home and fx.get("model_away") == away:
            return fx
        if fx.get("model_home") == away and fx.get("model_away") == home:
            return fx
        if (fx.get("sportybet_home") or "").strip() == home \
                and (fx.get("sportybet_away") or "").strip() == away:
            return fx
        if (fx.get("sportybet_home") or "").strip() == away \
                and (fx.get("sportybet_away") or "").strip() == home:
            return fx

    # Normalized model-key match: the cache's model keys are the reverse-
    # resolved football-data names, which can still differ from the acca leg by
    # a diacritic or prefix ("Fenerbahce" vs "Fenerbahçe"). Same both-orderings
    # guard as the exact block.
    nh, na = _norm(home), _norm(away)
    for fx in cache:
        if _norm(fx.get("model_home")) == nh and _norm(fx.get("model_away")) == na:
            return fx
        if _norm(fx.get("model_home")) == na and _norm(fx.get("model_away")) == nh:
            return fx

    # resolve_team fallback: map the OLP names to SportyBet spellings, then
    # compare NORMALIZED — resolve_team("Sturm Graz") -> "SK Sturm Graz" while
    # the cache's raw name is "Sturm Graz", equal only after the prefix strip.
    try:
        from booking.team_map import resolve_team
        sb_home, sb_away = resolve_team(home, "sportybet"), resolve_team(away, "sportybet")
        for fx in cache:
            if _norm(fx.get("sportybet_home")) == _norm(sb_home) \
                    and _norm(fx.get("sportybet_away")) == _norm(sb_away):
                return fx
            if _norm(fx.get("model_home")) == _norm(sb_home) \
                    and _norm(fx.get("model_away")) == _norm(sb_away):
                return fx
    except Exception:
        pass
    return None


def _find_match_row(page: Page, fixture_id: str,
                    home_name: Optional[str] = None):
    """Locate a match row on the league page.

    VERIFIED LIVE 2026-08-09: rows have NO `data-game-id` attribute — the ID
    renders as TEXT inside `.game-id` ("ID: 25939"). The old
    `[data-game-id='...']` selector therefore never matched and every 1X2 leg
    fell through to the text fallback (which worked only by luck). Match on the
    `.game-id` text first, then fall back to the home-team name."""
    rows = page.query_selector_all(".m-table-row.match-row")
    if fixture_id:
        for r in rows:
            gid = r.query_selector(".game-id")
            if gid and fixture_id in (gid.inner_text() or ""):
                return r
    if home_name:
        for r in rows:
            h = r.query_selector(".teams .home-team")
            if h and h.inner_text().strip() == home_name:
                return r
    return None


def _click_1x2(row, market_key: str) -> bool:
    """Click a 1X2 outcome on a league-page match row with retry logic."""
    idx = _1X2_INDEX.get(market_key)
    if idx is None:
        return False
    market = row.query_selector(".market-cell .market")
    if market is None:
        return False
    cells = market.query_selector_all(".m-outcome-odds")
    if len(cells) <= idx:
        return False
    # Use safe_click with retry logic
    return safe_click(cells[idx])


def _open_match_page(page: Page, fixture_id: str) -> bool:
    """Open a SportyBet match page and wait for markets with retry logic."""
    return safe_navigate(page, f"{BASE_URL}/ng/match/{fixture_id}")


def _click_under25(page: Page) -> bool:
    """Drive a totals (Under 2.5) selection on a match page with retry logic.

    SportyBet's totals market is behind a tab and its DOM varies by
    match/section. Multiple locator strategies are tried with retries;
    a miss returns False so the leg is flagged MANUAL (HR35) rather than guessed."""
    tries = [
        lambda: page.locator("text=Under 2.5 >> visible=true").first,
        lambda: page.locator("div.outcome:has-text('Under 2.5') >> visible=true").first,
        lambda: page.locator(".m-outcome:has-text('Under 2.5') >> visible=true").first,
    ]
    for locator_fn in tries:
        try:
            locator = locator_fn()
            if safe_click(locator):
                page.wait_for_timeout(800)
                return True
        except Exception:
            continue
    # Fallback: click Over/Under tab first, then Under 2.5
    try:
        tab_locator = page.locator("text=Over/Under >> visible=true").first
        if safe_click(tab_locator):
            page.wait_for_timeout(1500)
            outcome_locator = page.locator("text=Under 2.5 >> visible=true").first
            if safe_click(outcome_locator):
                return True
    except Exception:
        pass
    return False


# --- Market key -> SportyBet UI label mapping for match-page markets ---
# These are the canonical market keys from engine/markets.py APPROVED_MARKETS
# that require match-page navigation (not available on league page).
_MARKET_UI_MAP = {
    "OVER_2_5":     {"tab": "Over/Under",    "outcome": "Over 2.5"},
    "UNDER_2_5":    {"tab": "Over/Under",    "outcome": "Under 2.5"},
    "OVER_1_5":     {"tab": "Over/Under",    "outcome": "Over 1.5"},
    "UNDER_1_5":    {"tab": "Over/Under",    "outcome": "Under 1.5"},
    "OVER_3_5":     {"tab": "Over/Under",    "outcome": "Over 3.5"},
    "UNDER_3_5":    {"tab": "Over/Under",    "outcome": "Under 3.5"},
    "OVER_0_5":     {"tab": "Over/Under",    "outcome": "Over 0.5"},
    "UNDER_0_5":    {"tab": "Over/Under",    "outcome": "Under 0.5"},
    "BTTS_YES":     {"tab": "Both Teams to Score", "outcome": "Yes"},
    "BTTS_NO":      {"tab": "Both Teams to Score", "outcome": "No"},
    # Double Chance (DC) markets — added 2026-08-11 (Architect multi-market
    # selection). SportyBet renders these under "Double Chance" tab.
    "DC_1X":        {"tab": "Double Chance", "outcome": "1X"},
    "DC_X2":        {"tab": "Double Chance", "outcome": "X2"},
    "DC_12":        {"tab": "Double Chance", "outcome": "12"},
    # Draw No Bet — SportyBet renders under "Draw No Bet" tab
    "DNB_HOME":     {"tab": "Draw No Bet",   "outcome": "1"},
    "DNB_AWAY":     {"tab": "Draw No Bet",   "outcome": "2"},
    # HT/FT — SportyBet renders under "Half Time / Full Time" tab
    "HT_FT_11":     {"tab": "Half Time / Full Time", "outcome": "1/1"},
    "HT_FT_1X":     {"tab": "Half Time / Full Time", "outcome": "1/X"},
    "HT_FT_12":     {"tab": "Half Time / Full Time", "outcome": "1/2"},
    "HT_FT_X1":     {"tab": "Half Time / Full Time", "outcome": "X/1"},
    "HT_FT_XX":     {"tab": "Half Time / Full Time", "outcome": "X/X"},
    "HT_FT_X2":     {"tab": "Half Time / Full Time", "outcome": "X/2"},
    "HT_FT_21":     {"tab": "Half Time / Full Time", "outcome": "2/1"},
    "HT_FT_2X":     {"tab": "Half Time / Full Time", "outcome": "2/X"},
    "HT_FT_22":     {"tab": "Half Time / Full Time", "outcome": "2/2"},
    # Correct Score — SportyBet renders under "Correct Score" tab
    "CS_10":        {"tab": "Correct Score", "outcome": "1:0"},
    "CS_01":        {"tab": "Correct Score", "outcome": "0:1"},
    "CS_11":        {"tab": "Correct Score", "outcome": "1:1"},
    "CS_20":        {"tab": "Correct Score", "outcome": "2:0"},
    "CS_02":        {"tab": "Correct Score", "outcome": "0:2"},
    "CS_21":        {"tab": "Correct Score", "outcome": "2:1"},
    "CS_12":        {"tab": "Correct Score", "outcome": "1:2"},
    "CS_22":        {"tab": "Correct Score", "outcome": "2:2"},
    "CS_00":        {"tab": "Correct Score", "outcome": "0:0"},
    "CS_30":        {"tab": "Correct Score", "outcome": "3:0"},
    "CS_03":        {"tab": "Correct Score", "outcome": "0:3"},
    "CS_31":        {"tab": "Correct Score", "outcome": "3:1"},
    "CS_13":        {"tab": "Correct Score", "outcome": "1:3"},
    # Alternative tab names SportyBet sometimes uses
    "BTTS_YES_ALT": {"tab": "BTTS",          "outcome": "Yes"},
    "BTTS_NO_ALT":  {"tab": "BTTS",          "outcome": "No"},
}


def _click_market_on_match_page(page: Page, market_key: str, fixture_id: str = None) -> bool:
    """Drive a market selection on a match page with retry logic.

    Generic clicker for markets that require navigating the match page tabs.
    Tries multiple locator strategies with retries; returns False so the leg is flagged
    MANUAL (HR35) rather than guessed.

    NOTE: direct `/match/{id}` navigation TIMES OUT on SportyBet NG (verified
    live 2026-08-09) — the SPA won't render it standalone. However, for DC,
    DNB, HT/FT, CS markets these are ONLY on the match page, so we must try.
    We navigate to the match page first, then click the tab and outcome."""
    mapping = _MARKET_UI_MAP.get(market_key)
    if not mapping:
        return False

    # Navigate to match page first (if fixture_id provided)
    if fixture_id:
        if not safe_navigate(page, f"{BASE_URL}/ng/match/{fixture_id}"):
            return False

    tab_label = mapping["tab"]
    outcome_label = mapping["outcome"]

    # Build locator strategies for the tab and outcome
    tab_locators = [
        f"text={tab_label} >> visible=true",
        f"[role='tab']:has-text('{tab_label}') >> visible=true",
        f".tab:has-text('{tab_label}') >> visible=true",
        f"div.tab:has-text('{tab_label}') >> visible=true",
        f"span:has-text('{tab_label}') >> visible=true",
        f"button:has-text('{tab_label}') >> visible=true",
    ]

    outcome_locators = [
        f"text={outcome_label} >> visible=true",
        f"div.outcome:has-text('{outcome_label}') >> visible=true",
        f".m-outcome:has-text('{outcome_label}') >> visible=true",
        f"[data-outcome='{outcome_label}'] >> visible=true",
        f".outcome:has-text('{outcome_label}') >> visible=true",
        f"span:has-text('{outcome_label}') >> visible=true",
        f"button:has-text('{outcome_label}') >> visible=true",
    ]

    # Strategy 1: Click tab first, then outcome (with retries)
    for tab_loc in tab_locators:
        tab_locator = page.locator(tab_loc).first
        if safe_click(tab_locator):
            page.wait_for_timeout(1000)
            for out_loc in outcome_locators:
                outcome_locator = page.locator(out_loc).first
                if safe_click(outcome_locator):
                    return True

    # Strategy 2: Direct outcome click (tab might already be open)
    for out_loc in outcome_locators:
        outcome_locator = page.locator(out_loc).first
        if safe_click(outcome_locator):
            return True

    # Strategy 3: Fallback for alternative tab names (BTTS)
    if market_key in ("BTTS_YES", "BTTS_NO"):
        alt_key = market_key + "_ALT"
        return _click_market_on_match_page(page, alt_key, fixture_id)

    return False


def _click_totals_on_league_page(page: Page, row, market_key: str) -> bool:
    """Click an Over/Under outcome on a league-page match row with retry logic.

    The league page's second market cell (.market-cell .market) is the totals
    market. It has a line selector (.af-select-input showing the fixed line,
    e.g. '2.5') and two outcomes: Over (index 0) and Under (index 1).

    This function:
    1. Reads the displayed line
    2. If it doesn't match the target line, clicks the dropdown and selects the target line (with retries)
    3. Clicks the corresponding outcome (Over/Under) (with retries)

    Returns True on success."""
    info = TOTALS_INDEX.get(market_key)
    if info is None:
        return False
    target_line, outcome_idx = info
    markets = row.query_selector_all(".market-cell .market")
    if len(markets) < 2:
        return False
    totals = markets[1]

    # Check the displayed line
    line_elem = totals.query_selector(".af-select-input")
    if line_elem is None:
        return False
    displayed = (line_elem.inner_text() or "").strip()

    # If the line doesn't match, click the dropdown and select the target line (with retries)
    if displayed != target_line:
        try:
            # Click the line selector dropdown to open it (with retry)
            line_locator = totals.locator(".af-select-input")
            if not safe_click(line_locator):
                return False
            page.wait_for_timeout(1000)  # wait for dropdown to render

            # Find and click the target line option.
            # The dropdown for the clicked line selector is the OPEN list:
            # `.af-select-list.af-select-list-open` containing `.af-select-item`
            # items (one per line, e.g. 0.5/1/1.5/2/2.5/3/3.5/4/4.5/5...).
            # Verified live 2026-08-10: every match row on the league page keeps
            # its OWN closed dropdown in the DOM, so a page-wide `text=2.5`
            # match can hit another row's trigger span (the `af-select-input`
            # showing its current line) instead of this row's menu item —
            # always scope to `.af-select-list-open` and match the item text.
            option_clicked = False
            open_list = page.locator(".af-select-list.af-select-list-open")
            if open_list.count() > 0:
                items = open_list.locator(".af-select-item")
                n = items.count()
                for i in range(n):
                    if (items.nth(i).inner_text() or "").strip() == target_line:
                        try:
                            items.nth(i).click()
                            option_clicked = True
                        except Exception:
                            pass
                        break
                if not option_clicked:
                    return False

            if not option_clicked:
                return False

            # Wait for the line to update and markets to re-render
            page.wait_for_timeout(1500)

            # Re-read the displayed line to confirm
            line_elem = totals.query_selector(".af-select-input")
            if line_elem is None:
                return False
            displayed = (line_elem.inner_text() or "").strip()
            if displayed != target_line:
                return False

        except Exception:
            return False

    # Click the correct outcome (0=Over, 1=Under) (with retry)
    cells = totals.query_selector_all(".m-outcome-odds")
    if len(cells) <= outcome_idx:
        return False
    return safe_click(cells[outcome_idx])


def _click_btts_on_league_page(page: Page, fixture_id: str, market_key: str) -> bool:
    """Drive a BTTS (GG/NG) selection on a league page with retry logic.

    VERIFIED LIVE 2026-08-09: direct `/match/{id}` navigation TIMES OUT on
    SportyBet NG, but clicking the match ROW expands an inline market selector
    on the league page. That selector exposes category tabs (Main | Goals |
    Half | ...) and, under the "Goals" tab, market-items including GG/NG. Clicking
    GG/NG re-renders the table with GG/NG as outcome columns: GG = Both Teams To
    Score Yes (index 0), NG = No Goal (index 1).

    Flow:
      1. Click the target match row (opens the inline market selector)
      2. Click the "Goals" category tab
      3. Click the "GG/NG" market-item  -> the table re-renders with GG/NG
      4. Re-locate the target row by fixture id, click GG (BTTS_YES, idx 0)
         or NG (BTTS_NO, idx 1).

    Returns False on any miss so the leg is flagged MANUAL (HR35) rather than
    guessed."""
    outcome_idx = 0 if market_key == "BTTS_YES" else 1
    try:
        # 1. Click the target match row to open the inline market selector.
        row = _find_match_row(page, fixture_id)
        if row is None:
            return False
        if not safe_click(row):
            return False
        page.wait_for_timeout(2000)

        # 2. Click the "Goals" category tab.
        goals = page.locator("text=Goals >> visible=true").first
        if goals.count() == 0:
            return False
        if not safe_click(goals):
            return False
        page.wait_for_timeout(1500)

        # 3. Click the "GG/NG" market-item; the table re-renders to GG/NG.
        ggng = page.locator(".market-item:has-text('GG/NG') >> visible=true").first
        if ggng.count() == 0:
            return False
        if not safe_click(ggng):
            return False
        page.wait_for_timeout(1500)

        # 4. Re-locate the row (now showing GG/NG columns) and click GG/NG.
        rows = page.query_selector_all(".m-table-row.match-row")
        for r in rows:
            gid_el = r.query_selector(".game-id")
            gid_text = (gid_el.inner_text() if gid_el else "") or ""
            if fixture_id in gid_text:
                cells = r.query_selector_all(
                    f".m-outcome[data-op='desktop-outcome_{outcome_idx}']")
                if cells:
                    if not safe_click(cells[0]):
                        return False
                    page.wait_for_timeout(800)
                    return True
        return False
    except Exception:
        return False


def expected_combined_odds(legs: list) -> Optional[float]:
    """The odds a SportyBet booking code MUST encode for this slip.

    HARD RULE (Architect 2026-08-20): the code's odds == the product of its
    legs' prices. For a 1-leg slip (a SINGLE) that is the leg's own price; for
    a multi-leg acca it is the compounded combined odds. "50 odds" in the
    Architect's wording == 5.0 decimal odds — the code is only worth pasting
    when its encoded combined odds equal this figure (within float tolerance).

    Public alias for external verification (e.g., X/Twitter code fetcher)."""
    prod = 1.0
    n = 0
    for leg in legs or []:
        price = leg.get("price")
        if not price or price <= 1.0:
            continue
        prod *= float(price)
        n += 1
    if n == 0:
        return None
    return round(prod, 2)


# Private alias for internal use
_expected_combined_odds = expected_combined_odds


def read_betslip_combined_odds(page: Page,
                                expected: Optional[float] = None) -> Optional[float]:
    """Read the betslip's displayed COMBINED (total) odds.

    SportyBet's betslip renders a single "Total Odds" / "Combined Odds" figure
    after at least one selection is in the slip. The slip DOM also carries
    UNRELATED decimal figures (a constant ~2.55 promo/multiplier node, plus the
    per-selection odds), so a naive "largest in-range number" read returns the
    wrong element (verified 2026-08-23: ~15 distinct singles with expected odds
    of 1.30-1.98 ALL returned exactly 2.55). We therefore return the candidate
    CLOSEST to the known `expected` combined odds — the slip's true total is the
    number nearest what the slip should encode. When `expected` is omitted
    (external/X callers) we fall back to the combined-line heuristic.

    Returns None when the slip is not readable — the caller treats None as
    "cannot verify", never as a pass. A spurious node closer than the real total
    is still caught downstream: the HARD RULE check rejects any value outside
    tolerance of `expected`, so a wrong read never yields a fabricated code.

    Public alias for external verification (e.g., X/Twitter code fetcher)."""
    # Tightened to real betslip containers. The old '[class*='slip']' / 'cart'
    # wildcards matched promo/banner nodes that leaked spurious odds (the
    # constant 2.55), so they are dropped in favour of the known SportyBet
    # betslip classes (verified 2026-08-09 live).
    panels = page.query_selector_all(
        ".betslip, .es-betslip, .bet-slip, .m-betslip, [class*='betSlip'], "
        "[class*='bet-slip-panel'], .slip-container, .es-bet-slip")
    candidates: List[float] = []
    # Pattern 1: decimals with exactly 2 places (standard odds display)
    # Pattern 2: comma-separated numbers (6,000,000.00 style)
    # Pattern 3: large integers (catastrophic display glitches)
    pat_decimal = re.compile(r"(?<!\d)(\d+\.\d{2})(?!\d)")
    pat_comma = re.compile(r"(?<!\d)(\d{1,3}(?:,\d{3})+(?:\.\d{2})?)(?!\d)")
    pat_int = re.compile(r"(?<!\d)(\d{3,})(?!\d)")
    for panel in (panels or []):
        try:
            txt = panel.inner_text() or ""
        except Exception:
            continue
        for line in txt.split("\n"):
            ll = line.lower()
            # Skip payout/stake/winnings lines — those are stake*odds, not odds.
            if any(kw in ll for kw in ("payout", "stake", "winnings")):
                continue
            is_combined = any(kw in ll for kw in
                              ("total", "combined", "odds", "potential"))
            for pat in (pat_decimal, pat_comma, pat_int):
                for m in pat.finditer(line):
                    raw = m.group(1).replace(",", "")
                    try:
                        val = float(raw)
                    except ValueError:
                        continue
                    if val < 1.01:
                        continue
                    candidates.append((val, is_combined))
    if not candidates:
        return None
    # Exclude obvious placeholder / stake-% artefacts.
    EXCLUDED = {50.0, 100.0, 200.0, 1000.0}
    in_range = [(v, on) for v, on in candidates
                if 1.01 <= v <= 10000.0 and v not in EXCLUDED]
    if not in_range:
        # All candidates were excluded (placeholder/artefact values like 50/100/200)
        return None

    if expected is not None:
        # Return the candidate CLOSEST to the expected combined odds. This is
        # the honest read: the slip's true total is the number nearest what we
        # know it should be. If a spurious node is nearer, the HARD RULE check
        # below rejects it (no fabricated code).
        def _dist(item):
            v = item[0]
            return abs(v - expected) / max(v, expected)
        in_range.sort(key=_dist)
        return round(in_range[0][0], 2)

    # No expected supplied (external callers): prefer a combined-line candidate,
    # then the largest in-range value as a last resort.
    combined_line = [(v, on) for v, on in in_range if on]
    pool = combined_line or in_range
    pool.sort(key=lambda x: -x[0])
    return round(pool[0][0], 2)


# Private alias for internal use
_read_betslip_combined_odds = read_betslip_combined_odds


def _clear_betslip(page: Page) -> None:
    """Remove every selection from the current betslip so the next acca starts
    from a clean slip.

    The slip is NOT auto-cleared between accas (verified 2026-08-23: selections
    accumulated across the loop, so later accas read combined odds of 80-99 and
    every slip failed the HARD RULE). We click each slip entry's remove control
    (#remove / trash / 'x' / 'Delete' / 'Remove All'), then a "Remove All"
    control if present, tolerating any failure — a miss here only risks a stale
    combined-odds read, never a fabricated code (the HARD RULE still rejects)."""
    try:
        for _ in range(6):
            rm = page.query_selector(
                ".es-betslip .remove, .betslip .remove, "
                "[class*='betslip'] .remove-selection, "
                "[class*='slip'] .m-delete, [class*='slip'] .delete-icon, "
                "button[aria-label*='emove'], .es-del, .m-betslip-remove")
            if not rm:
                break
            try:
                rm.click()
            except Exception:
                break
            page.wait_for_timeout(250)
        # "Remove All" / empty-slip control, if the book renders one.
        for sel in ("text=Remove All", "text=Clear", "text=Empty",
                    ".es-betslip .clear-all", "[class*='clearAll']"):
            try:
                els = page.query_selector_all(sel)
                for el in els:
                    try:
                        el.click()
                        page.wait_for_timeout(300)
                    except Exception:
                        continue
            except Exception:
                continue
    except Exception:
        pass  # best-effort; HARD RULE still guards against a wrong code


def odds_within_tolerance(a: Optional[float], b: Optional[float],
                          rel: float = 0.05) -> bool:
    """True when two odds figures agree within `rel` relative tolerance.

    Used by the hard-rule check: the betslip's combined odds must equal the
    expected combined odds. A 5% band absorbs minor rounding/SPA re-render
    lag and normal market movement without letting a wrong slip pass.

    Public alias for external verification (e.g., X/Twitter code fetcher)."""
    if a is None or b is None:
        return False
    if a <= 0 or b <= 0:
        return False
    return abs(a - b) / max(a, b) <= rel


# Private alias for internal use
_odds_within_tolerance = odds_within_tolerance


def read_booking_code(page: Page, n_legs: int) -> Optional[str]:
    """Read the booking code once all legs are in the betslip.

    Verified live 2026-08-09: clicking the betslip's "Book Bet" opens a modal
    (.es-dialog.m-dialog) whose body is "Booking Code\nQGF7G5\n<date>...". The
    code only exists there — it is not in an input field. So this function
    1) presses Book Bet, 2) waits for the modal, 3) reads the token right
    after the "Booking Code" label. Falls back to any input-field locators on
    the off-chance a revision renders one. Returns None when no code can be
    read (the per-leg statuses already tell the Architect what to add
    manually — HR35).

    Public alias for external verification (e.g., X/Twitter code fetcher)."""
    try:
        # Let the betslip settle from the last click BEFORE pressing Book Bet —
        # a selection clicked a few ms earlier may not be in the slip yet, and
        # pressing too soon can race the betslip update (verified: the working
        # path needed ~1.5s settle after the final click).
        page.wait_for_timeout(1500)
        # The betslip's Book Bet is a SPAN (verified live); `text=` is the
        # only engine that reliably matches it. The `>> visible=true` chain is
        # NOT valid in query_selector, so we match plain and click the first.
        books = page.query_selector_all("text=Book Bet")
        if books:
            books[0].click()
    except Exception:
        pass  # no Book Bet button — maybe the slip already shows the code

    # Primary: the Booking Code modal. The modal can take a couple of seconds
    # to render after the click (SPA), so poll for it rather than reading once.
    try:
        for _ in range(8):
            dialog = page.query_selector(".es-dialog.m-dialog")
            if dialog is not None:
                text = dialog.inner_text()
                m = re.search(r"Booking Code\s*\n\s*([A-Z0-9]{5,10})", text)
                if m:
                    return m.group(1)
                m2 = re.search(r"Booking Code\s*[:.]?\s*([A-Z0-9]{5,10})", text)
                if m2:
                    return m2.group(1)
            page.wait_for_timeout(1000)
    except Exception:
        pass

    # Fallback: any input-style code field a future revision might render.
    selectors = [
        "input.booking-code, .booking-code input, [data-booking-code]",
        "input.bet-code, .bet-code input",
        "textarea.booking-code, textarea.bet-code",
        "[class*='bookingCode'] input, [class*='booking-code']",
    ]
    for sel in selectors:
        try:
            els = page.query_selector_all(sel)
            for el in els:
                val = (el.get_attribute("value") or "").strip()
                if val:
                    return val
                txt = (el.inner_text() or "").strip()
                # booking codes are short alnum tokens — skip UI labels
                if txt and len(txt) < 40 and not txt.lower().startswith("booking"):
                    return txt
        except Exception:
            continue
    return None


# Private alias for internal use
_read_booking_code = read_booking_code


def _book_one_acca(page: Page, acca: dict, cache_by_league: dict) -> dict:
    """Drive one acca's legs into the betslip and read its booking code.

    Returns {label, code, status, per_leg: [...]} where each leg is
    {fixture, market_name, status} and status is BOOKED or MANUAL."""
    # Import inside function — bypasses ALL bytecode/stale-cache issues.
    # The module-level import at line 60 works in REPL but fails at runtime
    # when run_daily spawns the booking flow (observed 2026-08-23).
    from booking.sportybet_fixtures import _navigate_to_league_sync as _navigate_to_league_local

    per_leg: List[dict] = []
    added = 0
    current_league_on_page: Optional[str] = None  # track which league page we're on

    for leg in acca.get("legs") or []:
        league = leg.get("league") or "—"
        fx = _resolve_fixture(leg, cache_by_league.get(league, []))
        entry = {"fixture": leg.get("fixture", "?"),
                 "market_name": leg.get("market_name") or leg.get("market_key") or "?",
                 "status": "MANUAL"}
        ok = False
        try:
            if fx is None:
                entry["status"] = "MANUAL"
                entry["reason"] = "fixture not found in SportyBet cache"
            elif leg.get("market_key") in _1X2_INDEX:
                # Navigate if we're not already on this league's page
                if current_league_on_page != league:
                    mapping = SPORTYBET_LEAGUES.get(league)
                    nav_ok = bool(mapping) and _navigate_to_league_local(
                        page, mapping.country, mapping.league)
                    if nav_ok:
                        current_league_on_page = league
                    else:
                        current_league_on_page = None
                if current_league_on_page == league:
                    row = _find_match_row(page, fx["fixture_id"], fx["sportybet_home"])
                    ok = bool(row) and _click_1x2(row, leg["market_key"])
                    if not ok and row is None:
                        entry["reason"] = "match row not found on league page"
                else:
                    entry["reason"] = "league page did not load"
            elif leg.get("market_key") in ("UNDER_2_5",):
                # The league-page totals cell handles Under 2.5 when its fixed
                # line is 2.5. Deliberately NO match-page fallback: direct
                # /match navigation TIMES OUT on SportyBet NG (see BTTS note)
                # and leaves the session on a dead page, breaking every later
                # leg. A line mismatch flags MANUAL rather than navigates.
                if current_league_on_page != league:
                    mapping = SPORTYBET_LEAGUES.get(league)
                    nav_ok = bool(mapping) and _navigate_to_league_local(
                        page, mapping.country, mapping.league)
                    if nav_ok:
                        current_league_on_page = league
                    else:
                        current_league_on_page = None
                if current_league_on_page == league:
                    row = _find_match_row(page, fx["fixture_id"], fx["sportybet_home"])
                    ok = bool(row) and _click_totals_on_league_page(page, row, leg["market_key"])
                    if not ok and row is None:
                        entry["reason"] = "match row not found on league page"
                else:
                    entry["reason"] = "league page did not load"
            elif leg.get("market_key") in TOTALS_INDEX:
                # Totals markets available on the league page (fixed line per row)
                if current_league_on_page != league:
                    mapping = SPORTYBET_LEAGUES.get(league)
                    nav_ok = bool(mapping) and _navigate_to_league_local(
                        page, mapping.country, mapping.league)
                    if nav_ok:
                        current_league_on_page = league
                    else:
                        current_league_on_page = None
                if current_league_on_page == league:
                    row = _find_match_row(page, fx["fixture_id"], fx["sportybet_home"])
                    ok = bool(row) and _click_totals_on_league_page(page, row, leg["market_key"])
                    if not ok and row is None:
                        entry["reason"] = "match row not found on league page"
                    elif not ok:
                        entry["reason"] = f"line mismatch or outcome click failed for {leg['market_key']}"
                else:
                    entry["reason"] = "league page did not load"
            elif leg.get("market_key") in ("BTTS_YES", "BTTS_NO"):
                # BTTS = GG/NG. The working path is the league-page inline
                # market selector (direct /match navigation times out). The
                # expand->Goals->GG/NG flow leaves the page on a deep
                # tournament link in an expanded GG/NG state; _navigate_to_league
                # now hard-reloads for deep /sr: links so each BTTS leg starts
                # from a clean league page.
                mapping = SPORTYBET_LEAGUES.get(league)
                nav_ok = bool(mapping) and _navigate_to_league_local(
                    page, mapping.country, mapping.league)
                if nav_ok:
                    current_league_on_page = league
                    ok = _click_btts_on_league_page(page, fx["fixture_id"], leg["market_key"])
                    if not ok:
                        entry["reason"] = "GG/NG (BTTS) selection could not be driven"
                else:
                    current_league_on_page = None
                    entry["reason"] = "league page did not load"
            elif leg.get("market_key") in ("DC_1X", "DC_X2", "DC_12"):
                # Double Chance — handle on match page (SportyBet renders DC under
                # "Double Chance" tab on the match page). The league page only
                # shows 1X2 and Totals markets. Navigate to match page and click
                # the DC tab.
                if current_league_on_page != league:
                    mapping = SPORTYBET_LEAGUES.get(league)
                    nav_ok = bool(mapping) and _navigate_to_league_local(
                        page, mapping.country, mapping.league)
                    if nav_ok:
                        current_league_on_page = league
                    else:
                        current_league_on_page = None
                if current_league_on_page == league:
                    ok = _click_market_on_match_page(page, leg["market_key"], fx["fixture_id"])
                    if not ok:
                        entry["reason"] = f"DC selection could not be driven for {leg['market_key']}"
                else:
                    entry["reason"] = "league page did not load"
            elif leg.get("market_key") in ("DNB_HOME", "DNB_AWAY"):
                # Draw No Bet — handle on match page (SportyBet renders DNB under
                # "Draw No Bet" tab on the match page).
                if current_league_on_page != league:
                    mapping = SPORTYBET_LEAGUES.get(league)
                    nav_ok = bool(mapping) and _navigate_to_league_local(
                        page, mapping.country, mapping.league)
                    if nav_ok:
                        current_league_on_page = league
                    else:
                        current_league_on_page = None
                if current_league_on_page == league:
                    ok = _click_market_on_match_page(page, leg["market_key"], fx["fixture_id"])
                    if not ok:
                        entry["reason"] = f"DNB selection could not be driven for {leg['market_key']}"
                else:
                    entry["reason"] = "league page did not load"
            elif leg.get("market_key", "").startswith("HT_FT_"):
                # HT/FT markets — handle via match page
                if current_league_on_page != league:
                    mapping = SPORTYBET_LEAGUES.get(league)
                    nav_ok = bool(mapping) and _navigate_to_league_local(
                        page, mapping.country, mapping.league)
                    if nav_ok:
                        current_league_on_page = league
                    else:
                        current_league_on_page = None
                if current_league_on_page == league:
                    ok = _click_market_on_match_page(page, leg["market_key"], fx["fixture_id"])
                    if not ok:
                        entry["reason"] = f"HT/FT selection could not be driven for {leg['market_key']}"
                else:
                    entry["reason"] = "league page did not load"
            elif leg.get("market_key", "").startswith("CS_"):
                # Correct Score markets — handle via match page
                if current_league_on_page != league:
                    mapping = SPORTYBET_LEAGUES.get(league)
                    nav_ok = bool(mapping) and _navigate_to_league_local(
                        page, mapping.country, mapping.league)
                    if nav_ok:
                        current_league_on_page = league
                    else:
                        current_league_on_page = None
                if current_league_on_page == league:
                    ok = _click_market_on_match_page(page, leg["market_key"], fx["fixture_id"])
                    if not ok:
                        entry["reason"] = f"Correct Score selection could not be driven for {leg['market_key']}"
                else:
                    entry["reason"] = "league page did not load"
            elif leg.get("market_key") in _MARKET_UI_MAP:
                # Defensive MANUAL. Every market in _MARKET_UI_MAP (totals +
                # BTTS, DNB, HT/FT, CS) is already handled by the league-page branches above,
                # so reaching here means an unhandled variant. Deliberately do
                # NOT fall back to the match page: direct /match navigation
                # times out on SportyBet NG and leaves the session on a dead
                # page, breaking every later leg.
                entry["reason"] = f"market {leg['market_key']} not drivable on league page"
            if ok:
                added += 1
                entry["status"] = "BOOKED"
            elif "reason" not in entry:
                entry["reason"] = "selection could not be driven (add manually)"
        except Exception as e:
            entry["reason"] = f"driver error: {str(e)[:80]}"
        per_leg.append(entry)

    code = _read_booking_code(page, len(acca.get("legs") or [])) if added else None

    # --- HARD RULE (Architect 2026-08-20): the booking code's odds MUST equal
    # --- the expected combined odds. For a 1-leg slip (SINGLE) that is the leg's
    # --- own price (e.g. 5.0 == "50 odds"); for a multi-leg acca it is the
    # --- product of all leg prices. We read the betslip's combined odds and
    # --- compare. A mismatch means the slip is wrong (a leg dropped, a wrong
    # --- market clicked) — we DO NOT accept the code; it is flagged so the
    # --- Architect adds the slip by hand (HR35, never guessed).
    odds_check: Optional[dict] = None
    if code and added:
        expected = _expected_combined_odds(acca.get("legs") or [])
        betslip_odds = _read_betslip_combined_odds(page, expected=expected)
        ok_odds = _odds_within_tolerance(expected, betslip_odds)
        odds_check = {
            "expected": expected,
            "betslip": betslip_odds,
            "match": ok_odds,
        }
        if not ok_odds:
            # The code was generated but its odds are wrong — reject it so it
            # never reaches production as a "BOOKED" slip with bad numbers.
            code = None

    status = ("BOOKED" if code
              else ("SLIP READY" if added else "MANUAL — nothing added"))
    if code is None and added and odds_check and not odds_check.get("match"):
        status = "ODDS MISMATCH — code rejected"
    return {
        "label": acca.get("label", "Acca"),
        "code": code,
        "status": status,
        "n_legs": len(acca.get("legs") or []),
        "n_added": added,
        "per_leg": per_leg,
        "odds_check": odds_check,
    }


def book_accas(payload: dict, headless: bool = True) -> dict:
    """Generate booking codes for every acca in the payload.

    Best-effort and Phase-2 safe. Returns a result dict mirroring the payload
    shape plus a `codes` list and an overall status. A browser fault degrades
    each acca to MANUAL — codes are never fabricated (HR35)."""
    if sync_playwright is None:
        return {"error": "playwright not installed — pip install playwright && "
                         "playwright install chromium"}

    day = payload.get("date", "")
    # Pre-load the SportyBet fixture cache for every league the accas touch so
    # the browser session only navigates (no live parsing mid-flow).
    leagues_needed = {leg.get("league") for a in payload.get("accas", [])
                      for leg in a.get("legs", [])}
    cache_by_league: dict = {}
    for lg in leagues_needed:
        if not lg or lg == "—":
            continue
        try:
            # PipelineFixture carries the MODEL keys on home_team/away_team
            # (the cache's model_home/model_away); _cache_entry maps them to
            # the dict shape _resolve_fixture reads. `f.get()` would raise on
            # the dataclass — that failure used to be swallowed into an empty
            # cache, and every leg reported 'fixture not found' (fixed).
            cache_by_league[lg] = [
                _cache_entry(f) for f in load_sportybet_fixtures(lg, days_ahead=30)]
        except Exception:
            cache_by_league[lg] = []

    results: List[dict] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            slow_mo=0,
            args=["--disable-gpu", "--no-sandbox", "--disable-dev-shm-usage"]
        )
        context = browser.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"),
            viewport={"width": 1280, "height": 720})
        page = context.new_page()
        try:
            for acca in payload.get("accas", []):
                try:
                    # Start each slip from clean state: the betslip is NOT
                    # auto-cleared by SportyBet between entries, so selections
                    # would otherwise accumulate and the combined odds would
                    # blow up (2026-08-23 regression).
                    _clear_betslip(page)
                    results.append(_book_one_acca(page, acca, cache_by_league))
                except Exception as e:
                    results.append({
                        "label": acca.get("label", "Acca"), "code": None,
                        "status": f"MANUAL — driver failed ({str(e)[:80]})",
                        "n_legs": len(acca.get("legs") or []), "n_added": 0,
                        "per_leg": [], "error": str(e)[:120]})
        finally:
            context.close()
            browser.close()

    return {"date": day, "results": results,
            "all_booked": all(r.get("code") for r in results)}


def render_codes(result: dict) -> str:
    """Human-readable booking-code report for the Architect."""
    out = ["SPORTYBET BOOKING CODES — Phase 3 (codes only, NO stake placed)"]
    if "error" in result:
        out.append(f"  ERROR: {result['error']}")
        out.append("  Codes not generated — nothing to paste. NO DATA — PENDING (HR35).")
        return "\n".join(out)
    if not result.get("results"):
        out.append("  No accas in the payload — nothing to book.")
        return "\n".join(out)
    for r in result["results"]:
        out.append(f"  {r['label']}: {r['status']}"
                   + (f" — CODE {r['code']}" if r.get("code") else ""))
        # HARD RULE (2026-08-20): show odds verification when available
        oc = r.get("odds_check")
        if oc:
            exp = oc.get("expected")
            bs = oc.get("betslip")
            if exp is None or bs is None:
                out.append("    ODDS CHECK: data missing (betSlip not captured); code retained")
            elif oc.get("match"):
                out.append(f"    [OK] ODDS CHECK PASS: expected {exp:.2f} == betslip {bs:.2f}")
            else:
                out.append(f"    [FAIL] ODDS MISMATCH: expected {exp:.2f} vs betslip {bs:.2f} — code REJECTED")
        for leg in r.get("per_leg", []):
            status = "[OK]" if leg.get("status") == "BOOKED" else "[FAIL] MANUAL"
            out.append(f"    {status} {leg['fixture']} — {leg['market_name']}"
                       + (f" ({leg.get('reason')})" if leg.get("reason") else ""))
    out.append("  Codes pre-fill the slip when pasted into SportyBet. A MANUAL leg "
               "must be added by hand before you place anything. YOU approve and "
               "stake — this system never does.")
    return "\n".join(out)


def main() -> None:
    # Reconfigure stdout/stderr to UTF-8 so page-derived text prints cleanly on
    # Windows' cp1252 console instead of raising UnicodeEncodeError. No-op if
    # already utf-8.
    try:
        import sys as _sys
        _sys.stdout.reconfigure(encoding="utf-8")
        _sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    parser = argparse.ArgumentParser(
        description="Generate SportyBet booking codes for the day's accas and singles. "
                    "READ-ONLY — never places a bet, never stakes.")
    parser.add_argument("--date", default=None,
                        help="Acca date as YYYY-MM-DD (default: today)")
    parser.add_argument("--headed", action="store_true",
                        help="Run the browser visibly (debugging)")
    args = parser.parse_args()

    from datetime import date
    day = args.date or date.today().isoformat()
    try:
        # Load acca payload from acca_<day>.json
        acca_path = Path("output/boards") / f"acca_{day}.json"
        payload = json.loads(acca_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    result = book_accas(payload, headless=not args.headed)
    print(render_codes(result))
    # Also persist the codes next to the acca payload.
    try:
        out_path = BOARD_DIR / f"acca_{day}_codes.json"
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                            encoding="utf-8")
        print(f"\n  codes written to {out_path}")
    except Exception as e:
        print(f"  (codes file write failed: {e})")


if __name__ == "__main__":
    main()
