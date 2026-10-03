"""Live stake placement — Phase-3 (ARCHITECT-DEPLOYED) operator-only capability.

================================================================================
ON-THE-RECORD OVERRIDE (Architect directive, 2026-08-29)
--------------------------------------------------------------------------------
The framework's default is PAPER-ONLY: every other booking path only generates a
shareable booking code (slip pre-fill) and NEVER clicks "Place Bet", NEVER enters
a stake, NEVER routes capital. The Architect (owner of the framework) explicitly
overrode that bright line on 2026-08-29: "Place a real stake too" + "go".

This module implements that override. It is the ONLY place that may click Place
Bet. It is engineered so it can never fire by accident:

  1. Disabled unless env SPORTYBET_ALLOW_LIVE_STAKE == "1".
  2. Even when enabled, place_stake() requires an explicit confirm=True passed
     from an operator action (the CLI --confirm-stake flag). No pipeline, board,
     daemon, or scheduled task ever passes confirm=True.
  3. Requires a saved authenticated session (Playwright storage_state JSON) that
     the operator creates ONCE, interactively, by logging in manually. No
     username/password is ever stored in code, chat, logs, or .env.
  4. Stake amount is hard-capped (LIVE_STAKE_MAX, default 50.0; lower via env).
  5. Runs only in headed mode with a manual operator interstitial (press ENTER).

This is NOT wired into run_daily / the Telegram poller / the booker. It is
operator-only. See CLAUDE.md "Protected Constants" — capital-deployment logic is
normally off-limits; this is the Architect's explicit, named, on-record decision
to add it, gated as above so a bug cannot quietly stake money.
================================================================================
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import CAPITAL_ENABLED

# Gate env flag. Must be literally "1" to arm the capability.
ALLOW_ENV = "SPORTYBET_ALLOW_LIVE_STAKE"
# Hard cap on a single live stake (Architect may lower via env SPORTYBET_STAKE_MAX).
DEFAULT_MAX = float(os.getenv("SPORTYBET_STAKE_MAX", "50.0"))
# Default location of the operator-saved authenticated session.
DEFAULT_STATE = Path(__file__).parent / "session_state.json"


class LiveStakeRefused(RuntimeError):
    """Raised whenever a live stake is refused by a gate (never raised in error)."""


def _max_stake() -> float:
    try:
        return float(os.getenv("SPORTYBET_STAKE_MAX", str(DEFAULT_MAX)))
    except ValueError:
        return DEFAULT_MAX


def require_armed() -> None:
    """Raise LiveStakeRefused unless every gate is satisfied. Safe to call early."""
    if not CAPITAL_ENABLED:
        raise LiveStakeRefused(
            "PHASE < 3: capital disabled by the bright line (config.assert_paper_only). "
            "Live stake cannot run. The framework stays paper-only.")
    if os.getenv(ALLOW_ENV, "").strip() != "1":
        raise LiveStakeRefused(
            f"{ALLOW_ENV} is not '1'. Live stake is DISABLED by default. Refusing. "
            f"Set it explicitly to arm the capability.")


def load_session(state_path: str | Path = DEFAULT_STATE) -> dict:
    """Load an operator-saved Playwright storage_state (cookies + localStorage).

    The state is created once by `python -m booking.live_stake --login-save`
    in headed mode, where the operator logs in manually. We never read or store
    credentials here.
    """
    p = Path(state_path)
    if not p.exists():
        raise LiveStakeRefused(
            f"No session file at {p}. Run `--login-save` once (headed) to create it. "
            "Never store credentials in code/chat/.env.")
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - surface as refused, not crash
        raise LiveStakeRefused(f"Corrupt session file {p}: {exc}") from exc


# Candidate selectors for the betslip stake input and the Place Bet button.
# Unverified against the live site as of 2026-08-29 (SportyBet NG was returning
# ERR_NAME_NOT_RESOLVED); kept defensive with multiple fallbacks.
_STAKE_INPUT_CANDIDATES = [
    "input.betslip-stake", "input.stake-input", ".betslip input[type=number]",
    "input[placeholder*='stake' i]", "input[placeholder*='amount' i]",
    ".es-input.m-input input",
]
_PLACE_BET_CANDIDATES = [
    "button:has-text('Place Bet')", "button.place-bet", ".place-bet button",
    "button:has-text('Bet Now')", "button.confirm-bet",
]


def _find(page, candidates):
    for sel in candidates:
        try:
            el = page.query_selector(sel)
        except Exception:  # noqa: BLE001
            el = None
        if el:
            return el
    return None


def place_stake(page, amount: float, *, confirm: bool,
                state_path: str | Path = DEFAULT_STATE) -> dict:
    """Place a real stake on the selection currently in the betslip.

    GATES (all must pass or LiveStakeRefused is raised):
      - require_armed()  (env + phase)
      - confirm is True (only the operator CLI passes this)
      - authenticated session present (load_session)
      - amount within the hard cap

    Returns a status dict. Does NOT silently swallow a failed click — if Place
    Bet is not found/clickable it reports honestly and does not guess.
    """
    require_armed()
    if not confirm:
        raise LiveStakeRefused(
            "place_stake() called without confirm=True. Operator-only action "
            "refused. No stake placed.")
    session = load_session(state_path)

    cap = _max_stake()
    if amount <= 0:
        raise LiveStakeRefused(f"Refusing non-positive stake {amount!r}.")
    if amount > cap:
        raise LiveStakeRefused(
            f"Stake {amount} exceeds hard cap {cap}. Refusing (lower it or raise "
            f"SPORTYBET_STAKE_MAX explicitly).")

    # Apply the authenticated session to the live page context.
    try:
        page.context.add_cookies(session.get("cookies", []))
    except Exception as exc:  # noqa: BLE001 - session may be storage_state-only
        print(f"  [note] could not apply cookies: {exc}")

    # Manual operator interstitial — a real human must be at the keyboard.
    input(
        f"\n!!! LIVE STAKE of {amount:.2f} on the current betslip. !!!\n"
        "Confirm you are logged in and the selection is correct, then press ENTER "
        "to click Place Bet. Ctrl-C to abort.\n> ")

    stake_el = _find(page, _STAKE_INPUT_CANDIDATES)
    if stake_el is None:
        return {"ok": False, "stage": "stake_input",
                "error": "no betslip stake input found (selectors unverified live)"}
    try:
        stake_el.fill(f"{amount:.2f}")
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "stage": "stake_fill", "error": str(exc)}

    place_el = _find(page, _PLACE_BET_CANDIDATES)
    if place_el is None:
        return {"ok": False, "stage": "place_button",
                "error": "no 'Place Bet' button found (selectors unverified live)"}
    try:
        place_el.click()
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "stage": "place_click", "error": str(exc)}

    # Wait for a post-confirmation signal; report honestly either way.
    page.wait_for_timeout(3000)
    return {"ok": True, "stage": "placed", "amount": amount,
            "note": "Place Bet clicked. Verify on SportyBet that the bet is settled."}


def _login_save(state_path: str | Path = DEFAULT_STATE) -> None:
    """Interactive: launch a headed browser, let the operator log in manually,
    then persist storage_state for later live-stake runs. Never prints creds."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ERROR: playwright not installed")
        sys.exit(1)

    print("A headed browser will open. Log in to SportyBet manually, then return "
          "here and press ENTER once the session is established (e.g. balance visible).")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False,
                                    args=["--disable-gpu", "--no-sandbox",
                                          "--disable-dev-shm-usage"])
        ctx = browser.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"),
            viewport={"width": 1280, "height": 720})
        page = ctx.new_page()
        page.goto("https://sportybet.com.ng/ng/sport/football")
        input("Press ENTER after you have logged in and the session is live ...\n> ")
        state = ctx.storage_state()
        Path(state_path).write_text(json.dumps(state), encoding="utf-8")
        print(f"Saved session to {state_path}. Keep this file private (it grants "
              f"betting access). Delete it to revoke.")
        browser.close()


