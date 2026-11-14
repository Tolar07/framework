"""
RUGBY SECONDARY-MARKET VALUE WATCH (framework #569, step 4: rugby). RECORD ONLY.

Same question as backtest/nba_secondary_value.py, volleyball_ and baseball_secondary_value.py, for the rugby matches on
the multi-sport board (output/multisport/rugby/ms_<day>.json: every SportyBet side at its first and last look, plus the
graded final score). The model: the expected total points is the mean total of EARLIER matches on the board
(walk-forward: a match never sees itself or later days; PENDING until MIN_HIST matches); the expected margin comes from
the board's FIRST-look two-way winner price (market 11, margin removed) as a normal margin of standard deviation
MARGIN_SD. That prices total points (market 18, negative binomial) and the points handicap (market 16, normal margin
with the half-point line). The winner is the primary market and equals the board by construction, so it is left out.
The total's mean is a league average, not a per-game number: a crude first model, and the report says what it earns.

For each side priced 1.60-2.60 at the first look: per market family, the bets with model edge >= 5% and >= 10%, how
often they landed vs the model's chance, return per unit, and CLV (first-look price x closing fair chance, margin
removed, - 1). Never picks, stakes or blocks; nothing reads this. A family that stays positive over MIN_GRADED graded
bets goes to the Architect (paper first); fewer reads COLLECTING. Missing data reads PENDING (HR35).

    python backtest/rugby_secondary_value.py   -> backtest/RUGBY_SECONDARY_VALUE.md
"""
from __future__ import annotations

import json
import re
from statistics import NormalDist
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backtest"))

import nba_secondary_value as nsv  # noqa: E402  (same stats, status and cell format)
from engine import event_model as em  # noqa: E402

BOARD = ROOT / "output" / "multisport" / "rugby"
OUT = ROOT / "backtest" / "RUGBY_SECONDARY_VALUE.md"
PRICE_LO, PRICE_HI = nsv.PRICE_LO, nsv.PRICE_HI
EDGE_LEVELS = nsv.EDGE_LEVELS
MAX_EDGE = 0.30                 # above this the gap is a stale price or a model miss, not value
MIN_HIST = 30                   # earlier graded matches before the league total is trusted
DISP_TOTAL = 12.0               # negative-binomial spread of both teams' points together (sd about 16 at a mean of 50)
MARGIN_SD = 17.0                # sd of the final margin in points


def final_ok(res) -> tuple[int, int] | None:
    f = (res or {}).get("final")
    if not f or len(f) != 2 or any(not isinstance(x, int) or x < 0 for x in f):
        return None
    return f[0], f[1]


def _group_fair(sides: dict, key: str) -> float | None:
    """Closing chance of one side with the margin removed within its market + line, from the last looks."""
    grp = [k for k in sides if k.split("|")[:2] == key.split("|")[:2] and (sides[k].get("last") or {}).get("price")]
    prices = {k: sides[k]["last"]["price"] for k in grp}
    if key not in prices or len(prices) < 2 or any(p <= 1 for p in prices.values()):
        return None
    return (1 / prices[key]) / sum(1 / p for p in prices.values())


def model_for(game: dict, hist: list[int]) -> dict | None:
    """Expected total and expected home margin; None (PENDING) without a two-way winner price or MIN_HIST matches."""
    if len(hist) < MIN_HIST:
        return None
    sides = game.get("sides") or {}

    def first(k):
        return ((sides.get(k) or {}).get("first") or {}).get("price")

    ph, pa = first("rugby:11||Home"), first("rugby:11||Away")
    if not ph or not pa or ph <= 1 or pa <= 1:
        return None
    p = (1 / ph) / (1 / ph + 1 / pa)
    return {"total": sum(hist) / len(hist), "margin": MARGIN_SD * NormalDist().inv_cdf(p)}


def _line(spec: str, name: str) -> float | None:
    m = re.match(rf"{name}=([-+]?[\d.]+)$", spec)
    return float(m.group(1)) if m else None


