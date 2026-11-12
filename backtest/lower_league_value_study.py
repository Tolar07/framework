"""
LOWER-LEAGUE VALUE STUDY (framework #584) - what the paper board's rule would have done on the archive.

Walk-forward over every graded SportyBet football game since 2026-10-08 (data/universe/graded_*), in kick-off order:
the goals model (engine/lower_league_value.Goals) is fitted only on games that kicked off before each one; a
second-tier-or-lower game gets the board's pick (largest positive value at SportyBet's last price) and is graded on
its 90-minute result. Reported by the size of the claimed gap, the question the video raises: do big 'model vs
market' gaps win, or do they mean the model is wrong? One rule, no tuning: 1 slice per band.
Output: backtest/LOWER_LEAGUE_VALUE_STUDY.md.  Usage: python backtest/lower_league_value_study.py
"""
from __future__ import annotations

import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import lower_league_value as lv  # noqa: E402
from engine import stats_history as sh  # noqa: E402

sys.path.insert(0, str(ROOT / "backtest"))
from league_profile_study import fmt, roi  # noqa: E402

REPORT = ROOT / "backtest" / "LOWER_LEAGUE_VALUE_STUDY.md"


def walk(rows: list[dict]) -> list[dict]:
    model = lv.Goals()
    picks = []
    for r in rows:
        row = {"sport": "football", "country": r["country"], "comp": r["comp"], "home": r["home"], "away": r["away"]}
        if lv.is_lower(row):
            p = lv.best_option(model, row, r.get("prices") or {})
            if p:
                p.update(band=lv.band(p["value"]), won=lv.won(p["option"], r["hg"], r["ag"]), league=r["league"])
                picks.append(p)
        model.add(r["league"], r["home"], r["away"], r["hg"], r["ag"])
    return picks


def main(argv: list[str] | None = None) -> int:
    rows = sh.load_sportybet()
    lower = [r for r in rows if lv.is_lower({"country": r["country"], "comp": r["comp"]})]
    picks = walk(rows)
    now = datetime.now(UTC)
    md = ["# Lower-league value study (framework #584)", "",
          f"Generated {now:%Y-%m-%d %H:%M} UTC by `backtest/lower_league_value_study.py`. PAPER ONLY. The video's "
          "'fair 1.60 vs market 2.55' style gaps are claims to test.", "",
          f"Data: {len(rows):,} graded SportyBet football games since 2026-10-08; **{len(lower):,} second-tier or "
          f"lower** ({len({r['league'] for r in lower})} competitions); {len(picks):,} got a pick (both teams with "
          f"{lv.MIN_TEAM}+ earlier games, a price {lv.PRICE_MIN}-{lv.PRICE_MAX}, value above zero).", "",
          "| Claimed gap (model chance x price - 1) | Bets | Hit | ROI | 90% range |", "|---|---|---|---|---|"]
    for name, *_ in lv.BANDS:
        md.append(f"| {name} | {fmt(roi([(p['won'], p['price']) for p in picks if p['band'] == name]))} |")
    md.append(f"| all picks | {fmt(roi([(p['won'], p['price']) for p in picks]))} |")
    md += ["", "| Option picked | Bets | Hit | ROI | 90% range |", "|---|---|---|---|---|"]
    for opt, _n in Counter(p["option"] for p in picks).most_common():
        md.append(f"| {opt} | {fmt(roi([(p['won'], p['price']) for p in picks if p['option'] == opt]))} |")
    md += ["", "Most common competitions in the lower-league set: "
           + ", ".join(f"{lg} ({n})" for lg, n in Counter(r["league"] for r in lower).most_common(12)) + ".", "",
           "## Reading",
           "- Read each band against zero AND against the others: if the biggest gaps lose most, the gap measures "
           "the model's error, not the market's (the push-back in #584).",
           "- Five weeks of games is a short record; the live paper board (engine/lower_league_value.py, every "
           f"sweep) keeps grading, and a band goes to the Architect only with {lv.READY_N}+ graded picks and a "
           "90% range above zero.", ""]
    REPORT.write_text("\n".join(md), encoding="utf-8")
    print(f"wrote {REPORT.relative_to(ROOT)}: {len(lower)} lower-league games, {len(picks)} picks")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
