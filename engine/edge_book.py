"""
EDGE BOOK — every SportyBet side beside the exchange's fair chance, all day, every game
(Architect 2026-11-04, steps 2-5 of "how the training turns into an edge"). RECORDED ONLY.

monitor/edge_run.py calls update() on every run (about every 30 min, the Oracle VM clock):
SportyBet's whole football + basketball list against Matchbook's open events. Per game, kept
in obs_<kick-off UTC date>.json.gz — in the Actions cache (data/cache/edge/) while the day is
being watched, then written to git once (data/edge/) when every game of the day has kicked off:

    events[<SportyBet event id>] = {sport, comp, country, covered, home, away, ko, mb,
                                    k: {<side key>: rec}}
    rec  s0 / s1     SportyBet's price, first and last look before kick-off
         p0 / p1     the exchange's fair chance, first and last look (p1 = the exchange close)
         b1 / l1 / q1  exchange best back, best lay, £ at the best back, last look
         t0 / t1     when (UTC, minutes)
         x           the GAP BOARD (step 3): the first look where SportyBet's price beat the
                     exchange's fair chance by GAP_MIN+ (s x p - 1), price SB_BAND, with
                     h  hours to kick-off (step 4, timing)
                     pm the exchange's move since the first look (p - p0; > 0: money came for it)
                     sm SportyBet's move since the first look (s / s0 - 1)

Only sides the exchange prices are kept (engine/exchange.canonical). Nothing is updated after
kick-off, so p1 is the last pre-match exchange price this job saw.
"""
from __future__ import annotations

import gzip
import json
from datetime import datetime
from pathlib import Path

from engine import exchange as ex

ROOT = Path(__file__).resolve().parent.parent
EDGE_DIR = ROOT / "data" / "edge"                 # finished days, in git (written once)
LIVE_DIR = ROOT / "data" / "cache" / "edge"       # days still being watched: the edge.yml Actions cache
GAP_MIN = 0.02
SB_BAND = (1.10, 5.00)


def path_for(day: str, folder: Path = LIVE_DIR) -> Path:
    return folder / f"obs_{day}.json.gz"