def _price(key: str, mod: dict, fin: tuple[int, int]) -> tuple[str, float, bool] | None:
    """(family, model chance, landed) for one side, or None when the model cannot settle it."""
    mid, _, rest = key.partition("|")
    spec, _, desc = rest.partition("|")
    home = desc.startswith("Home")
    if mid == "rugby:18":                                              # total points
        ln = _line(spec, "total")
        if ln is None or abs(ln) % 1 != 0.5:
            return None
        po = em.over(ln, mod["total"], DISP_TOTAL)
        over = desc.startswith("Over")
        return "Total points", po if over else 1 - po, (sum(fin) > ln) == over
    if mid == "rugby:16":                                              # points handicap, home line in the spec
        h = _line(spec, "hcp")
        if h is None or abs(h) % 1 != 0.5:
            return None
        h = h if home else -h
        sign = 1 if home else -1
        p = 1 - NormalDist(sign * mod["margin"], MARGIN_SD).cdf(-h)   # P(side margin + h > 0), half-point so no push
        return "Points handicap", p, sign * (fin[0] - fin[1]) + h > 0
    return None


def bets(game: dict, hist: list[int] | None = None) -> list[dict]:
    """Every graded, model-priced secondary side of one match's first look inside the price band."""
    fin = final_ok(game.get("result"))
    if not fin:
        return []
    mod = model_for(game, hist or [])
    if not mod:
        return []
    out = []
    for key, s in (game.get("sides") or {}).items():
        price = (s.get("first") or {}).get("price")
        if price is None or not (PRICE_LO <= price <= PRICE_HI):
            continue
        r = _price(key, mod, fin)
        if r is None:
            continue
        fam, p, won = r
        cf = _group_fair(game["sides"], key)
        out.append({"family": fam, "price": price, "p": p, "edge": p * price - 1, "won": int(won),
                    "clv": price * cf - 1 if cf else None})
    return out


def report(all_bets: list[dict], n_games: int, n_seen: int = 0) -> str:
    out = ["# RUGBY SECONDARY-MARKET VALUE WATCH (framework #569, rugby)", "",
           f"Record only. Each finished match's first SportyBet look; every side priced {PRICE_LO:.2f}-{PRICE_HI:.2f} "
           f"that the model prices, graded from the recorded final score. Model: expected total points = the mean total "
           f"of EARLIER matches only (walk-forward, PENDING until {MIN_HIST}); expected margin from the first-look winner price "
           f"(normal margin, sd {MARGIN_SD:.0f}); total points negative binomial. Cells: bets · landed vs model chance · "
           f"return per unit at the first-look price. Edge = model chance x price - 1, above {MAX_EDGE:.0%} dropped. "
           f"CLV = first-look price x closing fair chance - 1. Several lines per match count (a market study, not "
           f"the board). Written by `backtest/rugby_secondary_value.py`.", "",
           f"Matches with a final score: {n_seen} · priced and graded: {n_games}", ""]
    fams: dict[str, list[dict]] = defaultdict(list)
    for b in all_bets:
        if b["edge"] <= MAX_EDGE:
            fams[b["family"]].append(b)
    if not fams:
        return "\n".join(out + [f"NO DATA — PENDING (needs {MIN_HIST} earlier finished matches before a match is priced)"]) + "\n"
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
    """Walk-forward over days in order: a match is priced with the totals of strictly earlier days only."""
    all_bets, graded, seen_ids, n_seen = [], 0, set(), 0
    hist: list[int] = []
    for _day, doc in sorted(docs, key=lambda t: t[0]):
        day_games = []
        for g in (doc.get("games") or {}).values():
            ident = (g.get("home"), g.get("away"), g.get("ko"))
            if ident in seen_ids or not final_ok(g.get("result")):
                continue
            seen_ids.add(ident)
            day_games.append(g)
        n_seen += len(day_games)
        for g in day_games:
            b = bets(g, hist)
            if b:
                graded += 1
                all_bets += b
        hist += [sum(final_ok(g["result"])) for g in day_games]      # visible from the NEXT day on
    return report(all_bets, graded, n_seen)


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
    print(f"Rugby secondary value: {len(docs)} days -> {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
