"""
MULTI-SPORT BOARDS — every sport of the rollout after ice hockey (standing order 50; Architect
2026-11-05 23:34: "build everything ... all these sports ... schedule their practice to be done
soon. Get everything up and running"). Ice hockey has its own board (engine/ice_hockey.py, NHL
goals model); this module runs the other eight on one method:

  * every SportyBet game of the sport kicking off inside WINDOW, every side of every market in
    SPORTS[sport]["markets"], keyed "<sport>:<market id>|<specifier>|<outcome>";
  * the sharp reference = the Matchbook exchange's fair chance where Matchbook lists the same
    bet (CANON maps a SportyBet market onto the exchange's canonical key, engine/exchange.py);
  * the sport's own model = an Elo rating per team/player, learned from EVERY finished game of the
    sport on Flashscore (not only board games), updated at each grading run (learn());
    used on the winner market once both sides have MIN_GAMES rated games, blended as order 18:
    75% SportyBet (margin removed) + 25% Elo;
  * a side qualifies like a world basketball / hockey pick: price in BAND, chance >= 50%, value =
    price x chance - 1 >= +3% on a winner market or >= +5% on a line, at most +25%;
    one pick per game, the best value, FROZEN at the look it first qualified, with its own
    SportyBet booking code and the fields the bots read for wb_/ih_ picks;
  * every side of every game keeps its first and last look and is graded after the game (the
    paper record that learns from all markets, bet or not).
PAPER until the sport's live_from date in config/sport_rollout.json; live from then, gate or not.
NO STEAM (order 50): prices are recorded for value and CLV, never followed.

Written to output/multisport/<sport>/ms_<kick-off UTC date>.json; graded by run_multisport.py.
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from engine import exchange as ex

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "output" / "multisport"
DATA_DIR = ROOT / "data" / "multisport"
ROLLOUT = ROOT / "config" / "sport_rollout.json"
WINDOW = timedelta(hours=24)
BAND = (1.20, 2.00)
MIN_VALUE, LINE_VALUE, MAX_VALUE = 0.03, 0.05, 0.25
LIQ = 10.0
ANCHOR = 0.75
ELO_K, ELO_START, MIN_GAMES = 24.0, 1500.0, 8
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
_FEED = ("https://www.sportybet.com/api/ng/factsCenter/pcUpcomingEvents"
         "?sportId=sr:sport:{sid}&marketId={mk}&pageSize=100&pageNum={page}")
_MB = ("https://api.matchbook.com/edge/rest/events?sport-ids={ids}&states=open&include-prices=true"
       "&price-depth=1&odds-type=DECIMAL&exchange-type=back-lay&currency=GBP&per-page=100&offset={off}")

# winner: the market that settles on who wins (Elo prices it). periods: Flashscore period
# pairs counted as "regulation" for market 1 / 60 (None = the final score is regulation).
# canon: SportyBet market id -> exchange canonical prefix where Matchbook lists the same bet.
# exclude: competitions left out (table tennis integrity: Setka Cup and similar, order 50).
SPORTS: dict[str, dict] = {
    "american_football": {"sb": 16, "fs": 5, "mb": [1], "markets": "219,1,60,223,225", "winner": "219",
                          "reg_periods": 4, "canon": {"219": "ml", "223": "hcp", "225": "total"}},
    "snooker": {"sb": 19, "fs": 15, "mb": [120], "markets": "186,493,494", "winner": "186",
                "canon": {"186": "ml"}},
    "darts": {"sb": 22, "fs": 14, "mb": [116], "markets": "186", "winner": "186", "canon": {"186": "ml"}},
    "volleyball": {"sb": 23, "fs": 12, "mb": [1939998342510016], "markets": "186,188,237,238", "winner": "186",
                   "canon": {"186": "ml"}},
    "table_tennis": {"sb": 20, "fs": 25, "mb": [1389388027310017], "markets": "186,237,238", "winner": "186",
                     "canon": {"186": "ml"}, "exclude": ("setka", "tt cup", "liga pro", "elite series")},
    "cricket": {"sb": 21, "fs": 13, "mb": [110], "markets": "340,1,10,11", "winner": "340",
                "canon": {"340": "ml", "1": "1x2"}},
    "rugby": {"sb": 12, "fs": 8, "mb": [18, 114], "markets": "1,406,10,11,16,14,18", "winner": "406",
              "canon": {"1": "1x2", "16": "hcp", "18": "total"}},
    "tennis": {"sb": 5, "fs": 2, "mb": [9], "markets": "186,187,188,189,202", "winner": "186",
               "canon": {"186": "ml", "187": "hcp", "189": "total"}},
    "baseball": {"sb": 3, "fs": 6, "mb": [3], "markets": "251,256,258", "winner": "251",
                 "canon": {"251": "ml", "256": "hcp", "258": "total"}},
}
WINNER_MARKETS = {"186", "219", "251", "340", "406", "1"}


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310 — fixed https hosts
        return json.loads(r.read().decode("utf-8"))


def split_key(key: str) -> tuple[str, str, str, str]:
    """'tennis:186||Home' -> ('tennis', '186', '', 'Home')."""
    sport, rest = key.split(":", 1)
    mid, spec, out = (rest.split("|") + ["", ""])[:3]
    return sport, mid, spec, out


def is_paper(sport: str, day: str, path: Path = ROLLOUT) -> bool:
    """Paper until the sport's live_from date (order 50); a missing or non-date live_from = paper."""
    try:
        cfg = json.loads(path.read_text(encoding="utf-8"))
        s = next(x for x in cfg["sports"] if x["sport"] == sport or sport in x.get("covers", []))
        return not re.fullmatch(r"\d{4}-\d{2}-\d{2}", s["live_from"]) or day < s["live_from"]
    except Exception:  # noqa: BLE001 — no readable schedule = stay on paper
        return True


