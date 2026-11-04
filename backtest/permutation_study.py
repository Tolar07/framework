"""
PERMUTATION TEST OF THE EDGE RULE (issue #297, the Architect 2026-11-04). RECORDED ONLY.

Could the rule's record have come from noise? Every model-rated, graded fixture keeps its model chances and its
SportyBet FIRST prices (the price on offer before the board, not the close); only the results are redrawn,
1,000 times. The rule is re-applied to each redraw:

    fixed      back every side whose model chance beats 1/price by EDGE (5 points: the board's edge rule)
    tuned      the same, at whichever threshold in GRID did best on that data - so the search the threshold
               came from is counted too (neurotrader https://www.youtube.com/watch?v=NLBXgSmRBgU @ 04:18-13:32;
               Lopez de Prado on backtest overfitting https://www.youtube.com/watch?v=sGcov6tOQ7k @ 09:52-13:04)

The null is "the model knows nothing the market does not": each redraw samples every fixture's result from
SportyBet's own margin-removed chances (1X2, over/under 2.5, BTTS each drawn from its market). The issue's plain
shuffle within league x season was run first and is NOT used: moving results between fixtures also breaks the
link between price and result (favourites stop winning more often), so the shuffled worlds pay long shots far
too often and every rule looks worse than noise (p 0.99 on 879 fixtures, 2026-11-04). shuffled() is kept as the
league x season block sampler for the unit test only.

p = share of redraws at least as profitable as the real results (flat stakes). A small p says the rule finds
something noise does not; p near 0.5 says its record is what luck alone would give. Sides tested: home / draw /
away, over / under 2.5, BTTS yes / no. Nothing here changes a pick, stake, threshold or rule.

    python backtest/permutation_study.py     -> backtest/PERMUTATION_STUDY.md + memory/permutation_study.json
"""
from __future__ import annotations

import json
import random
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from data import fixture_features as ff  # noqa: E402

OUT_MD = ROOT / "backtest" / "PERMUTATION_STUDY.md"
OUT_JSON = ROOT / "memory" / "permutation_study.json"
EDGE = 0.05
GRID = (0.02, 0.03, 0.05, 0.08, 0.10)
SHUFFLES = 1000
SEED = 20261104
MIN_FIXTURES = 100
SIDES = ("home", "draw", "away", "over 2.5", "under 2.5", "btts yes", "btts no")


def outcomes(ft: str) -> dict[str, int] | None:
    try:
        h, a = (int(x) for x in ft.split("-"))
    except (AttributeError, ValueError):
        return None
    o = int(h + a > 2.5)
    b = int(h > 0 and a > 0)
    return {"home": int(h > a), "draw": int(h == a), "away": int(h < a),
            "over 2.5": o, "under 2.5": 1 - o, "btts yes": b, "btts no": 1 - b}


def chances(p: list[float]) -> dict[str, float]:
    """The ledger's model chances [home, draw, away, o1.5, o2.5, o3.5, btts] by side."""
    return {"home": p[0], "draw": p[1], "away": p[2], "over 2.5": p[4], "under 2.5": 1 - p[4],
            "btts yes": p[6], "btts no": 1 - p[6]}


def prices(urow: dict | None) -> dict[str, float]:
    q = ((urow or {}).get("first") or {}).get("p") or {}
    out: dict[str, float] = {}
    for key, names in (("1x2", ("home", "draw", "away")), ("ou2.5", ("over 2.5", "under 2.5")),
                       ("btts", ("btts yes", "btts no"))):
        xs = q.get(key) or []
        if len(xs) == len(names):
            for n, x in zip(names, xs, strict=True):
                if isinstance(x, (int, float)) and x > 1:
                    out[n] = float(x)
    return out


