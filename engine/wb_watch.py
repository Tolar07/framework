"""
WORLD BASKETBALL LINE WATCH — the NBA line watch's price check (monitor/nba_watch.py) for the
world basketball / NCAA picks (framework#390; Architect 2026-11-06: "NBA and basketball, they're the
same thing ... inherit all its attributes of NBA").

RECORD-ONLY. It never changes a pick, a stake, a threshold or a code. On every edge-book look
(monitor/edge_run.py, ~30 min) each frozen pick in output/world_basketball/wb_<day>.json whose game
has not started is re-priced against the CURRENT sharp price (the Matchbook exchange's fair chance,
or ESPN's line for NCAA) and the CURRENT SportyBet price:

  * every look is appended to output/world_basketball/wb_watch_<day>.json (price, fair chance, value);
  * VALUE GONE  - SportyBet now pays below fair (value < 0): "skip it if you haven't placed it";
  * NOT OFFERED - SportyBet no longer lists the side (the booking code can't be placed);
  * LINE MOVED  - the sharp fair chance moved MOVE_P or more since the pick was frozen.
Each alert is raised once per pick. Alerts go to the Architect's own chat, like the NBA watch.

Star out before tip-off: NCAA picks get a team-news verdict from engine/wb_team_news.py (ESPN roster injuries,
framework#391); EuroLeague / other leagues have no feed, so the watch reads PENDING for them (HR35).
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from engine import exchange as ex
from engine import world_basketball as wb

MOVE_P = 0.05          # the sharp fair chance must move 5 points to count as a line move
STAR_OUT = "PENDING (NCAA: see wb_news_<day>.jsonl, engine/wb_team_news.py; other leagues: no injury feed, framework#391)"


def watch_path(day: str, folder: Path = wb.OUT_DIR) -> Path:
    return folder / f"wb_watch_{day}.json"


def current_fair(pick: dict, row: dict, events: list[dict]) -> float | None:
    """The sharp fair chance of the pick's side right now, from the source it was priced with."""
    key = pick.get("key")
    if not key:
        return None
    ko = ex._dt(pick.get("ko"))
    if str(pick.get("source", "")).startswith("espn"):
        try:
            from datetime import timedelta

            from engine import ncaa_lines as nl
            gs = nl.games(ko) + nl.games(ko - timedelta(days=1))
            g = nl.match(pick["home"], pick["away"], ko, gs)
            ln = nl.line(g) if g else None
            return nl.fair(key, ln) if ln else None
        except Exception:  # noqa: BLE001 - a feed fault leaves the fair chance unknown, never a guess
            return None
    mb = ex.match_event(pick["home"], pick["away"], ko, [e for e in events if e.get("_sport") == "basketball"])
    b = ex.quote(key, ex.index_event(mb)) if mb else None
    return b.get("p") if b else None


def check(pick: dict, entry: dict, row: dict | None, fair_now: float | None, now: datetime) -> list[str]:
    """Update `entry` (this pick's watch record) with one look; return NEW alert lines."""
    price = (row or {}).get("sides", {}).get(pick.get("key")) if row else None
    value = round(price * fair_now - 1, 4) if price and fair_now else None
    entry.setdefault("looks", []).append({"at": now.strftime("%Y-%m-%dT%H:%MZ"), "price": price,
                                          "fair": None if fair_now is None else round(fair_now, 4),
                                          "value": value})
    entry["star_out"] = STAR_OUT
    done = entry.setdefault("alerts", [])
    label = f"{pick['home']} v {pick['away']}: {pick['pick']}"
    code = pick.get("code") or "PENDING"
    out = []
    if row is not None and price is None and "not_offered" not in done:
        done.append("not_offered")
        out.append(f"{label} - no longer offered on SportyBet (code {code} can't be placed)")
    elif value is not None and value < 0 and "value_gone" not in done:
        done.append("value_gone")
        out.append(f"{label} - sent @{pick['price']:.2f} ({pick['value']:+.1%}); now @{price:.2f}, fair "
                   f"{1 / fair_now:.2f} ({value:+.1%}). VALUE GONE - skip it if you haven't placed it (code {code})")
    if fair_now is not None and pick.get("fair") and abs(fair_now - pick["fair"]) >= MOVE_P \
            and "line_moved" not in done:
        done.append("line_moved")
        out.append(f"{label} - sharp chance moved {pick['fair']:.0%} -> {fair_now:.0%} since the pick was sent")
    return out


def update(rows: list[dict], events: list[dict], now: datetime, folder: Path = wb.OUT_DIR) -> list[str]:
    """One look over every not-yet-started world basketball pick. Returns the new alert lines."""
    by_id = {r["id"]: r for r in rows}
    alerts: list[str] = []
    if not folder.exists():
        return alerts
    for p in sorted(folder.glob("wb_20*.json")):
        day = p.stem[3:]
        doc = json.loads(p.read_text(encoding="utf-8"))
        picks = [x for x in doc.get("picks", []) if (ex._dt(x.get("ko")) or now) > now]
        if not picks:
            continue
        wp = watch_path(day, folder)
        wdoc = json.loads(wp.read_text(encoding="utf-8")) if wp.exists() else {"date": day, "picks": {}}
        for pick in picks:
            row = by_id.get(pick["sb_event_id"])
            fair_now = current_fair(pick, row or {}, events) if row else None
            entry = wdoc["picks"].setdefault(pick["sb_event_id"], {"pick": pick["pick"]})
            alerts += check(pick, entry, row, fair_now, now)
        wp.write_text(json.dumps(wdoc, indent=1, ensure_ascii=False), encoding="utf-8")
    return alerts


def render(alerts: list[str], now: datetime) -> str:
    return "\n".join(["OLP XDV - WORLD BASKETBALL LINE WATCH (record-only)", f"Checked {now:%H:%M} UTC", "",
                      *[f" - {a}" for a in alerts], "",
                      "Prices move fast near tip-off: check the price is still there before acting."])
