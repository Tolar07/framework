"""Verify External Booking Code — loads a SportyBet code and validates odds.

WHAT THIS DOES
  Takes a SportyBet booking code (from X/Twitter or manual input), loads it into
  SportyBet via Playwright, reads the betslip's combined odds, and compares them
  against the expected combined odds computed from the leg prices.

  This reuses the exact same verification logic as the internal booking module:
  - _expected_combined_odds() — product of leg prices
  - _read_betslip_combined_odds() — read betslip total odds
  - _odds_within_tolerance() — 2% relative tolerance check

ARCHITECTURE
  1. Load booking code into SportyBet (navigate to booking page, enter code)
  2. Wait for betslip to populate with the slip's legs
  3. Read each leg's price from the betslip (to compute expected combined odds)
  4. Read betslip's displayed combined odds
  5. Compare: betslip_combined == expected_combined (within 2% tolerance)
  6. Output PASS/FAIL with details

HARD RULE (Architect 2026-08-20)
  "50 odds must equal 50 odds" — the betslip's combined odds MUST equal the
  product of individual leg odds within 2% tolerance. A mismatch means:
  - A leg was dropped/added incorrectly
  - Wrong market was selected
  - SportyBet display bug (e.g., 6 -> 6,000,000)
  The code is REJECTED and flagged for manual review.

HR35 COMPLIANCE
  - Never guesses — if odds can't be read, reports "NO DATA — PENDING"
  - All gaps surfaced honestly
  - Only PASS codes trigger Telegram notification

USAGE
  python -m booking.verify_external_code <CODE> [--headed] [--json]

  CODE          : SportyBet booking code (6-10 alphanumeric, e.g., TFS8TR)
  --headed      : Run browser visibly (debugging)
  --json        : Output machine-readable JSON result
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Optional

try:
    from playwright.sync_api import sync_playwright, Page
except ImportError:
    sync_playwright = None

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# Import verification helpers from booking_codes
from booking.booking_codes import (
    expected_combined_odds,
    read_betslip_combined_odds,
    odds_within_tolerance,
    read_booking_code,
    BASE_URL,
)

SPORTYBET_BOOKING_URL = f"{BASE_URL}/booking"


@dataclass
class VerificationResult:
    """Result of verifying an external booking code."""
    code: str
    status: str  # PASS | FAIL | ERROR | NO_DATA
    expected_combined_odds: Optional[float]
    betslip_combined_odds: Optional[float]
    tolerance_check: Optional[bool]
    leg_count: int
    leg_prices: list[float]
    error_message: Optional[str]
    timestamp: str

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

    def summary(self) -> str:
        lines = [
            f"EXTERNAL CODE VERIFICATION — {self.code}",
            f"  Status: {self.status}",
        ]
        if self.status == "PASS":
            lines.append(f"  ✓ ODDS CHECK PASS: expected {self.expected_combined_odds:.2f} == betslip {self.betslip_combined_odds:.2f}")
        elif self.status == "FAIL":
            lines.append(f"  ✗ ODDS MISMATCH: expected {self.expected_combined_odds:.2f} vs betslip {self.betslip_combined_odds:.2f} — CODE REJECTED")
        elif self.status == "NO_DATA":
            lines.append(f"  ⚠ NO DATA — PENDING: {self.error_message}")
        else:
            lines.append(f"  ✗ ERROR: {self.error_message}")
        if self.leg_prices:
            lines.append(f"  Leg prices: {', '.join(f'{p:.2f}' for p in self.leg_prices)} ({self.leg_count} legs)")
        return "\n".join(lines)


def load_booking_code(page: Page, code: str) -> bool:
    """Load a booking code into SportyBet.

    Navigates to the booking page, enters the code, and submits.
    Returns True if the betslip populated successfully.
    """
    try:
        page.goto(SPORTYBET_BOOKING_URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2000)

        # Find the booking code input field
        # SportyBet's booking page has an input for the code
        input_selectors = [
            "input[placeholder*='Booking']",
            "input[placeholder*='booking']",
            "input[placeholder*='Code']",
            "input[placeholder*='code']",
            "input.booking-code",
            "input.bet-code",
            "[data-booking-code] input",
            "input[type='text']",  # fallback
        ]

        code_input = None
        for sel in input_selectors:
            try:
                code_input = page.query_selector(sel)
                if code_input:
                    break
            except Exception:
                continue

        if not code_input:
            # Try finding by label text
            try:
                labels = page.query_selector_all("label")
                for label in labels:
                    if "booking" in (label.inner_text() or "").lower():
                        inp = label.query_selector("input")
                        if inp:
                            code_input = inp
                            break
            except Exception:
                pass

        if not code_input:
            return False

        # Enter the code
        code_input.fill("")
        code_input.type(code, delay=50)
        page.wait_for_timeout(500)

        # Submit — look for a "Load" / "Apply" / "Search" button
        submit_selectors = [
            "text=Load",
            "text=Apply",
            "text=Search",
            "text=Load Bet",
            "button:has-text('Load')",
            "button:has-text('Apply')",
            "[type='submit']",
        ]
        submitted = False
        for sel in submit_selectors:
            try:
                btn = page.query_selector(sel)
                if btn:
                    btn.click()
                    submitted = True
                    break
            except Exception:
                continue

        if not submitted:
            # Try pressing Enter
            code_input.press("Enter")

        # Wait for betslip to populate
        page.wait_for_timeout(3000)

        # Check if betslip has content
        betslip_panels = page.query_selector_all(
            ".betslip, .bet-slip, .slip, [class*='betslip'], [class*='slip'], "
            ".es-betslip, .cart, [class*='cart']"
        )
        for panel in betslip_panels:
            try:
                txt = panel.inner_text() or ""
                if txt.strip() and len(txt) > 10:
                    return True
            except Exception:
                continue

        return False

    except Exception as e:
        print(f"Error loading booking code: {e}")
        return False


def read_leg_prices_from_betslip(page: Page) -> list[float]:
    """Read individual leg prices from the betslip.

    SportyBet's betslip shows each leg with its price. We extract all
    decimal odds (numbers > 1.00 with 2 decimals) that appear in the
    betslip panel and are NOT the combined total.

    Returns list of leg prices.
    """
    panels = page.query_selector_all(
        ".betslip, .bet-slip, .slip, [class*='betslip'], [class*='slip'], "
        ".es-betslip, .cart, [class*='cart']"
    )

    import re
    pat_decimal = re.compile(r"(?<!\d)(\d+\.\d{2})(?!\d)")

    leg_prices = []
    for panel in (panels or []):
        try:
            txt = panel.inner_text() or ""
        except Exception:
            continue

        lines = txt.split("\n")
        for line in lines:
            line_lower = line.lower()
            # Skip lines that look like combined/total odds
            if any(kw in line_lower for kw in ("total", "combined", "potential")):
                continue
            for m in pat_decimal.finditer(line):
                raw = m.group(1)
                try:
                    val = float(raw)
                except ValueError:
                    continue
                if 1.01 <= val <= 10.0:  # Leg prices are typically 1.01 - 10.0
                    leg_prices.append(val)

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for p in leg_prices:
        if p not in seen:
            seen.add(p)
            unique.append(p)

    return unique


def verify_code(code: str, headless: bool = True) -> VerificationResult:
    """Verify a SportyBet booking code end-to-end."""
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())

    if sync_playwright is None:
        return VerificationResult(
            code=code,
            status="ERROR",
            expected_combined_odds=None,
            betslip_combined_odds=None,
            tolerance_check=None,
            leg_count=0,
            leg_prices=[],
            error_message="playwright not installed",
            timestamp=timestamp,
        )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, slow_mo=0)
        context = browser.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"),
            viewport={"width": 1280, "height": 720})
        page = context.new_page()

        try:
            # Step 1: Load the booking code
            print(f"Loading booking code: {code}")
            loaded = load_booking_code(page, code)
            if not loaded:
                return VerificationResult(
                    code=code,
                    status="NO_DATA",
                    expected_combined_odds=None,
                    betslip_combined_odds=None,
                    tolerance_check=None,
                    leg_count=0,
                    leg_prices=[],
                    error_message="Failed to load booking code — betslip did not populate",
                    timestamp=timestamp,
                )

            # Step 2: Read leg prices from betslip
            leg_prices = read_leg_prices_from_betslip(page)
            print(f"  Leg prices read: {[f'{p:.2f}' for p in leg_prices]}")

            # Step 3: Compute expected combined odds from leg prices
            # Build leg dicts with price for expected_combined_odds()
            legs = [{"price": p} for p in leg_prices]
            expected = expected_combined_odds(legs)
            print(f"  Expected combined odds: {expected}")

            # Step 4: Read betslip's displayed combined odds
            betslip_odds = read_betslip_combined_odds(page)
            print(f"  Betslip combined odds: {betslip_odds}")

            # Step 5: Compare
            if expected is None or betslip_odds is None:
                return VerificationResult(
                    code=code,
                    status="NO_DATA",
                    expected_combined_odds=expected,
                    betslip_combined_odds=betslip_odds,
                    tolerance_check=None,
                    leg_count=len(leg_prices),
                    leg_prices=leg_prices,
                    error_message="Could not read odds for comparison (expected or betslip)",
                    timestamp=timestamp,
                )

            match = odds_within_tolerance(expected, betslip_odds)

            if match:
                status = "PASS"
                error = None
            else:
                status = "FAIL"
                error = f"Odds mismatch: expected {expected:.2f}, betslip {betslip_odds:.2f}"

            return VerificationResult(
                code=code,
                status=status,
                expected_combined_odds=expected,
                betslip_combined_odds=betslip_odds,
                tolerance_check=match,
                leg_count=len(leg_prices),
                leg_prices=leg_prices,
                error_message=error,
                timestamp=timestamp,
            )

        except Exception as e:
            return VerificationResult(
                code=code,
                status="ERROR",
                expected_combined_odds=None,
                betslip_combined_odds=None,
                tolerance_check=None,
                leg_count=0,
                leg_prices=[],
                error_message=f"Verification error: {str(e)[:200]}",
                timestamp=timestamp,
            )
        finally:
            context.close()
            browser.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify a SportyBet booking code by loading it and checking odds."
    )
    parser.add_argument("code", help="SportyBet booking code (6-10 alphanumeric)")
    parser.add_argument("--headed", action="store_true",
                        help="Run browser visibly (debugging)")
    parser.add_argument("--json", action="store_true",
                        help="Output machine-readable JSON")
    args = parser.parse_args()

    code = args.code.strip().upper()
    if not re.match(r"^[A-Z0-9]{6,10}$", code):
        print(f"ERROR: Invalid code format: {code}. Expected 6-10 alphanumeric.")
        sys.exit(1)

    result = verify_code(code, headless=not args.headed)

    if args.json:
        print(result.to_json())
    else:
        print(result.summary())

    # Exit code: 0 = PASS, 1 = FAIL/NO_DATA, 2 = ERROR
    if result.status == "PASS":
        sys.exit(0)
    elif result.status == "ERROR":
        sys.exit(2)
    else:
        sys.exit(1)


if __name__ == "__main__":
    import re
    main()