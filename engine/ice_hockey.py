"""
ICE HOCKEY BOARD — sport 1 of the multi-sport rollout (standing order 50, Architect 2026-11-05:
"each week a new sport ... shadow, paper trade and everything. Then the next week it goes live").
Schedule and switches: config/sport_rollout.json. Live from its `live_from` date; until then the
board is PAPER (doc["paper"] = True) and the bots record its picks without staking.

The world basketball board's method (engine/world_basketball.py), with hockey's markets:
  * every SportyBet ice hockey game kicking off inside WINDOW, every side of every market
    (1X2, winner incl. OT, handicap incl. OT, totals, Asian handicap, 3-way handicap, GG/NG);
  * the sharp reference = the Matchbook exchange's fair chance (moneyline, 1X2 excl. OT,
    handicap); NHL games also get the goals model's chance (engine/hockey_model.py);
  * a side qualifies like a world basketball pick: price in BAND, chance >= 50%, value =
    price x chance - 1 >= +3% on a result market or >= +5% on a line, at most +25%;
    exchange-priced sides need LIQ GBP at the best back; model-priced sides (NHL only, no
    exchange quote) use the order-18 anchor 75% SportyBet (margin removed) + 25% model;
  * one pick per game, the best value, FROZEN at the look it first qualified, with its own
    SportyBet booking code — the fields the bots read for wb_/nba_ picks;
  * EVERY side of every game keeps its first and last look (price, exchange fair, model) and
    is graded after the game: the paper record that learns from all markets, bet or not.
NO STEAM (order 50): nothing here reads or follows price moves to pick.

Written to output/ice_hockey/ih_<kick-off UTC date>.json; graded by run_hockey.py --grade
from Flashscore (sport 4: periods 1-3 = regulation, final incl. OT/SO).
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from engine import exchange as ex
from engine import hockey_model as hm

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "output" / "ice_hockey"
ROLLOUT = ROOT / "config" / "sport_rollout.json"
WINDOW = timedelta(hours=24)
BAND = (1.20, 2.00)
RESULT_MARKETS = ("1", "406")
MIN_VALUE, LINE_VALUE, MAX_VALUE = 0.03, 0.05, 0.25
LIQ = 10.0
ANCHOR = 0.75                     # order 18: chance = 75% SportyBet (de-vigged) + 25% model
MARKET_IDS = "1,406,410,18,16,14,29"
_FEED = ("https://www.sportybet.com/api/ng/factsCenter/pcUpcomingEvents"
         "?sportId=sr:sport:4&marketId=" + MARKET_IDS + "&pageSize=100&pageNum={page}")
_MB = ("https://api.matchbook.com/edge/rest/events?sport-ids=6&states=open&include-prices=true"
       "&price-depth=1&odds-type=DECIMAL&exchange-type=back-lay&currency=GBP&per-page=100&offset={off}")
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
# Which bot can trade each market (Matchbook ice hockey lists Moneyline, Match Odds excl. OT,
# Handicap, Total; Betfair MATCH_ODDS, MONEY_LINE, handicaps, totals; SportyBet all by code).
# Matchbook/Betfair totals include overtime, SportyBet's 18 is regulation only: not the same bet.
MATCHBOOK_MARKETS = ("1", "406", "410")
BETFAIR_MARKETS = ("1", "406", "410")


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode("utf-8"))


def is_paper(day: str, path: Path = ROLLOUT) -> bool:
    """Paper until the sport's live_from date (order 50); live from that date, gate or not."""
    try:
        cfg = json.loads(path.read_text(encoding="utf-8"))
        s = next(x for x in cfg["sports"] if x["sport"] == "ice_hockey")
        return day < s["live_from"]
    except Exception:  # noqa: BLE001 — no readable schedule = stay on paper
        return True


