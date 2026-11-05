"""
EDGE SCOREBOARD — steps 1, 3, 4, 5 and 7 of the edge plan (Architect 2026-11-04: "how can
the training turn to an edge?"). RECORDED ONLY: nothing reads it to pick, stake or block.

STEP 1, the scoreboard changes. A pick is judged by whether its PRICE beat the true chance,
not by whether it won. The true chance is the Matchbook exchange's fair chance (no margin,
engine/exchange.py); its last pre-match look is the exchange close (engine/edge_book.py):
    gap at entry  price x exchange chance when the pick was made - 1
    CLV           price x exchange close - 1   (> 0: the price beat the closing fair chance)
    return        £1 flat at the price taken, ± 1 standard error
CLV is the fast test: it needs no result and has far less noise than the return.

Groups:
    board       the football singles, all and by market family; the BTTS singles
    venue       the same singles at Matchbook's back after commission, and at the better book
    nba         the NBA board's picks, all and by SportyBet market (68 = 1st-half total) (step 5)
    world basketball  the paper board for every other league (engine/world_basketball.py), by league
    gap board   every SportyBet side, any game, the first time its price beat the exchange's fair
                chance by 2%+ (step 3); by gap size, sport, covered or not; by hours to kick-off
                and by how the exchange had moved since the first look (step 4, timing)
    baseline    every graded SportyBet side at its last price against the exchange close: what
                SportyBet's margin costs

STEP 7, promotion on proof. A strategy (not a baseline) is READY FOR ARCHITECT only with
PROMOTE_N+ graded picks, mean CLV > 0 that survives a Benjamini-Hochberg cut at q = BH_Q across
every strategy tested, and a flat return above 0. Fewer picks: COLLECTING. Otherwise NO EDGE
YET. Promotion to money is the Architect's call; this only says when the evidence is there.

STEP 6 is engine/residual_model.py, fitted here on the same graded sides.

Writes memory/edge_scoreboard.json, memory/residual_model.json, backtest/EDGE_SCOREBOARD.md.
"""
from __future__ import annotations

import json
import math
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from engine import edge_book as eb  # noqa: E402
from engine import exchange as ex  # noqa: E402
from engine import residual_model as rm  # noqa: E402

OUT_JSON = ROOT / "memory" / "edge_scoreboard.json"
OUT_MODEL = ROOT / "memory" / "residual_model.json"
OUT_MD = ROOT / "backtest" / "EDGE_SCOREBOARD.md"
PICKS_DIR = ROOT / "output" / "picks"
PROMOTE_N = 200
MIN_TEST_N = 30
BH_Q = 0.05
MB_COMMISSION = 0.02
GAP_STEPS = (0.02, 0.03, 0.05)
_ALIAS = {"BTTS_YES": "SB:29||Yes", "OVER_2_5": "SB:18|total=2.5|Over 2.5"}


# ---------------------------------------------------------------- loading
def grade_basketball(key: str, res: dict) -> int | None:
    """1/0 for a "B:" side from the final score (overtime included); the 1st-half total (68)
    from the half-time points `ht` when the result carries them. None for a push or a market
    the result can't settle."""
    h, a = res.get("h"), res.get("a")
    if h is None or a is None:
        return None
    mid, spec, out = (key[2:].split("|") + ["", ""])[:3]
    o = out.lower()
    if mid == "219" and o in ("home", "away"):
        return int((h > a) == (o == "home")) if h != a else None
    if mid in ("225", "68"):
        m = re.search(r"total=([\d.]+)", spec)
        if not m or not o.startswith(("over", "under")):
            return None
        if mid == "68":
            ht = res.get("ht") or [None, None]
            if ht[0] is None or ht[1] is None:
                return None
            h, a = ht
        t = float(m.group(1))
        return None if h + a == t else int((h + a > t) == o.startswith("over"))
    if mid == "223":
        m = re.fullmatch(r"(home|away) \(([+-]?[\d.]+)\)", o)
        if not m:
            return None
        line = float(m.group(2))
        margin = (h - a if m.group(1) == "home" else a - h) + line
        return None if margin == 0 else int(margin > 0)
    return None


def universe_results(load=None) -> dict[str, dict[str, int]]:
    """{SportyBet event id: {side key: won}} from the graded universe."""
    from engine import universe as uv
    rows = load() if load else uv.load_graded()
    out: dict[str, dict[str, int]] = {}
    for r in rows:
        res = r.get("result")
        if not res or not r.get("id"):
            continue
        if r.get("sport") == "football":
            out[r["id"]] = {x["key"]: x["won"] for x in uv.all_records(r, "last")}
        else:
            out[r["id"]] = {"__res__": res}          # basketball: graded per key on demand
    return out


