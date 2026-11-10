"""
WORLD BASKETBALL EVERY-MARKET RECORD - twin of engine/nba_markets.py for NCAA (2 x 20-min halves) and the
other world leagues (framework#394; Architect 2026-11-06: "NBA and basketball, they're the same thing ...
inherit all its attributes of NBA").

RECORD-ONLY. Nothing here changes a pick, a stake, a threshold or a code. On every edge-book look
(monitor/edge_run.py, ~30 min) each non-NBA basketball game kicking off within WINDOW has SportyBet's whole
market page read (engine/nba_markets.full_event / compact_markets, reused) and appended to

    output/world_basketball/wb_markets_<UTC date>.jsonl     one line per game per look

NCAA games also carry ESPN's sharp line (engine/ncaa_lines.py) and the ESPN game id they settle on. The look is
graded after the game from ESPN's final and its two half scores (settle_ncaa): winner, handicap, total, 1st-half
total / handicap / 1X2 / odd-even and team points in the 1st half. A market whose rule is not confirmed
(2nd half: overtime in or out?) is counted but never graded - PENDING, not a guess (HR35).
EuroLeague / FIBA / other leagues are recorded too, but there is no free result feed with period scores for
them, so their looks stay PENDING (never an invented score, HR59). backtest/wb_market_study.py reads the record.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from engine import exchange as ex
from engine import nba_markets as nm
from engine import nba_value as nv
from engine import ncaa_lines as nl
from engine import world_basketball as wb

WINDOW = wb.WINDOW


def is_ncaa(row: dict) -> bool:
    return "ncaa" in (row.get("comp") or "").lower()


def path_for(day: str, folder: Path = wb.OUT_DIR) -> Path:
    return folder / f"wb_markets_{day}.jsonl"


def _espn_game(row: dict, ko: datetime) -> dict | None:
    return nl.match(row["home"], row["away"], ko, nl.games(ko) + nl.games(ko - timedelta(days=1)))


def snapshot(row: dict, now: datetime, reader=None, espn=None) -> dict | None:
    """One look at one game: every market plus (NCAA) the ESPN game and sharp line. None = unreadable page."""
    reader = reader or nm.full_event
    try:
        markets = nm.compact_markets(reader(str(row["id"])))
    except Exception:  # noqa: BLE001 - a page that will not load is a missing look, never a fake one
        return None
    if not markets:
        return None
    ko = ex._dt(row.get("ko"))
    g = ln = None
    if is_ncaa(row) and ko is not None:
        try:
            g = (espn or _espn_game)(row, ko)
            ln = nl.line(g) if g else None
        except Exception:  # noqa: BLE001 - no sharp line is PENDING, not a guess
            g = ln = None
    return {"at": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "event_id": str(row["id"]), "comp": row.get("comp"),
            "tip": row.get("ko"), "home": row.get("home"), "away": row.get("away"),
            "espn_id": g["id"] if g else None, "sharp": ln, "markets": markets}


def update(rows: list[dict], now: datetime, folder: Path = wb.OUT_DIR, reader=None, espn=None) -> int:
    """Append one look per upcoming non-NBA basketball game. Returns how many looks were saved."""
    kept = []
    for r in rows:
        if r.get("sport") != "basketball" or r.get("covered"):
            continue
        ko = ex._dt(r.get("ko"))
        if ko is None or not now < ko <= now + WINDOW:
            continue
        s = snapshot(r, now, reader, espn)
        if s:
            kept.append(s)
    if kept:
        folder.mkdir(parents=True, exist_ok=True)
        with path_for(now.strftime("%Y-%m-%d"), folder).open("a", encoding="utf-8") as f:
            for s in kept:
                f.write(json.dumps(s, separators=(",", ":")) + "\n")
    return len(kept)


def load(folder: Path = wb.OUT_DIR) -> list[dict]:
    rows = []
    for p in sorted(folder.glob("wb_markets_*.jsonl")):
        rows += [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
    return rows


def last_looks(rows: list[dict]) -> list[dict]:
    """Each game's last look taken before tip-off."""
    best: dict[str, dict] = {}
    for r in rows:
        if not r.get("tip") or nm._t(r["at"]) >= nm._t(r["tip"]):
            continue
        if r["event_id"] not in best or nm._t(r["at"]) > nm._t(best[r["event_id"]]["at"]):
            best[r["event_id"]] = r
    return list(best.values())


