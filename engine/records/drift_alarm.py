"""
DRIFT ALARM — to-do #7 idea 9 (RECORDED ONLY). Per market family, a two-sided CUSUM over the
board singles graded on boards before this one, in date order:

    down = max(0, down + (chance - won) - K)    the family lands less often than its chance says
    up   = max(0, up + (won - chance) - K)      ... more often (the other side of the same read)
    alarm "down" / "up" when either passes H

K = 0.02 and H = 2.0 were chosen on the earlier half by backtest/REASONING_IDEAS_STUDY.md (later
half: half stake under the alarm would have gained +1.91% +- 1.15% a pick). Recorded only:
single["drift"] = {"family", "n", "down", "up", "alarm"}; doc["drift"] = every family's state.
"""
from __future__ import annotations

from engine.records._common import graded_singles, num, singles

K = 0.02
H = 2.0
_STATE: dict[str, dict] = {}


def _family(market: str) -> str:
    try:
        from engine.learning import family
        return family(market)
    except Exception:  # noqa: BLE001 — a family is a label; fall back to the market id
        return str(market).split("|", 1)[0]


def states(rows: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for r in sorted(rows, key=lambda r: r["date"]):
        p = num(r.get("chance"))
        if p is None:
            continue
        won = 1.0 if r["result"] == "won" else 0.0
        st = out.setdefault(_family(r.get("market") or ""), {"n": 0, "down": 0.0, "up": 0.0})
        st["n"] += 1
        st["down"] = round(max(0.0, st["down"] + (p - won) - K), 4)
        st["up"] = round(max(0.0, st["up"] + (won - p) - K), 4)
    for st in out.values():
        st["alarm"] = "down" if st["down"] > H else ("up" if st["up"] > H else None)
    return out


def annotate_doc(doc: dict, target: str) -> str:
    if target not in _STATE:
        _STATE.clear()
        _STATE[target] = states(graded_singles(target))
    fams = _STATE[target]
    for s in singles(doc):
        f = _family(s.get("market") or "")
        s["drift"] = {"family": f, **fams.get(f, {"n": 0, "down": 0.0, "up": 0.0, "alarm": None})}
    doc["drift"] = fams
    return f"drift {sum(1 for v in fams.values() if v['alarm'])} alarms / {len(fams)} families"