# ── SportyBet ───────────────────────────────────────────────────────────────────────────────
def fetch_sportybet(get=_get) -> list[dict]:
    """Every upcoming SportyBet ice hockey game as a row {id, country, comp, home, away, ko,
    sides {key: price}, oids {key: outcome id}}. Keys are "H:<market id>|<specifier>|<outcome>"."""
    rows, page = [], 1
    while page <= 10:
        d = (get(_FEED.format(page=page)) or {}).get("data") or {}
        for t in d.get("tournaments") or []:
            for e in t.get("events") or []:
                rows.append(row_of(e, t))
        if page * 100 >= int(d.get("totalNum") or 0):
            break
        page += 1
    return rows


def row_of(e: dict, t: dict) -> dict:
    cat = (e.get("sport") or {}).get("category") or {}
    ko = datetime.fromtimestamp(int(e.get("estimateStartTime", 0)) / 1000, tz=UTC)
    sides, oids = {}, {}
    for m in e.get("markets") or []:
        if str(m.get("status")) != "0":
            continue
        for o in m.get("outcomes") or []:
            if str(o.get("isActive", 1)) != "1":
                continue
            try:
                price = float(o.get("odds"))
            except (TypeError, ValueError):
                continue
            key = f"H:{m.get('id')}|{m.get('specifier') or ''}|{o.get('desc')}"
            sides[key] = price
            oids[key] = o.get("id")
    return {"id": e.get("eventId"), "country": cat.get("name"), "comp": t.get("name"),
            "home": e.get("homeTeamName"), "away": e.get("awayTeamName"),
            "ko": ko.strftime("%Y-%m-%dT%H:%M:%SZ"), "sides": sides, "oids": oids}


def devig(key: str, sides: dict) -> float | None:
    """SportyBet's own chance for a side, margin removed within its market + specifier."""
    mid, spec, _ = (key[2:].split("|") + ["", ""])[:3]
    group = {k: v for k, v in sides.items() if k[2:].split("|")[:2] == [mid, spec]}
    if len(group) < 2 or any(v <= 1 for v in group.values()):
        return None
    tot = sum(1 / v for v in group.values())
    return (1 / sides[key]) / tot


# ── Matchbook exchange ──────────────────────────────────────────────────────────────────────
def fetch_matchbook(get=_get) -> list[dict]:
    out: list[dict] = []
    try:
        while len(out) < 600:
            d = get(_MB.format(off=len(out)))
            evs = d.get("events") or []
            out += evs
            if not evs or len(out) >= int(d.get("total") or 0):
                break
    except Exception:  # noqa: BLE001 — no exchange = model/no pick, never a blocked board
        pass
    return out


def canonical(key: str) -> str | None:
    """A hockey SportyBet side -> the exchange's canonical key (engine/exchange.py), or None."""
    mid, spec, out = (key[2:].split("|") + ["", ""])[:3]
    o = out.strip().lower()
    if mid == "406" and o in ("home", "away"):
        return f"ml|{o}"
    if mid == "1" and o in ("home", "draw", "away"):
        return f"1x2|{o}"
    if mid == "410":
        mm = re.fullmatch(r"(home|away) \(([+-]?\d+(?:\.\d+)?)\)", o)
        if mm and float(mm.group(2)) % 1 == 0.5:
            return f"hcp|{float(mm.group(2)):g}|{mm.group(1)}"
    return None


# ── NHL model ───────────────────────────────────────────────────────────────────────────────
class NHL:
    """The goals model fitted on NHL history, with SportyBet names mapped to NHL abbrevs."""

    def __init__(self, games: list[dict], as_of: str):
        self.model = hm.fit(games, as_of)
        self.names: dict[str, str] = {}
        for g in games:
            self.names[g["home_name"]] = g["home"]
            self.names[g["away_name"]] = g["away"]

    def abbrev(self, name: str) -> str | None:
        best = max(self.names, key=lambda n: ex.alike(name, n), default=None)
        return self.names[best] if best and ex.alike(name, best) >= 0.8 else None

    def chances(self, row: dict) -> dict[str, float]:
        if self.model is None or (row.get("comp") or "").upper() != "NHL":
            return {}
        h, a = self.abbrev(row["home"] or ""), self.abbrev(row["away"] or "")
        if not h or not a or not self.model.knows(h, a):
            return {}
        grid = self.model.grid(h, a)
        out = {}
        for key in row["sides"]:
            mid, spec, o = (key[2:].split("|") + ["", ""])[:3]
            p = hm.chance(mid, spec, o, grid, self.model.ot_home)
            if p is not None:
                out[key] = round(p, 4)
        return out


