"""
VOLLEYBALL walk-forward backtest (framework#342, multi-sport rollout; record-only).

The board rates volleyball with the shared win-probability Elo (engine/multisport.py). The only free, dated,
final-score volleyball history is ESPN's NCAA women's season (sets won by each side; one request per day because
a year query is capped at 1000 events). It is a college source, not the pro leagues in scope, but the sport and the
best-of-5 format are the same, so it tests the Elo recipe (K x home edge) honestly: every setting tried is counted,
chosen on the first years, reported on the later years only. Also records how often the winner takes the match 3-0.
Table tennis has NO free dated results source: it reads PENDING (HR35), never invented (HR59).

No free closing odds, so this measures accuracy, not return; return and CLV come from the shadow board's own
graded record. Record only: nothing here changes a stake, a bar, a threshold or the live switch.

  python backtest/volleyball_backtest.py      writes backtest/VOLLEYBALL_TABLE_TENNIS_STUDY.md
"""
from __future__ import annotations

import itertools
import json
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import rugby_backtest as rb  # noqa: E402  (shared Elo replay + Brier scoring)

OUT = ROOT / "backtest" / "VOLLEYBALL_TABLE_TENNIS_STUDY.md"
CACHE = ROOT / "backtest" / "cache" / "volleyball"
YEARS = tuple(range(2016, 2026))      # fall seasons (Aug 20 - Dec 31)
TUNE_YEARS = (2016, 2020)
KS = (16.0, 24.0, 32.0, 48.0)
HOME = (0.0, 40.0, 70.0)
API = "https://site.api.espn.com/apis/site/v2/sports/volleyball/womens-college-volleyball/scoreboard?dates={d}&limit=1000"
MIN_TUNE_N = 300


def fetch_day(d: str) -> list[dict]:
    f = CACHE / f"{d}.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    req = urllib.request.Request(API.format(d=d), headers={"User-Agent": "olp-xdv-backtest"})
    with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310 (fixed https URL)
        evs = json.load(r).get("events", [])
    slim = [{"date": e.get("date"), "status": e.get("status"), "competitions": [{"competitors": [
        {"homeAway": c.get("homeAway"), "score": c.get("score"), "team": {"displayName": c["team"]["displayName"]}}
        for c in e["competitions"][0]["competitors"]]}]} for e in evs if e.get("competitions")]
    CACHE.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(slim), encoding="utf-8")
    return slim


def days() -> list[str]:
    out = []
    for y in YEARS:
        d, end = date(y, 8, 20), date(y, 12, 31)
        while d <= end:
            out.append(d.strftime("%Y%m%d"))
            d += timedelta(days=1)
    return out


def load(fetch=fetch_day, day_list: list[str] | None = None) -> list[dict]:
    day_list = day_list if day_list is not None else days()

    def one(d):
        try:
            return d, fetch(d)
        except Exception as ex:  # a day that will not load is skipped and counted, never invented
            return d, ex

    with ThreadPoolExecutor(8) as pool:
        res = list(pool.map(one, day_list))
    failed = sum(isinstance(e, Exception) for _, e in res)
    if failed:
        print(f"{failed} days not loaded")
    games, seen = [], set()
    for _, evs in res:
        if isinstance(evs, Exception):
            continue
        for g in rb.parse(evs, "NCAA women"):
            if max(g["hs"], g["as"]) != 3 or min(g["hs"], g["as"]) > 2:
                continue   # a finished best-of-5 match has exactly one side on 3 sets and the other on 0-2
            key = (g["day"], frozenset((g["home"], g["away"])))
            if key not in seen:
                seen.add(key)
                games.append(g)
    games.sort(key=lambda g: (g["day"], g["home"]))
    for g in games:
        g["year"] = int(g["day"][:4])
        g["y"] = float(g["hs"] > g["as"])
    return games


