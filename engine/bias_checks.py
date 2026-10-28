"""
BIAS CHECKS — to-do #7 idea 2 (RECORDED ONLY, changes no stake, no threshold, no pick).

How does SportyBet's price for this kind of side usually do? From every graded universe game BEFORE
the board date (data/universe, engine.universe.all_records — every side of every market, both
sports), each (sport, market id, price band) cell keeps:

    n, landed       sides settled and the share that won
    fair            the mean de-vigged chance SportyBet gave them
    bias            landed - fair: > 0 the book has been pricing this kind of side too long
                    (favourite-longshot bias shows up here band by band)
    ret             flat 1-unit return at the price
    shrunk          bias * n / (n + SHRINK_N): a thin cell says little

Markets are yes/no, so each pick carries its own side ("yes") and the other side of the line
("no", priced at the complement of the pick's chance) — and `short_leg` marks a leg under 1.30,
the band the tipster-slip study found underperforms. Public-team bias needs public-money data the
framework does not have; it is listed as missing in docs/REASONING_IDEAS_AUDIT.md.

Where it writes: engine/picks_ledger.write_ledger adds single["bias"] to every board single (and
study / dropped single). Nothing reads it to pick or stake; backtest/bias_checks_study.py measures
it walk-forward. Wiring it into stakes needs the Architect's OK after out-of-sample gains.
"""
from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable

BANDS = (1.01, 1.20, 1.30, 1.50, 1.75, 2.00, 2.50, 4.00, 1000.0)
SHRINK_N = 200
SHORT_LEG = 1.30
MIN_CELL = 30


def band(price: float | None) -> str | None:
    if price is None:
        return None
    try:
        x = float(price)
    except (TypeError, ValueError):
        return None
    for lo, hi in zip(BANDS, BANDS[1:], strict=False):
        if lo <= x < hi:
            return f"{lo:.2f}-{hi:.2f}" if hi < 1000 else f"{lo:.2f}+"
    return None


def family(key: str) -> str:
    """'SB:18|total=1.5|Over 1.5' -> 'SB:18'; basketball 'total|155.5|over' -> 'total'."""
    return key.split("|", 1)[0]


def records(rows: Iterable[dict]) -> list[dict]:
    """Every settled side of every graded game, with its sport and kick-off."""
    from engine import universe as uv
    out = []
    for r in rows:
        for rec in uv.all_records(r, "first"):
            if rec.get("fair") is None or not rec.get("price"):
                continue
            out.append({**rec, "sport": r.get("sport"), "ko": r.get("ko") or ""})
    return out


def table(recs: Iterable[dict], before: str | None = None) -> dict[str, dict]:
    """Cells keyed 'sport|family|band' and 'sport|*|band' from records that kicked off before
    `before` (ISO date or datetime string; None = all)."""
    acc: dict[str, list[float]] = defaultdict(lambda: [0, 0, 0.0, 0.0])
    for r in recs:
        if before and r["ko"] >= before:
            continue
        b = band(r["price"])
        if b is None:
            continue
        ret = r["price"] - 1 if r["won"] else -1.0
        for k in (f"{r['sport']}|{family(r['key'])}|{b}", f"{r['sport']}|*|{b}"):
            a = acc[k]
            a[0] += 1
            a[1] += r["won"]
            a[2] += r["fair"]
            a[3] += ret
    out = {}
    for k, (n, won, fair, ret) in acc.items():
        landed, f = won / n, fair / n
        bias = landed - f
        out[k] = {"n": int(n), "landed": round(landed, 4), "fair": round(f, 4), "bias": round(bias, 4),
                  "se": round(math.sqrt(max(f * (1 - f), 1e-6) / n), 4), "ret": round(ret / n, 4),
                  "shrunk": round(bias * n / (n + SHRINK_N), 4)}
    return out


def cell(tab: dict, sport: str, key: str, price: float | None) -> dict | None:
    """The pick's family cell, or the all-markets cell of its band when the family is thin."""
    b = band(price)
    if b is None:
        return None
    c = tab.get(f"{sport}|{family(key)}|{b}")
    if c and c["n"] >= MIN_CELL:
        return {"cell": f"{family(key)}|{b}", **c}
    c = tab.get(f"{sport}|*|{b}")
    return {"cell": f"*|{b}", **c} if c else None


def annotate(single: dict, tab: dict, sport: str = "football") -> dict | None:
    """single["bias"]: the pick's side ("yes") and the other side of the line ("no")."""
    key, price = single.get("market") or "", single.get("price")
    try:
        p = float(price)
    except (TypeError, ValueError):
        return None
    if p <= 1:
        return None
    no_price = 1 / (1 - 1 / p) if p > 1.0001 else None     # the complement of the pick's chance
    return {"yes": cell(tab, sport, key, p), "no": cell(tab, sport, key, no_price),
            "short_leg": p < SHORT_LEG}


_TAB: dict[str, dict] = {}


def annotate_doc(doc: dict, target: str) -> str:
    """Add single["bias"] to every single-shaped list of a picks doc; the table holds only games
    that kicked off before `target`. Never raises."""
    try:
        if target not in _TAB:
            from engine import universe as uv
            _TAB.clear()
            _TAB[target] = table(records(r for r in uv.load_graded() if r.get("sport") == "football"),
                                 before=target)
        tab = _TAB[target]
        n = 0
        for slot in ("singles", "study", "singles_dropped"):
            for s in doc.get(slot) or []:
                b = annotate(s, tab)
                if b:
                    s["bias"] = b
                    n += 1
        return f"bias recorded {n}"
    except Exception as e:  # noqa: BLE001 — the ledger is always written
        return f"bias skipped ({str(e)[:60]})"