# ── SportyBet ───────────────────────────────────────────────────────────────────────────────
def fetch_sportybet(sport: str, get=_get) -> list[dict]:
    cfg = SPORTS[sport]
    rows, page = [], 1
    while page <= 10:
        d = (get(_FEED.format(sid=cfg["sb"], mk=cfg["markets"], page=page)) or {}).get("data") or {}
        for t in d.get("tournaments") or []:
            if any(x in (t.get("name") or "").lower() for x in cfg.get("exclude", ())):
                continue
            for e in t.get("events") or []:
                rows.append(row_of(sport, e, t))
        if page * 100 >= int(d.get("totalNum") or 0):
            break
        page += 1
    return rows


def row_of(sport: str, e: dict, t: dict) -> dict:
    cat = (e.get("sport") or {}).get("category") or {}
    ko = datetime.fromtimestamp(int(e.get("estimateStartTime", 0)) / 1000, tz=timezone.utc)
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
            key = f"{sport}:{m.get('id')}|{m.get('specifier') or ''}|{o.get('desc')}"
            sides[key] = price
            oids[key] = o.get("id")
    return {"id": e.get("eventId"), "sport": sport, "country": cat.get("name"), "comp": t.get("name"),
            "home": e.get("homeTeamName"), "away": e.get("awayTeamName"),
            "ko": ko.strftime("%Y-%m-%dT%H:%M:%SZ"), "sides": sides, "oids": oids}


def match_name(name: str) -> str:
    """'Monteiro, Thiago' (SportyBet's player form) -> 'Thiago Monteiro' (the exchange's)."""
    if name and name.count(",") == 1:
        last, first = (x.strip() for x in name.split(","))
        return f"{first} {last}"
    return name or ""


def devig(key: str, sides: dict) -> float | None:
    _s, mid, spec, _o = split_key(key)
    group = {k: v for k, v in sides.items() if split_key(k)[1:3] == (mid, spec)}
    if len(group) < 2 or any(v <= 1 for v in group.values()):
        return None
    return (1 / sides[key]) / sum(1 / v for v in group.values())


# ── Matchbook exchange ──────────────────────────────────────────────────────────────────────
def fetch_matchbook(sport: str, get=_get) -> list[dict]:
    out: list[dict] = []
    try:
        ids = ",".join(str(x) for x in SPORTS[sport]["mb"])
        while len(out) < 1000:
            d = get(_MB.format(ids=ids, off=len(out)))
            evs = d.get("events") or []
            out += evs
            if not evs or len(out) >= int(d.get("total") or 0):
                break
    except Exception:  # noqa: BLE001 — no exchange = Elo / record only, never a blocked board
        pass
    return out