def _read(p: Path) -> dict | None:
    try:
        with gzip.open(p, "rt", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def load(day: str, live: Path = LIVE_DIR, final: Path = EDGE_DIR) -> dict:
    for folder in (live, final):
        p = path_for(day, folder)
        if p.exists():
            doc = _read(p)
            if doc is not None:
                return doc
    return {"day": day, "events": {}}


def save(doc: dict, folder: Path = LIVE_DIR) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    p = path_for(doc["day"], folder)
    with gzip.open(p, "wt", encoding="utf-8") as f:
        json.dump(doc, f, separators=(",", ":"), sort_keys=True)
    return p


def finalize(now: datetime, live: Path = LIVE_DIR, final: Path = EDGE_DIR) -> list[str]:
    """Move every day whose games have all kicked off (a UTC day before today) from the
    cache into git, once: a file rewritten every 30 min would bloat the repo's history."""
    moved = []
    today = now.strftime("%Y-%m-%d")
    for p in sorted(live.glob("obs_*.json.gz")) if live.exists() else []:
        day = p.name[4:14]
        if day < today:
            final.mkdir(parents=True, exist_ok=True)
            p.replace(final / p.name)
            moved.append(day)
    return moved


def load_all(live: Path = LIVE_DIR, final: Path = EDGE_DIR) -> dict[str, dict]:
    """Every day on record, the live copy winning over the finished one."""
    docs: dict[str, dict] = {}
    for folder in (final, live):
        for p in sorted(folder.glob("obs_*.json.gz")) if folder.exists() else []:
            doc = _read(p)
            if doc is not None:
                docs[p.name[4:14]] = doc
    return docs


def _stamp(now: datetime) -> str:
    return now.strftime("%Y-%m-%dT%H:%MZ")


def side_prices(row: dict) -> dict[str, float]:
    """{side key: SportyBet price} for one SportyBet game row (edge_run.sb_rows)."""
    return dict(row.get("sides") or {})


def update_event(ev: dict, sides: dict[str, float], idx: dict[str, dict], ko: datetime,
                 now: datetime) -> int:
    """Fold one look into one game's record. Returns how many sides were seen."""
    if now >= ko:
        return 0
    hours = round((ko - now).total_seconds() / 3600, 2)
    seen = 0
    k = ev.setdefault("k", {})
    for key, s in sides.items():
        b = ex.quote(key, idx)
        if not b or not s:
            continue
        p = b.get("p")
        rec = k.get(key)
        if rec is None:
            if p is None:
                continue                    # never priced fairly: not worth keeping yet
            rec = k[key] = {"s0": s, "p0": p, "t0": _stamp(now), "h0": hours, "x": None}
        if rec.get("p0") is None and p is not None:
            rec["p0"] = p
        rec.update({"s1": s, "t1": _stamp(now), "b1": b.get("back"), "l1": b.get("lay"), "q1": b.get("liq")})
        if p is not None:
            rec["p1"] = p
        seen += 1
        if rec.get("x") is None and p is not None and SB_BAND[0] <= s <= SB_BAND[1]:
            gap = s * p - 1
            if gap >= GAP_MIN:
                rec["x"] = {"at": _stamp(now), "h": hours, "s": s, "p": p, "g": round(gap, 4),
                            "pm": round(p - rec["p0"], 4) if rec.get("p0") is not None else None,
                            "sm": round(s / rec["s0"] - 1, 4) if rec.get("s0") else None}
    return seen


def update(docs: dict[str, dict], rows: list[dict], events: list[dict], now: datetime) -> dict:
    """Fold one sweep (SportyBet rows + Matchbook events) into the day files in `docs`
    ({day: doc}, created as needed). Returns counts."""
    by_sport: dict[str, list[dict]] = {}
    for e in events:
        by_sport.setdefault(e.get("_sport") or "football", []).append(e)
    stats = {"rows": len(rows), "matched": 0, "sides": 0, "new_gaps": 0}
    for r in rows:
        ko = ex._dt(r.get("ko"))
        if ko is None or ko <= now:
            continue
        day = ko.strftime("%Y-%m-%d")
        doc = docs.setdefault(day, {"day": day, "events": {}})
        ev = doc["events"].get(r["id"])
        mb = None
        if ev and ev.get("mb"):
            mb = next((e for e in by_sport.get(r["sport"], []) if e.get("id") == ev["mb"]), None)
        if mb is None:
            mb = ex.match_event(r["home"], r["away"], ko, by_sport.get(r["sport"], []))
        if mb is None:
            continue
        stats["matched"] += 1
        if ev is None:
            ev = doc["events"][r["id"]] = {k: r.get(k) for k in ("sport", "comp", "country", "covered", "home", "away")}
        ev["ko"], ev["mb"] = r["ko"], mb.get("id")
        before = sum(1 for x in ev.get("k", {}).values() if x.get("x"))
        stats["sides"] += update_event(ev, side_prices(r), ex.index_event(mb), ko, now)
        stats["new_gaps"] += sum(1 for x in ev.get("k", {}).values() if x.get("x")) - before
        if not ev.get("k"):
            del doc["events"][r["id"]]
    return stats


def find(docs_by_day: dict[str, dict], event_id: str | None, home: str, away: str,
         day: str | None) -> dict | None:
    """One game's record: by SportyBet event id, else by both names on the day."""
    if event_id:
        for doc in docs_by_day.values():
            ev = doc["events"].get(event_id)
            if ev:
                return ev
    if not day:
        return None
    best, score = None, 0.0
    for d in (day,):
        for ev in (docs_by_day.get(d) or {}).get("events", {}).values():
            sh, sa = ex.alike(home, ev.get("home") or ""), ex.alike(away, ev.get("away") or "")
            if min(sh, sa) >= 0.7 and sh + sa > score:
                best, score = ev, sh + sa
    return best
