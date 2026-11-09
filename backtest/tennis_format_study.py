"""
Tennis format shadow (framework#380; record-only, walk-forward).

Question: does the Pinnacle close under-state the favourite when the match is best-of-5 (men's Slams)? Candidate:
take the best-of-5 price, restate it as the same players' best-of-3 chance with engine/format_prob.py (hold/break chain
with tiebreak), correct it with the favourite-long-shot slope learned ONLY on earlier years' best-of-3 matches (thousands
more than Slams), and restate it back as best-of-5. Every year Y is predicted from years < Y only. One candidate, one
try; the last year is reported as the held-out year. Nothing here changes a pick, stake, bar or live switch.

  python backtest/tennis_format_study.py      writes backtest/TENNIS_FORMAT_STUDY.md  (needs tennis-data.co.uk)
"""
from __future__ import annotations

import math
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import tennis_backtest as tb  # noqa: E402
from engine import format_prob as fp  # noqa: E402

OUT = ROOT / "backtest" / "TENNIS_FORMAT_STUDY.md"
MIN_BO5 = 150  # PENDING (HR35) below this many best-of-5 matches in the scored years
EDGE = 0.02


def fit_slope(rows: list[dict]) -> float:
    """Slope k in p = sig(k * logit(mkt)) with the lowest log-loss on `rows` (grid 0.80..1.30)."""
    best, best_ll = 1.0, float("inf")
    for i in range(0, 51):
        k = 0.80 + i * 0.01
        ll = 0.0
        for g in rows:
            p = min(max(tb.sig(k * tb.logit(g["mkt"])), 1e-9), 1 - 1e-9)
            ll -= math.log(p if g["y"] else 1 - p)
        if ll < best_ll:
            best, best_ll = k, ll
    return best


def candidate(mkt: float, k: float, best_of: int) -> float:
    """Format-restated, slope-corrected chance for a match priced `mkt` in `best_of` sets (falls back to mkt)."""
    if best_of == 3:
        return tb.sig(k * tb.logit(mkt))
    m3 = fp.convert_tennis(mkt, best_of, 3)
    if m3 is None:
        return mkt
    p5 = fp.convert_tennis(tb.sig(k * tb.logit(m3)), 3, best_of)
    return mkt if p5 is None else p5


def walk_forward(games: list[dict], years: list[int]) -> list[dict]:
    out = []
    for y in years:
        train = [g for g in games if g["year"] < y and g["bo"] == 3]
        if len(train) < 2000:
            continue
        k = fit_slope(train)
        test = [g for g in games if g["year"] == y and g["bo"] == 5]
        n = len(test)
        row = {"year": y, "k": k, "n": n, "brier_mkt": None, "brier_cand": None, "bets": 0, "roi": None, "hit": None}
        if n:
            cands = [candidate(g["mkt"], k, 5) for g in test]
            row["brier_mkt"] = sum((g["mkt"] - g["y"]) ** 2 for g in test) / n
            row["brier_cand"] = sum((c - g["y"]) ** 2 for g, c in zip(test, cands)) / n
            stake = prof = wins = 0.0
            for g, c in zip(test, cands):
                # back the side the candidate rates above the market by EDGE at the Pinnacle close (no commission)
                if c - g["mkt"] >= EDGE:
                    side_a, odds = True, g["pa"]
                elif (1 - c) - (1 - g["mkt"]) >= EDGE:
                    side_a, odds = False, g["pb"]
                else:
                    continue
                won = (g["y"] == 1.0) == side_a
                stake += 1
                wins += won
                prof += (odds - 1) if won else -1
            row.update(bets=int(stake), roi=(prof / stake if stake else None), hit=(wins / stake if stake else None))
        out.append(row)
    return out


def run(games: list[dict]) -> str:
    made = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    bo5 = [g for g in games if g["bo"] == 5]
    rows = walk_forward(games, sorted({g["year"] for g in games}))
    L = ["# Tennis format shadow", "",
         f"Made {made} by `backtest/tennis_format_study.py` (framework#380). Record only, walk-forward.", "",
         f"Data: {len(games)} completed ATP/WTA matches with a Pinnacle close (tennis-data.co.uk); {len(bo5)} are best-of-5.",
         "Candidate (one try): best-of-5 price -> same players' best-of-3 chance (hold/break chain, tiebreak, "
         f"serve {fp.TOUR_SERVE:.0%} between equals, an assumption) -> slope learned on EARLIER years' best-of-3 matches "
         "-> back to best-of-5. Compared with the market on best-of-5 matches only.", "",
         "| Year | Slope k (from earlier Bo3) | Bo5 matches | Brier market | Brier candidate | Bets (edge >= 2%) | Hit | "
         "ROI at the close |", "|---|---|---|---|---|---|---|---|"]
    tn = tm = tc = 0.0
    for r in rows:
        if not r["n"]:
            continue
        f = lambda v, p=True: "-" if v is None else (f"{v:.1%}" if p else f"{v:.4f}")  # noqa: E731
        L.append(f"| {r['year']} | {r['k']:.2f} | {r['n']} | {f(r['brier_mkt'], False)} | {f(r['brier_cand'], False)} | "
                 f"{r['bets']} | {f(r['hit'])} | {f(r['roi'])} |")
        tn += r["n"]
        tm += r["brier_mkt"] * r["n"]
        tc += r["brier_cand"] * r["n"]
    L.append("")
    if tn < MIN_BO5:
        L += [f"**PENDING (HR35):** only {int(tn)} scored best-of-5 matches (< {MIN_BO5}); no verdict.", ""]
    else:
        d = tc / tn - tm / tn
        L += [f"All scored years: {int(tn)} best-of-5 matches, Brier market {tm / tn:.4f}, candidate {tc / tn:.4f} "
              f"({'candidate better' if d < 0 else 'market better or equal'} by {abs(d):.4f}). "
              f"Held-out (last year) is the final row. A Brier gap this small on ~{int(tn)} matches is inside noise "
              "unless it repeats every year; nothing is promoted from this table alone.", ""]
    L += ["## Reading", "",
          "- Pinnacle's close is the sharp benchmark; beating it on Brier or at the close is rare, so a null result is the "
          "expected, honest outcome. The value of the module is the format conversion for markets that have no sharp "
          "price (volleyball, table tennis, darts, snooker legs / frames, exchange prices in short formats).",
          "- Practitioner claims behind the idea: favourites win more often the longer the format "
          "(Pinnacle video @ 01:32 and Action Network video @ 04:09, as cited in framework#380; not re-watched here). "
          "Record only; no stake, bar or live switch reads this."]
    return "\n".join(L) + "\n"


def main() -> int:
    games = tb.load()
    if len(games) < 3000:
        print(f"only {len(games)} matches read: NO DATA - PENDING")
        return 1
    for g in games:
        g.setdefault("bo", 3)
    OUT.write_text(run(games), encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