def _won(results: dict[str, dict], event_id: str, key: str) -> int | None:
    g = results.get(event_id)
    if not g:
        return None
    if "__res__" in g:
        return grade_basketball(key, g["__res__"]) if key.startswith("B:") else None
    return g.get(key)


def _picks(name: str, picks_dir: Path) -> list[tuple[str, dict]]:
    out = []
    for f in sorted(picks_dir.glob(f"{name}_20*.json")):
        try:
            out.append((f.stem.split("_", 1)[1], json.loads(f.read_text(encoding="utf-8"))))
        except (OSError, ValueError):
            continue
    return out


# ---------------------------------------------------------------- metrics
def _mean_se(xs: list[float]) -> tuple[float | None, float | None]:
    if not xs:
        return None, None
    m = sum(xs) / len(xs)
    if len(xs) < 2:
        return m, None
    v = sum((x - m) ** 2 for x in xs) / (len(xs) - 1)
    return m, math.sqrt(v / len(xs))


def summarize(name: str, rows: list[dict], kind: str = "strategy") -> dict:
    """rows: {price, won 0/1 or None, p_entry?, p_close?}."""
    graded = [r for r in rows if r.get("won") in (0, 1) and r.get("price")]
    roi, roi_se = _mean_se([r["price"] - 1 if r["won"] else -1.0 for r in graded])
    gaps = [r["price"] * r["p_entry"] - 1 for r in rows if r.get("p_entry") and r.get("price")]
    clvs = [r["price"] * r["p_close"] - 1 for r in rows if r.get("p_close") and r.get("price")]
    gap, _ = _mean_se(gaps)
    clv, clv_se = _mean_se(clvs)

    def rnd(x: float | None) -> float | None:
        return None if x is None else round(x, 4)

    return {"name": name, "kind": kind, "n": len(graded),
            "hit": rnd(sum(r["won"] for r in graded) / len(graded)) if graded else None,
            "roi": rnd(roi), "roi_se": rnd(roi_se), "n_entry": len(gaps), "gap_entry": rnd(gap),
            "n_clv": len(clvs), "clv": rnd(clv), "clv_se": rnd(clv_se),
            "beat": rnd(sum(1 for c in clvs if c > 0) / len(clvs)) if clvs else None}


def promotion(groups: list[dict]) -> list[dict]:
    """Step 7: status per strategy, Benjamini-Hochberg across every strategy tested."""
    tested = [g for g in groups if g["kind"] == "strategy" and g["n_clv"] >= MIN_TEST_N
              and g["clv"] is not None and g["clv_se"]]
    for g in tested:
        z = g["clv"] / g["clv_se"]
        g["_p"] = 0.5 * math.erfc(z / math.sqrt(2))          # one-sided: CLV > 0
    ranked = sorted(tested, key=lambda g: g["_p"])
    m, cut = len(ranked), 0
    for i, g in enumerate(ranked, 1):
        if g["_p"] <= BH_Q * i / m:
            cut = i
    passed = {g["name"] for g in ranked[:cut]}
    out = []
    for g in groups:
        if g["kind"] != "strategy":
            continue
        p = g.pop("_p", None)
        if g["n"] < PROMOTE_N:
            status = f"COLLECTING ({g['n']} of {PROMOTE_N})"
        elif g["name"] in passed and (g["roi"] or 0) > 0:
            status = "READY FOR ARCHITECT"
        else:
            status = "NO EDGE YET"
        out.append({"name": g["name"], "status": status, "n": g["n"], "clv": g["clv"],
                    "p_value": None if p is None else round(p, 4), "bh_pass": g["name"] in passed,
                    "roi": g["roi"]})
    return out


def _bucket_h(h: float | None) -> str:
    if h is None:
        return "unknown"
    return "<1h" if h < 1 else "1-6h" if h < 6 else "6-24h" if h < 24 else "24h+"


def _bucket_move(pm: float | None) -> str:
    if pm is None:
        return "no first look"
    return "exchange moved FOR it (2+ pts)" if pm >= 0.02 else \
        "exchange moved AGAINST it (2+ pts)" if pm <= -0.02 else "exchange flat"


