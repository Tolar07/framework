"""
VOLLEYBALL SECONDARY-MARKET VALUE WATCH (framework #569, step 4: volleyball). RECORD ONLY.

Same question as backtest/nba_secondary_value.py, hockey_ and tennis_secondary_value.py, for the matches on the
multi-sport board (output/multisport/volleyball/ms_<day>.json: every SportyBet side at its first and last look, plus
the graded set scores). The model is engine/volleyball_events.py: the board's FIRST-look two-way match price (margin
removed) becomes a best-of-5 set-score ladder (set-momentum rule, re-implemented from the idea), which prices the
set handicap (market 188). Total points (market 238) is priced from the ladder's chance of 3 / 4 / 5 sets mixed with
the point totals of EARLIER matches on the board (walk-forward: a match never sees itself or later matches); it reads
PENDING until each set count has MIN_PER_COUNT earlier matches. The match winner is the primary market and equals the
board by construction, so it is left out. Point handicap (237) has no model yet: PENDING, never invented (HR35/HR59).

For each side priced 1.60-2.60 at the first look: per market family, the bets with model edge >= 5% and >= 10%, how
often they landed vs the model's chance, return per unit, and CLV (first-look price x closing fair chance, margin
removed, - 1). Never picks, stakes or blocks; nothing reads this. A family that stays positive over MIN_GRADED graded
bets goes to the Architect (paper first); fewer reads COLLECTING. Best-of-3 matches and unfinished sets are left out.

    python backtest/volleyball_secondary_value.py   -> backtest/VOLLEYBALL_SECONDARY_VALUE.md
"""
from __future__ import annotations

import json
import re
import sys
from bisect import insort
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backtest"))

import nba_secondary_value as nsv  # noqa: E402  (same stats, status and cell format)
from engine import volleyball_events as ve  # noqa: E402

BOARD = ROOT / "output" / "multisport" / "volleyball"
OUT = ROOT / "backtest" / "VOLLEYBALL_SECONDARY_VALUE.md"
PRICE_LO, PRICE_HI = nsv.PRICE_LO, nsv.PRICE_HI
EDGE_LEVELS = nsv.EDGE_LEVELS
MAX_EDGE = 0.30                 # above this the gap is a stale price or a model miss, not value
MOMENTUM = 0.10                 # set-momentum m, the middle value the engine's own study scans (0.0-0.20)


def valid_sets(periods) -> bool:
    """Best-of-5 only: a side reached 3 sets, each set finished (25 / 15 to win by 2)."""
    if not periods or not 3 <= len(periods) <= 5:
        return False
    for i, (a, b) in enumerate(periods):
        target = 15 if i == 4 else 25
        hi, lo = max(a, b), min(a, b)
        if hi < target or hi - lo < 2 or (hi > target and hi - lo != 2):
            return False
    won = sum(1 for a, b in periods if a > b)
    return 3 in (won, len(periods) - won)


def _group_fair(sides: dict, key: str) -> float | None:
    """Closing chance of one side with the margin removed within its market + line, from the last looks."""
    grp = [k for k in sides if k.split("|")[:2] == key.split("|")[:2] and (sides[k].get("last") or {}).get("price")]
    prices = {k: sides[k]["last"]["price"] for k in grp}
    if key not in prices or len(prices) < 2 or any(p <= 1 for p in prices.values()):
        return None
    return (1 / prices[key]) / sum(1 / p for p in prices.values())


def model_for(game: dict, hist: dict | None) -> dict | None:
    """Ladder numbers from the first-look winner price; None (PENDING) when there is no two-way price."""
    sides = game.get("sides") or {}

    def first(k):
        return ((sides.get(k) or {}).get("first") or {}).get("price")

    ph, pa = first("volleyball:186||Home"), first("volleyball:186||Away")
    if not ph or not pa or ph <= 1 or pa <= 1:
        return None
    p = (1 / ph) / (1 / ph + 1 / pa)
    return ve.predict(p, MOMENTUM, hist)


def _line(spec: str, name: str) -> float | None:
    m = re.match(rf"{name}=([-+]?[\d.]+)$", spec)
    return float(m.group(1)) if m else None


def _price(key: str, mod: dict, res: dict, hist: dict | None) -> tuple[str, float, bool] | None:
    """(family, model chance, landed) for one side, or None when the model/result cannot settle it."""
    per = res["periods"]
    mid, _, rest = key.partition("|")
    spec, _, desc = rest.partition("|")
    side_home = desc.startswith("Home")
    hs = sum(1 for a, b in per if a > b)
    if mid == "volleyball:188":                                    # set handicap (home line in the spec)
        h = _line(spec, "hcp")
        if h is None:
            return None
        h = h if side_home else -h
        p = 0.0
        for score, pr in mod["score"].items():
            xa, xb = (int(t) for t in score.split("-"))
            p += pr if ((xa - xb) if side_home else (xb - xa)) + h > 0 else 0.0
        margin = (2 * hs - len(per)) * (1 if side_home else -1)
        return "Set handicap", p, margin + h > 0
    if mid == "volleyball:238":                                    # total points
        ln = _line(spec, "total")
        if ln is None or not hist or not all(len(hist.get(n, [])) >= ve.MIN_PER_COUNT for n in (3, 4, 5)):
            return None
        sc = mod["score"]
        n_sets = {3: sc["3-0"] + sc["0-3"], 4: sc["3-1"] + sc["1-3"], 5: sc["3-2"] + sc["2-3"]}
        po = sum(n_sets[n] * ve.over(hist[n], ln) for n in (3, 4, 5))
        over = desc.startswith("Over")
        tot = sum(a + b for a, b in per)
        return "Total points", po if over else 1 - po, (tot > ln) == over
    return None


