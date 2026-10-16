"""Matchbook's public exchange prices beside SportyBet's, for every game the
universe sweep watches (Architect 2026-10-16: "integrate Matchbook into the
framework fully ... so we don't have any price mismatch or missing market";
bet365 is being retired, Matchbook replaces it).

Read without a login (Matchbook's public /edge/rest/events, back-lay, GBP).
For each SportyBet game this records Matchbook's best BACK price for the same
markets the sweep keeps (engine/universe.py `prices`), in the same shape:

  football    1x2 [home, draw, away] · ou1.5/ou2.5/ou3.5 [over, under] ·
              btts [yes, no] · dc [1X, 12, X2]
  basketball  win [home, away] · total [line, over, under] · hcp [line, home, away]
              (total / hcp at SportyBet's own main line — a line Matchbook
              does not list stays missing, never a neighbouring line)

A market Matchbook does not list, or lists with no back money, is left out:
the study counts it as "missing on Matchbook". Prices are what you would get
before Matchbook's 2% commission on winnings (COMMISSION).
"""
from __future__ import annotations

import json
import re
import time
import unicodedata
import urllib.request
from collections.abc import Callable
from datetime import datetime, timedelta
from difflib import SequenceMatcher

API = "https://api.matchbook.com/edge/rest/events"
SPORT_IDS = {"football": 15, "basketball": 4}
COMMISSION = 0.02
KICKOFF_TOLERANCE = timedelta(minutes=20)
_UA = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
_NOISE = {"fc", "cf", "sc", "ac", "afc", "fk", "sk", "cd", "ud", "club", "de", "the", "bc", "kk", "bk"}


def _get(url: str) -> dict:
    for i in range(3):
        try:
            req = urllib.request.Request(url, headers=_UA)  # noqa: S310 (fixed https URL)
            with urllib.request.urlopen(req, timeout=40) as r:  # noqa: S310 (fixed https URL)
                return json.loads(r.read())
        except Exception:  # noqa: BLE001 — retry, then report
            time.sleep(2 + 2 * i)
    raise RuntimeError("Matchbook feed unavailable")


def fetch(get: Callable[[str], dict] = _get, max_events: int = 1500) -> list[dict]:
    """Every open football and basketball event with prices (both sports, one pass)."""
    ids = ",".join(str(v) for v in SPORT_IDS.values())
    out: list[dict] = []
    while len(out) < max_events:
        d = get(f"{API}?sport-ids={ids}&states=open&include-prices=true&price-depth=1"
                f"&odds-type=DECIMAL&exchange-type=back-lay&currency=GBP&per-page=100&offset={len(out)}")
        evs = d.get("events") or []
        out += evs
        if not evs or len(out) >= int(d.get("total") or 0):
            break
    return out


# ── names ────────────────────────────────────────────────────────────────────
def _norm(name: str) -> str:
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    return " ".join(w for w in re.sub(r"[^a-z0-9 ]+", " ", s).split() if w not in _NOISE)