# ── picking ─────────────────────────────────────────────────────────────────────────────────
def qualifies(key: str, price: float, p: float) -> float | None:
    value = price * p - 1
    need = MIN_VALUE if key[2:].split("|")[0] in RESULT_MARKETS else LINE_VALUE
    return value if BAND[0] <= price <= BAND[1] and p >= 0.50 and need <= value <= MAX_VALUE else None


def candidates(row: dict, idx: dict[str, dict], model: dict[str, float]) -> list[dict]:
    out = []
    for key, price in row["sides"].items():
        c = canonical(key)
        b = idx.get(c) if c else None
        if b and b.get("p") and (b.get("liq") or 0) >= LIQ:
            v = qualifies(key, price, b["p"])
            if v is not None:
                out.append({"key": key, "price": price, "fair": round(b["p"], 4), "value": round(v, 4),
                            "source": "matchbook", "back": b.get("back"), "lay": b.get("lay"), "liq": b.get("liq")})
                continue
        if key in model and not (b and b.get("p")):
            q = devig(key, row["sides"])
            if q is None:
                continue
            p = ANCHOR * q + (1 - ANCHOR) * model[key]
            v = qualifies(key, price, p)
            if v is not None:
                out.append({"key": key, "price": price, "fair": round(p, 4), "value": round(v, 4),
                            "source": "nhl model (75% SportyBet)", "model": model[key]})
    return out


def describe(key: str, home: str, away: str) -> str:
    mid, spec, out = (key[2:].split("|") + ["", ""])[:3]
    o = out.strip()
    if mid in ("1", "406"):
        name = {"home": home, "away": away}.get(o.lower())
        tail = " (60 min)" if mid == "1" else " (incl. OT)"
        return f"{name} to win{tail}" if name else "Draw (60 min)"
    if mid in ("410", "16"):
        mm = re.fullmatch(r"(Home|Away) \(([+-]?[\d.]+)\)", o)
        if mm:
            return f"{home if mm.group(1) == 'Home' else away} {mm.group(2)}{' (incl. OT)' if mid == '410' else ' (60 min)'}"
    if mid == "18":
        return f"{o} goals (60 min)"
    if mid == "29":
        return f"Both teams to score: {o} (60 min)"
    return f"{o} [{mid} {spec}]".strip()


def venues(key: str, on_matchbook: bool) -> dict:
    mid = key[2:].split("|")[0]
    return {"sportybet": True, "matchbook": on_matchbook and mid in MATCHBOOK_MARKETS,
            "betfair_market": mid in BETFAIR_MARKETS}


def _book(sel: dict) -> str | None:
    """A SportyBet booking code (GitHub Actions only; None = PENDING)."""
    if os.environ.get("GITHUB_ACTIONS") != "true":
        return None
    try:
        from pipeline.sportybet_booking import create_booking_code
        return create_booking_code([sel])[0]
    except Exception:  # noqa: BLE001
        return None


def path_for(day: str, folder: Path = OUT_DIR) -> Path:
    return folder / f"ih_{day}.json"


def _look(price, fair, model, at) -> dict:
    return {"price": price, "fair": fair, "model": model, "at": at}