def canonical(key: str) -> list[str]:
    """Exchange canonical keys that pay the same as this SportyBet side (first found wins)."""
    sport, mid, spec, out = split_key(key)
    kind = SPORTS.get(sport, {}).get("canon", {}).get(mid)
    o = out.strip().lower()
    if kind == "ml" and o in ("home", "away"):
        return [f"ml|{o}", f"1x2|{o}"]          # a two-way Match Odds book is keyed 1x2 on Matchbook
    if kind == "1x2" and o in ("home", "draw", "away"):
        return [f"1x2|{o}"]
    if kind == "hcp":
        mm = re.fullmatch(r"(home|away) \(([+-]?\d+(?:\.\d+)?)\)", o)
        if mm and float(mm.group(2)) % 1 == 0.5:
            return [f"hcp|{float(mm.group(2)):g}|{mm.group(1)}"]
    if kind == "total":
        mm = re.fullmatch(r"total=(\d+(?:\.\d+)?)", spec)
        if mm and float(mm.group(1)) % 1 == 0.5 and o.startswith(("over", "under")):
            return [f"total|{float(mm.group(1)):g}|{o.split()[0]}"]
    return []


def quote(key: str, idx: dict) -> dict | None:
    for c in canonical(key):
        b = idx.get(c)
        if b and b.get("p"):
            return b
    return None


# ── Elo, learned from every finished game of the sport ─────────────────────────────────────
def elo_path(sport: str) -> Path:
    return DATA_DIR / sport / "elo.json"


def load_elo(sport: str) -> dict:
    p = elo_path(sport)
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"ratings": {}, "games": {}, "seen": [], "brier": [0.0, 0]}


def norm(name: str) -> str:
    return ex.norm(name or "")


def elo_p(elo: dict, home: str, away: str) -> float | None:
    """Home side's chance to win, or None until both have MIN_GAMES rated games."""
    h, a = norm(home), norm(away)
    gh, ga = elo["games"].get(h, 0), elo["games"].get(a, 0)
    if gh < MIN_GAMES or ga < MIN_GAMES:
        return None
    rh, ra = elo["ratings"].get(h, ELO_START), elo["ratings"].get(a, ELO_START)
    return 1 / (1 + 10 ** ((ra - rh) / 400))


def learn(elo: dict, games: list[dict]) -> int:
    """Update ratings with finished games not seen before (oldest first). The pre-game chance of
    every game where both sides were rated is scored (Brier) first: the model's walk-forward
    record. Returns how many games were added."""
    seen = set(elo.get("seen") or [])
    n = 0
    for g in sorted(games, key=lambda x: x.get("kickoff_utc") or ""):
        gid = f"{g['home']}|{g['away']}|{g.get('kickoff_utc') or ''}"
        if gid in seen or g.get("winner") not in (1, 2):
            continue
        h, a = norm(g["home"]), norm(g["away"])
        p = elo_p(elo, g["home"], g["away"])
        y = 1.0 if g["winner"] == 1 else 0.0
        if p is not None:
            elo["brier"][0] += (p - y) ** 2
            elo["brier"][1] += 1
        rh, ra = elo["ratings"].get(h, ELO_START), elo["ratings"].get(a, ELO_START)
        e = 1 / (1 + 10 ** ((ra - rh) / 400))
        elo["ratings"][h] = round(rh + ELO_K * (y - e), 2)
        elo["ratings"][a] = round(ra - ELO_K * (y - e), 2)
        elo["games"][h] = elo["games"].get(h, 0) + 1
        elo["games"][a] = elo["games"].get(a, 0) + 1
        seen.add(gid)
        n += 1
    elo["seen"] = sorted(seen)[-20000:]
    return n


def save_elo(sport: str, elo: dict) -> None:
    p = elo_path(sport)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(elo, ensure_ascii=False), encoding="utf-8")


def model_chances(row: dict, elo: dict) -> dict[str, float]:
    """Elo's chance for the winner market's two sides."""
    w = SPORTS[row["sport"]]["winner"]
    p = elo_p(elo, row.get("home") or "", row.get("away") or "")
    if p is None:
        return {}
    out = {}
    for key in row["sides"]:
        _s, mid, _spec, o = split_key(key)
        if mid == w and o.lower() in ("home", "away"):
            out[key] = round(p if o.lower() == "home" else 1 - p, 4)
    return out


