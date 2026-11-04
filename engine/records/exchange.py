"""
EXCHANGE — step 2 of the edge plan (Architect 2026-11-04), RECORDED ONLY. Every board single
gets the Matchbook exchange's fair chance for the same bet at the moment the board is written
(engine/exchange.py), so the edge is measured at entry, not only at the close.

single["exchange"]:
    p        the exchange's fair chance (no margin), None on a thin book
    back     Matchbook's best back, before its 2% commission; lay, liq (£ at the best back)
    gap      price x p - 1: SportyBet's price against the fair chance (> 0 = SportyBet beats it)
    mb_net   Matchbook's back after commission
    best     "sportybet" / "matchbook": which book pays more for this pick

A pick whose market the exchange does not list, or whose fixture it does not carry, gets no
block (HR35). The exchange close (p1) and the result are joined later by
monitor/edge_scoreboard.py from the edge book (engine/edge_book.py).
"""
from __future__ import annotations

from datetime import UTC, datetime

from engine import exchange as ex
from engine.records._common import num, singles, when

MB_COMMISSION = 0.02
_EVENTS: list[dict] | None = None


def events() -> list[dict]:
    """One Matchbook read per process; a failed read is remembered as empty (no retry storm)."""
    global _EVENTS
    if _EVENTS is None:
        try:
            _EVENTS = ex.fetch_events()
        except Exception:  # noqa: BLE001 — no exchange price is a missing label, never a failure
            _EVENTS = []
    return _EVENTS


def record(s: dict, evs: list[dict]) -> dict | None:
    price = num(s.get("price"))
    ko = when(s.get("kickoff_utc"))
    if not price or ko is None or not s.get("market"):
        return None
    e = ex.match_event(s.get("home") or "", s.get("away") or "", ko, evs)
    if e is None:
        return None
    b = ex.quote(s["market"], ex.index_event(e))
    if not b:
        return None
    p, back = b.get("p"), b.get("back")
    net = round(1 + (back - 1) * (1 - MB_COMMISSION), 3) if back else None
    return {"p": p, "back": back, "lay": b.get("lay"), "liq": b.get("liq"),
            "gap": round(price * p - 1, 4) if p else None, "mb_net": net,
            "best": None if net is None else "sportybet" if price >= net else "matchbook"}


def annotate_doc(doc: dict, target: str, now: datetime | None = None) -> str:
    """Only picks not yet kicked off and not yet priced: a later ledger write (grading, a
    replay in backtest/records_study.py) keeps the entry price and never reads in-play."""
    now = now or datetime.now(UTC)
    todo = [s for s in singles(doc) if "exchange" not in s
            and (ko := when(s.get("kickoff_utc"))) is not None and ko > now]
    if not todo:
        return "exchange: nothing to price"
    evs = events()
    n = 0
    for s in todo:
        r = record(s, evs)
        if r:
            s["exchange"] = r
            n += 1
    return f"exchange {n} of {len(todo)}"