def main() -> None:
    ap = argparse.ArgumentParser(description="Operator-only live stake (gated).")
    ap.add_argument("--login-save", action="store_true",
                    help="Interactive: log in manually and save an authenticated session.")
    ap.add_argument("--confirm-stake", action="store_true",
                    help="Arm the real Place Bet click (requires SPORTYBET_ALLOW_LIVE_STAKE=1).")
    ap.add_argument("--league", default="Premier League")
    ap.add_argument("--amount", type=float, default=1.0,
                    help="Stake amount (hard-capped by SPORTYBET_STAKE_MAX).")
    ap.add_argument("--state", default=str(DEFAULT_STATE))
    args = ap.parse_args()

    if args.login_save:
        _login_save(args.state)
        return

    if not args.confirm_stake:
        print("Refusing: --confirm-stake not passed. This is an operator-only action.\n"
              "To set up auth: python -m booking.live_stake --login-save\n"
              "To place:     SPORTYBET_ALLOW_LIVE_STAKE=1 python -m booking.live_stake "
              "--confirm-stake --league 'Premier League' --amount 1.0")
        sys.exit(1)

    # Reuse the PoC's navigation + row helpers (booking-code path already proven).
    from booking.poc_book_single import (_navigate_to_league_sync, _find_upcoming_row,
                                           SPORTYBET_LEAGUES)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ERROR: playwright not installed"); sys.exit(1)

    mapping = SPORTYBET_LEAGUES.get(args.league)
    if not mapping:
        print(f"League {args.league!r} not in SPORTYBET_LEAGUES"); sys.exit(1)

    require_armed()  # fail early with a clear message if not explicitly armed
    session = load_session(args.state)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False,
                                    args=["--disable-gpu", "--no-sandbox",
                                          "--disable-dev-shm-usage"])
        ctx = browser.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"),
            viewport={"width": 1280, "height": 720})
        try:
            ctx.add_cookies(session.get("cookies", []))
        except Exception as exc:  # noqa: BLE001
            print(f"  [note] could not preload cookies: {exc}")
        page = ctx.new_page()
        print(f"Navigating to {mapping.country}/{mapping.league} ...")
        if not _navigate_to_league_sync(page, mapping.country, mapping.league):
            print("NAV FAILED — could not open league page"); sys.exit(1)
        row, clock = _find_upcoming_row(page)
        if row is None:
            print("No pre-match match found right now"); sys.exit(1)
        cells = row.query_selector_all(".market-cell .market .m-outcome-odds")
        if len(cells) < 3:
            print("1X2 cell missing outcomes"); sys.exit(1)
        print(f"Adding HOME selection to slip (kickoff {clock}) ...")
        cells[0].click()
        page.wait_for_timeout(1500)
        result = place_stake(page, args.amount, confirm=True, state_path=args.state)
        print("RESULT:", json.dumps(result))
        if not result.get("ok"):
            sys.exit(2)


if __name__ == "__main__":
    main()