# ── picking ─────────────────────────────────────────────────────────────────────────────────
def qualifies(key: str, price: float, p: float) -> float | None:
    value = price * p - 1
    need = MIN_VALUE if split_key(key)[1] in WINNER_MARKETS else LINE_VALUE
    return value if BAND[0] <= price <= BAND[1] and p >= 0.50 and need <= value <= MAX_VALUE else None


def candidates(row: dict, idx: dict, model: dict[str, float]) -> list[dict]:
    out = []
    for key, price in row["sides"].items():
        b = quote(key, idx)
        if b and (b.get("liq") or 0) >= LIQ:
            v = qualifies(key, price, b["p"])
            if v is not None:
                out.append({"key": key, "price": price, "fair": round(b["p"], 4), "value": round(v, 4),
                            "source": "matchbook", "back": b.get("back"), "lay": b.get("lay"), "liq": b.get("liq")})
            continue
        if key in model and not b:
            q = devig(key, row["sides"])
            if q is None:
                continue
            p = ANCHOR * q + (1 - ANCHOR) * model[key]
            v = qualifies(key, price, p)
            if v is not None:
                out.append({"key": key, "price": price, "fair": round(p, 4), "value": round(v, 4),
                            "source": "elo (75% SportyBet)", "model": model[key]})
    return out


def describe(key: str, home: str, away: str) -> str:
    _s, mid, spec, out = split_key(key)
    o = out.strip()
    side = {"home": home, "away": away}.get(o.lower())
    if side and mid in WINNER_MARKETS:
        return f"{side} to win"
    mm = re.fullmatch(r"(Home|Away) \(([+-]?[\d.:]+)\)", o)
    if mm:
        return f"{home if mm.group(1) == 'Home' else away} {mm.group(2)}"
    return f"{o} [{mid} {spec}]".strip()


def venues(key: str, on_matchbook: bool) -> dict:
    sport, mid, _spec, _o = split_key(key)
    canon = SPORTS.get(sport, {}).get("canon", {})
    return {"sportybet": True, "matchbook": on_matchbook and mid in canon, "betfair_market": mid in canon}


def _book(sel: dict) -> str | None:
    if os.environ.get("GITHUB_ACTIONS") != "true":
        return None
    try:
        from pipeline.sportybet_booking import create_booking_code
        return create_booking_code([sel])[0]
    except Exception:  # noqa: BLE001 — PENDING, retried next look
        return None


def path_for(sport: str, day: str, folder: Path = OUT_DIR) -> Path:
    return folder / sport / f"ms_{day}.json"


def update(sport: str, rows: list[dict], mb_events: list[dict], elo: dict, now: datetime,
           folder: Path = OUT_DIR, book=_book) -> tuple[int, int]:
    """One look for one sport: record every side, freeze new picks. Returns (games, picks added)."""
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
            p = path_for(sport, day, folder)
            docs[day] = (json.loads(p.read_text(encoding="utf-8")) if p.exists()
                         else {"date": day, "sport": sport, "picks": [], "games": {}})
        doc = docs[day]
        doc["paper"] = is_paper(sport, day)
        mb = ex.match_event(match_name(r["home"]), match_name(r["away"]), ko, mb_events)
        idx = ex.index_event(mb) if mb else {}
        model = model_chances(r, elo)
        g = doc["games"].setdefault(r["id"], {"country": r.get("country"), "comp": r.get("comp"),
                                              "home": r["home"], "away": r["away"], "ko": r["ko"],
                                              "sides": {}, "result": None})
        g["matchbook"] = bool(mb)
        for key, price in r["sides"].items():
            b = quote(key, idx)
            look = {"price": price, "fair": round(b["p"], 4) if b else None, "model": model.get(key), "at": at}
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
        _s, mid, spec, out = split_key(best["key"])
        oid = r["oids"].get(best["key"])
        code = book({"eventId": r["id"], "marketId": mid, "specifier": spec, "outcomeId": oid}) if oid else None
        doc["picks"].append({"sb_event_id": r["id"], "country": r.get("country"), "comp": r.get("comp"),
                             "home": r["home"], "away": r["away"], "ko": r["ko"], "sport": sport,
                             "pick": describe(best["key"], r["home"], r["away"]), **best,
                             "market_id": mid, "specifier": spec, "outcome": out, "outcome_id": oid,
                             "code": code, "venues": venues(best["key"], mb is not None),
                             "chance": best["fair"], "tip": r["ko"], "event_id": r["id"],
                             "paper": doc["paper"], "at": at, "result": None})
        added += 1
    for day, doc in docs.items():
        p = path_for(sport, day, folder)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    return seen, added


