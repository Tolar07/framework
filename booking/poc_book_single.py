"""Proof-of-concept: book ONE live SportyBet selection and read its booking code.

Proves the browser->betslip->code path works end-to-end. Phase-3 safe: it
adds a single selection to the slip and copies the booking code. It NEVER
clicks Place Bet and NEVER enters a stake. The Architect pastes the code and
approves any real money.

Usage:
  py -3.12 -m booking.poc_book_single --league "Premier League" [--headed]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from playwright.sync_api import sync_playwright, Page
except ImportError:
    sync_playwright = None

from booking.league_map import SPORTYBET_LEAGUES

BASE_URL = "https://sportybet.com.ng"
CLOCK_RE = re.compile(r"^\d{1,2}:\d{2}$")  # pre-match kickoff, not HT/H2/Ended

# Chromium in some sandboxes has a broken internal DNS resolver (curl/python
# resolve fine, but Chromium hits ERR_NAME_NOT_RESOLVED — often the unmapped
# AAAA record). Pin every resolved address family with --host-resolver-rules so
# the browser does not depend on its own resolver.
import socket

# Known Cloudflare IPs for sportybet.com.ng (resolved externally, hardcoded here
# because DNS resolution may fail in this sandbox). sportybet.com.ng resolves
# and serves the Nigeria site; sportybet.com does not resolve in this env.
SPORTYBET_COM_NG_IPS = ["104.21.10.148", "172.67.163.154"]


def _resolver_rule(host: str) -> str:
    if host == "sportybet.com.ng":
        rules = []
        for ip in SPORTYBET_COM_NG_IPS:
            rules.append(f"MAP {host}:443 {ip}")
        return ",".join(rules) if rules else ""
    rules = []
    for fam, _, _, _, sockaddr in socket.getaddrinfo(host, 443):
        ip = sockaddr[0]
        if ":" in ip:  # IPv6 — bracket it for the rule
            rules.append(f"MAP {host}:443 [{ip}]")
        else:
            rules.append(f"MAP {host}:443 {ip}")
    return ",".join(rules) if rules else ""


def _navigate_to_league(page: Page, country: str, league: str,
                        registry_league: str | None = None) -> bool:
    """Navigate to a competition's page. `league` is SportyBet's DISPLAY name.

    registry_league is the OLP registry key ("Russian Premier League") and is
    what SPORTYBET_CATEGORY_TOURNAMENT is keyed on. It matters enormously:

    SPORTYBET_LEAGUES maps our name to SportyBet's display name, and several
    collapse onto generic strings. Looking the id up by the DISPLAY name gave:

        Russian Premier League    -> "Premier League" -> (1, 17)   ENGLAND
        Kazakhstan Premier League -> "Premier League" -> (1, 17)   ENGLAND
        Europa League             -> "UEFA Europa League" -> None
        Serbian Super Liga        -> "Super Liga"    -> None
        Estonian Meistriliiga     -> "Meistriliiga"  -> None

    So booking a Russian or Kazakh leg navigated to the ENGLISH Premier League
    page, searched it for "Gazovik Orenburg", and reported "match row not found
    on league page" — pointing at the row when the page itself was wrong. This
    is the same wrong-competition failure that once filled Premier_League.json
    with "Betis v Getafe".
    """
    """Direct navigation (bypasses sportybet_fixtures helper which ignores DNS pin).
    Uses the direct deep-link pattern from _navigate_to_league_sync."""
    # Use the same direct-URL mapping as the builder, but try with IP if DNS fails
    # Defined in rebuild_cache, not sportybet_fixtures. The old import raised
    # ImportError inside the booking driver, which surfaced per leg as
    # "driver error: cannot import name 'SPORTYBET_CATEGORY_TOURNAMENT'" and
    # left every leg MANUAL with no code. Same wrong-module import as
    # _navigate_to_league had in booking_codes.
    from booking.rebuild_cache import SPORTYBET_CATEGORY_TOURNAMENT
    # host/ip are bound unconditionally: the popular-list fallback further down
    # references both, but they used to be assigned ONLY inside the
    # `if cat_tour...` branch below. Any league without a resolved tournament id
    # therefore raised UnboundLocalError ("cannot access local variable 'host'")
    # from inside the booking driver, which surfaced per leg as
    # "MANUAL - driver error" and produced no code.
    # HOSTS, in order. Both work; www.sportybet.com consistently returns more
    # rows than sportybet.com.ng for the same tournament (22 vs 17 on La Liga,
    # 2026-09-17), so it leads.
    #
    # THE RAW-IP FALLBACKS ARE GONE. They navigated to https://<cloudflare-ip>/
    # which CANNOT work: without SNI matching the certificate, Chromium fails
    # every time with ERR_SSL_VERSION_OR_CIPHER_MISMATCH. Each attempt burned a
    # 45s timeout AND left the tab sitting on chrome-error://chromewebdata,
    # which then broke navigation for every subsequent leg in the run — one
    # unreachable league poisoned the whole slip. Removing them is strictly
    # better: they never once succeeded.
    hosts = ["www.sportybet.com", "sportybet.com.ng"]

    # Registry key first; display name only as a last resort, and never when it
    # would silently resolve to another country's competition.
    cat_tour = None
    for key in (registry_league, league):
        if key:
            cand = SPORTYBET_CATEGORY_TOURNAMENT.get(key)
            if cand and tuple(cand)[:2] != (0, 0):
                cat_tour = cand
                break
    if cat_tour and cat_tour[0] != 0:
        cat_id, tour_id = cat_tour
        for host in hosts:
            direct_url = (f"https://{host}/ng/sport/football/"
                          f"sr:category:{cat_id}/sr:tournament:{tour_id}"
                          f"?source=sport_menu&sort=2")
            try:
                print(f"  -> Direct URL: {direct_url}")
                page.goto(direct_url, wait_until="domcontentloaded", timeout=45000)
                # SportyBet is a client-side SPA: the HTML shell returns 200
                # instantly and the fixture list is rendered by JS afterwards,
                # so a fixed sleep either wastes time or samples too early.
                # Wait for the ROWS themselves.
                try:
                    page.wait_for_selector(".m-table-row.match-row", timeout=20000)
                except Exception:
                    pass
                rows = page.query_selector_all(".m-table-row.match-row")
                if rows:
                    print(f"     rows: {len(rows)}")
                    return True
                print("     no rows rendered")
            except Exception as e:
                print(f"  x direct nav error ({host}): {str(e)[:90]}")

    # Fallback: football homepage, then click the league in the popular list.
    for host in hosts:
        base = f"https://{host}/ng/sport/football"
        try:
            print(f"  -> Fallback to homepage: {base}")
            page.goto(base, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(3000)
            league_link = page.locator(
                f'.popular-list .top-link:has(.top-link-item:has-text("{league}"))'
            ).first
            if league_link.count():
                league_link.click()
                try:
                    page.wait_for_selector(".m-table-row.match-row", timeout=20000)
                except Exception:
                    pass
                rows = page.query_selector_all(".m-table-row.match-row")
                if rows:
                    return True
        except Exception as e:
            print(f"  x click nav error ({host}): {str(e)[:90]}")
    return False


def _find_upcoming_row(page: Page):
    """Return the first league-page match row that is pre-match (has a clean
    HH:MM clock, no in-play status). Drives the LIVE page, not the cache."""
    rows = page.query_selector_all(".m-table-row.match-row")
    for r in rows:
        clock = r.query_selector(".clock-time")
        status = r.query_selector(".match-status, .status, .live-tag")
        st_txt = (status.inner_text() or "").strip() if status else ""
        if st_txt and st_txt.upper() not in ("",):
            # In-play markers like HT / 45:00 / LIVE -> skip
            if not CLOCK_RE.match(st_txt):
                continue
        if clock:
            ct = (clock.inner_text() or "").strip()
            # A pre-match row shows a future kickoff clock; in-play rows show
            # elapsed time or status text. Accept only a clean HH:MM kickoff.
            if CLOCK_RE.match(ct):
                return r, ct
    return None, None


def _read_code(page: Page) -> str | None:
    page.wait_for_timeout(1500)
    for sel in page.query_selector_all("text=Book Bet"):
        try:
            sel.click()
            break
        except Exception:
            continue
    for _ in range(8):
        dlg = page.query_selector(".es-dialog.m-dialog")
        if dlg:
            txt = dlg.inner_text() or ""
            m = re.search(r"Booking Code\s*\n\s*([A-Z0-9]{5,10})", txt)
            if m:
                return m.group(1)
            m2 = re.search(r"Booking Code\s*[:.]?\s*([A-Z0-9]{5,10})", txt)
            if m2:
                return m2.group(1)
        page.wait_for_timeout(1000)
    # input-field fallback
    for sel in ("input.booking-code", ".booking-code input", "[data-booking-code]"):
        el = page.query_selector(sel)
        if el:
            v = (el.get_attribute("value") or "").strip()
            if v:
                return v
    return None


def main() -> None:
    if sync_playwright is None:
        print("ERROR: playwright not installed")
        sys.exit(1)
    ap = argparse.ArgumentParser()
    ap.add_argument("--league", default="Premier League")
    ap.add_argument("--headed", action="store_true")
    args = ap.parse_args()

    mapping = SPORTYBET_LEAGUES.get(args.league)
    if not mapping:
        print(f"League {args.league!r} not in SPORTYBET_LEAGUES")
        sys.exit(1)

    resolver_rule = _resolver_rule("sportybet.com.ng")
    launch_args = ["--disable-gpu", "--no-sandbox", "--disable-dev-shm-usage"]
    if resolver_rule:
        launch_args.append(f"--host-resolver-rules={resolver_rule}")
    print(f"Launch args: {launch_args}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headed, args=launch_args)
        # Verify the resolver rule is active
        try:
            print(f"Browser process PID: {browser.process.pid if hasattr(browser, 'process') else 'N/A'}")
        except:
            pass
        ctx = browser.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"),
            viewport={"width": 1280, "height": 720})
        page = ctx.new_page()
        try:
            print(f"Navigating to {mapping.country}/{mapping.league} ...")
            ok = _navigate_to_league(page, mapping.country, mapping.league)
            if not ok:
                print("NAV FAILED — could not open league page")
                sys.exit(1)

            row, clock = _find_upcoming_row(page)
            if row is None:
                print("No pre-match (upcoming) match found on this league page right now")
                sys.exit(1)

            home = row.query_selector(".teams .home-team")
            away = row.query_selector(".teams .away-team")
            gid = row.query_selector(".game-id")
            home_t = (home.inner_text() if home else "?").strip()
            away_t = (away.inner_text() if away else "?").strip()
            gid_t = (gid.inner_text() if gid else "").strip()
            print(f"Picked: {home_t} v {away_t}  kickoff {clock}  {gid_t}")

            # Click HOME (1X2 index 0)
            market = row.query_selector(".market-cell .market")
            if market is None:
                print("No 1X2 market cell on row")
                sys.exit(1)
            cells = market.query_selector_all(".m-outcome-odds")
            if len(cells) < 3:
                print("1X2 cell missing outcomes")
                sys.exit(1)
            cells[0].click()
            page.wait_for_timeout(1500)

            # Read combined odds for honesty
            code = _read_code(page)
            if code:
                print(f"RESULT: selection added to slip. BOOKING CODE = {code}")
                print("This code pre-fills the slip on SportyBet. NO stake placed, "
                      "NO Place Bet clicked. Paste + approve + stake yourself.")
            else:
                print("Selection clicked but no booking code modal appeared "
                      "(slip may be in a state needing review) — MANUAL.")
        finally:
            browser.close()


if __name__ == "__main__":
    main()
