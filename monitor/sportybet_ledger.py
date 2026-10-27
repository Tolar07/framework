"""
SPORTYBET EVIDENCE — what the Architect's real SportyBet bets did, fed back here.

The Architect, 2026-10-20: "make SportyBet results feed the framework too". The
placer (omniroute-test scripts/sportybet_placer/place.py, on the Architect's PC)
places the board's codes at 22:00 and, after each run, writes what happened to
each code into data/sportybet/placed_<date>.json. This module joins that with the
board's own grading (output/picks/picks_<date>.json) and writes per-section
evidence into data/sportybet/summary.json: which slip builds really pay at the
odds actually taken.

THIS REPO IS PUBLIC. The placer writes counts and rates only: code, section,
status, legs, odds taken, stake in UNITS of the day's base stake, and a skip
reason. No naira, no bet id, no balance.

    python monitor/sportybet_ledger.py            # rebuild data/sportybet/summary.json
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "sportybet"
PICKS = ROOT / "output" / "picks"
SUMMARY = DATA / "summary.json"
SECTIONS = ("safe3", "accas", "alts", "combined", "megas")


def board_results(picks: dict) -> dict:
    """{code: result} for every slip on the board ('won' / 'lost' / None while open)."""
    out = {}
    for sec in SECTIONS:
        for x in picks.get(sec) or []:
            code = (x.get("code") or "").strip().upper()
            if code:
                out[code] = x.get("result")
    return out


def summarise(data_dir: Path = DATA, picks_dir: Path = PICKS) -> dict:
    groups: dict = {}
    skipped: dict = {}
    days = 0
    for f in sorted(data_dir.glob("placed_*.json")):
        try:
            placed = json.loads(f.read_text(encoding="utf-8"))
            picks = json.loads((picks_dir / f"picks_{placed['date']}.json").read_text(encoding="utf-8"))
        except (OSError, ValueError, KeyError):
            continue
        days += 1
        res = board_results(picks)
        for b in placed.get("bets") or []:
            sec = b.get("section") or "?"
            if b.get("status") != "placed":
                why = (b.get("reason") or b.get("status") or "?").split(":")[0][:40]
                skipped[why] = skipped.get(why, 0) + 1
                continue
            for key in (sec, "all"):
                g = groups.setdefault(key, {"placed": 0, "settled": 0, "won": 0,
                                            "units": 0.0, "returned": 0.0, "odds_sum": 0.0})
                units = float(b.get("units") or 1)
                odds = float(b.get("odds") or 0)
                g["placed"] += 1
                got = res.get(str(b.get("code", "")).upper())
                if got in ("won", "lost"):
                    g["settled"] += 1
                    g["units"] += units
                    g["odds_sum"] += odds
                    if got == "won":
                        g["won"] += 1
                        g["returned"] += units * odds
    out = {}
    for k, g in groups.items():
        out[k] = {"placed": g["placed"], "settled": g["settled"], "won": g["won"],
                  "avg_odds": round(g["odds_sum"] / g["settled"], 2) if g["settled"] else None,
                  "return": round(g["returned"] / g["units"] - 1, 4) if g["units"] else None}
    return {"updated": datetime.now(UTC).date().isoformat(), "days": days,
            "sections": dict(sorted(out.items())), "skipped": dict(sorted(skipped.items()))}


def lines(summary_path: Path = SUMMARY) -> list[str]:
    """For the weekly review / debrief."""
    if not summary_path.exists():
        return ["SportyBet (real bets): PENDING — nothing placed by the placer yet"]
    s = json.loads(summary_path.read_text(encoding="utf-8"))
    secs = s.get("sections") or {}
    if not secs:
        return [f"SportyBet (real bets): nothing placed yet ({s.get('days', 0)} day(s) read)"]
    out = [f"SportyBet (real bets, {s.get('days')} day(s), at the odds taken):"]
    for k, g in secs.items():
        ret = "PENDING" if g["return"] is None else f"{g['return']:+.1%}"
        out.append(f"  {k}: {g['placed']} placed, {g['won']}/{g['settled']} landed, "
                   f"avg odds {g['avg_odds'] or 'PENDING'}, return {ret}")
    if s.get("skipped"):
        out.append("  not placed: " + ", ".join(f"{k} {v}" for k, v in s["skipped"].items()))
    return out


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    s = summarise()
    SUMMARY.write_text(json.dumps(s, indent=1) + "\n", encoding="utf-8")
    print("\n".join(lines()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