# ---------------------------------------------------------------- build
def collect(obs: dict[str, dict], results: dict[str, dict], picks_dir: Path = PICKS_DIR) -> dict:
    """Every row group, plus the residual model's rows."""
    G: dict[str, list[dict]] = {}
    kinds: dict[str, str] = {}
    model_rows: list[dict] = []

    def add(name: str, row: dict, kind: str = "strategy") -> None:
        G.setdefault(name, []).append(row)
        kinds[name] = kind

    # gap board + baseline + residual rows: every observed side, any game
    for day, doc in obs.items():
        for eid, ev in doc.get("events", {}).items():
            sport = ev.get("sport") or "football"
            for key, rec in (ev.get("k") or {}).items():
                won = _won(results, eid, key)
                if won is None:
                    continue
                if rec.get("s1") and rec.get("p1"):
                    add("baseline: every SportyBet side at its last price", {
                        "price": rec["s1"], "won": won, "p_close": rec["p1"]}, "baseline")
                if rec.get("s0") and rec.get("p0"):
                    model_rows.append({"day": day, "key": key, "sport": sport, "price": rec["s0"],
                                       "p": rec["p0"], "won": won, "h": rec.get("h0")})
                x = rec.get("x")
                if not x:
                    continue
                row = {"price": x["s"], "won": won, "p_entry": x["p"], "p_close": rec.get("p1")}
                for step in GAP_STEPS:
                    if x["g"] >= step:
                        add(f"gap board: gap {step:.0%}+", row)
                add(f"gap board: {sport}", row)
                add(f"gap board: {'covered' if ev.get('covered') else 'not covered'} leagues", row)
                add(f"gap board timing: {_bucket_h(x.get('h'))} before kick-off", row)
                add(f"gap board timing: {_bucket_move(x.get('pm'))}", row)

    # the board's own picks (football singles, BTTS singles, NBA)
    for day, doc in _picks("picks", picks_dir):
        for s in doc.get("singles") or []:
            key = _ALIAS.get(s.get("market") or "", s.get("market") or "")
            ev = eb.find(obs, s.get("sb_event_id"), s.get("home") or "", s.get("away") or "", day)
            rec = (ev or {}).get("k", {}).get(key) or {}
            exb = s.get("exchange") or {}
            won = {"won": 1, "lost": 0}.get(s.get("result"))
            price = ex._f(s.get("price"))
            if not price:
                continue
            p_entry = exb.get("p") or rec.get("p0")
            row = {"price": price, "won": won, "p_entry": p_entry, "p_close": rec.get("p1")}
            fam = (s.get("drift") or {}).get("family") or key.split("|", 1)[0]
            add("board: football singles", row)
            add(f"board family: {fam}", row)
            back = exb.get("back") or rec.get("b1")
            if back:
                net = 1 + (back - 1) * (1 - MB_COMMISSION)
                add("venue: board singles at Matchbook (after 2%)", {**row, "price": net}, "baseline")
                add("venue: board singles at the better book", {**row, "price": max(price, net)}, "baseline")
                add("venue: same singles at SportyBet", row, "baseline")
            if won is not None and p_entry and ex._f(s.get("chance_raw")):
                model_rows.append({"day": day, "key": key, "sport": "football", "price": price,
                                   "p": p_entry, "won": won, "model": ex._f(s.get("chance_raw")),
                                   "board": True})
        for b in doc.get("btts") or []:
            legs = b.get("alt_legs") or []
            if len(legs) != 1:
                continue
            leg = legs[0]
            ev = eb.find(obs, None, leg.get("home") or "", leg.get("away") or "", day)
            rec = (ev or {}).get("k", {}).get("SB:29||Yes") or {}
            price = ex._f(b.get("odds"))
            if price:
                add("board: BTTS singles", {"price": price, "won": {"won": 1, "lost": 0}.get(b.get("result")),
                                            "p_entry": rec.get("p0"), "p_close": rec.get("p1")})
    for day, doc in _picks("nba", picks_dir):
        for p in doc.get("picks") or []:
            key = ex.nba_key(p)
            ev = eb.find(obs, p.get("event_id"), p.get("home") or "", p.get("away") or "", day)
            rec = (ev or {}).get("k", {}).get(key) or {}
            price = ex._f(p.get("price"))
            if not price:
                continue
            row = {"price": price, "won": {"won": 1, "lost": 0}.get(p.get("result")),
                   "p_entry": rec.get("p0"), "p_close": rec.get("p1")}
            add("nba: board picks", row)
            add(f"nba market: {p.get('market_id')}", row)
    from engine import world_basketball as wbb      # the paper world-basketball board (2026-11-05)
    for _day, doc in wbb.load_all():
        for p in doc.get("picks") or []:
            rec = (eb.find(obs, p.get("sb_event_id"), "", "", None) or {}).get("k", {}).get(p["key"]) or {}
            row = {"price": p["price"], "won": _won(results, p["sb_event_id"], p["key"]),
                   "p_entry": p.get("fair"), "p_close": rec.get("p1")}
            add("world basketball: all leagues", row)
            add(f"world basketball: {p.get('comp')}", row)
    return {"groups": [summarize(n, rows, kinds[n]) for n, rows in sorted(G.items())], "model_rows": model_rows}