def collect(ledger_dir: Path = ff.LEDGER_DIR, urows: list[dict] | None = None) -> list[dict]:
    """One record per graded model-rated fixture with first prices: stratum, chances, prices, results."""
    if urows is None:
        from engine import universe as uv
        urows = uv.load_graded()
    uidx = ff.universe_index(urows)
    out = []
    for path in sorted(ledger_dir.glob("picks_*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        day = doc.get("date") or path.stem[6:]
        for fx in doc.get("rated") or []:
            y = outcomes(fx.get("ft"))
            p = fx.get("p")
            if fx.get("src") != "model" or y is None or not isinstance(p, list) or len(p) < 7:
                continue
            px = prices(ff.find_universe(fx, day, uidx))
            if px:
                out.append({"stratum": f"{fx.get('league') or '?'}|{ff.season_of(day)}",
                            "p": chances(p), "px": px, "y": y})
    return out


def flat_return(recs: list[dict], ys: list[dict], edge: float) -> tuple[float, int]:
    """(mean flat return per bet, bets) of backing every side whose chance beats 1/price by `edge`."""
    tot, n = 0.0, 0
    for r, y in zip(recs, ys, strict=True):
        for side, price in r["px"].items():
            if r["p"][side] - 1 / price >= edge:
                tot += (price - 1) if y[side] else -1.0
                n += 1
    return (tot / n if n else 0.0), n


def tuned_return(recs: list[dict], ys: list[dict]) -> tuple[float, float]:
    best = max(GRID, key=lambda e: flat_return(recs, ys, e)[0])
    return flat_return(recs, ys, best)[0], best


def shuffled(recs: list[dict], rng: random.Random) -> list[dict]:
    """The results reassigned at random among fixtures of the same league x season."""
    by: dict[str, list[int]] = defaultdict(list)
    for i, r in enumerate(recs):
        by[r["stratum"]].append(i)
    ys = [r["y"] for r in recs]
    for idx in by.values():
        perm = idx[:]
        rng.shuffle(perm)
        for i, j in zip(idx, perm, strict=True):
            ys[i] = recs[j]["y"]
    return ys


def _fair(xs: list[float]) -> list[float]:
    inv = [1 / x for x in xs]
    t = sum(inv)
    return [v / t for v in inv]


def market_draw(recs: list[dict], rng: random.Random) -> list[dict]:
    """Results drawn from the market's margin-removed chances: the world where the model adds nothing."""
    ys = []
    for r in recs:
        px, y = r["px"], dict(r["y"])
        if all(k in px for k in ("home", "draw", "away")):
            u, f = rng.random(), _fair([px["home"], px["draw"], px["away"]])
            res = "home" if u < f[0] else ("draw" if u < f[0] + f[1] else "away")
            y.update(home=int(res == "home"), draw=int(res == "draw"), away=int(res == "away"))
        for a, b in (("over 2.5", "under 2.5"), ("btts yes", "btts no")):
            if a in px and b in px:
                hit = int(rng.random() < _fair([px[a], px[b]])[0])
                y.update({a: hit, b: 1 - hit})
        ys.append(y)
    return ys


def test(recs: list[dict], shuffles: int = SHUFFLES, seed: int = SEED) -> dict:
    if len(recs) < MIN_FIXTURES:
        return {"fixtures": len(recs), "verdict": "PENDING", "why": f"fewer than {MIN_FIXTURES} fixtures"}
    rng = random.Random(seed)  # noqa: S311 — seeded study, not security
    real_ys = [r["y"] for r in recs]
    real, bets = flat_return(recs, real_ys, EDGE)
    real_t, best = tuned_return(recs, real_ys)
    ge = ge_t = 0
    for _ in range(shuffles):
        ys = market_draw(recs, rng)
        ge += flat_return(recs, ys, EDGE)[0] >= real
        ge_t += tuned_return(recs, ys)[0] >= real_t
    p, p_t = (ge + 1) / (shuffles + 1), (ge_t + 1) / (shuffles + 1)
    verdict = "BEATS NOISE" if p < 0.05 else ("WEAK" if p < 0.20 else "NO BETTER THAN NOISE")
    return {"fixtures": len(recs), "strata": len({r["stratum"] for r in recs}), "shuffles": shuffles,
            "fixed": {"edge": EDGE, "bets": bets, "flat_return": round(real, 4), "p": round(p, 4)},
            "tuned": {"best_edge": best, "flat_return": round(real_t, 4), "p": round(p_t, 4)},
            "verdict": verdict}


def report(rec: dict) -> str:
    L = ["# PERMUTATION TEST — could the edge rule's record come from noise? (issue #297)", "",
         f"Built {rec['built_at']}. Recorded only: nothing here changes a pick, stake or rule.", ""]
    t = rec["test"]
    if t["verdict"] == "PENDING":
        return "\n".join(L + [f"PENDING — {t['why']} ({t['fixtures']} so far)."]) + "\n"
    f, u = t["fixed"], t["tuned"]
    L += [f"{t['fixtures']} graded fixtures in {t['strata']} league-seasons, SportyBet first prices, "
          f"results redrawn {t['shuffles']} times from SportyBet's own margin-removed chances.", "",
          "| Rule | Bets | Flat return | p (share of redraws as good) |", "|---|---|---|---|",
          f"| {f['edge']:.0%} edge (fixed) | {f['bets']} | {f['flat_return']:+.1%} | {f['p']:.3f} |",
          f"| best of {', '.join(f'{g:.0%}' for g in GRID)} (tuned: {u['best_edge']:.0%}) | — | "
          f"{u['flat_return']:+.1%} | {u['p']:.3f} |", "",
          f"**Verdict: {t['verdict']}.** p under 0.05 = the rule finds something the market's own prices do not; "
          "near 0.5 = its record is what luck gives at those prices."]
    return "\n".join(L) + "\n"


def summary_line(rec: dict) -> str:
    t = rec["test"]
    if t["verdict"] == "PENDING":
        return f"permutation test: PENDING ({t['fixtures']} fixtures)"
    return (f"permutation test (5-pt rule): {t['fixed']['bets']} bets, flat {t['fixed']['flat_return']:+.1%}, "
            f"p {t['fixed']['p']:.3f} (tuned p {t['tuned']['p']:.3f}) · {t['verdict']}")


def main() -> int:
    rec = {"built_at": datetime.now(UTC).isoformat(timespec="seconds"), "recorded_only": True, "issue": 297,
           "test": test(collect())}
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(rec, indent=1), encoding="utf-8")
    OUT_MD.write_text(report(rec), encoding="utf-8")
    print(summary_line(rec))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
