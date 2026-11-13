"""
NBA SECONDARY-MARKET VALUE WATCH (framework #569, step 1: basketball). RECORD ONLY.

Architect 2026-11-11: "the right selection was from secondary market ... how does this also apply to other
sports?" Every market family SportyBet lists on an NBA game (quarter / half totals and handicaps, team totals,
...) is priced by engine/nba_value.fair_chance (shadow=True) from the sharp line. For each outcome priced at
PRICE_LO-PRICE_HI at the game's FIRST look the shadow bet is: take that price, grade after the game. Per family:
bets with model edge >= 5% and >= 10%, how often they landed vs the model's chance, return per unit, and CLV
(first-look price against the closing price with SportyBet's margin removed).

Never picks, stakes or blocks; no board reads this. A family that stays positive over MIN_GRADED graded bets
goes to the Architect (paper first). A family with fewer bets reads COLLECTING; a missing sharp line or box
score leaves an outcome out (HR35), nothing is invented (HR59).

    python backtest/nba_secondary_value.py   -> backtest/NBA_SECONDARY_VALUE.md
"""
from __future__ import annotations

import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backtest"))

from engine import nba_markets as nm  # noqa: E402
from engine import nba_value as nv  # noqa: E402

OUT = ROOT / "backtest" / "NBA_SECONDARY_VALUE.md"
PRICE_LO, PRICE_HI = 1.60, 2.60
EDGE_LEVELS = (0.05, 0.10)
MAX_EDGE = nv.MAX_EV            # above this the gap is a stale line, not value (as the board treats it)
MIN_GRADED = 200


def first_looks(rows: list[dict]) -> list[dict]:
    """Each game's first look taken before its tip-off."""
    best: dict[str, dict] = {}
    for r in rows:
        if not r.get("tip") or nm._t(r["at"]) >= nm._t(r["tip"]):
            continue
        if r["event_id"] not in best or nm._t(r["at"]) < nm._t(best[r["event_id"]]["at"]):
            best[r["event_id"]] = r
    return list(best.values())


def _sharp(r: dict):
    from types import SimpleNamespace
    sh = r.get("sharp") or {}
    return SimpleNamespace(ml_home=sh.get("ml_home"), ml_away=sh.get("ml_away"),
                           spread=sh.get("spread"), total=sh.get("total"))


def _close_fair(last: dict | None) -> dict:
    """{(market id, specifier, outcome): closing chance with the margin removed} from a game's last look."""
    out: dict = {}
    for m in (last or {}).get("markets") or []:
        prices = [p for _d, p in m["outcomes"]]
        if not m.get("open", True) or any(p <= 1 for p in prices):
            continue
        inv = sum(1 / p for p in prices)
        for d, p in m["outcomes"]:
            out[(m["id"], m.get("spec") or "", d)] = (1 / p) / inv
    return out


def bets(first: dict, last: dict | None, game, box=None) -> list[dict]:
    """Every outcome of the first look in the price band with a model chance, graded; [] if no sharp line."""
    from nba_market_study import family
    sharp = _sharp(first)
    if not sharp.total:
        return []
    close = _close_fair(last)
    out = []
    for m in first.get("markets") or []:
        if not m.get("open", True):
            continue
        spec = m.get("spec") or ""
        for desc, price in m["outcomes"]:
            if not (PRICE_LO <= price <= PRICE_HI):
                continue
            p = nv.fair_chance(m["id"], spec, desc, sharp, shadow=True)
            if p is None:
                continue
            won = nm.settle_any(m["id"], spec, desc, game.hs, game.as_, game.q_home, game.q_away,
                                name=m.get("name") or "", box=box)
            if won is None:
                continue
            cf = close.get((m["id"], spec, desc))
            out.append({"family": family(m), "price": price, "p": p, "edge": p * price - 1, "won": int(won),
                        "clv": (price * cf - 1) if cf else None, "event_id": first["event_id"]})
    return out


def _stats(rs: list[dict]) -> dict:
    n = len(rs)
    if not n:
        return {"n": 0}
    rets = [r["price"] * r["won"] - 1 for r in rs]
    mean = sum(rets) / n
    se = (sum((x - mean) ** 2 for x in rets) / (n - 1) / n) ** 0.5 if n > 1 else None
    clvs = [r["clv"] for r in rs if r["clv"] is not None]
    return {"n": n, "hit": sum(r["won"] for r in rs) / n, "p": sum(r["p"] for r in rs) / n, "ret": mean, "se": se,
            "clv": sum(clvs) / len(clvs) if clvs else None}


