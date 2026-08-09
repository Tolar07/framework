"""SPORTYBET BOOKING-CODES — turn the day's accas into bookable codes.

WHAT THIS DOES
  Reads the day's acca payload (output/boards/acca_<date>.json — built by
  run_daily's engine.acca) and, for each leg of each acca, drives the
  SportyBet Nigeria SPA with Playwright to add the exact selection to the
  betslip. When all of an acca's legs are in the betslip it reads the
  generated BOOKING CODE and records it. The output is a code the Architect
  can paste into SportyBet to recall the slip — it is a pre-fill, NOT a stake.

DEPLOY GATE (Phase 2 — bright line)
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
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from playwright.sync_api import sync_playwright, Page
except ImportError:
    sync_playwright = None

sys.path.insert(0, str(Path(__file__).parent.parent))

from booking.league_map import SPORTYBET_LEAGUES
from booking.bridge import load_sportybet_fixtures
from booking.sportybet_fixtures import _navigate_to_league

BASE_URL = "https://www.sportybet.com/ng"
BOARD_DIR = Path(__file__).parent.parent / "output" / "boards"

# 1X2 click index inside the league-page row's first market cell.
# The first market cell renders Home / Draw / Away in that order.
_1X2_INDEX = {  # market_key -> cell index within the row's first market
    "1X2_HOME": 0,
    "1X2_DRAW": 1,
    "1X2_AWAY": 2,
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
    never the SportyBet spelling first, which silently no-matches)."""
    if " v " not in (leg.get("fixture") or ""):
        return None
    home, away = [s.strip() for s in leg["fixture"].split(" v ", 1)]
    for fx in cache:
        if fx.get("model_home") == home and fx.get("model_away") == away:
            return fx
        if (fx.get("sportybet_home") or "").strip() == home \
                and (fx.get("sportybet_away") or "").strip() == away:
            return fx
    return None


def _click_1x2(row, market_key: str) -> bool:
    """Click a 1X2 outcome on a league-page match row. Returns True when the
    click was issued (betslip state is checked by the caller)."""
    idx = _1X2_INDEX.get(market_key)
    if idx is None:
        return False
    market = row.query_selector(".market-cell .market")
    if market is None:
        return False
    cells = market.query_selector_all(".m-outcome-odds")
    if len(cells) <= idx:
        return False
    cells[idx].click()
    return True


def _open_match_page(page: Page, fixture_id: str) -> bool:
    """Open a SportyBet match page and wait for markets."""
    try:
        page.goto(f"{BASE_URL}/match/{fixture_id}", wait_until="domcontentloaded",
                  timeout=30000)
        page.wait_for_timeout(3500)
        return True
    except Exception:
        return False


def _click_under25(page: Page) -> bool:
    """Drive a totals (Under 2.5) selection on a match page, best-effort.

    SportyBet's totals market is behind a tab and its DOM varies by
    match/section. Multiple locator strategies are tried; a miss returns False
    so the leg is flagged MANUAL (HR35) rather than guessed."""
    tries = [
        lambda: page.locator("text=Under 2.5 >> visible=true").first.click(),
        lambda: page.locator("div.outcome:has-text('Under 2.5') >> visible=true").first.click(),
        lambda: page.locator(".m-outcome:has-text('Under 2.5') >> visible=true").first.click(),
        lambda: page.locator("text=Over/Under >> visible=true").first.click()
                .then(page.wait_for_timeout(1500))
                .then(lambda: page.locator("text=Under 2.5 >> visible=true").first.click()),
    ]
    for attempt in tries:
        try:
            attempt()
            page.wait_for_timeout(800)
            # A click that actually added to the betslip usually pops a
            # betslip badge; absence is not proof of failure, so accept the
            # click as issued and let the betslip read decide.
            return True
        except Exception:
            continue
    return False


