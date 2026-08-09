"""ACCUMULATOR PREP — turn the day's Tier A/B picks into a ready-to-paste bet slip.

Reads today's board (output/boards/board_<date>.json — the same payload the web
dashboard serves) and formats the Tier A/B deploy-shortlist picks as a bet slip:
selections, per-leg market + odds, combined parlay odds, and a suggested total
stake. The output is a COPY-PASTE artefact — this script NEVER places a bet and
never submits anything anywhere. Capital deployment stays manual, with the
Architect, per the Phase 2 paper-only bright line.

Pick rule (matches the board, so the slip can never drift from what was shown):
  * ONLY fixtures with softness_tier in (A, B) AND on_deploy_shortlist.
  * Market = best_market (the priced headlined market) when one exists.
  * If no live price, the leg is listed with its breakeven trigger price and
    marked "NO PRICE — back at {trigger}+" so the Architect can confirm on
    SportyBet before adding it.
  * Away wins are never recommended (ID405 — proven-negative market); a pick
    whose best_market_key is an away win is flagged and excluded.

Usage:
    python scripts/accumulator_prep.py                  # today's board
    python scripts/accumulator_prep.py 2026-08-08       # a specific board
    python scripts/accumulator_prep.py --stake 1000     # suggested total stake (NGN)
    python scripts/accumulator_prep.py --json           # machine-readable slip

This is a READ-ONLY tool: it imports nothing that writes to the brain, ledger,
or ledger-adjacent stores.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import date
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine import markets as mkt  # noqa: E402 — canonical market keys + display names

BOARD_DIR = Path(__file__).parent.parent / "output" / "boards"

# Suggested stake defaults. This is a formatting default for the slip, NOT a
# capital authority — the Architect remains the only person who can stake.
DEFAULT_STAKE_NGN = 1000.0

# Total parlay stake cap suggestion — an accumulator's combined odds grow fast,
# and each additional leg multiplies the variance, so the suggested stake is
# scaled DOWN as the combined odds rise. Honest guidance, never a mandate.
COMBINED_ODDS_STAKE_FLOOR = 0.15  # never suggest more than 15% of the cap


def load_board(day: str) -> list[dict]:
    """Load today's board_<date>.json from output/boards. Returns [] when the
    board file is missing — an honest empty result (HR35), never a fabricated
    one."""
    path = BOARD_DIR / f"board_{day}.json"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    return payload.get("board", [])


def _pick_market(bf: dict) -> tuple[str, Optional[float], Optional[float]]:
    """(market name, price, model_prob) for one fixture's accumulator leg.

    Prefers the priced headlined market (best_market/best_price) — the actual
    price the board recommended against. Falls back to the strongest approved
    market's breakeven trigger price when no live price was captured (quota /
    no odds source). The breakeven trigger is the price at which the model's
    probability breaks even; back only AT OR LONGER than it (the board's own
    HR30 rule)."""
    name = bf.get("best_market")
    price = bf.get("best_price")
    prob = bf.get("best_model_prob")
    if name and price is not None:
        return name, price, prob

    # No live price: derive the strongest APPROVED market from the model probs.
    # probs here is the JSON dict from board_<date>.json (schema.probs_to_dict),
    # NOT a FixtureProbabilities object — map the dict's market probabilities.
    p = bf.get("probs") or {}
    home = p.get("home_team", "Home")
    away = p.get("away_team", "Away")
    prob_map = {
        mkt.HOME: p.get("p_home"),
        mkt.DRAW: p.get("p_draw"),
        mkt.AWAY: p.get("p_away"),
        mkt.OVER_25: p.get("p_over_25"),
        mkt.UNDER_25: None if p.get("p_over_25") is None else 1.0 - p["p_over_25"],
        mkt.OVER_15: p.get("p_over_15"),
        mkt.UNDER_15: None if p.get("p_over_15") is None else 1.0 - p["p_over_15"],
        mkt.BTTS_YES: p.get("p_btts_yes"),
        mkt.BTTS_NO: None if p.get("p_btts_yes") is None else 1.0 - p["p_btts_yes"],
    }
    candidates = [(mkt.display(k, home, away), pr, k)
                  for k in mkt.APPROVED_MARKETS
                  if (pr := prob_map.get(k)) is not None]
    if not candidates:
        return "NO DATA — PENDING", None, None
    name, prob, key = max(candidates, key=lambda c: c[1])
    trigger = bf.get("mes_trigger_price")
    return name, trigger, prob


def _leg_line(bf: dict, idx: int, stake: float) -> tuple[str, Optional[float], Optional[str]]:
    """One leg of the slip. Returns (line, price, warning) where warning flags
    legs that need Architect attention (no price / away pick)."""
    fixture = bf.get("fixture", "?")
    name, price, prob = _pick_market(bf)

    # ID405: away wins are proven-negative — never in the slip.
    best_key = bf.get("best_market_key") or ""
    if best_key == mkt.AWAY:
        return (f"{idx}. {fixture} — {name} "
                f"(away win, ID405 blocked — EXCLUDED from slip)", None,
                "away pick excluded")
    if best_key == mkt.OVER_25:
        # Over 2.5 has a proven-negative price line too (ID405).
        return (f"{idx}. {fixture} — {name} "
                f"(Over 2.5 blocked by ID405 — EXCLUDED from slip)", None,
                "over 2.5 pick excluded")

    price_txt = f"{price:.2f}" if price is not None else "NO PRICE — confirm on SportyBet"
    prob_txt = f"{round(prob*100)}%" if prob is not None else "NO DATA — PENDING"
    if price is None:
        warning = "no live price — use breakeven trigger, confirm before betting"
    else:
        warning = None
    return (f"{idx}. {fixture} — {name} @ {price_txt} ({prob_txt})",
            price, warning)


def build_slip(day: str, stake: float) -> dict:
    """Assemble the full slip for a day.

    Returns a dict with legs, combined odds, suggested stake, and any warnings.
    An empty board or no eligible picks returns an honest NO PICK message — the
    framework's value is disciplined filtering; a quiet day is a correct result,
    not a failure."""
    board = load_board(day)
    eligible = [bf for bf in board
                if bf.get("softness_tier") in ("A", "B")
                and bf.get("on_deploy_shortlist")]

    legs: list[str] = []
    prices: list[float] = []
    warnings: list[str] = []
    excluded: list[str] = []

    for i, bf in enumerate(eligible, 1):
        line, price, warn = _leg_line(bf, i, stake)
        if warn and "EXCLUDED" in line:
            excluded.append(line)
            continue
        legs.append(line)
        if price is not None:
            prices.append(price)
        if warn:
            warnings.append(f"{line} — {warn}")

    combined = 1.0
    for p in prices:
        combined *= p
    combined = None if not prices else combined

    # Suggested total stake: scale with combined odds so the slip doesn't
    # casually suggest a big capital figure on a long-shot parlay. Paper-only —
    # this number is a formatting default, not a deployment instruction.
    suggested = stake
    if combined is not None and combined > 0:
        suggested = round(min(stake, stake * COMBINED_ODDS_STAKE_FLOOR * 10 / combined), 0)
        suggested = max(100, suggested)  # keep it readable; still paper-only

    return {
        "day": day,
        "n_legs": len(legs),
        "legs": legs,
        "excluded": excluded,
        "combined_odds": combined,
        "suggested_stake": suggested,
        "warnings": warnings,
        "board_missing": not board,
    }


def render_slip(s: dict) -> str:
    """Human-readable slip, ready to copy into SportyBet."""
    out: list[str] = []
    if s["board_missing"]:
        out.append(f"ACCUMULATOR PREP — {s['day']}\n"
                   "NO BOARD FOUND — output/boards/board_<date>.json missing. "
                   "Run the daily pipeline first, or pass the right date. "
                   "NO DATA — PENDING (HR35, nothing fabricated).")
        return "\n".join(out)

    out.append(f"ACCUMULATOR PREP — {s['day']}")
    out.append("Tier A/B deploy-shortlist picks only. Phase 2 paper — nothing "
               "placed by this system.")
    if not s["legs"]:
        out.append("NO DEPLOY-ELIGIBLE PICKS today — a valid, honest result.")
        if s["excluded"]:
            out.append("Excluded by market gate (ID405):")
            out.extend(f"  {e}" for e in s["excluded"])
        return "\n".join(out)

    out.append("LEGS (paste order):")
    out.extend(s["legs"])
    if s["excluded"]:
        out.append("EXCLUDED by market gate (ID405):")
        out.extend(f"  {e}" for e in s["excluded"])
    if s["combined_odds"] is not None:
        out.append(f"COMBINED ODDS: {s['combined_odds']:.2f}")
    out.append(f"SUGGESTED TOTAL STAKE: {s['suggested_stake']:,.0f} "
               f"(paper-only default — Architect decides)")
    if s["warnings"]:
        out.append("ARCHITECT REVIEW REQUIRED:")
        out.extend(f"  ⚠ {w}" for w in s["warnings"])
    out.append("HONEST EDGE LINE: excellent informed process, NOT a demonstrated "
               "profitable edge. No bet is live until the Architect places it "
               "manually.")
    return "\n".join(out)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Format the day's Tier A/B picks into a ready-to-paste "
                    "SportyBet accumulator slip. READ-ONLY — never places a bet.")
    parser.add_argument("day", nargs="?", default=date.today().isoformat(),
                        help="Board date as YYYY-MM-DD (default: today)")
    parser.add_argument("--stake", type=float, default=DEFAULT_STAKE_NGN,
                        help="Suggested total stake figure (paper default)")
    parser.add_argument("--json", action="store_true",
                        help="Emit the slip as JSON instead of human text")
    args = parser.parse_args()

    slip = build_slip(args.day, args.stake)
    if args.json:
        json.dump(slip, sys.stdout, indent=2, ensure_ascii=False)
        print()
        return
    print(render_slip(slip))


if __name__ == "__main__":
    main()
