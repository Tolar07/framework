"""MLB starting-pitcher shadow backtest (framework#382; record-only). Walk-forward on the cached ESPN scoreboards and
closing moneylines baseball_backtest.py already fetched: each game's two starters and first-5-inning runs come from the
same scoreboard (`probables`, `linescores`). The model (engine/mlb_pitcher.py) is replayed in date order, judged
against the de-vigged close on the held-out seasons (tuned 2019-2022, reported 2023-2025), next to the same model with
the starters blanked (so the starter's worth is visible). No F5 moneyline is in the free data: the F5 market is
graded against the base rate only, and its price test reads PENDING (HR35, HR59). Nothing changes a stake or a bar.

  python backtest/mlb_pitcher_backtest.py      writes backtest/MLB_PITCHER_STUDY.md
"""
from __future__ import annotations

import itertools
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import baseball_backtest as bb  # noqa: E402
from backtest import results_walkforward as wf  # noqa: E402
from backtest.tennis_backtest import blend  # noqa: E402
from engine.mlb_pitcher import F5, Ratings  # noqa: E402

OUT = ROOT / "backtest" / "MLB_PITCHER_STUDY.md"
SHRINK = (4.0, 8.0, 16.0)
DECAY = (0.95, 0.98, 1.0)
MKT_W = (0.0, 0.25, 0.5)


def extras(event: dict) -> dict:
    """Starter ids and first-five-innings runs of one finished ESPN event (None where absent)."""
    c = (event.get("competitions") or [{}])[0]
    out = {}
    for t in c.get("competitors") or []:
        side = "b" if t.get("homeAway") == "home" else "a"
        pr = (t.get("probables") or [{}])[0] if t.get("probables") else {}
        out["sp" + side] = str(pr.get("playerId")) if pr.get("playerId") else None
        ls = [x.get("value") for x in t.get("linescores") or []]
        out["f5" + side] = float(sum(ls[:F5])) if len(ls) >= F5 else None
    return out


def attach(games: list[dict], get=None) -> int:
    """Add spa/spb/f5a/f5b to each priced game from the (cached) scoreboards. Returns games lacking a starter."""
    by_day: dict[str, dict] = {}
    for g in games:
        by_day.setdefault(g["key"][:10], {})[g["id"]] = g
    for day, ids in by_day.items():
        # ESPN dates are UTC; a late game can sit on the previous scoreboard day
        for d in (day, (date.fromisoformat(day) - timedelta(days=1)).isoformat()):
            ds = d.replace("-", "")
            board = bb.cached(f"sb_{ds}.json", bb.BOARD.format(d=ds), get)
            for e in (board or {}).get("events") or []:
                g = ids.get(str(e.get("id")))
                if g is not None and "spa" not in g:
                    g.update(extras(e))
    miss = 0
    for g in games:
        for k in ("spa", "spb", "f5a", "f5b"):
            g.setdefault(k, None)
        miss += g["spa"] is None or g["spb"] is None
    return miss


def replay(games: list[dict], shrink: float, decay: float, use_sp: bool = True) -> list[dict | None]:
    r = Ratings(shrink, decay)
    out = []
    for g in games:
        gg = g if use_sp else {**g, "spa": None, "spb": None}
        out.append(r.predict(gg))
        r.update(gg)
    return out


def evaluate(games, preds, seasons, key, mw=0.0) -> dict:
    rows, mrows = [], []
    for g, p in zip(games, preds, strict=True):
        if p is None or not (seasons[0] <= g["season"] <= seasons[1]):
            continue
        rows.append((blend(p[key], g["mkt"], mw), g["y"]))
        mrows.append((g["mkt"], g["y"]))
    r = wf.score(rows)
    m = wf.score(mrows)
    r["mkt_ll"], r["mkt_brier"] = m["ll"], m["brier"]
    return r


def f5_eval(games, preds, seasons) -> dict:
    """F5 'visitor leads after 5' (ties dropped) vs the model chance renormalised without the tie; and the base rate."""
    rows = []
    for g, p in zip(games, preds, strict=True):
        if p is None or g["f5a"] is None or g["f5b"] is None or g["f5a"] == g["f5b"]:
            continue
        if not (seasons[0] <= g["season"] <= seasons[1]):
            continue
        y = 1.0 if g["f5a"] > g["f5b"] else 0.0
        pa = (p["f5_a"] - 0.5 * p["f5_tie"]) / (1 - p["f5_tie"])
        rows.append((min(max(pa, 0.01), 0.99), y))
    if not rows:
        return {"model": {"n": 0}, "base": None}
    rate = sum(y for _, y in rows) / len(rows)
    return {"model": wf.score(rows), "base": wf.score([(rate, y) for _, y in rows])}