def alike(a: str, b: str) -> float:
    a, b = _norm(a), _norm(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    ta, tb = set(a.split()), set(b.split())
    return max(SequenceMatcher(None, a, b).ratio(), 0.9 * len(ta & tb) / min(len(ta), len(tb)))


def split_event(name: str) -> tuple[str, str]:
    """(home, away). Football 'Home vs Away'; US sports 'Away at Home'."""
    if " at " in name and " vs " not in name and " v " not in name:
        a, h = name.split(" at ", 1)
        return h.strip(), a.strip()
    for sep in (" vs ", " v "):
        if sep in name:
            h, a = name.split(sep, 1)
            return h.strip(), a.strip()
    return name, ""


def _dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _sport_of(e: dict) -> str | None:
    sid = e.get("sport-id")
    if sid is None:
        tags = {(t.get("type"), (t.get("name") or "").lower()) for t in e.get("meta-tags") or []}
        return "basketball" if ("SPORT", "basketball") in tags else "football" if ("SPORT", "soccer") in tags else None
    return next((k for k, v in SPORT_IDS.items() if int(sid) == v), None)


def match(row: dict, events: list[dict]) -> dict | None:
    """The Matchbook event for a universe row: kick-off within 20 min, both names
    close (each >= 0.5, together >= 1.3), the best one — else None."""
    ko = _dt(row.get("ko"))
    if ko is None:
        return None
    best, score = None, 0.0
    for e in events:
        if _sport_of(e) not in (None, row.get("sport")):
            continue
        st = _dt(e.get("start"))
        if st is None or abs(st - ko) > KICKOFF_TOLERANCE:
            continue
        eh, ea = split_event(e.get("name") or "")
        sh, sa = alike(row.get("home") or "", eh), alike(row.get("away") or "", ea)
        if min(sh, sa) >= 0.5 and sh + sa >= 1.3 and sh + sa > score:
            best, score = e, sh + sa
    return best


# ── prices ───────────────────────────────────────────────────────────────────
def _back(r: dict | None) -> float | None:
    if not r or r.get("status", "open") != "open":
        return None
    ps = [p for p in r.get("prices") or [] if p.get("side") == "back" and p.get("available-amount", 0) > 0]
    return max((float(p.get("decimal-odds") or p.get("odds")) for p in ps), default=None)


def _f(x) -> float | None:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def quote(e: dict, sport: str, sb: dict | None = None) -> dict:
    """Matchbook's best back prices for one event, in engine/universe.py's shape.
    `sb` (SportyBet's own prices for the game) gives the basketball lines to look up."""
    eh, ea = split_event(e.get("name") or "")
    out: dict = {}
    for m in e.get("markets") or []:
        if m.get("status", "open") != "open":
            continue
        name = (m.get("name") or "").strip().lower()
        rs = {(r.get("name") or "").strip().lower(): r for r in m.get("runners") or []}
        line = _f(m.get("handicap"))
        if sport == "football":
            if m.get("market-type") == "one_x_two":
                row = [_back(rs.get(eh.lower())), _back(rs.get("draw")), _back(rs.get(ea.lower()))]
                if all(row):
                    out["1x2"] = row
            elif name == "total" and line is not None and f"{line:g}" in ("1.5", "2.5", "3.5"):
                row = [_back(rs.get(f"over {line:g}")), _back(rs.get(f"under {line:g}"))]
                if all(row):
                    out[f"ou{line:g}"] = row
            elif m.get("market-type") == "both_to_score":
                row = [_back(rs.get("yes")), _back(rs.get("no"))]
                if all(row):
                    out["btts"] = row
            elif name == "double chance":
                row = [_back(rs.get(f"{eh} or draw".lower())), _back(rs.get(f"{eh} or {ea}".lower())),
                       _back(rs.get(f"draw or {ea}".lower()))]
                if all(row):
                    out["dc"] = row
        else:
            if m.get("market-type") == "money_line":
                row = [_back(rs.get(eh.lower())), _back(rs.get(ea.lower()))]
                if all(row):
                    out["win"] = row
            elif name == "total" and sb and sb.get("total") and line == sb["total"][0]:
                row = [_back(rs.get(f"over {line:g}")), _back(rs.get(f"under {line:g}"))]
                if all(row):
                    out["total"] = [line, *row]
            elif name == "handicap" and sb and sb.get("hcp"):
                want = sb["hcp"][0]                     # SportyBet's line, home-relative
                home = next((r for r in m.get("runners") or [] if _f(r.get("handicap")) == want
                             and alike((r.get("name") or "").rsplit(" ", 1)[0], eh) >= 0.8), None)
                away = next((r for r in m.get("runners") or [] if _f(r.get("handicap")) == -want
                             and alike((r.get("name") or "").rsplit(" ", 1)[0], ea) >= 0.8), None)
                if home and away and _back(home) and _back(away):
                    out["hcp"] = [want, _back(home), _back(away)]
    return out


def attach(pending: dict, now: datetime, events: list[dict] | None = None,
           get: Callable[[str], dict] = _get) -> str:
    """Put Matchbook's prices on every not-yet-started universe game: `mb_first`
    (kept) and `mb_last` (replaced each sweep). Returns a one-line note."""
    try:
        events = fetch(get) if events is None else events
    except Exception as e:  # noqa: BLE001 — Matchbook down never stops the sweep
        return f"Matchbook unavailable ({str(e)[:60]})"
    stamp = now.strftime("%Y-%m-%dT%H:%MZ")
    found = priced = 0
    for row in pending.values():
        ko = _dt(row.get("ko"))
        if ko is None or ko <= now:
            continue
        e = match(row, events)
        if e is None:
            continue
        found += 1
        p = quote(e, row.get("sport") or "football", (row.get("last") or {}).get("p"))
        if p:
            priced += 1
            snap = {"at": stamp, "id": e.get("id"), "p": p}
            row.setdefault("mb_first", snap)
            row["mb_last"] = snap
    return f"Matchbook: {len(events)} events, {found} games matched, {priced} priced"


def nba_back(events: list[dict], pick: dict) -> float | None:
    """Matchbook's best back for one NBA board pick (winner 219, handicap 223,
    total 225, at SportyBet's own line), or None when Matchbook doesn't list it."""
    e = match({"sport": "basketball", "home": pick.get("home"), "away": pick.get("away"),
               "ko": pick.get("tip")}, events)
    if e is None:
        return None
    mid, out = str(pick.get("market_id")), (pick.get("outcome") or "").lower()
    m = re.search(r"(?:hcp|total)=([+-]?\d+(?:\.\d+)?)", pick.get("specifier") or "")
    line = float(m.group(1)) if m else None
    if mid == "219":
        q = quote(e, "basketball").get("win")
        return (q[0] if out.startswith("home") else q[1]) if q else None
    if mid == "225" and line is not None:
        q = quote(e, "basketball", {"total": [line]}).get("total")
        return (q[1] if out.startswith("over") else q[2]) if q else None
    if mid == "223" and line is not None:
        q = quote(e, "basketball", {"hcp": [line]}).get("hcp")
        return (q[1] if out.startswith("home") else q[2]) if q else None
    return None                                   # team totals / periods: not on Matchbook


def nba_events(get: Callable[[str], dict] = _get) -> list[dict]:
    """Basketball events only (cheap: one or two pages); [] when Matchbook is down."""
    try:
        return [e for e in fetch(get) if _sport_of(e) in (None, "basketball")]
    except Exception:  # noqa: BLE001 — a missing Matchbook price never blocks a board
        return []