def status(s5: dict) -> str:
    n = s5.get("n", 0)
    if n < MIN_GRADED:
        return f"COLLECTING ({n} of {MIN_GRADED})"
    if s5["ret"] > 0 and s5["se"] and s5["ret"] > 2 * s5["se"]:
        return "FOR THE ARCHITECT (paper first)"
    return "no steady edge" if s5["ret"] <= 0 else "positive, not yet 2 se"


def _cell(s: dict) -> str:
    if not s["n"]:
        return "—"
    se = f" ± {s['se']:.1%}" if s.get("se") else ""
    return f"{s['n']} · {s['hit']:.0%} vs {s['p']:.0%} · {s['ret']:+.1%}{se}"


def report(all_bets: list[dict], n_games: int) -> str:
    out = ["# NBA SECONDARY-MARKET VALUE WATCH (framework #569, basketball)", "",
           f"Record only. Each game's first SportyBet look before tip-off; every outcome priced "
           f"{PRICE_LO:.2f}-{PRICE_HI:.2f} that the sharp-line model (engine/nba_value, shadow) prices; graded from "
           f"ESPN. Cells: bets · landed vs model chance · return per unit at the first-look price. Edge = model chance "
           f"x price - 1, above {MAX_EDGE:.0%} dropped as a stale line. CLV = first-look price x closing fair chance - 1. "
           f"Several lines per game count (a market study, not the board). Written by "
           f"`backtest/nba_secondary_value.py`. Player props need #558 and are not priced here (PENDING).", "",
           f"Games graded: {n_games}", ""]
    fams: dict[str, list[dict]] = defaultdict(list)
    for b in all_bets:
        if b["edge"] <= MAX_EDGE:
            fams[b["family"]].append(b)
    if not fams:
        return "\n".join(out + ["NO DATA — PENDING (no graded game with a sharp line yet)"]) + "\n"
    out += ["| Market family | edge 5%+ | edge 10%+ | CLV (5%+) | status |", "|---|---|---|---:|---|"]
    rows = []
    for fam, rs in fams.items():
        s5 = _stats([r for r in rs if r["edge"] >= EDGE_LEVELS[0]])
        s10 = _stats([r for r in rs if r["edge"] >= EDGE_LEVELS[1]])
        rows.append((s5.get("n", 0), fam, s5, s10))
    for _n, fam, s5, s10 in sorted(rows, key=lambda t: -t[0]):
        clv = f"{s5['clv']:+.1%}" if s5.get("clv") is not None else "PENDING"
        out.append(f"| {fam} | {_cell(s5)} | {_cell(s10)} | {clv} | {status(s5)} |")
    return "\n".join(out + [""]) + "\n"


def build(rows: list[dict], games: dict, boxes: dict | None = None) -> str:
    boxes = boxes or {}
    lasts = {r["event_id"]: r for r in nm.last_looks(rows)}
    all_bets, graded = [], 0
    for f in first_looks(rows):
        g = games.get(f["event_id"])
        if g is None:
            continue
        graded += 1
        all_bets += bets(f, lasts.get(f["event_id"]), g, boxes.get(f["event_id"]))
    return report(all_bets, graded)


def main() -> int:
    import nba_market_study as ms

    from data import nba_players as npl
    rows = ms.looks()
    games = {}
    for r in rows:
        if datetime.fromisoformat(r["tip"].replace("Z", "+00:00")) < datetime.now().astimezone() - timedelta(hours=3):
            g = ms.espn_game(r)
            if g is not None:
                games[r["event_id"]] = g
    boxes = {}
    for eid, g in games.items():
        try:
            boxes[eid] = nm.box_stats(npl.summary(g.id, True), g.home, g.away)
        except Exception:  # noqa: BLE001 - a missing box score leaves those markets out
            continue
    OUT.write_text(build(rows, games, boxes), encoding="utf-8")
    print(f"NBA secondary value: {len(rows)} games, {len(games)} graded -> {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