def run(games: list[dict], notes=None, miss: int = 0) -> str:
    last = max(g["season"] for g in games)
    test = (bb.TUNE[1] + 1, last)
    grid = list(itertools.product(SHRINK, DECAY))
    cache = {c: replay(games, *c) for c in grid}
    blank = {c: replay(games, *c, use_sp=False) for c in grid}
    combos = [c + (w,) for c in grid for w in MKT_W]
    tuned = {c: evaluate(games, cache[c[:2]], bb.TUNE, "full_a", c[2]) for c in combos}
    ok = {c: t for c, t in tuned.items() if t["n"] >= 1000}
    best_alone = min((c for c in ok if c[2] == 0.0), key=lambda c: ok[c]["ll"], default=None)
    best = min(ok, key=lambda c: ok[c]["ll"], default=None)
    tries = len(combos)

    def line(name, r):
        if not r or not r["n"]:
            return f"| {name} | 0 | PENDING | PENDING | PENDING | PENDING |"
        return f"| {name} | {r['n']} | {r['brier']:.4f} | {r['ll']:.4f} | {r['mkt_brier']:.4f} | {r['mkt_ll']:.4f} |"

    def lab(c):
        s = f"shrink {c[0]:g}, decay {c[1]:g}"
        return s + (f", market weight {c[2]:.0%}" if len(c) > 2 else "")
    L = ["# MLB starting-pitcher model, shadow backtest", "",
         f"Made {datetime.now(UTC):%Y-%m-%d %H:%M UTC} by `backtest/mlb_pitcher_backtest.py` (framework#382). "
         f"{len(games)} priced MLB games {games[0]['season']}-{last} (cached ESPN scoreboard: starters + first-five "
         f"runs; closing moneyline). Tries counted: **{tries}**. Chosen on {bb.TUNE[0]}-{bb.TUNE[1]}, reported on "
         f"**{test[0]}-{test[1]} only**. {miss} games had no starter on the scoreboard (league-average starter used, "
         "flagged, never invented).", ""]
    if notes:
        L += ["Not loaded: " + "; ".join(notes), ""]
    L += ["## Full game moneyline vs the de-vigged close (held-out)", "",
          "| Rule | Games | Brier | Log loss | Close Brier | Close log loss |", "|---|---|---|---|---|---|"]
    res = {}
    if best_alone:
        res["alone"] = evaluate(games, cache[best_alone[:2]], test, "full_a")
        res["nosp"] = evaluate(games, blank[best_alone[:2]], test, "full_a")
        L.append(line(f"Starter model alone: {lab(best_alone)}", res["alone"]))
        L.append(line("Same model, starters blanked (team offence only)", res["nosp"]))
    if best:
        res["best"] = evaluate(games, cache[best[:2]], test, "full_a", best[2])
        L.append(line(f"Best blended with the close: {lab(best)}", res["best"]))
    L += ["", "## First 5 innings (no F5 price in the free data)", ""]
    if best_alone:
        f = f5_eval(games, cache[best_alone[:2]], test)
        if f["model"]["n"]:
            L += [f"{f['model']['n']} held-out games, ties after 5 dropped. Log loss: starter model "
                  f"**{f['model']['ll']:.4f}** vs the base rate {f['base']['ll']:.4f} (Brier {f['model']['brier']:.4f} "
                  f"vs {f['base']['brier']:.4f}). F5 price test: PENDING (no F5 moneyline recorded yet; shadow it from "
                  "Opening Day against the exchange)."]
    L += ["", "## Reading", ""]
    if res.get("alone") and res["alone"]["n"]:
        a, ns = res["alone"], res["nosp"]
        L.append(f"- Starters change log loss by {a['ll'] - ns['ll']:+.4f} vs team offence alone "
                 f"({'help' if a['ll'] < ns['ll'] else 'no help'}); model alone {a['ll']:.4f} vs close {a['mkt_ll']:.4f}: "
                 + ("beats the price." if a["ll"] < a["mkt_ll"] else "the close is still the better chance."))
    if res.get("best") and res["best"]["n"]:
        b = res["best"]
        L.append(f"- Blended best {b['ll']:.4f} vs close {b['mkt_ll']:.4f}: "
                 + ("information beyond the price, held-out." if b["ll"] < b["mkt_ll"] - 0.0005 else
                    "no information beyond the price: price baseball off the exchange."))
    L += [f"- {tries} tries; held-out lines only. Starter rating = opponents' first-5 runs per start (a proxy, not "
          "FIP/xFIP); batter-hand splits and bullpen workload need data not in the free cache (PENDING).",
          "- Record only: no stake, bar, threshold or live switch changes."]
    return "\n".join(L) + "\n"


def main() -> int:
    games, notes = bb.load()
    if len(games) < 5000:
        print(f"only {len(games)} games read: NO DATA - PENDING ({'; '.join(notes)})")
        return 1
    miss = attach(games)
    text = run(games, notes, miss)
    OUT.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
