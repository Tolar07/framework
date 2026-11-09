"""
MULTI-SPORT BLEND STUDY (framework#383) - RECORD ONLY.

The live multi-sport pick blends 25% Elo with 75% price (engine/multisport.ANCHOR). The NFL backtest (#373) showed
that blend loses 7.2%/bet and is LESS accurate than the closing price (Brier 0.2119 vs 0.2107). So the default is the
price; a sport earns an Elo weight only if the weight, fitted on its EARLIER games, beats the price on its LATER games.

Per rollout sport, on the graded shadow record (output/multisport/<sport>/ms_*.json, every winner-market game with a
result, an Elo chance and a price), p_price = the exchange's fair chance, else SportyBet's two prices with the margin
removed. p = w x Elo + (1 - w) x p_price for w in GRID (every try counted, TRIES). w is fitted on the earlier half by
Brier, then judged on the later half: Brier against the price, a paired z of the difference, and the return of the
live rule (edge >= EDGE pts over the price chance) at SportyBet's recorded price with 2% commission on winnings.
A weight above 0 is written only if later-half Brier beats the price with z <= -1.645 on >= MIN_TEST games; fewer
games reads PENDING (HR35). Writes memory/multisport_blend.json and backtest/MULTISPORT_BLEND_STUDY.md.
It changes NO live rule: engine/multisport.ANCHOR stays as it is until the Architect or the shadow-promotion rule
moves it.

    python backtest/multisport_blend_study.py
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OUT_MD = ROOT / "backtest" / "MULTISPORT_BLEND_STUDY.md"
OUT_JSON = ROOT / "memory" / "multisport_blend.json"
GRID = [i / 20 for i in range(0, 11)]          # Elo weight 0 .. 0.5; 0 = the price alone, 0.25 = the live blend
TRIES = len(GRID)
MIN_LEARN = MIN_TEST = 100
Z_BAR = -1.645
EDGE = 0.04
COMMISSION = 0.02


def rows_for(sport: str, docs: list[tuple[str, dict]]) -> list[dict]:
    """One row per graded home/away winner side that has an Elo chance and a price chance."""
    from engine import multisport as ms
    winner = ms.SPORTS[sport]["winner"]
    out = []
    for day, doc in docs:
        for gid, g in (doc.get("games") or {}).items():
            sides = g.get("sides") or {}
            for key, s in sides.items():
                _sp, mid, _spec, o = ms.split_key(key)
                first = s.get("first") or {}
                if mid != winner or o.lower() not in ("home", "away") or s.get("won") is None:
                    continue
                if first.get("model") is None or not first.get("price"):
                    continue
                q = first.get("fair")
                src = "exchange"
                if q is None:
                    prices = {k: v["first"]["price"] for k, v in sides.items()
                              if v.get("first") and v["first"].get("price")}
                    q = ms.devig(key, prices)
                    src = "sportybet"
                if q is None:
                    continue
                out.append({"day": day, "gid": gid, "price": first["price"], "price_p": q, "src": src,
                            "model": first["model"], "won": int(s["won"])})
    return sorted(out, key=lambda r: (r["day"], r["gid"]))


def brier(rows: list[dict], w: float) -> float:
    return sum((w * r["model"] + (1 - w) * r["price_p"] - r["won"]) ** 2 for r in rows) / len(rows)


def paired_z(rows: list[dict], w: float) -> float | None:
    d = [(w * r["model"] + (1 - w) * r["price_p"] - r["won"]) ** 2 - (r["price_p"] - r["won"]) ** 2 for r in rows]
    n = len(d)
    if n < 2:
        return None
    m = sum(d) / n
    var = sum((x - m) ** 2 for x in d) / (n - 1)
    return m / math.sqrt(var / n) if var > 0 else None


def bets(rows: list[dict], w: float) -> tuple[int, float | None]:
    """The live rule: bet a side whose blended chance is EDGE over the price chance; SportyBet's price, 2% commission."""
    rets = []
    for r in rows:
        p = w * r["model"] + (1 - w) * r["price_p"]
        if p - r["price_p"] >= EDGE:
            rets.append(((r["price"] - 1) * (1 - COMMISSION)) if r["won"] else -1.0)
    return len(rets), (sum(rets) / len(rets) if rets else None)


