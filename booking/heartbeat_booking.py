"""
HEARTBEAT BOOKING CODE — generate SportyBet booking code for the daily heartbeat.

Converts the single HeartbeatFixture into the acca payload format expected by
booking.booking_codes, runs the Playwright driver, and returns the booking code
(or MANUAL flag) for the Architect to paste into SportyBet.

Paper-mode only: NEVER places a bet, NEVER enters a stake.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Optional

from output.heartbeat import HeartbeatFixture


def heartbeat_to_acca_payload(heartbeat: HeartbeatFixture, target_date: str = None) -> dict:
    """
    Convert a HeartbeatFixture to the acca payload format for booking_codes.

    The acca payload format (from engine/acca.py) expects:
    {
        "date": "2026-08-29",
        "accas": [
            {
                "label": "SINGLE — Racing Santander v Elche",
                "legs": [
                    {
                        "fixture": "Racing Santander v Elche",
                        "league": "La Liga",
                        "market_key": "BTTS_YES",
                        "market_name": "Both teams to score — yes",
                        "pick": "BTTS Yes",
                        "price": 1.67,
                        "prob": 0.60,
                        "ev": 0.10,
                        "edge": 0.10,
                        "verification_stamp": "PENDING"
                    }
                ]
            }
        ]
    }
    """
    if target_date is None:
        target_date = date.today().isoformat()

    # Map heartbeat market_type/pick to market_key used by booking_codes
    market_key = _map_pick_to_market_key(heartbeat.pick, heartbeat.market_type)

    # Market name for display (what appears on SportyBet)
    market_name = _format_market_name(heartbeat.pick, heartbeat.market_type)

    leg = {
        "fixture": heartbeat.fixture,
        "league": heartbeat.league,
        "market_key": market_key,
        "market_name": market_name,
        "pick": heartbeat.pick,
        "price": heartbeat.price,
        "prob": heartbeat.probability,
        "ev": heartbeat.edge,
        "edge": heartbeat.edge,
        "verification_stamp": "BOOKED" if heartbeat.verification_passed else "PENDING",
    }

    # Label follows production intent: "SINGLE — <fixture>"
    label = f"SINGLE — {heartbeat.fixture}"

    return {
        "date": target_date,
        "accas": [{
            "label": label,
            "legs": [leg],
        }]
    }


def _map_pick_to_market_key(pick: str, market_type: str) -> str:
    """Map human-readable pick to SportyBet market_key."""
    pick_lower = pick.lower()

    if market_type == "1X2":
        if "home" in pick_lower:
            return "1X2_HOME"
        elif "draw" in pick_lower:
            return "1X2_DRAW"
        elif "away" in pick_lower:
            return "1X2_AWAY"
    elif market_type == "O/U":
        if "over" in pick_lower:
            if "1.5" in pick or "1 5" in pick:
                return "OVER_1_5"
            elif "2.5" in pick or "2 5" in pick:
                return "OVER_2_5"
            elif "3.5" in pick or "3 5" in pick:
                return "OVER_3_5"
        elif "under" in pick_lower:
            if "1.5" in pick or "1 5" in pick:
                return "UNDER_1_5"
            elif "2.5" in pick or "2 5" in pick:
                return "UNDER_2_5"
            elif "3.5" in pick or "3 5" in pick:
                return "UNDER_3_5"
    elif market_type == "BTTS":
        if "yes" in pick_lower or "btts" in pick_lower:
            return "BTTS_YES"
        elif "no" in pick_lower:
            return "BTTS_NO"
    elif market_type == "DC":
        if "1x" in pick_lower:
            return "DC_1X"
        elif "x2" in pick_lower:
            return "DC_X2"
        elif "12" in pick_lower:
            return "DC_12"
    elif market_type == "DNB":
        if "home" in pick_lower:
            return "DNB_HOME"
        elif "away" in pick_lower:
            return "DNB_AWAY"
    elif market_type == "HT/FT":
        # Format like "1/1", "X/2", etc.
        return pick.replace("/", "_").replace("-", "_").upper()
    elif market_type == "CS":
        # Correct score like "1:0", "2:1"
        return f"CS_{pick.replace(':', '')}"

    # Fallback: return as-is, booking_codes will flag MANUAL
    return pick.upper().replace(" ", "_")


def _format_market_name(pick: str, market_type: str) -> str:
    """Format market name for display on SportyBet."""
    if market_type == "BTTS":
        return "Both Teams to Score — Yes" if "yes" in pick.lower() else "Both Teams to Score — No"
    elif market_type == "O/U":
        if "over" in pick.lower():
            return pick.replace("Over", "Over").replace("goals", "goals")
        else:
            return pick.replace("Under", "Under").replace("goals", "goals")
    elif market_type == "DC":
        return f"Double Chance — {pick.upper()}"
    elif market_type == "DNB":
        return f"Draw No Bet — {pick}"
    elif market_type == "HT/FT":
        return f"Half Time / Full Time — {pick}"
    elif market_type == "CS":
        return f"Correct Score — {pick}"
    else:
        return pick


def generate_heartbeat_booking_code(
    heartbeat: HeartbeatFixture,
    target_date: str = None,
    headless: bool = True
) -> dict:
    """
    Generate a SportyBet booking code for the heartbeat.

    Args:
        heartbeat: HeartbeatFixture with the day's pick
        target_date: Date string (YYYY-MM-DD), defaults to today
        headless: Run browser headless (True for production, False for debug)

    Returns:
        {
            "code": "ABC123" or None,
            "status": "BOOKED" | "MANUAL" | "ERROR",
            "payload": <the acca payload sent>,
            "result": <full booking_codes result>,
            "error": <error message if any>
        }
    """
    try:
        from booking.booking_codes import book_accas
    except ImportError as e:
        return {
            "code": None,
            "status": "ERROR",
            "payload": None,
            "result": None,
            "error": f"booking_codes import failed: {e}"
        }

    payload = heartbeat_to_acca_payload(heartbeat, target_date)

    try:
        result = book_accas(payload, headless=headless)
    except Exception as e:
        return {
            "code": None,
            "status": "ERROR",
            "payload": payload,
            "result": None,
            "error": f"book_accas failed: {str(e)[:200]}"
        }

    # Extract code from the first (and only) acca result
    if result.get("results"):
        acca_result = result["results"][0]
        code = acca_result.get("code")
        status = acca_result.get("status", "MANUAL")
        return {
            "code": code,
            "status": status,
            "payload": payload,
            "result": result,
            "error": None,
        }

    return {
        "code": None,
        "status": "MANUAL — no result returned",
        "payload": payload,
        "result": result,
        "error": "No acca result in booking response",
    }


def render_heartbeat_booking_report(booking_result: dict) -> str:
    """Render a human-readable report for the heartbeat booking code."""
    out = ["SPORTYBET HEARTBEAT BOOKING CODE — Phase 3 (code only, NO stake placed)"]

    if booking_result.get("error"):
        out.append(f"  ERROR: {booking_result['error']}")
        out.append("  No code generated — add manually on SportyBet.")
        return "\n".join(out)

    code = booking_result.get("code")
    status = booking_result.get("status", "MANUAL")

    out.append(f"  Status: {status}")
    if code:
        out.append(f"  CODE: {code}")
        out.append("  Paste this code into SportyBet to pre-fill the slip.")
    else:
        out.append("  No code captured — slip must be built manually.")

    # Show the leg details
    payload = booking_result.get("payload", {})
    for acca in payload.get("accas", []):
        for leg in acca.get("legs", []):
            out.append(f"    {leg['fixture']} ({leg['league']})")
            out.append(f"      {leg['market_name']} @ {leg['price']}")

    out.append("\n  YOU approve and stake — this system never does.")
    return "\n".join(out)


def main():
    """CLI: generate heartbeat booking code for today."""
    import argparse
    import json
    from output.heartbeat import get_heartbeat_stats

    parser = argparse.ArgumentParser(
        description="Generate SportyBet booking code for today's heartbeat."
    )
    parser.add_argument("--date", default=None, help="Date YYYY-MM-DD (default: today)")
    parser.add_argument("--headed", action="store_true", help="Run browser visibly")
    args = parser.parse_args()

    # Load today's heartbeat from the generated file
    target_date = args.date or date.today().isoformat()
    heartbeat_file = Path("output/boards") / f"heartbeat_{target_date}.txt"

    if not heartbeat_file.exists():
        # Fallback: check repo root
        heartbeat_file = Path(f"heartbeat_{target_date}.txt")
        if not heartbeat_file.exists():
            print(f"ERROR: No heartbeat file found for {target_date}")
            return 1

    # Parse the heartbeat file to reconstruct HeartbeatFixture
    # The file format is the rendered Telegram output
    import re
    content = heartbeat_file.read_text(encoding="utf-8")

    # Simple parser for the rendered heartbeat format
    lines = content.split("\n")
    fixture = ""
    league = ""
    pick = ""
    prob = 0.0
    edge = 0.0
    price = 0.0
    bookmaker = "Bet365"

    for line in lines:
        if "⚽" in line and "League" in line:
            league = line.replace("⚽", "").strip()
        elif "🕐" in line and "v" in line:
            fixture = line.replace("🕐", "").strip().split("   ")[-1]
        elif "💡" in line and "Pick:" in line:
            # Pick: 🤝 Both teams to score -- yes (60%)
            pick_match = re.search(r"Pick:\s*[\w\s]+\s*([^(]+)\s*\((\d+)%\)", line)
            if pick_match:
                pick = pick_match.group(1).strip()
                prob = int(pick_match.group(2)) / 100.0
        elif "📈" in line and "Edge:" in line:
            edge_match = re.search(r"Edge:\s*([+-]?[\d.]+)%", line)
            if edge_match:
                edge = float(edge_match.group(1)) / 100.0
        elif "💷" in line:
            price_match = re.search(r"[\d.]+$", line.strip())
            if price_match:
                price = float(price_match.group(0))

    if not fixture:
        print("ERROR: Could not parse heartbeat file")
        return 1

    heartbeat = HeartbeatFixture(
        fixture=fixture,
        kickoff_time="??:??",
        league=league,
        pick=pick,
        probability=prob,
        edge=edge,
        market_type=_infer_market_type(pick),
        bookmaker=bookmaker,
        price=price,
        verification_passed=False,
    )

    print(f"Generating booking code for: {heartbeat.fixture} — {heartbeat.pick} @ {heartbeat.price}")
    result = generate_heartbeat_booking_code(heartbeat, target_date, headless=not args.headed)
    print(render_heartbeat_booking_report(result))

    # Save result next to heartbeat file
    try:
        out_path = Path("output/boards") / f"heartbeat_{target_date}_code.json"
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n  Code result written to {out_path}")
    except Exception as e:
        print(f"  (result file write failed: {e})")

    return 0


def _infer_market_type(pick: str) -> str:
    """Infer market type from pick string."""
    pick_lower = pick.lower()
    if "btts" in pick_lower or "both teams" in pick_lower:
        return "BTTS"
    elif "over" in pick_lower or "under" in pick_lower:
        return "O/U"
    elif "double chance" in pick_lower or "dc" in pick_lower:
        return "DC"
    elif "draw no bet" in pick_lower or "dnb" in pick_lower:
        return "DNB"
    elif "half time" in pick_lower or "ht/ft" in pick_lower or "/" in pick:
        return "HT/FT"
    elif ":" in pick and pick.replace(":", "").isdigit():
        return "CS"
    else:
        return "1X2"


if __name__ == "__main__":
    main()