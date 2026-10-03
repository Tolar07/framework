"""Live-watch for Club Friendlies — a test of the live-monitor machinery.

Polls TheSportsDB (lookupevent) for today's Club Friendlies and renders each
event's state: NOT STARTED (with kickoff countdown) -> LIVE (in-play, score
when the source provides it) -> FT (settled into the sandbox ledger).

HONESTY: a live match with no in-play score reads "LIVE — no in-play score
from source (NO DATA)", never a fabricated running score. A result is taken
from the source at FT, never guessed.
"""
from __future__ import annotations

import datetime
import json
import time
from typing import Callable, Optional
from urllib import request

from sandbox import friendlies

KEY = friendlies.KEY


def day_friendlies(day: str | None = None) -> list[dict]:
    """All Club Friendlies on the given day (today) from TheSportsDB eventsday."""
    day = day or datetime.date.today().isoformat()
    url = (f"{friendlies.API_BASE}/{KEY}/eventsday.php?d={day}&l="
           f"{friendlies.CLUB_FRIENDLIES_ID}")
    try:
        return (_json(url)).get("events") or []
    except Exception:
        return []


def _json(url: str):
    with request.urlopen(url, timeout=15) as r:
        return json.load(r)


def _lookup(eid: str) -> dict:
    d = _json(f"{friendlies.API_BASE}/{KEY}/lookupevent.php?id={eid}")
    return (d.get("events") or [{}])[0]


def state_of(ev: dict) -> tuple[str, Optional[str], str]:
    """(state, score, note) for one TheSportsDB friendly event."""
    status = (ev.get("strStatus") or "").strip().upper()
    ts = ev.get("strTimestamp") or ""
    hs, as_ = ev.get("intHomeScore"), ev.get("intAwayScore")
    if status in ("NS", "NOT STARTED", ""):
        # not started yet — countdown if we know the kickoff (TheSportsDB times are UTC)
        try:
            ko = datetime.datetime.fromisoformat(ts)
            if ko.tzinfo is None:
                ko = ko.replace(tzinfo=datetime.timezone.utc)
            mins = int((ko - datetime.datetime.now(datetime.timezone.utc)).total_seconds() // 60)
            note = f"kickoff in {mins} min" if mins > 0 else "about to start"
        except ValueError:
            note = "kickoff time unknown (NO DATA)"
        return "NOT STARTED", None, note
    if status in ("CANC", "CANCELLED", "CANCELED", "POSTPONED",
                  "ABANDONED", "SUSPENDED", "DELAYED"):
        return "CANCELLED", None, "not played"
    if status in ("FT", "FINISHED", "MATCH FINISHED", "FULL TIME"):
        score = f"{hs}-{as_}" if hs is not None and as_ is not None else None
        return "FT", score, "final"
    # anything else (1H/2H/HT/IN PLAY/...): genuinely in play
    score = f"{hs}-{as_}" if hs is not None and as_ is not None else None
    note = f"LIVE {score}" if score else "LIVE — no in-play score from source (NO DATA)"
    return "LIVE", score, note


def _line(ev: dict) -> str:
    state, score, note = state_of(ev)
    name = ev.get("strEvent") or ev.get("strHomeTeam") or "?"
    return f"  {state:11s} {name:34s} {note}"


def live_watch(interval: int, settle: Optional[Callable[[str, str, str], int]] = None,
               hours: int = 16) -> int:
    """Poll today's Club Friendlies every `interval` seconds; print the board on
    state/score change; call settle(eid, score, state) at FT. Returns how many
    matches reached FT."""
    today = datetime.date.today().isoformat()
    deadline = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=hours)
    last = None
    finished = 0
    while datetime.datetime.now(datetime.timezone.utc) < deadline:
        evs = day_friendlies(today)
        if not evs:
            print("[%s UTC] no Club Friendlies on record for today — NO DATA — PENDING"
                  % datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M"), flush=True)
            time.sleep(interval)
            continue
        block = [f"[{datetime.datetime.now(datetime.timezone.utc).strftime('%H:%M')} UTC] "
                 f"Club Friendlies — {len(evs)} event(s) today"]
        pending = False
        for ev in sorted(evs, key=lambda e: e.get("strTimestamp") or ""):
            state, score, _ = state_of(ev)
            if state != "FT":
                pending = True
            block.append(_line(ev))
            if state == "FT" and settle:
                eid = str(ev.get("idEvent"))
                n = settle(eid, score or "", state)
                if n:
                    block.append(f"        -> settled {n} prediction row(s): {score}")
                    finished += 1
        text = "\n".join(block)
        if text != last:
            print(text, flush=True)
            last = text
        if not pending:
            print("\nAll today's friendlies settled.", flush=True)
            return finished
        time.sleep(interval)
    return finished