# -- results: ESPN men's college scoreboard, final + two halves ---------------------------------------------
def finals(day: datetime) -> dict[str, dict]:
    """{espn id: {hs, as, h1: (home, away), ot}} for the COMPLETED games of one US date."""
    blob = nl._get(nl._SB.format(d=day.strftime("%Y%m%d"))) or {}
    out = {}
    for e in blob.get("events") or []:
        comp = (e.get("competitions") or [{}])[0]
        if not ((comp.get("status") or {}).get("type") or {}).get("completed"):
            continue
        t = {c.get("homeAway"): c for c in comp.get("competitors") or []}
        try:
            hs, as_ = int(t["home"]["score"]), int(t["away"]["score"])
            lh = [int(x["value"]) for x in t["home"].get("linescores") or []]
            la = [int(x["value"]) for x in t["away"].get("linescores") or []]
        except (KeyError, TypeError, ValueError):
            continue
        if len(lh) < 2 or len(la) < 2:
            continue
        out[str(e["id"])] = {"hs": hs, "as": as_, "h1": (lh[0], la[0]), "ot": len(lh) > 2 or len(la) > 2}
    return out


def settle_ncaa(mid: str, spec: str, outcome: str, g: dict, name: str = "") -> int | None:
    """1 won / 0 lost for an NCAA outcome whose rule is known, else None (PENDING)."""
    h1h, h1a = g["h1"]
    o = outcome.strip().lower()
    if mid in ("60", "64"):                       # 1st half 1X2 / draw no bet
        res = "home" if h1h > h1a else "away" if h1a > h1h else "draw"
        return None if (mid == "64" and res == "draw") else int(o == res)
    if mid == "74":                               # 1st half odd / even
        return int(o == ("odd" if (h1h + h1a) % 2 else "even"))
    if mid == "66":                               # 1st half handicap
        h = nv._line(spec, "hcp")
        if h is None:
            return None
        m = h1h - h1a + h
        return None if m == 0 else int(o.startswith("home") == (m > 0))
    if mid in ("68", "69", "70"):                 # 1st half total / team points: the NBA rules on a 2-long list
        r = nv.settle({"market_id": mid, "specifier": spec, "outcome": outcome}, g["hs"], g["as"],
                      [h1h, 0], [h1a, 0])
        return None if r is None else int(r == "won")
    if mid in ("219", "223", "225", "229"):       # whole game, overtime included
        return nm.settle_any(mid, spec, outcome, g["hs"], g["as"], None, None, name=name)
    return None


def grade(rows: list[dict], results: dict[str, dict]) -> tuple[list[dict], dict]:
    """([{event_id, mid, name, side, price, fair, model, won}], {'pending': n}) for every gradable outcome.
    Outcomes with no rule, or whose game has no ESPN result (every non-NCAA game), count as pending."""
    out, pending = [], 0
    for r in rows:
        g = results.get(str(r.get("espn_id"))) if r.get("espn_id") else None
        for m in r["markets"]:
            if not m.get("open", True) or any(p <= 1 for _d, p in m["outcomes"]):
                continue
            inv = sum(1 / p for _d, p in m["outcomes"])
            for desc, p in m["outcomes"]:
                w = settle_ncaa(m["id"], m.get("spec") or "", desc, g, m.get("name") or "") if g else None
                if w is None:
                    pending += 1
                    continue
                model = nl.fair(f"B:{m['id']}|{m.get('spec') or ''}|{desc}", r["sharp"]) if r.get("sharp") else None
                out.append({"event_id": r["event_id"], "mid": m["id"], "name": m.get("name") or m["id"],
                            "side": desc, "price": p, "fair": (1 / p) / inv, "model": model, "won": w})
    return out, {"pending": pending}