def run(games: list[dict]) -> str:
    last = max((g["year"] for g in games), default=TUNE_YEARS[1])
    test = (TUNE_YEARS[1] + 1, last)
    tune_g = [g for g in games if TUNE_YEARS[0] <= g["year"] <= TUNE_YEARS[1]]
    base = sum(g["y"] for g in tune_g) / len(tune_g) if tune_g else 0.5
    cache = {(k, h): rb.replay(games, k, h) for k, h in itertools.product(KS, HOME)}
    tries = len(cache)
    tuned = {kh: rb.evaluate(games, p, TUNE_YEARS) for kh, p in cache.items()}
    ok = {kh: t for kh, t in tuned.items() if t["n"] >= MIN_TUNE_N}
    best = min(ok, key=lambda kh: ok[kh]["brier"]) if ok else None
    live = rb.evaluate(games, cache[(24.0, 0.0)], test, base)   # the shared board setting
    held = rb.evaluate(games, cache[best], test, base) if best else None
    sweep = [g for g in games if test[0] <= g["year"] <= test[1]]
    sweep_rate = (sum(min(g["hs"], g["as"]) == 0 for g in sweep) / len(sweep)) if sweep else None
    made = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    def line(name, r):
        if not r["n"]:
            return f"| {name} | 0 | PENDING | PENDING | PENDING |"
        return f"| {name} | {r['n']} | {r['brier']:.4f} | {r['base']:.4f} | {r['hit']:.1%} |"

    L = ["# Volleyball + table tennis study", "",
         f"Made {made} by `backtest/volleyball_backtest.py` (framework#342). **Volleyball:** {len(games)} NCAA women's "
         f"matches (ESPN final set scores, Aug-Dec of {YEARS[0]}-{YEARS[-1]}). Settings tried: **{tries}** (K x home "
         f"edge); chosen on {TUNE_YEARS[0]}-{TUNE_YEARS[1]}, reported on **{test[0]}-{test[1]} only**. Home sides won "
         f"{base:.1%} of tuning-year matches.", "",
         f"| Rule (held-out years) | Matches rated | Brier | Brier flat home-edge baseline ({base:.1%}) | Winner hit rate |",
         "|---|---|---|---|---|", line("Board setting: Elo K24, no home edge", live)]
    if held:
        L.append(line(f"Best on tuning years: K{best[0]:.0f}, home +{best[1]:.0f}", held))
    L += ["", "## Reading", ""]
    if live["n"] and held:
        L.append(f"- Elo vs flat baseline on held-out years: {live['brier']:.4f} vs {live['base']:.4f} "
                 + ("(the Elo carries information)." if live["brier"] < live["base"] else "(no better than the baseline)."))
        gain = live["brier"] - held["brier"]
        L.append(f"- Tuned setting K{best[0]:.0f}, home +{best[1]:.0f}: held-out Brier changed {gain:+.4f} vs the board setting "
                 + ("(a shadow candidate for volleyball, to be confirmed on the shadow board)." if gain > 0.0005
                    else "(no real help: leave the board setting alone)."))
    else:
        L.append("- PENDING: too little tuning data.")
    if sweep_rate is not None:
        L.append(f"- Held-out matches won 3-0: {sweep_rate:.1%} (the share a set-by-set format model must reproduce; "
                 "see framework#380).")
    L += ["- **Scope caveat:** college, not the pro leagues in scope; it tests the Elo recipe, not pro strength. "
          "Pro leagues have no free dated results feed found.",
          "", "## Table tennis", "",
          "- PENDING: no free dated WTT/ITTF results source was found (ESPN has none; the open feeds are Setka-type "
          "leagues, excluded by the issue for integrity risk). Nothing is invented (HR59). Table tennis stays on the "
          "shadow board's own graded record until a source is wired.",
          f"- {tries} settings tried; the held-out line is the honest one.",
          "- Record only: nothing here changes a stake, a bar or the live switch."]
    return "\n".join(L) + "\n"


def main() -> int:
    games = load()
    if len(games) < 2000:
        print(f"only {len(games)} matches read: NO DATA - PENDING")
        return 1
    text = run(games)
    OUT.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
