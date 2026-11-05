"""
NBA BLEND STUDY — how much of each market's chance should come from the sharp-line model and
how much from SportyBet's own price (Architect 2026-11-05: "let everything go live ... make
sure the prediction is improved for it").

The shadow board showed the model OVERCONFIDENT on quarter and 2nd-half totals (stated 59%,
won ~50%). A chance that leans on the model where it is weak finds "value" that isn't there.
Per market group, p = w x model + (1 - w) x SportyBet's fair chance (its two prices, margin
removed). w is fitted on the EARLIER half of the recorded games (log loss, every outcome of
every two-way line), then judged on the LATER half: log loss, and the return of the board's
bars with the blended chance. A group keeps w = 1 (model only) unless the blend beats it on
the later half. Writes backtest/NBA_BLEND_STUDY.md and memory/nba_blend.json (read by
engine/nba_value.py).

    python backtest/nba_blend_study.py
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "backtest")]

OUT = ROOT / "backtest" / "NBA_BLEND_STUDY.md"
OUT_JSON = ROOT / "memory" / "nba_blend.json"
GRID = [i / 20 for i in range(21)]


def group(mid: str, spec: str) -> str | None:
    from engine import nba_value as nv
    return nv.blend_group(mid, spec)


def _ll(rows: list[dict], w: float) -> float:
    s = 0.0
    for r in rows:
        p = min(max(w * r["model"] + (1 - w) * r["fair"], 1e-4), 1 - 1e-4)
        s -= math.log(p if r["won"] else 1 - p)
    return s / len(rows)


def picks_return(rows: list[dict], w: float) -> tuple[int, float | None, float | None]:
    """The board's bars with the blended chance: one pick per game and group (best value)."""
    from engine import nba_value as nv
    best: dict[tuple, dict] = {}
    for r in rows:
        p = w * r["model"] + (1 - w) * r["fair"]
        ev = p * r["price"] - 1
        need = nv.MIN_EV_WINNER if r["mid"] == "219" else nv.MIN_EV_LINE
        if nv.BAND[0] <= r["price"] <= nv.BAND[1] and p >= nv.MIN_CHANCE and need <= ev <= nv.MAX_EV:
            k = (r["event_id"], r["family"])
            if k not in best or ev > best[k]["_ev"]:
                best[k] = {**r, "_ev": ev}
    rets = [b["price"] * b["won"] - 1 for b in best.values()]
    if not rets:
        return 0, None, None
    m = sum(rets) / len(rets)
    se = math.sqrt(sum((x - m) ** 2 for x in rets) / (len(rets) - 1) / len(rets)) if len(rets) > 1 else None
    return len(rets), m, se


def fit(rows: list[dict]) -> dict:
    tips = sorted({r["tip"] for r in rows})
    cut = tips[len(tips) // 2]
    out = {}
    for g in sorted({r["group"] for r in rows}):
        rs = [r for r in rows if r["group"] == g]
        learn = [r for r in rs if r["tip"] < cut]
        test = [r for r in rs if r["tip"] >= cut]
        if len(learn) < 200 or len(test) < 200:
            out[g] = {"w": 1.0, "why": f"too few outcomes ({len(learn)} / {len(test)})"}
            continue
        w = min(GRID, key=lambda x: _ll(learn, x))
        ll1, llw, ll0 = _ll(test, 1.0), _ll(test, w), _ll(test, 0.0)
        n1, r1, s1 = picks_return(test, 1.0)
        nw, rw, sw = picks_return(test, w)
        use = llw < ll1
        out[g] = {"w": w if use else 1.0, "w_fit": w, "learn": len(learn), "test": len(test),
                  "ll_model": round(ll1, 5), "ll_blend": round(llw, 5), "ll_market": round(ll0, 5),
                  "picks_model": [n1, r1, s1], "picks_blend": [nw, rw, sw],
                  "why": "blend beats the model on the later half" if use else "model alone holds"}
    return {"cut": cut, "groups": out}


def render(res: dict) -> str:
    def ret(x):
        n, m, se = x
        return "—" if m is None else f"{n} · {m:+.1%}" + (f" ± {se:.1%}" if se else "")
    L = ["# NBA BLEND STUDY — model vs SportyBet's own price, per market group", "",
         "p = w × sharp-line model + (1 − w) × SportyBet fair (margin removed). w learned on games "
         f"before {res['cut'][:10]}, judged on the games from then on. Log loss: lower is better "
         "(model only / blend / SportyBet only). Picks: the board's bars with that chance, one per game "
         "and group, on the later games. Written by `backtest/nba_blend_study.py`.", "",
         "| Group | w used | w fitted | outcomes learn / test | log loss model · blend · SportyBet | "
         "picks, model only | picks, blend | |", "|---|---:|---:|---|---|---|---|---|"]
    for g, f in res["groups"].items():
        if "ll_model" not in f:
            L.append(f"| {g} | {f['w']:.2f} | — | — | — | — | — | {f['why']} |")
            continue
        L.append(f"| {g} | {f['w']:.2f} | {f['w_fit']:.2f} | {f['learn']} / {f['test']} | "
                 f"{f['ll_model']:.4f} · {f['ll_blend']:.4f} · {f['ll_market']:.4f} | {ret(f['picks_model'])} | "
                 f"{ret(f['picks_blend'])} | {f['why']} |")
    return "\n".join(L) + "\n"


def main() -> int:
    import nba_market_study as st
    rows = st.looks()
    games = {}
    for r in rows:
        if datetime.fromisoformat(r["tip"].replace("Z", "+00:00")) < datetime.now().astimezone() - timedelta(hours=3):
            g = st.espn_game(r)
            if g is not None:
                games[r["event_id"]] = g
    settled, _ = st.settle_rows(rows, games)
    data = []
    for r in settled:
        g = group(r["mid"], r["spec"])
        if r["stage"] != "regular" or r["model"] is None or g is None or not r.get("tip"):
            continue
        data.append({**r, "group": g})
    res = fit(data)
    OUT.write_text(render(res), encoding="utf-8")
    OUT_JSON.write_text(json.dumps({"built": datetime.now().astimezone().strftime("%Y-%m-%dT%H:%MZ"),
                                    "cut": res["cut"], "w": {g: f["w"] for g, f in res["groups"].items()}},
                                   indent=1), encoding="utf-8")
    print(render(res))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
