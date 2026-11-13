"""
SPORTYBET STAT MARKETS vs THE EVENT MODEL - shadow value watch (framework #567). RECORD ONLY.

Architect 2026-11-11: build this first among the event-model items. Step 1 is a catalogue: every market id and
name SportyBet lists on a football match page, each mapped to the event model's stat (engine/event_model.py
REGISTRY) and scope (match / home team / away team), or left UNMAPPED (never guessed). Step 2 keeps every over/under
line of a mapped stat before kick-off (first look and last look, like engine/edge_book.py, so closing-price value can
be measured). Step 3 sets the model's over chance beside each price and writes the gap. The Architect's target is
sides with model edge >= EDGE_MIN at prices PRICE_LO-PRICE_HI; they are only LISTED, by stat family.

Never picks, stakes, blocks or moves another number. A line the model does not publish stays PENDING (HR35); a price
that is missing is never invented (HR59). The module is called from engine/stat_lines.py, which already reads each
match page inside Actions (SportyBet's event API refuses the UK PC).
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

from engine import fixture_match as fm

EDGE_MIN = 0.05
PRICE_LO, PRICE_HI = 1.60, 2.60

# (keywords all present in the lower-cased market name) -> event_model stat. First match wins; order matters.
STAT_RULES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("corner",), "corners"),
    (("shots on target",), "sot"),
    (("shot on target",), "sot"),
    (("total shots",), "shots"),
    (("offside",), "offsides"),
    (("foul",), "fouls"),
    (("booking",), "yellow"),
    (("yellow",), "yellow"),
    (("card",), "yellow"),
)
# the stats SportyBet counts differently from the model's plain count: a mapped line is recorded and compared but
# flagged (bookings are points on some markets, so the model's yellow count is only an approximation)
APPROX = {"yellow"}


def classify(name: str) -> tuple[str, str] | None:
    """(model stat, scope) for a market name, or None. Scope: match, home, away or h1 (a half; never compared)."""
    n = (name or "").lower()
    stat = next((s for kws, s in STAT_RULES if all(k in n for k in kws)), None)
    if stat is None:
        return None
    if "1st half" in n or "first half" in n or "2nd half" in n or "second half" in n:
        return stat, "h1"
    if "home" in n:
        return stat, "home"
    if "away" in n:
        return stat, "away"
    return stat, "match"


def _total(spec: str | None) -> str | None:
    m = re.search(r"total=([0-9.]+)", spec or "")
    return m.group(1) if m else None


def _price(x) -> float | None:
    try:
        v = float(x)
        return v if v > 1.0 else None
    except (TypeError, ValueError):
        return None


def catalogue_update(cat: dict, event: dict) -> None:
    """Fold one match page into the catalogue {market id: name, mapped stat, scope, specifier example, events}."""
    for m in event.get("markets") or []:
        mid = str(m.get("id"))
        name = m.get("desc") or m.get("name") or ""
        row = cat.setdefault(mid, {"name": name, "stat": None, "scope": None, "spec": None, "outcomes": None,
                                   "events": 0})
        if name and not row["name"]:
            row["name"] = name
        got = classify(row["name"])
        row["stat"], row["scope"] = got if got else (None, None)
        row["spec"] = row["spec"] or (m.get("specifier") or "")
        if not row["outcomes"]:
            row["outcomes"] = [o.get("desc") for o in (m.get("outcomes") or [])][:4]
        row["events"] += 1


def wide_lines(event: dict) -> dict:
    """{"corners:match": {"9.5": [over, under]}, "sot:home": {...}} for every open over/under line of a mapped stat."""
    out: dict = {}
    for m in event.get("markets") or []:
        got = classify(m.get("desc") or m.get("name") or "")
        tot = _total(m.get("specifier"))
        if not got or not tot or m.get("status") not in (None, 0, "0"):
            continue
        px = {(o.get("desc") or "").split(" ")[0].lower(): _price(o.get("odds")) for o in m.get("outcomes") or []
              if o.get("isActive", 1) in (1, "1", True, None)}
        if px.get("over") and px.get("under"):
            out.setdefault(f"{got[0]}:{got[1]}", {})[tot] = [px["over"], px["under"]]
    return out


def model_over(game: dict | None, stat: str, scope: str, line: str) -> float | None:
    """The event model's chance of OVER `line`, or None (PENDING) when it does not publish that stat/line."""
    e = ((game or {}).get("events") or {}).get(stat)
    if not e:
        return None
    key = {"match": "over", "home": "home_over", "away": "away_over"}.get(scope)
    p = (e.get(key) or {}).get(str(float(line))) if key else None
    return float(p) if p is not None else None


def watch_rows(wide: dict, game: dict | None) -> list[dict]:
    """One row per side per line: price, model chance, edge = chance x price - 1, and whether it is in the band."""
    rows = []
    for key, lines in wide.items():
        stat, scope = key.split(":")
        for ln, (o, u) in lines.items():
            p = model_over(game, stat, scope, ln)
            if p is None:
                continue
            for side, px, ch in (("over", o, p), ("under", u, 1 - p)):
                edge = round(ch * px - 1, 4)
                rows.append({"stat": stat, "scope": scope, "line": ln, "side": side, "odds": px, "p": round(ch, 3),
                             "edge": edge, "approx": stat in APPROX,
                             "target": edge >= EDGE_MIN and PRICE_LO <= px <= PRICE_HI})
    return rows


