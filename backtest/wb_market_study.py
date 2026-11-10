"""
WORLD BASKETBALL MARKET + PERIOD STUDY - twin of backtest/nba_market_study.py and nba_period_study.py for NCAA
(2 x 20-min halves) (framework#394). RECORD-ONLY: a study, not a selector.

Reads output/world_basketball/wb_markets_*.jsonl (engine/wb_markets.py), takes each game's last look before
tip-off, grades every outcome whose rule is known from ESPN's final and half scores, and prints:

  1. per market: how often it landed against SportyBet's own chance (margin removed) and the return of
     GBP 1 flat on every outcome at its price;
  2. SHADOW board: the live board's bars (engine/world_basketball: price 1.20-2.00, chance >= 50%, value
     +3% winner / +5% line, at most +25%) applied, on paper, to every market the ESPN sharp line prices
     (engine/ncaa_lines.fair), next to the live rule and never replacing it;
  3. PERIOD: the 1st half's real share of the game's points against engine/ncaa_lines.H1_SHARE.

Non-NCAA leagues (EuroLeague / FIBA 4x10) have no free period-score feed: their outcomes read PENDING (HR35).

    python backtest/wb_market_study.py      -> backtest/WB_MARKET_STUDY.md  (stdout only when there is no data)
"""
from __future__ import annotations

import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from engine import ncaa_lines as nl  # noqa: E402
from engine import wb_markets as wm  # noqa: E402
from engine import world_basketball as wb  # noqa: E402

REPORT = ROOT / "backtest" / "WB_MARKET_STUDY.md"
WINNER = "219"


def _mean_se(xs: list[float]) -> tuple[float, float | None]:
    n = len(xs)
    m = sum(xs) / n
    return m, ((sum((x - m) ** 2 for x in xs) / (n - 1) / n) ** 0.5 if n > 1 else None)


def shadow_picks(graded: list[dict]) -> list[dict]:
    """Graded outcomes that clear the live board's bars at SportyBet's last price, by the sharp line's chance."""
    out = []
    for r in graded:
        p = r["model"]
        if p is None:
            continue
        ev = p * r["price"] - 1
        need = wb.MIN_VALUE.get(r["mid"], wb.LINE_VALUE)
        if wb.BAND[0] <= r["price"] <= wb.BAND[1] and p >= 0.5 and need <= ev <= wb.MAX_VALUE:
            out.append({**r, "ev": ev})
    return out


def by_market(graded: list[dict]) -> list[str]:
    fams: dict[str, list[dict]] = defaultdict(list)
    for r in graded:
        fams[f"{r['name']} [{r['mid']}]"].append(r)
    out = ["| Market | outcomes | landed | fair | return |", "|---|---:|---:|---:|---:|"]
    for fam, rs in sorted(fams.items(), key=lambda kv: -len(kv[1])):
        n = len(rs)
        out.append(f"| {fam} | {n} | {sum(r['won'] for r in rs) / n:.1%} | {sum(r['fair'] for r in rs) / n:.1%} | "
                   f"{sum(r['price'] * r['won'] - 1 for r in rs) / n:+.1%} |")
    return out


def shadow_table(graded: list[dict]) -> list[str]:
    picks = shadow_picks(graded)
    if not picks:
        return ["NO SHADOW PICKS YET - PENDING", ""]
    fams: dict[str, list[dict]] = defaultdict(list)
    for r in picks:
        fams[f"{r['name']} [{r['mid']}]"].append(r)
    out = ["| Market | picks | won | stated chance | return +- se |", "|---|---:|---:|---:|---|"]
    for fam, rs in sorted(fams.items(), key=lambda kv: -len(kv[1])):
        mean, se = _mean_se([r["price"] * r["won"] - 1 for r in rs])
        out.append(f"| {fam} | {len(rs)} | {sum(r['won'] for r in rs) / len(rs):.0%} | "
                   f"{sum(r['model'] for r in rs) / len(rs):.0%} | {mean:+.1%}" + (f" +- {se:.1%}" if se else "") + " |")
    return out + [""]


def half_share(results: dict[str, dict], espn_ids: set[str]) -> tuple[int, float | None]:
    """(games, mean 1st-half points / final points over regulation games the record covers)."""
    sh = [(g["h1"][0] + g["h1"][1]) / (g["hs"] + g["as"]) for k, g in results.items()
          if k in espn_ids and not g["ot"] and g["hs"] + g["as"] > 0]
    return len(sh), (sum(sh) / len(sh) if sh else None)


def build(rows: list[dict], results: dict[str, dict]) -> str:
    looks = wm.last_looks(rows)
    graded, st = wm.grade(looks, results)
    ids = {r["espn_id"] for r in looks if r.get("espn_id")}
    n_ncaa = sum(1 for r in looks if r.get("espn_id") in results)
    out = ["# WORLD BASKETBALL MARKET STUDY - every SportyBet market against the results (NCAA)", "",
           "Each game's last look before tip-off, every outcome graded from ESPN's final and half scores. "
           "*landed* = how often it won; *fair* = SportyBet's own chance (prices, margin removed); *return* = GBP 1 "
           "flat on every outcome at its price. A study, not a selector: nothing here changes a pick. "
           "Written by `backtest/wb_market_study.py` from `engine/wb_markets.py`.", "",
           f"Games recorded (last look pre-tip): {len(looks)} | NCAA games graded: {n_ncaa} | "
           f"outcomes graded: {len(graded)} | PENDING (no rule or no result, e.g. EuroLeague / FIBA): {st['pending']}", ""]
    if not graded:
        return "\n".join(out + ["NO GRADED DATA YET - PENDING", ""])
    out += ["## Per market", "", *by_market(graded), "",
            "## SHADOW board - the live bars on every market the ESPN line prices (paper)", "", *shadow_table(graded)]
    n, share = half_share(results, ids)
    out += ["## Period - the 1st half's share of the game's points (regulation games)", ""]
    if share is None:
        out += ["NO DATA - PENDING", ""]
    else:
        out += [f"{n} games: real share {share:.2%} vs engine/ncaa_lines.H1_SHARE {nl.H1_SHARE:.2%} "
                f"(difference {share - nl.H1_SHARE:+.2%}). Record-only; the board's value is unchanged.", ""]
    return "\n".join(out)


def main() -> int:
    rows = wm.load()
    days = set()
    for r in wm.last_looks(rows):
        t = datetime.fromisoformat(r["tip"].replace("Z", "+00:00"))
        days |= {t - timedelta(days=1), t}
    results: dict[str, dict] = {}
    for d in sorted(days):
        results.update(wm.finals(d))
    text = build(rows, results)
    if rows:
        REPORT.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
