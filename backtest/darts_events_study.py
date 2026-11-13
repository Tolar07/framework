"""
Darts events study (framework #592, Event models #13; RECORD ONLY). Writes backtest/DARTS_EVENTS_STUDY.md.

Question: does the leg ladder in engine/darts_events.py (board Elo win chance -> per-leg chance -> exact leg score) beat the
plain climatology of earlier first-to-6 matches at (a) the exact leg score (favourite side) and (b) every total-legs
half-line? Data: data/darts/pl_results.json (Premier League Darts nights, dated, all first to 6 legs). 180s, most 180s and
checkouts: PENDING (no per-visit record is stored). No free historical correct-score / total price exists: accuracy, not return.

Same walk-forward as backtest/snooker_events_study.py (reused): a match on day D sees only matches dated before D-1, Elo and
climatology both; Elo shrink settings (1.0/0.9/0.8/0.7) counted, chosen on matches before SPLIT, reported from SPLIT on.
Nothing here changes a pick, stake or threshold.

  python backtest/darts_events_study.py
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import snooker_events_study as ss  # noqa: E402

DATA = ROOT / "data" / "darts" / "pl_results.json"
OUT = ROOT / "backtest" / "DARTS_EVENTS_STUDY.md"
SPLIT = "2025-01-01"
MIN_FORMAT = 60


def load() -> list[dict]:
    try:
        rows = json.loads(DATA.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    rows = rows if isinstance(rows, list) else next((v for v in rows.values() if isinstance(v, list)), [])
    return [{"date": r["date"], "kickoff_utc": r["kickoff_utc"], "home": r["home"], "away": r["away"],
             "home_frames": r["home_sets"], "away_frames": r["away_sets"]}
            for r in rows if r.get("date") and r.get("home_sets") is not None and r.get("away_sets") is not None]


def render(rows: list[dict], now: datetime) -> str:
    L = ["# Darts events study (correct score in legs, total legs; 180s and checkouts PENDING)", "",
         f"Made {now:%Y-%m-%d %H:%M} UTC by `backtest/darts_events_study.py` (framework #592). Record only, a shadow; "
         "no price in the source, so accuracy not edge.", ""]
    if not rows:
        return "\n".join(L + ["NO DATA - PENDING.", ""])
    res = ss.run(rows, min_format=MIN_FORMAT)
    tune = {s: [r for r in v["rows"] if r["day"] < SPLIT] for s, v in res.items()}
    if not any(tune.values()):
        return "\n".join(L + ["No tuning-period match with enough history - PENDING.", ""])
    best = min(ss.SHRINK, key=lambda s: ss.summarise(tune[s], "sc_m", "sc_b")[0] if tune[s] else 9e9)
    held = [r for r in res[best]["rows"] if r["day"] >= SPLIT]
    L += [f"Settings tried: **{len(ss.SHRINK)}** (Elo shrink {', '.join(str(s) for s in ss.SHRINK)}); chosen on matches before "
          f"{SPLIT}: **{best}**. Held-out matches from {SPLIT}: **{len(held)}** (first to 6 legs).", "",
          "| Event | Ladder log loss | Climatology log loss | Gain (base - ladder) | s.e. |", "|---|---|---|---|---|"]
    for name, a, b in (("Exact leg score (favourite side)", "sc_m", "sc_b"), ("Total legs over, every line", "tot_m", "tot_b")):
        m, bs, sem, _ = ss.summarise(held, a, b)
        L.append(f"| {name} | {m:.4f} | {bs:.4f} | {bs - m:+.4f} | {sem:.4f} |")
    L += ["", "Calibration of the total-legs over chance (all lines, tuning and held-out pooled, chosen shrink):", "",
          "| Predicted | Cases | Happened |", "|---|---|---|"]
    for lo in (0.0, 0.2, 0.4, 0.6, 0.8):
        c = [y for pm, y in res[best]["cal"] if lo <= pm < lo + 0.2 or (lo == 0.8 and pm >= 1.0)]
        if c:
            L.append(f"| {lo:.1f}-{lo + 0.2:.1f} | {len(c)} | {sum(c) / len(c):.3f} |")
    L += ["", "Total 180s, most 180s, checkouts: **PENDING** (HR35). No per-visit record is stored; DartsOrakel returned 403 "
          "(2026-11-12). Candidates: PDC stats pages, dartsconnect. A scraper and graded counts come before any model.", "",
          "## Reading", "",
          "- Positive gain = the ladder beats repeating how earlier first-to-6 matches finished; within about 2 s.e. of zero is no proof.",
          "- The ladder uses one per-leg chance (throw-first alternation ignored); the alternating model is darts_format_study.py.",
          "- Record only: nothing here changes a stake, a bar, a threshold or the live switch.", ""]
    return "\n".join(L)


def main(now: datetime | None = None) -> str:
    text = render(load(), now or datetime.now(UTC))
    OUT.write_text(text, encoding="utf-8")
    return text


if __name__ == "__main__":
    print(main())