def update(rows: list[dict], mb_events: list[dict], nhl: NHL | None, now: datetime,
           folder: Path = OUT_DIR, book=_book) -> tuple[int, int]:
    """One look: record every side of every game inside WINDOW, freeze new picks.
    Returns (games seen, picks added)."""
    docs: dict[str, dict] = {}
    seen = added = 0
    at = now.strftime("%Y-%m-%dT%H:%MZ")
    for r in rows:
        ko = ex._dt(r.get("ko"))
        if ko is None or not now < ko <= now + WINDOW or not r["sides"]:
            continue
        seen += 1
        day = ko.strftime("%Y-%m-%d")
        if day not in docs:
            p = path_for(day, folder)
            docs[day] = (json.loads(p.read_text(encoding="utf-8")) if p.exists()
                         else {"date": day, "sport": "ice_hockey", "picks": [], "games": {}})
        doc = docs[day]
        doc["paper"] = is_paper(day)
        mb = ex.match_event(r["home"], r["away"], ko, mb_events)
        idx = ex.index_event(mb) if mb else {}
        model = nhl.chances(r) if nhl else {}
        g = doc["games"].setdefault(r["id"], {"country": r.get("country"), "comp": r.get("comp"),
                                              "home": r["home"], "away": r["away"], "ko": r["ko"],
                                              "sides": {}, "result": None})
        g["matchbook"] = bool(mb)
        for key, price in r["sides"].items():
            c = canonical(key)
            b = idx.get(c) if c else None
            look = _look(price, round(b["p"], 4) if b and b.get("p") else None, model.get(key), at)
            s = g["sides"].setdefault(key, {"first": look})
            s["last"] = look
        have = next((x for x in doc["picks"] if x["sb_event_id"] == r["id"]), None)
        if have is not None:
            if not have.get("code") and have.get("outcome_id"):
                have["code"] = book({"eventId": r["id"], "marketId": have["market_id"],
                                     "specifier": have["specifier"], "outcomeId": have["outcome_id"]})
            continue
        best = max(candidates(r, idx, model), key=lambda c: c["value"], default=None)
        if best is None:
            continue
        mid, spec, out = (best["key"][2:].split("|") + ["", ""])[:3]
        oid = r["oids"].get(best["key"])
        code = book({"eventId": r["id"], "marketId": mid, "specifier": spec, "outcomeId": oid}) if oid else None
        doc["picks"].append({"sb_event_id": r["id"], "country": r.get("country"), "comp": r.get("comp"),
                             "home": r["home"], "away": r["away"], "ko": r["ko"], "sport": "ice_hockey",
                             "pick": describe(best["key"], r["home"], r["away"]), **best,
                             "market_id": mid, "specifier": spec, "outcome": out, "outcome_id": oid,
                             "code": code, "venues": venues(best["key"], mb is not None),
                             "chance": best["fair"], "tip": r["ko"], "event_id": r["id"],
                             "paper": doc["paper"], "at": at, "result": None})
        added += 1
    for day, doc in docs.items():
        folder.mkdir(parents=True, exist_ok=True)
        path_for(day, folder).write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    return seen, added


# ── grading ─────────────────────────────────────────────────────────────────────────────────
def parse_flashscore(text: str) -> list[dict]:
    """Finished ice hockey games from a Flashscore sport-4 day feed: regulation = periods 1-3,
    final = AG/AH (overtime; a shootout adds the winner's goal)."""
    out, league = [], ""
    for block in text.split("~"):
        kv: dict[str, str] = {}
        for f in block.split("¬"):
            if "÷" in f:
                k, v = f.split("÷", 1)
                kv.setdefault(k, v)
        if "ZA" in kv:
            league = kv["ZA"]
            continue
        if "AA" not in kv or kv.get("AB") != "3":
            continue
        try:
            fh, fa = int(kv["AG"]), int(kv["AH"])
            rh = sum(int(kv[k]) for k in ("BA", "BC", "BE"))
            ra = sum(int(kv[k]) for k in ("BB", "BD", "BF"))
            ko = datetime.fromtimestamp(int(kv.get("AD", "0")), tz=UTC)
        except (KeyError, ValueError):
            continue
        out.append({"league": league, "home": kv.get("AE", ""), "away": kv.get("AF", ""),
                    "fthg": fh, "ftag": fa, "reg": [rh, ra], "final": [fh, fa], "stage": kv.get("AC"),
                    "kickoff_utc": ko.strftime("%Y-%m-%dT%H:%M:%SZ")})
    return out