def _pct(x: float | None, se: float | None = None) -> str:
    if x is None:
        return "PENDING"
    return f"{x:+.1%}" + (f" ± {se:.1%}" if se else "")


def render(doc: dict) -> str:
    lines = ["# EDGE SCOREBOARD", "",
             "Written by `monitor/edge_scoreboard.py` (see its docstring). A pick is judged by whether "
             "its PRICE beat the Matchbook exchange's fair chance (no margin), at entry and at the "
             "exchange close, not by whether it won. RECORDED ONLY.", "",
             f"Built {doc['built_at']}. {doc['summary']}", "",
             "| Group | Graded | Won | Return ± se | Gap at entry (n) | CLV vs exchange close ± se (n) | Beat close |",
             "|---|---:|---:|---|---|---|---:|"]
    def share(x: float | None) -> str:
        return "PENDING" if x is None else f"{x:.0%}"

    for g in doc["groups"]:
        tag = " *(baseline)*" if g["kind"] == "baseline" else ""
        lines.append(f"| {g['name']}{tag} | {g['n']} | {share(g['hit'])} | {_pct(g['roi'], g['roi_se'])} | "
                     f"{_pct(g['gap_entry'])} ({g['n_entry']}) | {_pct(g['clv'], g['clv_se'])} ({g['n_clv']}) | "
                     f"{share(g['beat'])} |")
    lines += ["", "## Promotion (step 7)", "",
              f"READY FOR ARCHITECT = {PROMOTE_N}+ graded, CLV > 0 surviving Benjamini-Hochberg at "
              f"q = {BH_Q} across every strategy tested, flat return > 0. Money is the Architect's call.", "",
              "| Strategy | Status | Graded | CLV | p | BH |", "|---|---|---:|---|---:|---|"]
    for p in doc["promotion"]:
        lines.append(f"| {p['name']} | {p['status']} | {p['n']} | {_pct(p['clv'])} | "
                     f"{'—' if p['p_value'] is None else p['p_value']} | {'pass' if p['bh_pass'] else '—'} |")
    lines += ["", "## Residual model (step 6)", "",
              "Starts from the exchange's fair chance and learns only what it misses "
              "(`engine/residual_model.py`), walk-forward by day.", ""]
    for m in doc["residual"]:
        wf = m.get("walk_forward") or {}
        lines.append(f"- **{m['name']}**: {m['status']}; {m['n']} rows"
                     + (f"; out-of-sample log-loss gain {wf['gain']:+.5f} ± {wf['se']:.5f} over {wf['n']}"
                        if wf else ""))
    return "\n".join(lines) + "\n"


def build(now: datetime | None = None, obs: dict | None = None, results: dict | None = None,
          picks_dir: Path = PICKS_DIR, write: bool = True) -> str:
    now = now or datetime.now(UTC)
    obs = eb.load_all() if obs is None else obs
    results = universe_results() if results is None else results
    c = collect(obs, results, picks_dir)
    groups = c["groups"]
    promo = promotion(groups)
    residual = [rm.study(c["model_rows"], "every SportyBet side, exchange at first look"),
                rm.study([r for r in c["model_rows"] if r.get("board")], "board picks: our model vs the exchange")]
    ready = [p["name"] for p in promo if p["status"] == "READY FOR ARCHITECT"]
    board = next((g for g in groups if g["name"] == "board: football singles"), None)
    summary = (f"Edge: {len(ready)} strateg{'y' if len(ready) == 1 else 'ies'} ready for the Architect"
               + (f" ({', '.join(ready)})" if ready else "")
               + (f"; board singles CLV vs exchange close {_pct(board['clv'])} over {board['n_clv']}"
                  if board and board["n_clv"] else "; board singles: exchange close PENDING"))
    doc = {"built_at": now.strftime("%Y-%m-%dT%H:%MZ"), "summary": summary, "groups": groups,
           "promotion": promo, "residual": residual}
    try:
        old = json.loads(OUT_JSON.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        old = {}
    if {**old, "built_at": None} == {**doc, "built_at": None}:
        return summary + " (unchanged, not rewritten)"
    if write:
        OUT_JSON.write_text(json.dumps(doc, indent=1), encoding="utf-8")
        OUT_MODEL.write_text(json.dumps({"built_at": doc["built_at"], "recorded_only": True,
                                         "studies": residual}, indent=1), encoding="utf-8")
        OUT_MD.write_text(render(doc), encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(build())