# ── results and grading ─────────────────────────────────────────────────────────────────────
def parse_flashscore(text: str) -> list[dict]:
    """Finished games of a Flashscore day feed: final AG/AH, winner AS (1/2), periods BA.. ."""
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
            ko = datetime.fromtimestamp(int(kv.get("AD", "0")), tz=timezone.utc)
        except (KeyError, ValueError):
            continue
        periods = []
        for hk, ak in (("BA", "BB"), ("BC", "BD"), ("BE", "BF"), ("BG", "BH"), ("BI", "BJ")):
            try:
                periods.append([int(kv[hk]), int(kv[ak])])
            except (KeyError, ValueError):
                break
        win = kv.get("AS")
        out.append({"league": league, "home": kv.get("AE", ""), "away": kv.get("AF", ""),
                    "fthg": fh, "ftag": fa, "final": [fh, fa], "periods": periods,
                    "winner": int(win) if win in ("1", "2") else None, "stage": kv.get("AC"),
                    "kickoff_utc": ko.strftime("%Y-%m-%dT%H:%M:%SZ")})
    return out


def results_days(sport: str, days: list[date], today: date | None = None) -> list[dict]:
    from data import flashscore_results as fr
    today = today or datetime.now(timezone.utc).date()
    sign = fr.feed_sign()
    out: list[dict] = []
    for d in days:
        off = (d - today).days
        if off > 0 or off < -7:
            continue
        try:
            text = fr._get(fr._FEED.replace("f_1_", f"f_{SPORTS[sport]['fs']}_").format(offset=off),
                           {"x-fsign": sign, "Referer": "https://www.flashscore.co.uk/"})
            out += parse_flashscore(text)
        except Exception:  # noqa: BLE001 — ungraded now, retried next run
            continue
    return out


def _num(spec: str, key: str) -> float | None:
    m = re.search(rf"{key}=([+-]?\d+(?:\.\d+)?)", spec or "")
    return float(m.group(1)) if m else None


def settle(sport: str, mid: str, spec: str, outcome: str, r: dict) -> int | None:
    """1 won / 0 lost / None void or not settleable from the result, for one side."""
    o = (outcome or "").strip().lower()
    fh, fa = r["final"]
    per = r.get("periods") or []
    win = r.get("winner") or (1 if fh > fa else 2 if fa > fh else None)
    reg_n = SPORTS.get(sport, {}).get("reg_periods")
    if reg_n and len(per) >= reg_n:
        rh, ra = sum(p[0] for p in per[:reg_n]), sum(p[1] for p in per[:reg_n])
    else:
        rh, ra = fh, fa
    # points/games across all periods (tennis games, volleyball / table tennis points)
    ph, pa = (sum(p[0] for p in per), sum(p[1] for p in per)) if per else (None, None)
    if mid in ("186", "219", "251", "340", "406"):
        if win is None:
            return None
        return int(o == ("home" if win == 1 else "away"))
    if mid == "1":
        res = "home" if rh > ra else "away" if ra > rh else "draw"
        return int(o == res)
    if mid == "60":
        if len(per) < 2:
            return None
        h1, a1 = per[0][0] + per[1][0], per[0][1] + per[1][1]
        return int(o == ("home" if h1 > a1 else "away" if a1 > h1 else "draw"))
    if mid == "10":
        res = "home" if rh > ra else "away" if ra > rh else "draw"
        parts = {"home or draw": {"home", "draw"}, "home or away": {"home", "away"},
                 "draw or away": {"draw", "away"}, "1x": {"home", "draw"}, "12": {"home", "away"},
                 "x2": {"draw", "away"}}.get(o)
        return int(res in parts) if parts else None
    if mid == "11":
        if rh == ra:
            return None
        return int(o == ("home" if rh > ra else "away"))
    if mid == "202":
        n = int(_num(spec, "setnr") or 0)
        if n < 1 or len(per) < n or per[n - 1][0] == per[n - 1][1]:
            return None
        return int(o == ("home" if per[n - 1][0] > per[n - 1][1] else "away"))
    hc = re.fullmatch(r"(home|away) \(([+-]?\d+(?:\.\d+)?)\)", o)
    if mid in ("223", "16", "256", "493", "188", "187", "237") and hc:
        if mid in ("187", "237"):
            if ph is None:
                return None
            h, a = ph, pa
        elif mid == "16":
            h, a = rh, ra
        else:
            h, a = fh, fa
        m = (h - a) if hc.group(1) == "home" else (a - h)
        v = m + float(hc.group(2))
        return None if v == 0 else int(v > 0)
    if mid == "14":
        mm = re.fullmatch(r"(home|draw|away) \((\d+):(\d+)\)", o)
        if not mm:
            return None
        m = rh - ra + int(mm.group(2)) - int(mm.group(3))
        return int(mm.group(1) == ("home" if m > 0 else "away" if m < 0 else "draw"))
    if mid in ("225", "18", "258", "494", "189", "238"):
        line = _num(spec, "total")
        if line is None or not o.startswith(("over", "under")):
            return None
        if mid in ("189", "238"):
            if ph is None:
                return None
            tot = ph + pa
        elif mid == "18":
            tot = rh + ra
        else:
            tot = fh + fa
        if tot == line:
            return None
        return int((tot > line) == o.startswith("over"))
    return None


