"""
TENNIS SECONDARY-MARKET VALUE WATCH (framework #569, step 3: tennis). RECORD ONLY.

Same question as backtest/nba_secondary_value.py and hockey_secondary_value.py, for the singles matches on the
multi-sport board (output/multisport/tennis/ms_<day>.json: every SportyBet side at its first and last look, plus the
graded set scores). The model is engine/tennis_events.py, the point-level serve/return model, fitted so that its match
win chance equals the board's FIRST-look two-way price (margin removed). It then prices the secondary markets:
set 1 and set 2 winner, set handicap +-1.5 and total games. The match winner itself is the primary market and equals
the board by construction, so it is not a "secondary" and is left out.

For each side priced 1.60-2.60 at the first look: per market family, the bets with model edge >= 5% and >= 10%, how
often they landed vs the model's chance, return per unit, and CLV (first-look price x closing fair chance, margin
removed, - 1). Never picks, stakes or blocks; nothing reads this. A family that stays positive over MIN_GRADED graded
bets goes to the Architect (paper first); fewer reads COLLECTING. Doubles, retirements and unfinished sets are left
out (HR35); sets 3+ (only played when the match goes the distance), tie-break yes/no, set score and player aces /
double faults are PENDING: no board price or no serve data. Nothing is invented (HR59).

    python backtest/tennis_secondary_value.py   -> backtest/TENNIS_SECONDARY_VALUE.md
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backtest"))

import nba_secondary_value as nsv  # noqa: E402  (same stats, status and cell format)
from engine import format_prob as fp  # noqa: E402
from engine import tennis_events as te  # noqa: E402

BOARD = ROOT / "output" / "multisport" / "tennis"
OUT = ROOT / "backtest" / "TENNIS_SECONDARY_VALUE.md"
PRICE_LO, PRICE_HI = nsv.PRICE_LO, nsv.PRICE_HI
EDGE_LEVELS = nsv.EDGE_LEVELS
MAX_EDGE = 0.30                 # above this the gap is a stale price or a model miss, not value


def valid_sets(periods) -> bool:
    """True when every set is a finished set (no retirement mid-set). Singles only: no match tie-break scores."""
    if not periods or len(periods) < 2:
        return False
    for a, b in periods:
        hi, lo = max(a, b), min(a, b)
        if not ((hi == 6 and lo <= 4) or (hi == 7 and lo in (5, 6)) or (hi > 7 and hi - lo == 2)):
            return False
    return True


def _group_fair(sides: dict, key: str) -> float | None:
    """Closing chance of one side with the margin removed within its market + line, from the last looks."""
    grp = [k for k in sides if k.split("|")[:2] == key.split("|")[:2] and (sides[k].get("last") or {}).get("price")]
    prices = {k: sides[k]["last"]["price"] for k in grp}
    if key not in prices or len(prices) < 2 or any(p <= 1 for p in prices.values()):
        return None
    return (1 / prices[key]) / sum(1 / p for p in prices.values())


def model_for(game: dict, serve: dict | None = None) -> dict | None:
    """{'bo', 'sets', 'games', 'set_win'} from the first-look winner price; None (PENDING) when not priceable."""
    sides = game.get("sides") or {}

    def first(k):
        return ((sides.get(k) or {}).get("first") or {}).get("price")

    p_home = te.devig(first("tennis:186||Home"), first("tennis:186||Away"))
    comp, home = game.get("comp") or "", game.get("home") or ""
    if p_home is None or te.is_doubles(comp, home):
        return None
    bo, tour = te.best_of(comp), te.tour_of(comp)
    s = (serve or te.SERVE).get(tour, fp.TOUR_SERVE)
    d = fp.tennis_edge(p_home, bo, s)
    if d is None:
        return None
    m = te.match_dist(d, bo, s)
    sa, sb = min(1.0, max(0.0, s + d)), min(1.0, max(0.0, s - d))
    set_win = sum(p for ga, gb, p in te._set_dist(sa, sb) if ga > gb)
    return {"bo": bo, "sets": m["sets"], "games": m["games"], "set_win": set_win}


def _price(spec_key: str, desc: str, mod: dict, res: dict) -> tuple[str, float, bool] | None:
    """(family, model chance, landed) for one side, or None when the model/result cannot settle it."""
    per = res["periods"]
    mid, _, rest = spec_key.partition("|")
    spec = rest.partition("|")[0]
    side_home = desc.startswith("Home")
    if mid == "tennis:202":
        m = re.match(r"setnr=(\d)$", spec)
        n = int(m.group(1)) if m else 0
        if n not in (1, 2) or len(per) < n:
            return None
        a, b = per[n - 1]
        p = mod["set_win"] if side_home else 1 - mod["set_win"]
        return f"Set {n} winner", p, (a > b) == side_home
    if mid == "tennis:188":
        m = re.match(r"hcp=([-\d.]+)$", spec)
        if not m:
            return None
        # The spec's handicap belongs to the HOME side; the away side carries the opposite sign.
        h = float(m.group(1)) if side_home else -float(m.group(1))
        hs = sum(1 for a, b in per if a > b)
        margin = (2 * hs - len(per)) * (1 if side_home else -1)
        p = 0.0
        for score, pr in mod["sets"].items():
            xa, xb = (int(t) for t in score.split("-"))
            p += pr if ((xa - xb) if side_home else (xb - xa)) + h > 0 else 0.0
        return "Set handicap +-1.5", p, margin + h > 0
    if mid == "tennis:189":
        m = re.match(r"total=([\d.]+)$", spec)
        if not m:
            return None
        ln = float(m.group(1))
        tot = sum(a + b for a, b in per)
        over = desc.startswith("Over")
        po = te.over_prob(mod["games"], ln)
        return "Total games", po if over else 1 - po, (tot > ln) == over
    return None


def bets(game: dict, serve: dict | None = None) -> list[dict]:
    """Every graded, model-priced secondary side of one match's first look inside the price band."""
    res = game.get("result") or {}
    per = res.get("periods")
    if not res.get("winner") or not valid_sets(per):
        return []
    need = (te.best_of(game.get("comp") or "") // 2) + 1
    won_sets = sum(1 for a, b in per if a > b)
    if need not in (won_sets, len(per) - won_sets):          # nobody reached the sets needed: retirement
        return []
    mod = model_for(game, serve)
    if not mod:
        return []
    out = []
    for key, s in (game.get("sides") or {}).items():
        first = s.get("first") or {}
        price = first.get("price")
        if price is None or not (PRICE_LO <= price <= PRICE_HI):
            continue
        r = _price(key, key.split("|")[-1], mod, res)
        if r is None:
            continue
        fam, p, won = r
        cf = _group_fair(game["sides"], key)
        out.append({"family": fam, "price": price, "p": p, "edge": p * price - 1, "won": int(won),
                    "clv": price * cf - 1 if cf else None})
    return out


def report(all_bets: list[dict], n_games: int) -> str:
    out = ["# TENNIS SECONDARY-MARKET VALUE WATCH (framework #569, tennis)", "",
           f"Record only. Each singles match's first SportyBet look; every side priced {PRICE_LO:.2f}-{PRICE_HI:.2f} "
           f"that the point-level serve/return model (engine/tennis_events.py, fitted to the same first-look match "
           f"price) prices, graded from the recorded set scores. Cells: bets · landed vs model chance · return per "
           f"unit at the first-look price. Edge = model chance x price - 1, above {MAX_EDGE:.0%} dropped. CLV = "
           f"first-look price x closing fair chance - 1. Several lines per match count (a market study, not the "
           f"board). Written by `backtest/tennis_secondary_value.py`. PENDING: set 3+ winner, set score, tie-break "
           f"yes/no (no board price), aces and double faults (no free serve data), doubles.", "",
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


def build(docs: list[tuple[str, dict]], serve: dict | None = None) -> str:
    all_bets, graded, seen = [], 0, set()
    for _day, doc in docs:
        for g in (doc.get("games") or {}).values():
            ident = (g.get("home"), g.get("away"), g.get("ko"))
            if ident in seen or not g.get("result"):
                continue
            seen.add(ident)
            b = bets(g, serve)
            if b:
                graded += 1
                all_bets += b
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
    from monitor.tennis_events_run import study
    docs = load_all()
    OUT.write_text(build(docs, study()[0] or None), encoding="utf-8")
    print(f"Tennis secondary value: {len(docs)} days -> {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
