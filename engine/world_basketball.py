"""
WORLD BASKETBALL — the NBA board's method for every other basketball league SportyBet lists
(Architect 2026-11-05: "start widening the basketball reach to other leagues aside this NBA").
STAKED (Architect 2026-11-05 13:20 UTC: "Once the world basketball and the NCAA board is ready and
everything is done and it's fully ready, staking should continue. Then the bots continue with it.").
matchbook-agent, betfair-agent and sportybet-agent read wb_<date>.json like nba_<date>.json, at the
NBA board's stakes and money rules; every pick carries the NBA board's fields and its own code.
It is still graded per league on the edge scoreboard.

Why this method: picking the likeliest side at SportyBet's price loses the margin in every
basketball league on record (universe, 1,998 games since 7 Oct: favourites at 55-85% returned
-1% to -30% by league). The NBA board wins only where SportyBet pays MORE than a sharp fair
price (engine/nba_value.py). Outside the NBA the sharp price is the Matchbook exchange's fair
chance (engine/exchange.py), which lists NCAA Division I, the EuroLeague and the EuroCup.

NCAA men's games are also priced from ESPN's sharp line (DraftKings / ESPN BET) with the shapes fitted in
backtest/NCAA_STUDY.md (engine/ncaa_lines.py), as the NBA board prices the NBA from ESPN BET.

Every edge-book look (monitor/edge_run.py, ~30 min) offers each non-NBA game kicking off within
WINDOW: its sides with an exchange fair chance (winner, handicap, total, 1st-half total). A side
qualifies like an NBA pick: price in BAND, fair chance >= 50%, value = price x fair - 1 >= +3% on
the winner or >= +5% on a line (the exchange book is thinner than ESPN's), at most +25% (above
that it is a stale line, never picked), and LIQ+ GBP at the exchange's best back. One pick per
game, the best value, FROZEN at the look it first qualified (the entry price). Written to
output/world_basketball/wb_<kick-off UTC date>.json; graded by monitor/edge_scoreboard.py from the
universe results, per league.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path

from engine import exchange as ex

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "output" / "world_basketball"
WINDOW = timedelta(hours=24)
BAND = (1.20, 2.00)
MIN_VALUE = {"219": 0.03}          # the winner market; every line market needs LINE_VALUE
LINE_VALUE = 0.05
MAX_VALUE = 0.25
LIQ = 10.0


def describe(key: str, home: str, away: str) -> str:
    mid, spec, out = (key[2:].split("|") + ["", ""])[:3]
    o = out.strip()
    if mid == "219":
        return f"{home if o.lower() == 'home' else away} to win"
    if mid == "223":
        m = re.fullmatch(r"(Home|Away) \(([+-]?[\d.]+)\)", o)
        return f"{home if m and m.group(1) == 'Home' else away} {m.group(2) if m else ''}".strip()
    if mid == "68":
        return f"1st half {o} points"
    return f"{o} points"


def _qualifies(key: str, price: float, p: float) -> float | None:
    value = price * p - 1
    need = MIN_VALUE.get(key[2:].split("|")[0], LINE_VALUE)
    return value if BAND[0] <= price <= BAND[1] and p >= 0.50 and need <= value <= MAX_VALUE else None


def candidates(row: dict, idx: dict[str, dict]) -> list[dict]:
    """Sides priced by the Matchbook exchange's fair chance."""
    out = []
    for key, price in (row.get("sides") or {}).items():
        b = ex.quote(key, idx)
        if not b or not b.get("p") or (b.get("liq") or 0) < LIQ:
            continue
        value = _qualifies(key, price, b["p"])
        if value is not None:
            out.append({"key": key, "price": price, "fair": round(b["p"], 4), "value": round(value, 4),
                        "source": "matchbook", "back": b.get("back"), "lay": b.get("lay"), "liq": b.get("liq")})
    return out


def ncaa_candidates(row: dict, ko: datetime) -> list[dict]:
    """NCAA sides priced from ESPN's sharp line with backtest/NCAA_STUDY.md's shapes (engine/ncaa_lines.py)."""
    from engine import ncaa_lines as nl
    gs = nl.games(ko) + nl.games(ko - timedelta(days=1))          # ESPN lists by US date
    g = nl.match(row["home"], row["away"], ko, gs)
    ln = nl.line(g) if g else None
    if not ln:
        return []
    out = []
    for key, price in (row.get("sides") or {}).items():
        p = nl.fair(key, ln)
        value = _qualifies(key, price, p) if p else None
        if value is not None:
            out.append({"key": key, "price": price, "fair": round(p, 4), "value": round(value, 4),  # type: ignore[arg-type]
                        "source": f"espn {ln.get('provider') or ''}".strip(), "line_total": ln.get("total"),
                        "line_spread": ln.get("spread")})
    return out


