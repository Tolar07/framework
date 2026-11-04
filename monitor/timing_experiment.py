"""
TIMING EXPERIMENT — Matchbook (early) v Betfair (late) on the same picks (framework #259).

Matchbook backs a framework pick when it is published; betfair-agent (MAX_TO_KICKOFF = 3 h) backs
the same picks late, after line-ups. That is a free A/B test of placement timing on identical
selections. For every pick both bots hold this records entry time, hours to kick-off, entry price
and CLV per bot, and the mean CLV difference early minus late with a 90% band.

One closing price serves both bots: the Matchbook close the agent records (`clv` = entry / close - 1).
Betfair records no close of its own, so its CLV here is its entry price against that same Matchbook
close (a common yardstick, not Betfair's own close). A bet with no Matchbook CLV reads PENDING (HR35).

RECORD-ONLY. When n >= MIN_PROPOSE pairs and the band excludes 0 a `timing` proposal is written for
the Architect (move both bots to the better time). Nothing here changes a stake, price rule or timing.
Ratios and hours only: this repo is public, so no stake, money figure, code or bet id is written.

Called from monitor/bot_grader.py run(); writes data/bots/timing_experiment.json.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from monitor import bot_grader as bg
from monitor.rule_scorecard import mean_band

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "bots" / "timing_experiment.json"
MIN_PROPOSE = 100       # pairs before a timing proposal is opened
SAME_TEAM = 0.8         # name similarity for the same side of the same fixture


def _hours(placed: str | None, ko: str | None) -> float | None:
    try:
        t0 = datetime.fromisoformat(str(placed).replace("Z", "+00:00"))
        t1 = datetime.fromisoformat(str(ko).replace("Z", "+00:00"))
        if t0.tzinfo is None:
            t0 = t0.replace(tzinfo=UTC)
        if t1.tzinfo is None:
            t1 = t1.replace(tzinfo=UTC)
        return round((t1 - t0).total_seconds() / 3600, 2)
    except (TypeError, ValueError):
        return None


def _leg(b: dict) -> dict | None:
    legs = b.get("legs") or []
    return legs[0] if len(legs) == 1 and legs[0].get("key") else None


def _same(a: dict, b: dict) -> bool:
    la, lb = _leg(a), _leg(b)
    return bool(la and lb and a.get("date") == b.get("date") and la["key"] == lb["key"]
                and bg._alike(la.get("home", ""), lb.get("home", "")) >= SAME_TEAM
                and bg._alike(la.get("away", ""), lb.get("away", "")) >= SAME_TEAM)


def pairs(bets: list[dict]) -> list[tuple[dict, dict]]:
    """(Matchbook bet, Betfair bet) holding the same selection; each Matchbook bet pairs once."""
    live = [b for b in bets if not b.get("paper") and _leg(b)]
    mbs = [b for b in live if b.get("bot") == "matchbook"]
    out, used = [], set()
    for bf in (b for b in live if b.get("bot") == "betfair"):
        for i, mb in enumerate(mbs):
            if i not in used and _same(mb, bf):
                used.add(i)
                out.append((mb, bf))
                break
    return out


def row(mb: dict, bf: dict) -> dict:
    """One pair. clv_diff = early CLV - late CLV, both against the Matchbook close."""
    try:
        early = float(mb["clv"])
        close = float(mb["odds"]) / (1 + early)
        late = float(bf["odds"]) / close - 1
    except (TypeError, ValueError, KeyError, ZeroDivisionError):
        early = late = None
    ko = (_leg(mb) or {}).get("ko")
    return {"date": mb.get("date"), "early_hours": _hours(mb.get("placed_at"), ko),
            "late_hours": _hours(bf.get("placed_at"), ko),
            "early_price": mb.get("odds"), "late_price": bf.get("odds"),
            "early_clv": None if early is None else round(early, 4),
            "late_clv": None if late is None else round(late, 4),
            "clv_diff": None if early is None or late is None else round(early - late, 4)}


def verdict(band: dict) -> str:
    if band["lo"] is None:
        return "PENDING"
    if band["lo"] > 0:
        return "early better"
    if band["hi"] < 0:
        return "late better"
    return "no difference shown"


def report_line(n_pairs: int, band: dict) -> str:
    if band["lo"] is None:
        return (f"Timing (Matchbook early v Betfair late, same picks): {n_pairs} pairs, {band['n']} with a close; "
                "mean CLV difference PENDING until 5 pairs have one.")
    return (f"Timing (Matchbook early v Betfair late, same picks): early minus late CLV {band['mean']:+.1%} "
            f"(90% band {band['lo']:+.1%} to {band['hi']:+.1%}, n={band['n']}) - {verdict(band)}.")


def proposal(band: dict) -> dict | None:
    if band["n"] < MIN_PROPOSE or band["lo"] is None or band["lo"] <= 0 <= band["hi"]:
        return None
    better = "early (publish time)" if band["lo"] > 0 else "late (about 3 h before kick-off)"
    return {"kind": "timing", "who": "matchbook v betfair",
            "line": f"TIMING: {band['n']} same-pick pairs, early minus late CLV {band['mean']:+.1%}, band "
                    f"{band['lo']:+.1%} to {band['hi']:+.1%}. Better time: {better}. Needs: your OK to move both bots.",
            "needs": "Architect sign-off to move both bots to the better time"}


def build(bets: list[dict], today: str) -> dict:
    rows = [row(mb, bf) for mb, bf in pairs(bets)]
    band = mean_band([r["clv_diff"] for r in rows if r["clv_diff"] is not None])
    return {"built_at": datetime.now(UTC).isoformat(timespec="seconds"), "as_of": today, "pairs": len(rows),
            "clv_diff": band, "verdict": verdict(band), "min_propose": MIN_PROPOSE,
            "proposal": proposal(band), "rows": rows[-200:], "report_line": report_line(len(rows), band)}


def save(doc: dict, path: Path = OUT) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=1), encoding="utf-8")


def load(path: Path = OUT) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