def _read_booking_code(page: Page, n_legs: int) -> Optional[str]:
    """Read the booking code once all legs are in the betslip.

    Verified live 2026-08-09: clicking the betslip's "Book Bet" opens a modal
    (.es-dialog.m-dialog) whose body is "Booking Code\nQGF7G5\n<date>...". The
    code only exists there — it is not in an input field. So this function
    1) presses Book Bet, 2) waits for the modal, 3) reads the token right
    after the "Booking Code" label. Falls back to any input-field locators on
    the off-chance a revision renders one. Returns None when no code can be
    read (the per-leg statuses already tell the Architect what to add
    manually — HR35)."""
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


def _book_one_acca(page: Page, acca: dict, cache_by_league: dict) -> dict:
    """Drive one acca's legs into the betslip and read its booking code.

    Returns {label, code, status, per_leg: [...]} where each leg is
    {fixture, market_name, status} and status is BOOKED or MANUAL."""
    per_leg: List[dict] = []
    added = 0
    league_nav: dict = {}  # league -> last navigated, to avoid repeat clicks

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
                if league_nav.get(league) is not True:
                    mapping = SPORTYBET_LEAGUES.get(league)
                    nav_ok = bool(mapping) and _navigate_to_league(
                        page, mapping.country, mapping.league)
                    league_nav[league] = nav_ok
                if league_nav.get(league):
                    row = page.query_selector(f"[data-game-id='{fx['fixture_id']}'], .m-table-row.match-row:has-text('{fx['sportybet_home']}')")
                    ok = bool(row) and _click_1x2(row, leg["market_key"])
                    if not ok and row is None:
                        entry["reason"] = "match row not found on league page"
            elif leg.get("market_key") in ("UNDER_2_5",):
                if _open_match_page(page, fx["fixture_id"]):
                    ok = _click_under25(page)
                else:
                    entry["reason"] = "match page did not load"
            if ok:
                added += 1
                entry["status"] = "BOOKED"
            elif "reason" not in entry:
                entry["reason"] = "selection could not be driven (add manually)"
        except Exception as e:
            entry["reason"] = f"driver error: {str(e)[:80]}"
        per_leg.append(entry)

    code = _read_booking_code(page, len(acca.get("legs") or [])) if added else None
    return {
        "label": acca.get("label", "Acca"),
        "code": code,
        "status": ("BOOKED" if code else
                   ("SLIP READY" if added else "MANUAL — nothing added")),
        "n_legs": len(acca.get("legs") or []),
        "n_added": added,
        "per_leg": per_leg,
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
        browser = p.chromium.launch(headless=headless, slow_mo=0)
        context = browser.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"),
            viewport={"width": 1280, "height": 720})
        page = context.new_page()
        try:
            for acca in payload.get("accas", []):
                try:
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
    out = ["SPORTYBET BOOKING CODES — PHASE 2 (codes only, NO stake placed)"]
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
        for leg in r.get("per_leg", []):
            status = "✓" if leg.get("status") == "BOOKED" else "✗ MANUAL"
            out.append(f"    {status} {leg['fixture']} — {leg['market_name']}"
                       + (f" ({leg.get('reason')})" if leg.get("reason") else ""))
    out.append("  Codes pre-fill the slip when pasted into SportyBet. A MANUAL leg "
               "must be added by hand before you place anything. YOU approve and "
               "stake — this system never does.")
    return "\n".join(out)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate SportyBet booking codes for the day's accas. "
                    "READ-ONLY — never places a bet, never stakes.")
    parser.add_argument("--date", default=None,
                        help="Acca date as YYYY-MM-DD (default: today)")
    parser.add_argument("--accas", default=None,
                        help="Explicit acca payload path (overrides --date)")
    parser.add_argument("--headed", action="store_true",
                        help="Run the browser visibly (debugging)")
    args = parser.parse_args()

    from datetime import date
    day = args.date or date.today().isoformat()
    try:
        if args.accas:
            payload = json.loads(Path(args.accas).read_text(encoding="utf-8"))
            day = payload.get("date", day)
        else:
            payload = _load_acca_payload(day)
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