# Which bot can trade each market (venue catalogues read 2026-11-05: Matchbook basketball =
# Moneyline, Handicap, Total, 1st Half Total, 1st Half Handicap; Betfair = MATCH_ODDS, HANDICAP,
# COMBINED_TOTAL; SportyBet = all of them, by booking code). Half lines only on the exchanges.
MATCHBOOK_MARKETS = ("219", "223", "225", "68", "66")
BETFAIR_MARKETS = ("219", "223", "225")


def venues(key: str, on_matchbook: bool) -> dict:
    """Where this pick could go: SportyBet always (its own price), Matchbook when the game is
    matched there and the market is one it lists, Betfair when the market is one it lists
    (whether Betfair lists the game is the Betfair bot's own lookup)."""
    mid = key[2:].split("|")[0]
    return {"sportybet": True, "matchbook": on_matchbook and mid in MATCHBOOK_MARKETS,
            "betfair_market": mid in BETFAIR_MARKETS}


def _book(sel: dict) -> str | None:
    """A SportyBet booking code for one pick (the same share endpoint as the NBA board). Only
    inside GitHub Actions: tests and desktop runs never call SportyBet. None = PENDING."""
    import os
    if os.environ.get("GITHUB_ACTIONS") != "true":
        return None
    try:
        from pipeline.sportybet_booking import create_booking_code
        return create_booking_code([sel])[0]
    except Exception:  # noqa: BLE001 — a failed booking leaves the code PENDING, the pick stands
        return None


def path_for(day: str, folder: Path = OUT_DIR) -> Path:
    return folder / f"wb_{day}.json"


def update(rows: list[dict], events: list[dict], now: datetime, folder: Path = OUT_DIR, book=_book) -> int:
    """Freeze a pick for every non-NBA basketball game that newly qualifies. Returns how many."""
    bb = [e for e in events if e.get("_sport") == "basketball"]
    docs: dict[str, dict] = {}
    added = 0
    for r in rows:
        if r.get("sport") != "basketball" or r.get("covered"):     # covered = the NBA board's own leagues
            continue
        ko = ex._dt(r.get("ko"))
        if ko is None or not now < ko <= now + WINDOW:
            continue
        day = ko.strftime("%Y-%m-%d")
        if day not in docs:
            p = path_for(day, folder)
            docs[day] = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"date": day, "picks": []}
        doc = docs[day]
        have = next((x for x in doc["picks"] if x["sb_event_id"] == r["id"]), None)
        if have is not None:                                         # frozen: the entry price stays
            if "market_id" not in have:                              # frozen before the bot fields
                mid, spec, out = (have["key"][2:].split("|") + ["", ""])[:3]
                have.update({"market_id": mid, "specifier": spec, "outcome": out.strip(),
                             "outcome_id": (r.get("oids") or {}).get(have["key"]), "code": None})
            have.setdefault("chance", have.get("fair"))
            have.setdefault("tip", have.get("ko"))
            have.setdefault("event_id", have.get("sb_event_id"))
            if not have.get("code") and have.get("outcome_id"):     # PENDING: retried every look
                have["code"] = book({"eventId": r["id"], "marketId": have["market_id"],
                                     "specifier": have["specifier"], "outcomeId": have["outcome_id"]})
            continue
        mb = ex.match_event(r["home"], r["away"], ko, bb)
        cands = candidates(r, ex.index_event(mb)) if mb else []
        if "ncaa" in (r.get("comp") or "").lower():
            cands += ncaa_candidates(r, ko)
        best = max(cands, key=lambda c: c["value"], default=None)
        if best is None:
            continue
        mid, spec, out = (best["key"][2:].split("|") + ["", ""])[:3]
        oid = (r.get("oids") or {}).get(best["key"])
        code = book({"eventId": r["id"], "marketId": mid, "specifier": spec, "outcomeId": oid}) if oid else None
        doc["picks"].append({"sb_event_id": r["id"], "country": r.get("country"), "comp": r.get("comp"),
                             "home": r["home"], "away": r["away"], "ko": r["ko"],
                             "pick": describe(best["key"], r["home"], r["away"]), **best,
                             "market_id": mid, "specifier": spec, "outcome": out, "outcome_id": oid,
                             "code": code, "venues": venues(best["key"], mb is not None),
                             "chance": best["fair"], "tip": r["ko"], "event_id": r["id"],   # what the bots read
                             "at": now.strftime("%Y-%m-%dT%H:%MZ"), "result": None})
        added += 1
    for day, doc in docs.items():
        if doc["picks"]:
            folder.mkdir(parents=True, exist_ok=True)
            path_for(day, folder).write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    return added


def load_all(folder: Path = OUT_DIR) -> list[tuple[str, dict]]:
    out = []
    for f in sorted(folder.glob("wb_*.json")) if folder.exists() else []:
        try:
            out.append((f.stem[3:], json.loads(f.read_text(encoding="utf-8"))))
        except (OSError, ValueError):
            continue
    return out
