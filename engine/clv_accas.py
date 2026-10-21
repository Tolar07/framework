"""
POSITIVE-CLV ACCAS (the Architect, 2026-10-21: keep the accas and megas, and also
"build from legs ... positive, then stake into"; "do both dynamically").

Closing-line value (entry price / closing price - 1) is the low-noise measure of an
edge: ~100 picks show it where profit needs ~2,500 at these prices. This builds up
to MAX_SLIPS extra accas from the day's deploy picks whose MARKET FAMILY has had a
positive mean CLV over the last WINDOW_DAYS, on at least MIN_N picks. The board's
own accas and megas are unchanged; these are booked beside them (section
"clv_accas" in the picks ledger), graded like the accas, and the SportyBet placer
places them first, weighted up. The family list is re-measured on every board, so
a family drops out as soon as its CLV turns negative ("dynamically").
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from statistics import mean

WINDOW_DAYS = 60
MIN_N = 50          # picks with a CLV before a family can count
MIN_LEGS, MAX_LEGS, MAX_SLIPS = 3, 4, 2


def family_clv(ledger_dir: Path, today: str) -> dict:
    """{family: {'n', 'clv'}} over the window; the ledger stores clv in percent."""
    from engine.learning import family
    since = (date.fromisoformat(today) - timedelta(days=WINDOW_DAYS)).isoformat()
    vals: dict = {}
    for path in sorted(Path(ledger_dir).glob("picks_*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not (since <= doc.get("date", "") < today):
            continue
        for s in doc.get("singles", []):
            if isinstance(s.get("clv"), (int, float)):
                vals.setdefault(family(s.get("market")), []).append(s["clv"] / 100)
    return {f: {"n": len(v), "clv": round(mean(v), 5)} for f, v in vals.items()}


def positive_families(stats: dict) -> set:
    return {f for f, s in stats.items() if s["n"] >= MIN_N and s["clv"] > 0}


def build(deploy: list, stats: dict) -> list[tuple]:
    """[(name, [(bf, pick, prob)], combo)] like the board's accas: one leg per fixture,
    the likeliest first, legs only from positive-CLV families."""
    from engine import markets as mkt
    from engine.learning import family
    ok = positive_families(stats)
    seen, legs = set(), []
    for bf in sorted(deploy, key=lambda b: -(b.best_model_prob or 0)):
        fx = bf.fixture.split(" (")[0]
        if (bf.probs is None or not bf.best_market_key or not bf.best_model_prob
                or fx in seen or family(bf.best_market_key) not in ok):
            continue
        seen.add(fx)
        legs.append((bf, mkt.display(bf.best_market_key, bf.probs.home_team, bf.probs.away_team),
                     bf.best_model_prob))
    out = []
    for i in range(MAX_SLIPS):
        group = legs[i * MAX_LEGS:(i + 1) * MAX_LEGS]
        if len(group) < MIN_LEGS:
            break
        combo = 1.0
        for _b, _p, q in group:
            combo *= q
        out.append((f"CLV acca {'AB'[i]}", group, combo))
    return out


def note(stats: dict, slips: list) -> str:
    fams = ", ".join(f"{f} {stats[f]['clv']:+.2%} over {stats[f]['n']}" for f in sorted(positive_families(stats)))
    return f"positive-CLV accas: {len(slips)} built from {fams or 'no family with positive CLV yet'}"
