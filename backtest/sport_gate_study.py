"""
SPORT GATE STUDY (framework#511, #512, record-only): for every graded side of a multi-sport board, the FIRST board gate
that removes it, and how each removed group did at its first price.

Gates, in the order the board applies them (engine/ice_hockey.qualifies + candidates):
  1 price band 1.20-2.00   2 chance 50%+   3 value bar (+3% result market, +5% line)
  4 exchange quote / model (a side with neither is priced only by SportyBet itself and never qualifies)
  5 value cap (+25% at most)
Chance = exchange fair chance, else 75% SportyBet (margin removed) + 25% model, else SportyBet margin removed.
Exchange LIQUIDITY (>= 10 GBP at the best back) is not stored per side, so that part of gate 4 reads PENDING (HR35).
The value bar here is the code default, not the decision layer's moving bar (order 51).

Record only: nothing here changes a pick rule, stake, threshold or the live switch.

  python backtest/sport_gate_study.py --sport ice_hockey     writes backtest/ICE_HOCKEY_GATE_STUDY.md
  python backtest/sport_gate_study.py --sport american_football   (and darts, volleyball, tennis ...)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

GATES = ("band", "chance", "value bar", "exchange/model", "value cap", "passes all gates")


def _cfg(sport: str) -> dict:
    """Board constants and graded docs for one sport. Ice hockey has its own board; every sport in engine.multisport.SPORTS shares the other one."""
    if sport == "ice_hockey":
        from engine import ice_hockey as m
        return {"band": m.BAND, "result": m.RESULT_MARKETS, "min": m.MIN_VALUE, "line": m.LINE_VALUE,
                "max": m.MAX_VALUE, "anchor": m.ANCHOR, "docs": m.load_all, "devig": m.devig,
                "mkt": lambda key: key[2:].split("|")[0]}
    from engine import multisport as ms          # every other sport of the rollout shares one board (engine/multisport.py)
    if sport in ms.SPORTS:
        return {"band": ms.BAND, "result": ms.WINNER_MARKETS, "min": ms.MIN_VALUE, "line": ms.LINE_VALUE,
                "max": ms.MAX_VALUE, "anchor": ms.ANCHOR, "docs": lambda: ms.load_all(sport), "devig": ms.devig,
                "mkt": lambda key: ms.split_key(key)[1]}
    raise SystemExit(f"sport {sport!r} not wired yet (PENDING)")


def chance(key: str, first: dict, game_first: dict, cfg: dict):
    """(chance, source) for a side from its first look; source in matchbook / model / sportybet / None."""
    if first.get("fair"):
        return first["fair"], "matchbook"
    q = cfg["devig"](key, game_first)
    if q is None:
        return None, None
    if first.get("model") is not None:
        return cfg["anchor"] * q + (1 - cfg["anchor"]) * first["model"], "model"
    return q, "sportybet"


def first_gate(key: str, price: float, p, src, cfg: dict) -> str:
    """The first gate that removes this side, or 'passes all gates'."""
    lo, hi = cfg["band"]
    if not lo <= price <= hi:
        return "band"
    if p is None or p < 0.50:
        return "chance"
    need = cfg["min"] if cfg["mkt"](key) in cfg["result"] else cfg["line"]
    value = price * p - 1
    if value < need:
        return "value bar"
    if src == "sportybet":
        return "exchange/model"
    if value > cfg["max"]:
        return "value cap"
    return "passes all gates"


def study(docs: list, cfg: dict) -> dict:
    out = {g: {"n": 0, "won": 0, "pnl": 0.0, "close": [], "fair": []} for g in GATES}
    for _day, doc in docs:
        for g in (doc.get("games") or {}).values():
            gfirst = {k: (s.get("first") or {}).get("price") for k, s in g["sides"].items()}
            gfirst = {k: v for k, v in gfirst.items() if v}
            for key, s in g["sides"].items():
                f, w = s.get("first") or {}, s.get("won")
                if w is None or not f.get("price"):
                    continue
                p, src = chance(key, f, gfirst, cfg)
                b = out[first_gate(key, f["price"], p, src, cfg)]
                b["n"] += 1
                b["won"] += bool(w)
                b["pnl"] += (f["price"] - 1) if w else -1.0
                last = s.get("last") or {}
                if last.get("price"):
                    b["close"].append(f["price"] / last["price"] - 1)
                if last.get("fair"):
                    b["fair"].append(f["price"] * last["fair"] - 1)
    return out


def _avg(xs):
    return f"{sum(xs) / len(xs):+.2%} (n={len(xs)})" if xs else "PENDING"


def report(sport: str, res: dict) -> str:
    total = sum(b["n"] for b in res.values())
    L = [f"# {sport.replace('_', ' ').title()} gate study (record-only, framework#511)", "",
         f"Graded sides: **{total}**. Each side is counted once, at the FIRST gate that removes it.", "",
         "| first gate that removes it | sides | share | won rate | return / unit (first price) | "
         "first vs close price | first vs exchange close |", "|---|---|---|---|---|---|---|"]
    for g in GATES:
        b = res[g]
        n = b["n"]
        if n:
            L.append(f"| {g} | {n} | {n / total:.1%} | {b['won'] / n:.1%} | {b['pnl'] / n:+.3f} | "
                     f"{_avg(b['close'])} | {_avg(b['fair'])} |")
        else:
            L.append(f"| {g} | 0 | 0% | PENDING | PENDING | PENDING | PENDING |")
    L += ["", "Exchange liquidity (10 GBP at the best back) is not stored per side: PENDING. "
          "Value bar = code default, not the decision layer's bar. Record only: no rule, stake or threshold changed.", ""]
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sport", required=True)
    a = ap.parse_args(argv)
    cfg = _cfg(a.sport)
    res = study(cfg["docs"](), cfg)
    if not sum(b["n"] for b in res.values()):
        print("no graded sides (PENDING): run `python monitor/fdata.py pull` first")
        return 0
    out = ROOT / "backtest" / f"{a.sport.upper()}_GATE_STUDY.md"
    out.write_text(report(a.sport, res), encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