def load_games(root: Path, day: str) -> list[dict]:
    p = root / "output" / "events" / f"events_{day}.json"
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("games") or []
    except (OSError, ValueError):
        return []


def find_game(games: list[dict], home: str, away: str) -> dict | None:
    """The model's game for a SportyBet fixture: both teams must pair STRONGLY, else None (no guessing)."""
    for g in games:
        if fm.team_score(home, g.get("home") or "") >= fm.STRONG and fm.team_score(away, g.get("away") or "") >= fm.STRONG:
            return g
    return None


def observe(store: dict, event: dict, now_s: str, games: list[dict]) -> None:
    """Record one look at a match into `store` ({event id: record}); first look kept, last replaced."""
    wide = wide_lines(event)
    eid = event.get("eventId")
    if not eid or not wide:
        return
    game = find_game(games, event.get("homeTeamName") or "", event.get("awayTeamName") or "")
    rows = watch_rows(wide, game)
    look = {"at": now_s, "lines": wide, "watch": rows}
    rec = store.get(eid)
    if rec:
        rec["last"] = look
    else:
        store[eid] = {"first": look, "last": look, "model_found": game is not None}
    store[eid]["model_found"] = game is not None


def family_report(records: list[dict]) -> dict:
    """{stat:scope: {"sides": n, "target": n, "mean_edge_target": x}} over the LAST look of each record."""
    agg: dict = defaultdict(lambda: {"sides": 0, "target": 0, "_e": 0.0})
    for r in records:
        for w in (r.get("last") or {}).get("watch") or []:
            a = agg[f"{w['stat']}:{w['scope']}"]
            a["sides"] += 1
            if w["target"]:
                a["target"] += 1
                a["_e"] += w["edge"]
    return {k: {"sides": v["sides"], "target": v["target"],
                "mean_edge_target": round(v["_e"] / v["target"], 3) if v["target"] else None}
            for k, v in sorted(agg.items())}


# stats a Flashscore detail row may carry under stats.match as [home, away]; absent ones stay PENDING
DETAIL_KEYS = {"corners": "corners", "fouls": "fouls", "sot": "sot", "shots": "shots", "offsides": "offsides",
               "yellow": "yellow"}


def _actual(stat: str, scope: str, detail: dict | None) -> float | None:
    st = ((detail or {}).get("stats") or {}).get("match") or {}
    v = st.get(DETAIL_KEYS.get(stat, ""))
    if not v or None in v:
        return None
    if stat == "yellow" and sum(x or 0 for x in (st.get("red") or [0, 0])) > 0:
        return None            # a red card changes the bookings count: not graded (as engine/stat_lines.py)
    return {"match": v[0] + v[1], "home": v[0], "away": v[1]}.get(scope)


def settle_rows(rows: list[dict], detail: dict | None) -> list[dict]:
    """Each watch row with `won` (1 / 0 / None = push or PENDING) and `pnl` per unit, from the real count."""
    out = []
    for w in rows:
        a = _actual(w["stat"], w["scope"], detail)
        won = pnl = None
        if a is not None:
            x = float(w["line"])
            if a != x:
                won = int((a > x) == (w["side"] == "over"))
                pnl = round(w["odds"] - 1, 4) if won else -1.0
            else:
                pnl = 0.0
        out.append({**w, "actual": a, "won": won, "pnl": pnl})
    return out


def settle_wide(wide: dict, root: Path, now, out_dir: Path, fetch_detail=None) -> int:
    """Grade the matches of `wide` that kicked off GRADE_AFTER ago, write them to out_dir/<month>.jsonl, drop them."""
    from datetime import datetime, timedelta

    from engine import stat_lines as sl
    due = {k: r for k, r in wide.items() if r.get("ko") and
           now - datetime.fromisoformat(r["ko"].replace("Z", "+00:00")) >= sl.GRADE_AFTER}
    if not due:
        return 0
    months = {r["ko"][:7] for r in due.values()} | {
        (datetime.fromisoformat(r["ko"][:10]) + timedelta(days=1)).strftime("%Y-%m") for r in due.values()}
    base = sl._read_jsonl(root / "data" / "world_facts", months)
    detail = {d["id"]: d for d in sl._read_jsonl(root / "data" / "world_facts_detail", months)}
    idx = sl._Index(base)
    n = 0
    for eid, r in due.items():
        age = now - datetime.fromisoformat(r["ko"].replace("Z", "+00:00"))
        hit = idx.find(r["home"], r["away"], r["ko"])
        if hit is None and age <= sl.GIVE_UP_AFTER:
            continue
        d = detail.get(hit["id"]) if hit else None
        if hit and d is None and fetch_detail is not None:
            try:
                d = fetch_detail(hit)
            except Exception:  # noqa: BLE001 - stats feed down: stays PENDING
                d = None
        if d is None and age <= sl.GIVE_UP_AFTER:
            continue
        watch = settle_rows((r.get("last") or {}).get("watch") or [], d)
        out_dir.mkdir(parents=True, exist_ok=True)
        rec = {"id": eid, "ko": r["ko"], "home": r["home"], "away": r["away"], "model_found": r.get("model_found"),
               "first": r.get("first"), "last_lines": (r.get("last") or {}).get("lines"), "watch": watch}
        with (out_dir / f"{r['ko'][:7]}.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False, separators=(",", ":")) + "\n")
        del wide[eid]
        n += 1
    return n