def fit(rows: list[dict]) -> dict:
    if len(rows) < MIN_LEARN + MIN_TEST:
        return {"w": 0.0, "status": "PENDING", "games": len(rows),
                "why": f"PENDING: {len(rows)} graded sides, need {MIN_LEARN + MIN_TEST}; the price stays the default"}
    cut = len(rows) // 2
    learn, test = rows[:cut], rows[cut:]
    w = min(GRID, key=lambda x: brier(learn, x))
    res = {"games": len(rows), "learn": len(learn), "test": len(test), "w_learned": w,
           "price_brier_test": round(brier(test, 0.0), 4), "blend_brier_test": round(brier(test, w), 4),
           "live_blend_brier_test": round(brier(test, 0.25), 4), "z_vs_price": None,
           "price_sources": {s: sum(r["src"] == s for r in rows) for s in ("exchange", "sportybet")}}
    z = paired_z(test, w) if w > 0 else None
    res["z_vs_price"] = None if z is None else round(z, 2)
    for tag, ww in (("live", 0.25), ("learned", w)):
        n, ret = bets(test, ww)
        res[f"bets_{tag}"], res[f"return_{tag}"] = n, None if ret is None else round(ret, 4)
    res["bets_price"] = bets(test, 0.0)[0]
    if w > 0 and z is not None and z <= Z_BAR and res["blend_brier_test"] < res["price_brier_test"]:
        res.update(w=w, status="BLEND", why=f"w={w} beat the price on the later {len(test)} sides (z {z:.2f})")
    else:
        res.update(w=0.0, status="PRICE", why="the price alone; no Elo weight beat it on the later games")
    return res


def load_docs(sport: str, folder: Path | None = None) -> list[tuple[str, dict]]:
    from engine import multisport as ms
    return ms.load_all(sport, folder or ms.OUT_DIR)


def run(folder: Path | None = None) -> dict:
    from engine import multisport as ms
    out = {s: fit(rows_for(s, load_docs(s, folder))) for s in sorted(ms.SPORTS)}
    return {"tries_per_sport": TRIES, "grid": GRID, "live_anchor_elo_weight": round(1 - ms.ANCHOR, 2),
            "rule": f"w > 0 only if the later-half Brier beats the price with z <= {Z_BAR} on >= {MIN_TEST} sides",
            "sports": out}


def report(res: dict) -> str:
    lines = ["# Multi-sport blend study (framework#383, record only)", "",
             f"Elo weight per sport against the price. {res['tries_per_sport']} weights tried per sport "
             f"({res['grid'][0]}..{res['grid'][-1]}); fitted on the earlier half, judged on the later half. "
             f"Rule: {res['rule']}. Live Elo weight is {res['live_anchor_elo_weight']} and stays so; "
             "this file moves nothing.", "",
             "| sport | status | sides | price Brier | live 25% Brier | learned w Brier | z | why |",
             "|---|---|---|---|---|---|---|---|"]
    for s, r in res["sports"].items():
        z = r.get("z_vs_price")
        lines.append(f"| {s} | {r['status']} | {r['games']} | {r.get('price_brier_test', 'PENDING')} | "
                     f"{r.get('live_blend_brier_test', 'PENDING')} | {r.get('blend_brier_test', 'PENDING')} | "
                     f"{z if z is not None else 'PENDING'} | {r['why']} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    res = run()
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(res, indent=1), encoding="utf-8")
    OUT_MD.write_text(report(res), encoding="utf-8")
    for s, r in res["sports"].items():
        print(f"{s}: {r['status']} - {r['why']}")


if __name__ == "__main__":
    main()
