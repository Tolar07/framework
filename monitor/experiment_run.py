"""
EXPERIMENT RUN — score every registered strategy in shadow and apply any
promotion / demotion (engine/experiments.py), before the board is built.

    python monitor/experiment_run.py [--dry] [--no-telegram]

Reads output/picks/ (the board's candidates, graded), output/reasoning/ and
data/universe/ (the paper rules). Writes memory/strategies.json (who is live per
slot + standings) and appends every change to memory/strategy_log.jsonl; one
Telegram line to the Architect per change. --dry prints and writes nothing.
"""
from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from engine import experiments as X  # noqa: E402


def _ins(r: dict) -> str:
    """In-sample (before the rule was written): shown, never counted."""
    s = r["in_sample"]
    if s["n"] == r["counted"]["n"] or s["roi"] is None:
        return ""
    return f"  [in-sample, not counted: {s['n']} bets, {s['roi']:+.1%}]"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="OLP XDV experiment engine")
    ap.add_argument("--dry", action="store_true", help="print standings; write and send nothing")
    ap.add_argument("--no-telegram", action="store_true")
    a = ap.parse_args(argv)
    today = datetime.now(UTC).date().isoformat()
    days = X.load_days()
    try:
        from engine import universe as uv
        rows = [r for r in uv.load_graded() if r.get("result")]
    except Exception as err:  # noqa: BLE001 — the board rules still run without the paper book
        print(f"universe not read ({err}) — paper rules scored as empty")
        rows = []
    try:
        contexts = X._postmortem().contexts(days)
    except ImportError:
        contexts = None
    reg, events = X.evaluate(days, X.universe_bets(rows), X.load_registry(), today, contexts)
    print(f"engine {'ON' if X.enabled() else 'OFF (OLP_EXPERIMENTS=off)'} · {len(days)} board days · "
          f"{len(rows)} universe games")
    for name, r in sorted(reg["standings"].items(), key=lambda kv: (kv[1]["slot"], kv[1]["status"] != "LIVE")):
        c = r["counted"]
        roi = f"{c['roi']:+.1%}" if c["roi"] is not None else "—"
        clv = f"{c['clv']:+.2%}" if c["clv"] is not None else "—"
        print(f"  [{r['slot']}] {r['status']:6} {name}: {c['n']} bets, return {roi}, CLV {clv} "
              f"({c['n_clv']} closes) — {r.get('vs_live', 'live')}" + _ins(r))
    for ev in events:
        print("EVENT", X.telegram_line(ev))
    if a.dry:
        return 0
    X.save(reg, events)
    if events and not a.no_telegram:
        try:
            from output.notify import send_architect
            send_architect("\n".join(X.telegram_line(ev) for ev in events))
        except Exception as err:  # noqa: BLE001 — the log already holds the change
            print(f"telegram not sent: {err}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
