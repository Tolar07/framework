"""
SportyBet booking codes — turn a board pick into a real, loadable share code.

WHAT
  SportyBet's public order-share endpoint takes a set of selections and returns
  a `shareCode` (the "booking code") plus a share URL. Anyone can load that code
  on SportyBet to see the exact slip. This is NOT placing a bet: no stake, no
  account, no money moves — it is the shareable slip the Architect then reviews
  and deploys himself (config.assert_paper_only stays in force; nothing here
  clicks Place Bet).

HOW (HR35 — never fabricate)
  Outcome identifiers are read straight from the SAME cached SportyBet feed the
  odds source uses (pipeline.odds_sportybet), so a code is only ever built from
  IDs SportyBet actually served. If a fixture, market or outcome can't be
  resolved, or the share call fails, this returns None and the board shows
  "PENDING" — it never invents a code.

  Verified live 2026-09-30: share endpoint returns bizCode 10000 with a real
  shareCode for both single and multi-leg (acca) slips.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Optional

from engine import markets as mkt
from pipeline.odds_sportybet import (SPORTYBET_TOURNAMENT_ID, _UA, map_team,
                                     _load_all_events)

_SHARE_URL = "https://www.sportybet.com/api/ng/orders/share"

# Deployable market key -> (SportyBet market desc, specifier, outcome desc).
# Only the outcome DESC is used to look up the id in the live feed; the numeric
# ids are never hardcoded (SportyBet can renumber them).
_SB_MARKET = {
    mkt.HOME: ("1X2", "", "Home"),
    mkt.DRAW: ("1X2", "", "Draw"),
    mkt.AWAY: ("1X2", "", "Away"),
    mkt.OVER_25: ("Over/Under", "total=2.5", "Over 2.5"),
    mkt.UNDER_25: ("Over/Under", "total=2.5", "Under 2.5"),
}


def _event_index() -> Optional[dict]:
    """{(league, home_model_key, away_model_key): raw_event} from the cached
    SportyBet feed, team names mapped to model keys so they match board
    fixtures. None if the feed is unavailable (caller degrades to PENDING)."""
    try:
        by_tid, _ = _load_all_events()
    except Exception:  # noqa: BLE001 — no feed -> no codes, never a guess
        return None
    tid_to_league = {tid: lg for lg, tid in SPORTYBET_TOURNAMENT_ID.items()}
    index: dict = {}
    for tid, events in by_tid.items():
        league = tid_to_league.get(tid)
        if not league:
            continue
        for ev in events:
            home = map_team(league, (ev.get("homeTeamName") or "").strip())
            away = map_team(league, (ev.get("awayTeamName") or "").strip())
            index[(league, home, away)] = ev
    return index


def resolve_selection(event: dict, market_key: str) -> Optional[dict]:
    """A share-ready selection for one market on one event, or None if the
    market/outcome isn't in the feed for this event (HR35)."""
    spec = _SB_MARKET.get(market_key)
    if not spec:
        return None
    m_desc, specifier, o_desc = spec
    for m in event.get("markets", []):
        if m.get("desc") != m_desc or (m.get("specifier") or "") != specifier:
            continue
        for o in m.get("outcomes", []):
            if o.get("desc") == o_desc and o.get("id") is not None:
                return {"eventId": event.get("eventId"), "marketId": m.get("id"),
                        "specifier": specifier, "outcomeId": o.get("id")}
    return None


def create_booking_code(selections: list[dict]) -> tuple[Optional[str], Optional[str], str]:
    """POST selections to SportyBet's share endpoint.
    Returns (share_code, share_url, note). On any failure: (None, None, reason)
    so the board renders PENDING rather than a fabricated code."""
    if not selections:
        return None, None, "no resolvable selections"
    body = json.dumps({"selections": selections}).encode()
    req = urllib.request.Request(
        _SHARE_URL, data=body, method="POST",
        headers={"User-Agent": _UA, "Accept": "application/json",
                 "Content-Type": "application/json",
                 "Origin": "https://www.sportybet.com",
                 "Referer": "https://www.sportybet.com/ng/sport/football"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            resp = json.loads(r.read().decode("utf-8", "replace"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as e:
        return None, None, f"share call failed ({e})"
    if resp.get("bizCode") != 10000 or not resp.get("isAvailable", False):
        return None, None, f"share rejected: {resp.get('message', 'unknown')}"
    data = resp.get("data", {})
    code = data.get("shareCode")
    if not code:
        return None, None, "share returned no code"
    return code, data.get("shareURL"), f"{len(selections)} leg(s)"


def _legs_to_selections(index: dict, legs: list[tuple]) -> list[dict]:
    """legs: [(league, home, away, market_key), ...] -> resolved selections.
    Silently drops any leg that can't be resolved (partial slips are never
    passed off as complete — the caller checks the count)."""
    out = []
    for league, home, away, key in legs:
        ev = index.get((league, home, away))
        if ev is None:
            continue
        sel = resolve_selection(ev, key)
        if sel:
            out.append(sel)
    return out


def code_for_legs(index: Optional[dict],
                  legs: list[tuple]) -> tuple[Optional[str], Optional[str]]:
    """(share_code, share_url) for a set of legs, or (None, None). Requires
    EVERY leg to resolve — a code that silently dropped a leg would misrepresent
    the slip (HR35)."""
    if not index or not legs:
        return None, None
    sels = _legs_to_selections(index, legs)
    if len(sels) != len(legs):
        return None, None
    code, url, _ = create_booking_code(sels)
    return code, url
