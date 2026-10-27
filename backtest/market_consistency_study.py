"""
MARKET CONSISTENCY STUDY — to-do #7 idea 1, measured out of sample (recorded only, no stakes).

Every graded football game in data/universe is refitted from its FIRST SportyBet look
(engine/market_consistency.py) and every side of every market (main markets, and full ladder
lines, as engine.market_consistency keeps them) gets its ev vs the book's own other markets.
Games are split at the median kick-off: the ev threshold is chosen on the EARLIER half, the
verdict reads the LATER half only. Both sides are read: the soft side, and the other side of the
same line.

    return  flat 1 unit at SportyBet's first price, settled on the 90-minute score
    CLV     first price x SportyBet's LAST de-vigged chance - 1 (games seen more than once)

Board singles (output/picks) are joined by event id and read the same way.
Writes backtest/MARKET_CONSISTENCY_STUDY.md.  Usage: python -m backtest.market_consistency_study
"""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import full_markets as fm  # noqa: E402
from engine import market_consistency as xm  # noqa: E402
from engine import universe as uv  # noqa: E402

OUT = ROOT / "backtest" / "MARKET_CONSISTENCY_STUDY.md"
THRESHOLDS = (0.0, 0.01, 0.02, 0.03, 0.05, 0.08)
MIN_N = 150


def _fair_map(p: dict) -> dict[str, float]:
    """De-vigged chance per side of the look, main markets and ladder lines."""
    out: dict[str, float] = {}
    names = {"1x2": ("home", "draw", "away"), "btts": ("yes", "no"), "dc": xm.DC_SIDES}
    for line in xm.OU_LINES:
        names[f"ou{line}"] = ("over", "under")
    for mk, sides in names.items():
        if mk == "dc":                # each dc side covers two results: chances sum to 2
            inv = [1 / float(v) for v in (p.get("dc") or []) if v and float(v) > 1]
            x = [2 * v / sum(inv) for v in inv] if len(inv) == 3 and 2 <= sum(inv) <= 2.6 else None
        else:
            x = xm._devig(p.get(mk) or [])
        if x and len(x) == len(sides):
            out.update({f"{mk}:{s}": v for s, v in zip(sides, x, strict=True)})
    groups: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for k, pr in (p.get("ladder") or {}).items():
        parsed = fm.parse_key(k)
        if parsed and pr:
            groups[f"{parsed[0]}|{parsed[1]}"].append((k, pr))
    for g in groups.values():
        x = xm._devig([pr for _, pr in g])
        if x:
            out.update({k: v for (k, _), v in zip(g, x, strict=True)})
    return out


def _rules(p: dict) -> dict[str, tuple[float, fm.Rule]]:
    out = {k: (pr, r) for k, pr, r in xm._main_sides(p)}
    for k, pr in (p.get("ladder") or {}).items():
        parsed = fm.parse_key(k)
        r = fm.rule_for(*parsed) if parsed else None
        if r and pr and float(pr) > 1:
            out[k] = (float(pr), r)
    return out


def _other(key: str) -> str:
    """Line id the side belongs to: '1x2', 'ou2.5', or 'SB:<id>|<spec>'."""
    return key.rsplit("|", 1)[0] if key.startswith("SB:") else key.split(":")[0]