def bets(game: dict, hist: dict | None = None) -> list[dict]:
    """Every graded, model-priced secondary side of one match's first look inside the price band."""
    res = game.get("result") or {}
    if not valid_sets(res.get("periods")):
        return []
    mod = model_for(game, hist)
    if not mod:
        return []
    out = []
    for key, s in (game.get("sides") or {}).items():
        price = (s.get("first") or {}).get("price")
        if price is None or not (PRICE_LO <= price <= PRICE_HI):
            continue
        r = _price(key, mod, res, hist)
        if r is None:
            continue
        fam, p, won = r
        cf = _group_fair(game["sides"], key)
        out.append({"family": fam, "price": price, "p": p, "edge": p * price - 1, "won": int(won),
                    "clv": price * cf - 1 if cf else None})
    return out


def report(all_bets: list[dict], n_games: int) -> str:
    out = ["# VOLLEYBALL SECONDARY-MARKET VALUE WATCH (framework #569, volleyball)", "",
           f"Record only. Each best-of-5 match's first SportyBet look; every side priced {PRICE_LO:.2f}-{PRICE_HI:.2f} "
           f"that the set-ladder model (engine/volleyball_events.py, fitted to the same first-look match price, "
           f"momentum {MOMENTUM}) prices, graded from the recorded set scores. Cells: bets · landed vs model chance · "
           f"return per unit at the first-look price. Edge = model chance x price - 1, above {MAX_EDGE:.0%} dropped. "
           f"CLV = first-look price x closing fair chance - 1. Several lines per match count (a market study, not "
           f"the board). Total points uses only EARLIER matches' point totals (walk-forward) and is PENDING until "
           f"each of 3 / 4 / 5 sets has {ve.MIN_PER_COUNT} of them. Point handicap is PENDING: no model. Written by "
           f"`backtest/volleyball_secondary_value.py`.", "",
           f"Matches graded: {n_games}", ""]
    fams: dict[str, list[dict]] = defaultdict(list)
    for b in all_bets:
        if b["edge"] <= MAX_EDGE:
            fams[b["family"]].append(b)
    if not fams:
        return "\n".join(out + ["NO DATA — PENDING (no graded match with a model price yet)"]) + "\n"
    out += ["| Market family | edge 5%+ | edge 10%+ | CLV (5%+) | status |", "|---|---|---|---:|---|"]
    rows = []
    for fam, rs in fams.items():
        s5 = nsv._stats([r for r in rs if r["edge"] >= EDGE_LEVELS[0]])
        s10 = nsv._stats([r for r in rs if r["edge"] >= EDGE_LEVELS[1]])
        rows.append((s5.get("n", 0), fam, s5, s10))
    for _n, fam, s5, s10 in sorted(rows, key=lambda t: -t[0]):
        clv = f"{s5['clv']:+.1%}" if s5.get("clv") is not None else "PENDING"
        out.append(f"| {fam} | {nsv._cell(s5)} | {nsv._cell(s10)} | {clv} | {nsv.status(s5)} |")
    return "\n".join(out + [""]) + "\n"


def build(docs: list[tuple[str, dict]]) -> str:
    """Walk-forward over days in order: a match is priced with point totals of strictly earlier days only."""
    all_bets, graded, seen = [], 0, set()
    hist: dict[int, list[int]] = {3: [], 4: [], 5: []}
    for _day, doc in sorted(docs, key=lambda t: t[0]):
        day_games, day_pts = [], []
        for g in (doc.get("games") or {}).values():
            ident = (g.get("home"), g.get("away"), g.get("ko"))
            if ident in seen or not g.get("result"):
                continue
            seen.add(ident)
            day_games.append(g)
        for g in day_games:
            b = bets(g, hist)
            if b:
                graded += 1
                all_bets += b
            per = g["result"].get("periods")
            if valid_sets(per):
                day_pts.append((len(per), sum(a + c for a, c in per)))
        for n, t in day_pts:                                        # visible from the NEXT day on
            insort(hist[n], t)
    return report(all_bets, graded)


def load_all() -> list[tuple[str, dict]]:
    docs = []
    for f in sorted(BOARD.glob("ms_*.json")):
        try:
            docs.append((f.stem[3:], json.loads(f.read_text(encoding="utf-8"))))
        except (OSError, ValueError):
            continue
    return docs


def main() -> int:
    docs = load_all()
    OUT.write_text(build(docs), encoding="utf-8")
    print(f"Volleyball secondary value: {len(docs)} days -> {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
