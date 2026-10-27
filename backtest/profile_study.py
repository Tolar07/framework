"""
PROFILE STUDY — do the pre-match team profiles read the games right?
(Architect 2026-10-13: know how every team operates, bet on or not, before
the paper book bets on them.)

Reads the graded universe (engine/universe.py) — every SportyBet football game
that carried a pre-match profile (data/team_profiles.py, attached by the
sweep before kick-off) — and writes backtest/PROFILE_STUDY.md:
  1. per profile lean: games, goals per game against the profile's goal hint,
     how often BTTS yes / Over 2.5 / Under 3.5 landed, against SportyBet's own
     fair chance (last price, margin removed), and a £1 flat return at that
     price;
  2. the goal hint's error: profile total vs actual goals, by hint band.
A study, not a selector: nothing here changes a board.

    python backtest/profile_study.py
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from engine import universe as uv  # noqa: E402

OUT = ROOT / "backtest" / "PROFILE_STUDY.md"
MIN_N = 20          # fewer games than this: shown, marked "too few"
# (label, price key, side index, won(h, a))
MARKETS = (("BTTS yes", "btts", 0, lambda h, a: h > 0 and a > 0),
           ("BTTS no", "btts", 1, lambda h, a: not (h > 0 and a > 0)),
           ("Over 2.5", "ou2.5", 0, lambda h, a: h + a > 2.5),
           ("Under 3.5", "ou3.5", 1, lambda h, a: h + a < 3.5))


def lean_of(r: dict) -> str:
    lean = (((r.get("profile") or {}).get("read") or {}).get("lean") or "")
    return lean.split(" — ")[0] if lean else ""


def profiled(rows: list[dict]) -> list[dict]:
    return [r for r in rows if r.get("sport") == "football" and r.get("profile")
            and (r.get("result") or {}).get("h") is not None and not r["result"].get("after_90")]


def market_line(games: list[dict], key: str, side: int, won) -> tuple[int, float, float | None, float | None]:
    """(priced games, landed share, SportyBet fair chance, £1 flat ROI)."""
    n = hits = 0
    fair = ret = 0.0
    for r in games:
        p = ((r.get("last") or {}).get("p") or {}).get(key)
        if not p or len(p) < 2 or not all(x and x > 1 for x in p[:2]):
            continue
        inv = [1 / p[0], 1 / p[1]]
        w = won(r["result"]["h"], r["result"]["a"])
        n += 1
        hits += w
        fair += inv[side] / sum(inv)
        ret += p[side] * w - 1
    if not n:
        return 0, 0.0, None, None
    return n, hits / n, fair / n, ret / n


def build(rows: list[dict]) -> str:
    games = profiled(rows)
    out = ["# PROFILE STUDY — pre-match team profiles against the results", "",
           "Every graded SportyBet football game that carried both teams' FotMob profile "
           "before kick-off (data/team_profiles.py), bet on or not. *Landed* is how often the "
           "market won; *fair* is SportyBet's own chance at the last price, margin removed; "
           "*ROI* is £1 flat at that price. A lean only says something when landed beats fair "
           f"over {MIN_N}+ games. A study, not a selector.", "",
           f"Profiled graded games: **{len(games)}**", ""]
    if not games:
        out.append("NO DATA — PENDING (no profiled game has been graded yet)")
        return "\n".join(out) + "\n"
    by: dict[str, list[dict]] = defaultdict(list)
    for r in games:
        by[lean_of(r) or "PENDING"].append(r)
    out += ["## 1. By profile lean", "",
            "| Lean | Games | Goals/game | Hint | " + " | ".join(f"{m[0]} landed / fair / ROI" for m in MARKETS) + " |",
            "|---|---:|---:|---:|" + "---|" * len(MARKETS)]
    for lean, gs in sorted(by.items(), key=lambda kv: -len(kv[1])):
        goals = sum(r["result"]["h"] + r["result"]["a"] for r in gs) / len(gs)
        hints = [r["profile"]["read"].get("total_hint") for r in gs if r["profile"]["read"].get("total_hint")]
        cells = []
        for _label, key, side, won in MARKETS:
            n, land, fair, roi = market_line(gs, key, side, won)
            cells.append("PENDING" if fair is None or roi is None
                         else f"{land:.0%} / {fair:.0%} / {roi:+.1%} ({n})")
        tag = "" if len(gs) >= MIN_N else " *(too few)*"
        hint = f"{sum(hints) / len(hints):.2f}" if hints else "PENDING"
        out.append(f"| {lean}{tag} | {len(gs)} | {goals:.2f} | {hint} | " + " | ".join(cells) + " |")
    out += ["", "## 2. The goal hint against the goals scored", "",
            "| Profile total hint | Games | Mean hint | Mean goals |", "|---|---:|---:|---:|"]
    bands: dict[str, list[tuple[float, int]]] = defaultdict(list)
    for r in games:
        t = r["profile"]["read"].get("total_hint")
        if t is None:
            continue
        band = "< 2.0" if t < 2 else "2.0–2.5" if t < 2.5 else "2.5–3.0" if t < 3 else "3.0+"
        bands[band].append((t, r["result"]["h"] + r["result"]["a"]))
    for band in ("< 2.0", "2.0–2.5", "2.5–3.0", "3.0+"):
        xs = bands.get(band)
        if xs:
            out.append(f"| {band} | {len(xs)} | {sum(t for t, _ in xs) / len(xs):.2f} | "
                       f"{sum(g for _, g in xs) / len(xs):.2f} |")
    return "\n".join(out) + "\n"


def main() -> int:
    text = build([r for r in uv.load_graded() if r.get("result")])
    OUT.write_text(text, encoding="utf-8")
    print(f"profile study: {text.splitlines()[4]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