def records(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        res = r.get("result") or {}
        first = (r.get("first") or {}).get("p") or (r.get("last") or {}).get("p")
        if r.get("sport") != "football" or res.get("after_90") or res.get("h") is None or not first:
            continue
        look = ((r.get("xm") or {}).get("first")) or xm.summary(first)
        if not look:
            continue
        last = (r.get("last") or {}).get("p") or {}
        seen_twice = (r.get("last") or {}).get("at") != (r.get("first") or {}).get("at")
        close = _fair_map(last) if seen_twice else {}
        own = _fair_map(first)
        for k, (price, rule) in _rules(first).items():
            s = xm.side_of(look, k)
            if s is None:
                continue
            outcome = rule(int(res["h"]), int(res["a"]))
            ret = price - 1 if outcome == "win" else (0.0 if outcome == "push" else -1.0)
            out.append({"id": r.get("id"), "ko": r.get("ko"), "key": k, "line": _other(k),
                        "family": k.split(":")[0] if not k.startswith("SB:") else k.split("|")[0],
                        "price": price, "ev": s[2], "ret": ret,
                        "gap": s[0] + s[1] - own[k] if k in own else None,
                        "clv": price * close[k] - 1 if k in close else None})
    return out


def _agg(rs: list[dict]) -> dict:
    n = len(rs)
    if not n:
        return {"n": 0}
    rets = [x["ret"] for x in rs]
    mean = sum(rets) / n
    sd = math.sqrt(sum((v - mean) ** 2 for v in rets) / max(n - 1, 1))
    clvs = [x["clv"] for x in rs if x["clv"] is not None]
    return {"n": n, "ret": mean, "se": sd / math.sqrt(n), "won": sum(x["ret"] > 0 for x in rs) / n,
            "clv": sum(clvs) / len(clvs) if clvs else None, "n_clv": len(clvs)}


def _fmt(a: dict) -> str:
    if not a.get("n"):
        return "| 0 | | | |"
    clv = f"{a['clv']:+.1%} ({a['n_clv']})" if a["clv"] is not None else "—"
    star = " **" if abs(a["ret"]) > 2 * a["se"] else ""
    return f"| {a['n']} | {a['won']:.1%} | {a['ret']:+.1%} ± {a['se']:.1%}{star} | {clv} |"


def _singles(by_event: dict[str, dict]) -> list[dict]:
    out = []
    for f in sorted((ROOT / "output" / "picks").glob("picks_*.json")):
        try:
            doc = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for s in doc.get("singles") or []:
            row = by_event.get(str(s.get("sb_event_id")))
            if not row or s.get("result") not in ("won", "lost", "void", "push"):
                continue
            first = (row.get("first") or {}).get("p") or {}
            parsed = fm.parse_key(s.get("market") or "")
            rule = fm.rule_for(*parsed) if parsed else None
            fit = xm.fit(first) if rule else None
            if fit is None:
                continue
            side = fm.evaluate(fit["matrix"], rule)
            price = float(s.get("price") or 0)
            ret = price - 1 if s["result"] == "won" else (-1.0 if s["result"] == "lost" else 0.0)
            out.append({"ko": row.get("ko"), "ev": price * side[0] + side[1] - 1, "ret": ret,
                        "clv": None})   # the single's own clv field is in other units
    return out


def main() -> str:
    rows = [r for r in uv.load_graded() if r.get("sport") == "football"]
    recs = records(rows)
    kos = sorted({x["ko"] for x in recs if x["ko"]})
    cut = kos[len(kos) // 2] if kos else ""
    early = [x for x in recs if x["ko"] < cut and x["gap"] is not None]
    late = [x for x in recs if x["ko"] >= cut and x["gap"] is not None]
    best_t, best = None, -9.0
    for t in THRESHOLDS:
        a = _agg([x for x in early if x["gap"] > t])
        if a["n"] >= MIN_N and a["ret"] > best:
            best_t, best = t, a["ret"]
    t = best_t if best_t is not None else 0.0
    soft_lines = {(x["id"], x["line"]) for x in late if x["gap"] > t}
    soft = [x for x in late if x["gap"] > t]
    other = [x for x in late if (x["id"], x["line"]) in soft_lines and x["gap"] <= t]
    L = [f"# MARKET CONSISTENCY STUDY — {datetime.now(UTC):%Y-%m-%dT%H:%MZ}", "",
         "To-do #7 idea 1, RECORDED ONLY. Joint Dixon-Coles grid fitted to SportyBet's own de-vigged "
         "1X2, O/U 1.5/2.5/3.5 and BTTS at the FIRST look; gap = the grid's chance - the side's own "
         "de-vigged chance (> 0: the book prices this side longer than its other markets say). "
         f"{len({x['id'] for x in recs})} graded games, {len(recs)} priced sides; later half starts at "
         f"kick-off {cut}. Threshold chosen on the earlier half (n >= {MIN_N}): **gap > {t:+.0%}**.", "",
         "## Earlier half (choosing the threshold)", "",
         "| gap > | n | landed | return | CLV (n) |", "|---|---|---|---|---|"]
    L += [f"| {th:+.0%} " + _fmt(_agg([x for x in early if x["gap"] > th])) for th in THRESHOLDS]
    L += ["", "## Later half — the verdict (both sides)", "",
          "| set | n | landed | return | CLV (n) |", "|---|---|---|---|---|",
          "| every side " + _fmt(_agg(late)),
          f"| soft side (gap > {t:+.0%}) " + _fmt(_agg(soft)),
          "| other side of those lines " + _fmt(_agg(other)),
          f"| gap <= {t:+.0%} (all) " + _fmt(_agg([x for x in late if x["gap"] <= t])),
          "| ev > 0 (beats the margin too) " + _fmt(_agg([x for x in late if x["ev"] > 0])),
          "| CONTROL: every side priced 1.20-2.00 " + _fmt(_agg([x for x in late if 1.2 <= x["price"] <= 2.0])),
          f"| soft side (gap > {t:+.0%}) priced 1.20-2.00 "
          + _fmt(_agg([x for x in soft if 1.2 <= x["price"] <= 2.0])),
          "| other side priced 1.20-2.00 " + _fmt(_agg([x for x in other if 1.2 <= x["price"] <= 2.0]))]
    fams: dict[str, list[dict]] = defaultdict(list)
    for x in soft:
        fams[x["family"]].append(x)
    L += ["", f"### Later half, soft sides by market (gap > {t:+.0%}, n >= 30)", "",
          "| market | n | landed | return | CLV (n) |", "|---|---|---|---|---|"]
    L += [f"| {f} " + _fmt(_agg(v)) for f, v in sorted(fams.items(), key=lambda kv: -len(kv[1])) if len(v) >= 30]
    by_event = {str(r.get("id")): r for r in rows}
    sg = _singles(by_event)
    if sg:
        L += ["", "## Board singles joined by event (all dates; read, not chosen on)", "",
              "| set | n | landed | return | CLV (n) |", "|---|---|---|---|---|",
              "| pick ev > 0 (grid chance x board price) " + _fmt(_agg([x for x in sg if x["ev"] > 0])),
              "| pick ev <= 0 " + _fmt(_agg([x for x in sg if x["ev"] <= 0]))]
    L += ["", "** = return more than 2 standard errors from zero. Nothing here changes a stake; wiring "
          "this into picks or stakes needs the Architect's OK after out-of-sample gains.", ""]
    OUT.write_text("\n".join(L), encoding="utf-8")
    return f"{len(recs)} sides, threshold gap > {t:+.0%}, later half soft n={len(soft)}"


if __name__ == "__main__":
    print(main())