def results(day: str, today: date | None = None) -> list[dict]:
    """Finished games around one UTC day (that day and the next), from Flashscore."""
    from data import flashscore_results as fr
    today = today or datetime.now(UTC).date()
    out: list[dict] = []
    sign = fr.feed_sign()
    for d in (date.fromisoformat(day), date.fromisoformat(day) + timedelta(days=1)):
        off = (d - today).days
        if off > 0:
            continue
        try:
            text = fr._get(fr._FEED.replace("f_1_", "f_4_").format(offset=off),
                           {"x-fsign": sign, "Referer": "https://www.flashscore.co.uk/"})
            out += parse_flashscore(text)
        except Exception:  # noqa: BLE001 — ungraded today, retried next run
            continue
    return out


def grade_doc(doc: dict, events: list[dict], now: datetime) -> int:
    """Settle every finished game's sides and picks. Returns how many games were graded."""
    from data import flashscore_results as fr
    n = 0
    for gid, g in (doc.get("games") or {}).items():
        if g.get("result"):
            continue
        ko = ex._dt(g.get("ko"))
        if ko is None or now < ko + timedelta(hours=3):
            continue
        ev = fr.find_result(events, g["home"], g["away"], g["ko"])
        if not ev or "reg" not in ev:
            continue
        reg, final = tuple(ev["reg"]), tuple(ev["final"])
        g["result"] = {"reg": list(reg), "final": list(final), "stage": ev.get("stage")}
        for key, s in g["sides"].items():
            mid, spec, o = (key[2:].split("|") + ["", ""])[:3]
            s["won"] = hm.settle(mid, spec, o, reg, final)
        for p in doc.get("picks") or []:
            if p["sb_event_id"] != gid or p.get("result"):
                continue
            w = hm.settle(p["market_id"], p["specifier"], p["outcome"], reg, final)
            last = (g["sides"].get(p["key"]) or {}).get("last") or {}
            p["result"] = "void" if w is None else "won" if w else "lost"
            p["pnl"] = 0.0 if w is None else round(p["price"] - 1, 4) if w else -1.0
            p["close_price"] = last.get("price")
            p["clv"] = round(p["price"] / last["price"] - 1, 4) if last.get("price") else None
            p["clv_fair"] = round(p["price"] * last["fair"] - 1, 4) if last.get("fair") else None
        n += 1
    return n


def load_all(folder: Path = OUT_DIR) -> list[tuple[str, dict]]:
    out = []
    for f in sorted(folder.glob("ih_*.json")) if folder.exists() else []:
        try:
            out.append((f.stem[3:], json.loads(f.read_text(encoding="utf-8"))))
        except (OSError, ValueError):
            continue
    return out


def scoreboard(docs: list[tuple[str, dict]]) -> dict:
    """Picks W-L, return at 1 unit, CLV; and every graded side by market (the paper record)."""
    picks = [p for _d, doc in docs for p in doc.get("picks") or [] if p.get("result") in ("won", "lost")]
    sb: dict = {"picks": len(picks), "won": sum(p["result"] == "won" for p in picks),
                "pnl": round(sum(p["pnl"] for p in picks), 3)}
    clv = [p["clv_fair"] for p in picks if p.get("clv_fair") is not None]
    sb["clv_fair_avg"] = round(sum(clv) / len(clv), 4) if clv else None
    by: dict[str, dict] = {}
    for _d, doc in docs:
        for g in (doc.get("games") or {}).values():
            for key, s in (g.get("sides") or {}).items():
                if s.get("won") is None:
                    continue
                mid = key[2:].split("|")[0]
                b = by.setdefault(mid, {"sides": 0, "won": 0, "pnl": 0.0, "model_brier": 0.0, "model_n": 0})
                price = (s.get("first") or {}).get("price") or 0
                b["sides"] += 1
                b["won"] += s["won"]
                b["pnl"] += (price - 1) if s["won"] else -1.0
                m = (s.get("first") or {}).get("model")
                if m is not None:
                    b["model_brier"] += (m - s["won"]) ** 2
                    b["model_n"] += 1
    for b in by.values():
        b["pnl"] = round(b["pnl"], 2)
        b["model_brier"] = round(b["model_brier"] / b["model_n"], 4) if b["model_n"] else None
    sb["all_sides_by_market"] = by
    return sb