def grade_doc(sport: str, doc: dict, events: list[dict], now: datetime) -> int:
    from data import flashscore_results as fr
    n = 0
    for gid, g in (doc.get("games") or {}).items():
        if g.get("result"):
            continue
        ko = ex._dt(g.get("ko"))
        if ko is None or now < ko + timedelta(hours=3):
            continue
        ev = fr.find_result(events, g["home"] or "", g["away"] or "", g["ko"])
        if not ev or "final" not in ev:
            continue
        g["result"] = {"final": ev["final"], "periods": ev.get("periods"), "winner": ev.get("winner"),
                       "stage": ev.get("stage")}
        for key, s in g["sides"].items():
            _sp, mid, spec, o = split_key(key)
            s["won"] = settle(sport, mid, spec, o, ev)
        for p in doc.get("picks") or []:
            if p["sb_event_id"] != gid or p.get("result"):
                continue
            w = settle(sport, p["market_id"], p["specifier"], p["outcome"], ev)
            last = (g["sides"].get(p["key"]) or {}).get("last") or {}
            p["result"] = "void" if w is None else "won" if w else "lost"
            p["pnl"] = 0.0 if w is None else round(p["price"] - 1, 4) if w else -1.0
            p["close_price"] = last.get("price")
            p["clv"] = round(p["price"] / last["price"] - 1, 4) if last.get("price") else None
            p["clv_fair"] = round(p["price"] * last["fair"] - 1, 4) if last.get("fair") else None
        n += 1
    return n


def load_all(sport: str, folder: Path = OUT_DIR) -> list[tuple[str, dict]]:
    out = []
    d = folder / sport
    for f in sorted(d.glob("ms_*.json")) if d.exists() else []:
        try:
            out.append((f.stem[3:], json.loads(f.read_text(encoding="utf-8"))))
        except (OSError, ValueError):
            continue
    return out


def scoreboard(docs: list[tuple[str, dict]], elo: dict | None = None) -> dict:
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
                mid = split_key(key)[1]
                b = by.setdefault(mid, {"sides": 0, "won": 0, "pnl": 0.0})
                price = (s.get("first") or {}).get("price") or 0
                b["sides"] += 1
                b["won"] += s["won"]
                b["pnl"] = round(b["pnl"] + ((price - 1) if s["won"] else -1.0), 2)
    sb["all_sides_by_market"] = by
    if elo:
        n = elo["brier"][1]
        sb["elo"] = {"rated": len(elo["ratings"]), "games_learned": len(elo.get("seen") or []),
                     "walk_forward_brier": round(elo["brier"][0] / n, 4) if n else None, "scored": n}
    return sb
