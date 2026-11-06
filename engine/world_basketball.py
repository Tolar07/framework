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


def _book_many(sels: list[dict]) -> str | None:
    """One SportyBet booking code for several selections (an acca). Same rules as _book."""
    import os
    if os.environ.get("GITHUB_ACTIONS") != "true":
        return None
    try:
        from pipeline.sportybet_booking import create_booking_code
        return create_booking_code(sels)[0]
    except Exception:  # noqa: BLE001 — not booked: retried on the next look
        return None


def path_for(day: str, folder: Path = OUT_DIR) -> Path:
    return folder / f"wb_{day}.json"


def update(rows: list[dict], events: list[dict], now: datetime, folder: Path = OUT_DIR, book=_book,
           book_many=_book_many) -> int:
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
    night_accas(now, folder, book=book_many)
    return added


# ALL-PICKS ACCA (the Architect, 2026-11-06 17:28 UK: "the framework just produces singles for this basketball
# games ... if it places the single, they should also make an ACCA, you know, all 13 in one [slip] ... and then
# place it"). A night is tip-offs from 12:00 UTC to 12:00 UTC the next day (the bots' night, sportybet-agent
# wb_night). From the first look within ACCA_LEAD of the night's first tip-off, every pick with a code that has
# not started goes on ONE slip, booked once and frozen in acca_<night>.json; the bots place that code. The
# singles are unchanged. Told before deciding: 13 legs at 54-65% each win about 1 time in 1,000.
ACCA_LEAD = timedelta(hours=2)
# THREE ACCAS (the Architect, 2026-11-06 17:51 UK: "for the 3ACCA, use 1,000 naira each on my account"): the
# all-picks slip plus the night split in two by tip-off (from SPLIT_MIN picks), all three in "accas". The
# top-level code stays the all-picks slip. Stakes are the bots' (sportybet-agent wb_acca: NGN 1,000 on account 1,
# the normal acca stake elsewhere; Architect 2026-11-06 18:35).
SPLIT_MIN = 4
# TWO TEST NIGHTS ONLY (the Architect, 2026-11-06 19:06 UK: "aside from the one I just did for 2 nights only";
# answered: tonight + tomorrow, then stop). The all + 2 halves slips are booked for these nights and no other;
# basketball gets its own football-style board (every section, staked) instead.
TEST_NIGHTS = frozenset({"2026-11-06", "2026-11-07"})


def night_of(tip: datetime) -> str:
    return (tip - timedelta(hours=12)).strftime("%Y-%m-%d")


def acca_path(night: str, folder: Path = OUT_DIR) -> Path:
    return folder / f"acca_{night}.json"


def _legs_of(x: dict) -> tuple[datetime, dict] | None:
    tip = ex._dt(x.get("tip") or x.get("ko"))
    if tip is None or not (x.get("code") and x.get("outcome_id") and x.get("market_id") and x.get("event_id")):
        return None
    return tip, x


def book_set(night: str, legs: list[tuple[datetime, dict]], now: datetime, book) -> dict | None:
    """The night's slips from legs (tip, pick): all picks, then from SPLIT_MIN picks the two halves by
    tip-off (first half rounded up, as run_nba.split_accas). All booked together, else None (retried)."""
    legs = sorted(legs, key=lambda tx: tx[0])
    groups = [("all", f"Basketball acca (all {len(legs)} picks)", legs)]
    if len(legs) >= SPLIT_MIN:
        half = (len(legs) + 1) // 2
        groups += [("A", f"Basketball acca A (first {half})", legs[:half]),
                   ("B", f"Basketball acca B (last {len(legs) - half})", legs[half:])]
    accas = []
    for key, name, g in groups:
        code = book([{"eventId": x["event_id"], "marketId": x["market_id"], "specifier": x.get("specifier") or "",
                      "outcomeId": x["outcome_id"]} for _, x in g])
        if not code:
            return None
        odds = chance = 1.0
        for _, x in g:
            odds *= float(x.get("price") or 1.0)
            chance *= float(x.get("chance") or 0.0)
        accas.append({"key": key, "name": name, "code": code, "legs": [x["event_id"] for _, x in g],
                      "codes": [x["code"] for _, x in g], "odds": round(odds, 2), "chance": round(chance, 5),
                      "result": None})
    return {"night": night, **{k: v for k, v in accas[0].items() if k != "key"},
            "first_tip": legs[0][1].get("tip"), "booked_at": now.strftime("%Y-%m-%dT%H:%MZ"), "accas": accas}


# ONE BASKETBALL (the Architect, 2026-11-06 18:35 UK: "MB[A] and N[CA]A or the basketball are one. So whatever
# board is being produced for basketball should include NBA and any other league ... the basketball world. So ...
# it creates its acc[a]s for it and splits"; answered: all + 2 halves by tip-off, booked with the morning NBA board).
# run_nba's morning board books ONE set for the NBA night (10:00 UTC to 10:00 UTC): its NBA picks plus every world
# basketball / NCAA pick of that window known by then, frozen in acca_<night>.json (night = the date the NBA night
# starts, the bots' placing date). The NBA board books no NBA-only accas any more. night_accas above stays the
# fallback for a night the morning board did not book (no NBA run), 2 h before its first tip-off.
def combined_accas(now: datetime, night: str, start: datetime, end: datetime, nba_picks: list[dict],
                   book, folder: Path = OUT_DIR) -> dict | None:
    """Book (once) the night's basketball slips from NBA + world basketball picks; the frozen doc, or None."""
    path = acca_path(night, folder)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    if night not in TEST_NIGHTS:
        return None
    legs: dict[str, tuple[datetime, dict]] = {}
    for x in list(nba_picks) + [x for _, doc in load_all(folder) for x in doc.get("picks") or []]:
        lx = _legs_of(x)
        if lx and start <= lx[0] < end and lx[0] > now:
            legs.setdefault(str(x["event_id"]), lx)     # one leg per game, NBA first
    if len(legs) < 2:
        return None
    doc = book_set(night, list(legs.values()), now, book)
    if doc is None:
        return None
    doc["source"] = "morning board: NBA + world basketball"
    folder.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    return doc


def night_accas(now: datetime, folder: Path = OUT_DIR, book=_book_many) -> list[str]:
    """Book and freeze each night's all-picks acca once it is due. Returns the nights booked now."""
    nights: dict[str, list[tuple[datetime, dict]]] = {}
    for _, doc in load_all(folder):
        for x in doc.get("picks") or []:
            lx = _legs_of(x)
            if lx:
                nights.setdefault(night_of(lx[0]), []).append(lx)
    made = []
    for night, legs in sorted(nights.items()):
        path = acca_path(night, folder)
        if path.exists() or night not in TEST_NIGHTS:       # frozen: booked once a night; test nights only
            continue
        legs = sorted([(t, x) for t, x in legs if t > now], key=lambda tx: tx[0])
        if len(legs) < 2 or legs[0][0] - now > ACCA_LEAD:
            continue
        booked = book_set(night, legs, now, book)
        if booked is None:
            continue                                        # PENDING: all booked together on the next look
        doc = booked
        folder.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
        made.append(night)
    return made


def load_all(folder: Path = OUT_DIR) -> list[tuple[str, dict]]:
    out = []
    for f in sorted(folder.glob("wb_*.json")) if folder.exists() else []:
        try:
            out.append((f.stem[3:], json.loads(f.read_text(encoding="utf-8"))))
        except (OSError, ValueError):
            continue
    return out
