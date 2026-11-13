"""
ICE HOCKEY SECONDARY-MARKET VALUE WATCH (framework #569, step 2: ice hockey). RECORD ONLY.

Same question as backtest/nba_secondary_value.py, for the NHL games engine/ice_hockey.py already records
(output/ice_hockey/ih_<day>.json: every SportyBet side at its first and last look, with the goals model's chance
and the graded result). For each side priced 1.60-2.60 at the game's FIRST look that the model prices: per market
family, the bets with model edge >= 5% and >= 10%, how often they landed vs the model's chance, return per unit,
and CLV (first-look price x closing fair chance, SportyBet's margin removed, - 1).

Never picks, stakes or blocks; nothing reads this. A family that stays positive over MIN_GRADED graded bets goes to
the Architect (paper first). Fewer bets reads COLLECTING. A side the model does not price, or a game without a
result, is left out (HR35); nothing is invented (HR59). Period totals, team totals and shots on goal are not on
SportyBet's hockey feed yet, so they are listed as PENDING, not priced.

    python backtest/hockey_secondary_value.py   -> backtest/HOCKEY_SECONDARY_VALUE.md
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backtest"))

import nba_secondary_value as nsv  # noqa: E402  (same stats, status and cell format)

OUT = ROOT / "backtest" / "HOCKEY_SECONDARY_VALUE.md"
PRICE_LO, PRICE_HI = nsv.PRICE_LO, nsv.PRICE_HI
EDGE_LEVELS = nsv.EDGE_LEVELS
MAX_EDGE = 0.30                 # above this the gap is a stale price or a model miss, not value
FAMILY = {"406": "Moneyline (incl. OT/SO)", "1": "3-way, 60 min", "16": "Handicap, 60 min",
          "410": "Puck line (incl. OT/SO)", "14": "3-way handicap", "18": "Total goals, 60 min",
          "29": "Both teams to score"}


def _group_fair(sides: dict, key: str) -> float | None:
    """Closing chance of one side with the margin removed within its market + line, from the last looks."""
    grp = [k for k in sides if k.split("|")[:2] == key.split("|")[:2] and (sides[k].get("last") or {}).get("price")]
    prices = {k: sides[k]["last"]["price"] for k in grp}
    if key not in prices or len(prices) < 2 or any(p <= 1 for p in prices.values()):
        return None
    return (1 / prices[key]) / sum(1 / p for p in prices.values())


def bets(game: dict) -> list[dict]:
    """Every graded, model-priced side of one game's first look inside the price band."""
    if not game.get("result"):
        return []
    out = []
    for key, s in (game.get("sides") or {}).items():
        first = s.get("first") or {}
        price, p = first.get("price"), first.get("model")
        if p is None or price is None or s.get("won") is None or not (PRICE_LO <= price <= PRICE_HI):
            continue
        cf = _group_fair(game["sides"], key)
        out.append({"family": FAMILY.get(key[2:].split("|")[0], "Other"), "price": price, "p": p,
                    "edge": p * price - 1, "won": int(s["won"]), "clv": price * cf - 1 if cf else None})
    return out


def report(all_bets: list[dict], n_games: int) -> str:
    out = ["# ICE HOCKEY SECONDARY-MARKET VALUE WATCH (framework #569, ice hockey)", "",
           f"Record only. Each NHL game's first SportyBet look; every side priced {PRICE_LO:.2f}-{PRICE_HI:.2f} that "
           f"the goals model (engine/hockey_model) prices, graded from Flashscore. Cells: bets · landed vs model "
           f"chance · return per unit at the first-look price. Edge = model chance x price - 1, above {MAX_EDGE:.0%} "
           f"dropped. CLV = first-look price x closing fair chance - 1. Several lines per game count (a market "
           f"study, not the board). Written by `backtest/hockey_secondary_value.py`. Period totals, team totals "
           f"and shots on goal are PENDING: not on SportyBet's hockey feed and not priced.", "",
           f"Games graded: {n_games}", ""]
    fams: dict[str, list[dict]] = defaultdict(list)
    for b in all_bets:
        if b["edge"] <= MAX_EDGE:
            fams[b["family"]].append(b)
    if not fams:
        return "\n".join(out + ["NO DATA — PENDING (no graded game with a model price yet)"]) + "\n"
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
    all_bets, graded = [], 0
    for _day, doc in docs:
        for g in (doc.get("games") or {}).values():
            if g.get("result"):
                graded += 1
                all_bets += bets(g)
    return report(all_bets, graded)


def main() -> int:
    from engine import ice_hockey as ih
    docs = ih.load_all()
    OUT.write_text(build(docs), encoding="utf-8")
    print(f"Hockey secondary value: {len(docs)} days -> {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
