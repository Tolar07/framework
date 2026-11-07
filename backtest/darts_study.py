"""
Darts shadow-board study (framework#341, Week A; record-only). Writes backtest/DARTS_STUDY.md.

No dated multi-season PDC results feed exists in the repo (HR35/HR59), so a 3-season backtest cannot be faked. What
this does instead is read what the darts shadow board has actually recorded (engine.multisport) and report, walk-forward
and honestly: how many graded sides and picks exist, the Elo walk-forward Brier against the 0.25 coin-flip baseline,
and the days of data. Anything with too little data reads PENDING. Every try is counted (one scoreboard, one Elo).
Nothing here changes a pick, stake, bar or the live switch.

  python backtest/darts_study.py
"""
from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import multisport as ms  # noqa: E402

OUT = ROOT / "backtest" / "DARTS_STUDY.md"
SPORT = "darts"
MIN_SCORED = 100  # Elo Brier verdict needs at least this many scored games, else PENDING
COIN_FLIP_BRIER = 0.25


BUCKETS = [(0.0, 0.25), (0.25, 0.4), (0.4, 0.55), (0.55, 0.7), (0.7, 1.01)]
MIN_BUCKET = 30  # a bucket with fewer graded sides reads PENDING, never a verdict


def calibration(docs: list[tuple[str, dict]]) -> list[dict]:
    """Price-implied chance (1/first price) vs the share that actually won, per bucket, over every graded side.

    Market-anchored check: if the price is calibrated, implied ~ actual. Raw implied (not de-vigged), so a small gap
    equal to the overround is expected. Sides with no price or no result are skipped (HR35: missing reads PENDING).
    """
    acc = [[0, 0, 0.0] for _ in BUCKETS]  # n, won, sum implied
    for _day, doc in docs:
        for g in (doc.get("games") or {}).values():
            for sd in (g.get("sides") or {}).values():
                price = ((sd.get("first") or {}).get("price"))
                won = sd.get("won")
                if not price or price <= 1.0 or won is None:
                    continue
                q = 1.0 / price
                for i, (lo, hi) in enumerate(BUCKETS):
                    if lo <= q < hi:
                        acc[i][0] += 1
                        acc[i][1] += 1 if won else 0
                        acc[i][2] += q
                        break
    out = []
    for (lo, hi), (n, w, sq) in zip(BUCKETS, acc, strict=True):
        ok = n >= MIN_BUCKET
        out.append({"lo": lo, "hi": min(hi, 1.0), "n": n, "won": w,
                    "implied": round(sq / n, 4) if ok else None, "actual": round(w / n, 4) if ok else None})
    return out


def summarise(docs: list[tuple[str, dict]], elo: dict | None) -> dict:
    sb = ms.scoreboard(docs, elo)
    e = sb.get("elo") or {}
    scored, brier = e.get("scored", 0), e.get("walk_forward_brier")
    if not scored or brier is None or scored < MIN_SCORED:
        verdict = f"PENDING (needs {MIN_SCORED} scored games, has {scored})"
    elif brier < COIN_FLIP_BRIER:
        verdict = f"Elo beats a coin flip ({brier:.4f} < {COIN_FLIP_BRIER})"
    else:
        verdict = f"Elo does NOT beat a coin flip ({brier:.4f} >= {COIN_FLIP_BRIER})"
    return {"days": len(docs), "first": docs[0][0] if docs else None, "last": docs[-1][0] if docs else None,
            "sb": sb, "verdict": verdict, "calibration": calibration(docs)}


# Probed 2026-11-07 (framework#341): TheSportsDB PDC Darts (league 4554), seasons 2022-2025, free key.
# Only tournament-day rows (15/season): no players, no scores. Not a usable results feed, so the backtest stays PENDING.
FEED_PROBE = [("TheSportsDB PDC Darts (4554), 2022-2025", 60, 0,
               "tournament-day rows only: no players, no scores")]


def feed_probe_lines() -> list[str]:
    out = ["## Results-feed probe (why the 3-season backtest is PENDING)", "",
           "| Source | Events | With a score | Finding |", "|---|---|---|---|"]
    for src, n, scored, note in FEED_PROBE:
        out.append(f"| {src} | {n} | {scored} | {note} |")
    return out + [""]


def render(s: dict, now: datetime) -> str:
    sb, e = s["sb"], s["sb"].get("elo") or {}
    lines = ["# Darts shadow study", "",
             f"Made {now:%Y-%m-%d %H:%M} UTC by `backtest/darts_study.py` (framework#341). Record only.", "",
             "A true 3-season walk-forward backtest vs the closing price needs a dated PDC results feed that does not "
             "exist yet (PENDING, HR35/HR59). This reads what the shadow board has recorded so far.", "",
             "## Shadow board so far", "",
             f"- Board days: {s['days']} ({s['first'] or 'none'} to {s['last'] or 'none'})",
             f"- Graded picks: {sb['picks']} (won {sb['won']}, paper P&L {sb['pnl']} units)",
             f"- Average CLV vs fair close: {sb['clv_fair_avg'] if sb['clv_fair_avg'] is not None else 'PENDING'}",
             f"- Players rated: {e.get('rated', 0)}; games learned: {e.get('games_learned', 0)}",
             f"- Elo walk-forward Brier: {e.get('walk_forward_brier') or 'PENDING'} over {e.get('scored', 0)} scored games",
             f"- Verdict: {s['verdict']}", "", "## Every side by market (all graded sides, not just picks)", "",
             "| Market | Sides | Won | Flat-stake P&L |", "|---|---|---|---|"]
    for mid, b in sorted(sb["all_sides_by_market"].items()):
        lines.append(f"| {mid} | {b['sides']} | {b['won']} | {b['pnl']} |")
    if not sb["all_sides_by_market"]:
        lines.append("| PENDING | 0 | 0 | 0 |")
    lines += ["", "## Price calibration (implied chance vs actual win rate, all graded sides)", "",
              "| Implied band | Sides | Won | Implied | Actual |", "|---|---|---|---|---|"]
    for b in s.get("calibration", []):
        imp = b["implied"] if b["implied"] is not None else f"PENDING (<{MIN_BUCKET})"
        act = b["actual"] if b["actual"] is not None else "PENDING"
        lines.append(f"| {b['lo']:.2f}-{b['hi']:.2f} | {b['n']} | {b['won']} | {imp} | {act} |")
    lines += [""] + feed_probe_lines()[:-1]
    lines += ["", "Record only: nothing here changes a stake, a bar or the live switch.", ""]
    return "\n".join(lines)


def run(now: datetime | None = None) -> str:
    docs = ms.load_all(SPORT)
    text = render(summarise(docs, ms.load_elo(SPORT)), now or datetime.now(UTC))
    OUT.write_text(text, encoding="utf-8")
    return text


if __name__ == "__main__":
    print(run())
