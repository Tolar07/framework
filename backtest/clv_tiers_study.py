"""
CLV RELIABILITY TIERS (issue #295, the Architect 2026-11-04). RECORDED ONLY.

CLV (beating the closing price) is the best early signal of an edge ONLY where the closing price is itself
sharp: liquid, full-game markets that exchanges and sharp books also price. In part-game markets, combos,
exotics and small leagues the close carries little information, so a rule can look good on CLV and still lose.
Unabated, https://www.youtube.com/watch?v=MIkpsiJzbcA @ 03:20-08:15.

Every graded board single gets a tier from three tests:
    1. hidden information before the close: part-game markets (first half) fail -> C
    2. sharp shaping: is the market type one an exchange / sharp book prices (1X2, DC, DNB, AH, totals, BTTS)?
       no -> C (combos, exact goals, multigoals, team goals, clean sheets, odd/even)
    3. liquidity: a sharp-shaped market in a top league (Big-5, UEFA club cups, NBA) -> A, elsewhere -> B

Per tier: mean CLV, beat-the-close rate, flat (level-stake) return, and the walk-forward check the issue asks
for: does a rule's CLV in its EARLIER half predict its flat return in the LATER half? Reported per tier. A pick
tier (SAFE, VALUE, ...) whose CLV evidence is mostly tier C is flagged. Nothing here changes a pick, stake,
threshold or rule; missing CLV reads PENDING (HR35).

    python backtest/clv_tiers_study.py      -> backtest/CLV_TIERS_STUDY.md + memory/clv_tiers.json
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

LEDGER_DIR = ROOT / "output" / "picks"
OUT_MD = ROOT / "backtest" / "CLV_TIERS_STUDY.md"
OUT_JSON = ROOT / "memory" / "clv_tiers.json"
SHARP_SHAPED = {1, 10, 11, 16, 18, 29}            # 1X2, DC, DNB, Asian handicap, goals totals, BTTS
PART_GAME = {60, 63, 64, 68}                      # first-half markets (SportyBet ids; NBA 68 = 1st half total)
NBA_FULL = {219, 223, 225}                        # NBA winner, handicap, total
TOP_LEAGUES = ("Premier League", "LaLiga", "La Liga", "Bundesliga", "Serie A", "Ligue 1",
               "Champions League", "Europa League", "Conference League", "NBA")
WEAK_SHARE = 0.5                                  # a pick tier with more than this share of tier-C CLV is flagged
MIN_SPLIT = 10                                    # bets per half before the walk-forward check reads
MIN_CELLS = 5                                     # rule x market cells before a tier's correlation reads


def market_id(key: str | None) -> tuple[str, int | None]:
    if not key:
        return "?", None
    if key.startswith("NBA:"):
        mid = key[4:].split("|", 1)[0]
        return "NBA", int(mid) if mid.isdigit() else None
    pk = fm.parse_key(key)
    return "SB", (pk[0] if pk else None)


def tier(key: str | None, league: str | None) -> str:
    src, mid = market_id(key)
    if mid is None:
        return "PENDING"
    if mid in PART_GAME:
        return "C"
    sharp = mid in NBA_FULL if src == "NBA" else mid in SHARP_SHAPED
    if not sharp:
        return "C"
    top = src == "NBA" or any(t.lower() in (league or "").lower() for t in TOP_LEAGUES)
    return "A" if top else "B"


def _flat(b: dict) -> float | None:
    if b.get("result") == "won" and isinstance(b.get("price"), (int, float)):
        return float(b["price"]) - 1.0
    if b.get("result") == "lost":
        return -1.0
    return None


def collect(ledger_dir: Path = LEDGER_DIR) -> list[dict]:
    """Every graded board single with its tier, CLV (percent, PENDING if not recorded) and flat return."""
    out = []
    for path in sorted(ledger_dir.glob("picks_*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        day = doc.get("date") or path.stem[6:]
        for s in doc.get("singles") or []:
            f = _flat(s)
            if f is None:
                continue
            clv = s.get("clv")
            out.append({"day": day, "tier": tier(s.get("market"), s.get("league")),
                        "mid": "{}:{}".format(*market_id(s.get("market"))),
                        "rule": str(s.get("tier") or "unlabelled"), "flat": f,
                        "clv": float(clv) if isinstance(clv, (int, float)) and not isinstance(clv, bool) else None})
    return out


def _corr(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return None if not sx or not sy else sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True)) / (sx * sy)


def walk_forward(rows: list[dict]) -> dict:
    """Per (rule, market type) cell: CLV in the earlier half of days v flat return in the later half. Across cells,
    the correlation says whether CLV earned early predicts money made later in that tier."""
    cells: dict[str, list[tuple[float, float]]] = defaultdict(list)
    by: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        by[(r["rule"], r.get("mid"), r["tier"])].append(r)
    for (_, _, t), rs in by.items():
        days = sorted({r["day"] for r in rs})
        if len(days) < 2:
            continue
        cut = days[len(days) // 2]
        early = [r["clv"] for r in rs if r["day"] < cut and r["clv"] is not None]
        late = [r["flat"] for r in rs if r["day"] >= cut]
        if len(early) >= MIN_SPLIT and len(late) >= MIN_SPLIT:
            cells[t].append((sum(early) / len(early), sum(late) / len(late)))
    out = {}
    for t, v in sorted(cells.items()):
        c = _corr([a for a, _ in v], [b for _, b in v]) if len(v) >= MIN_CELLS else None
        out[t] = {"cells": len(v), "corr": None if c is None else round(c, 3)}
    return out


def build(rows: list[dict]) -> dict:
    tiers: dict[str, dict] = {}
    for t in ("A", "B", "C", "PENDING"):
        rs = [r for r in rows if r["tier"] == t]
        clv = [r["clv"] for r in rs if r["clv"] is not None]
        tiers[t] = {"bets": len(rs), "clv_n": len(clv),
                    "mean_clv_pct": None if not clv else round(sum(clv) / len(clv), 3),
                    "beat_close": None if not clv else round(sum(c > 0 for c in clv) / len(clv), 3),
                    "flat_return": None if not rs else round(sum(r["flat"] for r in rs) / len(rs), 4)}
    flags = []
    for rule in sorted({r["rule"] for r in rows}):
        rs = [r for r in rows if r["rule"] == rule and r["clv"] is not None]
        if len(rs) >= MIN_SPLIT:
            weak = sum(r["tier"] == "C" for r in rs) / len(rs)
            if weak > WEAK_SHARE:
                flags.append({"rule": rule, "clv_n": len(rs), "tier_c_share": round(weak, 3)})
    return {"built_at": datetime.now(UTC).isoformat(timespec="seconds"), "recorded_only": True,
            "issue": 295, "tiers": tiers, "walk_forward": walk_forward(rows), "weak_evidence_rules": flags}


def _fmt(x, pct=False) -> str:
    if x is None:
        return "PENDING"
    return f"{x:+.1%}" if pct else f"{x:+.2f}"


def report(rec: dict) -> str:
    L = ["# CLV RELIABILITY TIERS — where 'we beat the close' can be trusted (issue #295)", "",
         f"Built {rec['built_at']}. Recorded only: nothing here changes a pick, stake or rule.", "",
         "A = sharp-shaped full-game market in a top league · B = sharp-shaped, smaller league · "
         "C = part-game, combo or exotic market (the close knows little).", "",
         "| Tier | Bets | CLV readings | Mean CLV | Beat the close | Flat return |", "|---|---|---|---|---|---|"]
    for t, c in rec["tiers"].items():
        clv = "PENDING" if c["mean_clv_pct"] is None else f"{c['mean_clv_pct']:+.2f}%"
        beat = "PENDING" if c["beat_close"] is None else f"{c['beat_close']:.0%}"
        L.append(f"| {t} | {c['bets']} | {c['clv_n']} | {clv} | {beat} | {_fmt(c['flat_return'], pct=True)} |")
    L += ["", "## Does early CLV predict later profit? (walk-forward, per tier)", ""]
    wf = rec["walk_forward"]
    if not wf:
        L.append("PENDING — too few rule x market cells with 10+ bets in each half.")
    for t, w in wf.items():
        L.append(f"- Tier {t}: {w['cells']} rule x market cells, correlation {'PENDING' if w['corr'] is None else w['corr']}")
    L += ["", "## Rules whose CLV evidence is mostly tier C", ""]
    L += [f"- {f['rule']}: {f['tier_c_share']:.0%} of {f['clv_n']} CLV readings are tier C"
          for f in rec["weak_evidence_rules"]] or ["- none"]
    return "\n".join(L) + "\n"


def summary_line(rec: dict) -> str:
    a, c = rec["tiers"]["A"], rec["tiers"]["C"]
    return (f"CLV tiers: A {a['clv_n']} readings mean {_fmt(a['mean_clv_pct'])}% · C {c['clv_n']} readings mean "
            f"{_fmt(c['mean_clv_pct'])}% · {len(rec['weak_evidence_rules'])} rule(s) resting on weak-tier CLV")


def main() -> int:
    rec = build(collect())
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(rec, indent=1), encoding="utf-8")
    OUT_MD.write_text(report(rec), encoding="utf-8")
    print(summary_line(rec))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
