"""
NCAA STUDY — the constants an NCAA board needs before it can price SportyBet's NCAA lines the way the
NBA board prices the NBA (engine/nba_value.py; Architect 2026-11-05: widen basketball beyond the NBA).

The NBA board's fair chance for a total line is Normal(sharp total, SD), for a handicap Normal(-sharp
spread, SD); NBA_STUDY measured SD 18.0 (total) and 13.7 (margin). College games are 40 minutes in two
halves, with other pace and foul rules, so they get their own numbers. This study reads ESPN's free
men's Division I scoreboard (finals + half-time linescores) and its odds feed (DraftKings, the line
before tip-off) on a sample of last season's dates, and measures:

    total miss    final total - sharp total         -> mean (bias) and SD
    margin miss   home margin + sharp home spread   -> mean and SD
    1st half      1st-half total / sharp total      -> share, and the SD of the miss

    python backtest/ncaa_study.py [--every 4]  -> backtest/NCAA_STUDY.md + backtest/cache/ncaa_games.json
"""
from __future__ import annotations

import argparse
import json
import math
import statistics as st
import sys
import time
import urllib.request
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "backtest" / "NCAA_STUDY.md"
CACHE = ROOT / "backtest" / "cache" / "ncaa_games.json"
SB = ("https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard"
      "?dates={d}&groups=50&limit=400")
ODDS = ("https://sports.core.api.espn.com/v2/sports/basketball/leagues/mens-college-basketball/events/{e}"
        "/competitions/{e}/odds")
SEASON = (date(2025, 11, 3), date(2026, 3, 8))       # last regular season (before the tournaments)


def _get(url: str) -> dict | None:
    for i in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "olp-ncaa-study"}),  # noqa: S310
                                        timeout=30) as r:
                return json.loads(r.read())
        except Exception:  # noqa: BLE001 — retry, then skip the item
            time.sleep(1 + i)
    return None


def games_on(d: date) -> list[dict]:
    blob = _get(SB.format(d=d.strftime("%Y%m%d"))) or {}
    out = []
    for e in blob.get("events") or []:
        comp = (e.get("competitions") or [{}])[0]
        if not (comp.get("status") or {}).get("type", {}).get("completed"):
            continue
        teams = {t.get("homeAway"): t for t in comp.get("competitors") or []}
        h, a = teams.get("home"), teams.get("away")
        if not h or not a:
            continue
        lh = [float(x.get("value") or 0) for x in h.get("linescores") or []]
        la = [float(x.get("value") or 0) for x in a.get("linescores") or []]
        out.append({"id": e["id"], "date": d.isoformat(), "hs": float(h.get("score") or 0), "as": float(a.get("score") or 0),
                    "h1": (lh[0] + la[0]) if lh and la else None, "ot": len(lh) > 2,
                    "neutral": bool(comp.get("neutralSite"))})
    return out


def attach_line(g: dict) -> dict:
    blob = _get(ODDS.format(e=g["id"])) or {}
    items = [i for i in blob.get("items") or [] if "Live" not in ((i.get("provider") or {}).get("name") or "")]
    if items:
        o = items[0]
        g["total"] = o.get("overUnder")
        g["spread"] = o.get("spread")                  # the home side's line
        g["provider"] = (o.get("provider") or {}).get("name")
    return g


def collect(every: int) -> list[dict]:
    have = {g["id"]: g for g in json.loads(CACHE.read_text(encoding="utf-8"))} if CACHE.exists() else {}
    d = SEASON[0]
    while d <= SEASON[1]:
        for g in games_on(d):
            if g["id"] not in have:
                have[g["id"]] = attach_line(g)
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(list(have.values())), encoding="utf-8")
        print(f"{d}: {len(have)} games so far", flush=True)
        d += timedelta(days=every)
    return list(have.values())


def _ms(xs: list[float]) -> tuple[float, float]:
    return st.mean(xs), st.pstdev(xs)


def report(games: list[dict]) -> str:
    lined = [g for g in games if g.get("total") is not None and g.get("spread") is not None]
    reg = [g for g in lined if not g["ot"]]
    tm = _ms([g["hs"] + g["as"] - g["total"] for g in lined])
    mm = _ms([(g["hs"] - g["as"]) + g["spread"] for g in lined])
    h1 = [g for g in reg if g.get("h1")]
    share = sum(g["h1"] for g in h1) / sum(g["total"] for g in h1) if h1 else float("nan")
    h1m = _ms([g["h1"] - share * g["total"] for g in h1]) if h1 else (float("nan"), float("nan"))

    def cover(sd: float, mean: float, xs: list[float]) -> float:
        """Share of games inside ±1 SD of the line + bias: ~68% if Normal fits."""
        return sum(1 for x in xs if abs(x - mean) <= sd) / len(xs)
    lines = ["# NCAA STUDY — constants for an NCAA board", "",
             f"Written by `backtest/ncaa_study.py` (ESPN free scoreboard + odds feed, men's Division I, "
             f"{SEASON[0]} to {SEASON[1]}, sampled dates). {len(games)} finished games read, {len(lined)} with a "
             f"pre-tip sharp line ({', '.join(sorted({str(g.get('provider')) for g in lined}))}).", "",
             "| Quantity | Mean miss (bias) | SD | inside ±1 SD (Normal ≈ 68%) | n | NBA board value |",
             "|---|---|---|---|---|---|",
             f"| final total − sharp total | {tm[0]:+.2f} | {tm[1]:.2f} | "
             f"{cover(tm[1], tm[0], [g['hs'] + g['as'] - g['total'] for g in lined]):.0%} | {len(lined)} | SD 18.0 |",
             f"| home margin + sharp spread | {mm[0]:+.2f} | {mm[1]:.2f} | "
             f"{cover(mm[1], mm[0], [(g['hs'] - g['as']) + g['spread'] for g in lined]):.0%} | {len(lined)} | SD 13.7 |",
             f"| 1st-half total − share × sharp total (no OT games) | {h1m[0]:+.2f} | {h1m[1]:.2f} | — | {len(h1)} | "
             f"share 0.502, SD 11.9 |", "",
             f"1st-half share of the sharp total: **{share:.4f}**.", "",
             "Use: an NCAA board would price SportyBet's total and handicap ladders as Normal(line + bias, SD) "
             "from these numbers, exactly as engine/nba_value.py does for the NBA, and qualify a pick only "
             "above its value bar. RECORDED ONLY until a forward test earns it a place (the Architect's call)."]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--every", type=int, default=4, help="sample every Nth day of the season")
    ap.add_argument("--report-only", action="store_true")
    a = ap.parse_args(argv)
    games = json.loads(CACHE.read_text(encoding="utf-8")) if a.report_only else collect(a.every)
    OUT.write_text(report(games), encoding="utf-8")
    print(OUT.read_text(encoding="utf-8"))
    return 0 if not math.isnan(len(games)) else 1


if __name__ == "__main__":
    sys.exit(main())
