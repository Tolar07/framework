"""
TIPSTER SLIPS — learn from the slips tipsters post on X (Architect 2026-10-08,
via the coordinator session: "learn from bet365 and SportyBet slips tipsters
post on X"). Paper only: nothing here selects a pick or stakes money, and no
finding is promoted without the Architect.

INPUT (written by the collector session; one slip per line, append-only):
  <folder>/slips_<post date UTC>.jsonl
    poster        "@handle"                     post_url  "https://x.com/<handle>/status/<id>" (the key)
    official      true for @SportyBet / @SportyBetNG "Top Picks"
    posted_at     ISO UTC                       book      "sportybet" | "bet365"
    code          SportyBet booking code        country   SportyBet site: "ng" (default) | "gh" | "ke"
    link          bet365 "Add To Your Bet Slip" URL        stated_odds  total odds the post states, or null
    legs          bet365: read from the post; SportyBet: [] — decoded here from the code. A leg:
      {sport: football|basketball, home, away, kickoff (ISO or null),
       market: football 1x2|dc|dnb|ou|btts|ah|team_total, the SportyBet specials 1up|2up
       (early payout), dc_1up, or_over ("Home Team or Over 2.5"), win_either_half, run3
       ("To Score 3 or More Goals in a Row"); basketball win|total|spread; or "other",
       selection: home|draw|away|1x|12|x2|over|under|yes|no, line (ah/spread: the SELECTED side's
       handicap), team (team_total, or_over, win_either_half: home|away; run3: home|away|any),
       price, text}
  Extra fields (e.g. "note") are ignored.

The folder is the PUBLIC repo's data/tipsters/ only once the Architect has
decided on poster names; until then it is a private folder outside any repo
(C:\\Users\\Motunrayo\\tipster_slips\\ on the desktop) — this code never copies
slips anywhere else.

DECODING: a SportyBet booking code is looked up on SportyBet's share API
(/api/<country>/orders/share/<code>) and each leg mapped to the vocabulary
above; anything else is kept as "other" (counted, not graded).
GRADING: once every leg's game is 3 h past kick-off, results come from
Flashscore through engine.universe.ResultIndex (the strict two-name match).
Football markets settle on 90 minutes — a game decided after extra time can't
settle them; basketball markets include overtime, as SportyBet's do.
A slip that has lost one leg is lost even if another leg can't be graded.
"""
from __future__ import annotations

import hashlib
import json
import re
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

from engine.universe import up_won

_SHARE = "https://www.sportybet.com/api/{cc}/orders/share/{code}"
_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
       "Accept": "application/json", "Referer": "https://www.sportybet.com/ng/",
       "Origin": "https://www.sportybet.com"}
GRADE_AFTER = timedelta(hours=3)
GIVE_UP_AFTER = timedelta(days=7)
DC = {"Home or Draw": "1x", "Home or Away": "12", "Draw or Away": "x2"}
# SportyBet market ids of the slip-only football markets (read off decoded slips, 2026-10-09)
UP = {"60200": "1up", "60100": "2up"}                  # 1X2 - 1UP / 2UP: early payout
OR_OVER = {"854": "home", "858": "away"}               # "Home Team or Over 2.5" / "Away or Over 2.5"
EITHER_HALF = {"50": "home", "51": "away"}             # "Home Team to Win Either Half"
RUN3 = {"60020": "any", "60021": "home", "60022": "away"}   # "... To Score 3 or More Goals in a Row"
# settled from the goal times / half-time score when the final score alone can't
TIMELINE = {"1up", "2up", "dc_1up", "win_either_half", "run3"}


def slip_key(slip: dict) -> str:
    return slip.get("post_url") or hashlib.sha256(json.dumps(slip, sort_keys=True).encode()).hexdigest()[:16]


def _jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def load_slips(folder: Path) -> list[dict]:
    out: dict[str, dict] = {}
    for p in sorted(folder.glob("slips_*.jsonl")):
        for s in _jsonl(p):
            out.setdefault(slip_key(s), s)
    return list(out.values())


def _done(folder: Path, prefix: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for p in sorted(folder.glob(f"{prefix}_*.jsonl")):
        for r in _jsonl(p):
            out[r["post_url"]] = r
    return out


def _append(folder: Path, prefix: str, day: str, row: dict) -> None:
    with (folder / f"{prefix}_{day}.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, separators=(",", ":"), ensure_ascii=False) + "\n")


# ── decoding SportyBet codes ─────────────────────────────────────────────────
def map_leg(event: dict) -> dict:
    """One SportyBet share-code leg -> the vocabulary (or "other")."""
    sport_id = (event.get("sport") or {}).get("id")
    sport = {"sr:sport:1": "football", "sr:sport:2": "basketball"}.get(sport_id, sport_id or "?")
    m = (event.get("markets") or [{}])[0]
    o = (m.get("outcomes") or [{}])[0]
    mid, spec, desc = str(m.get("id")), m.get("specifier") or "", (o.get("desc") or "").strip()
    try:
        price = float(o.get("odds"))
    except (TypeError, ValueError):
        price = 0.0
    ko = event.get("estimateStartTime")
    cat = (event.get("sport") or {}).get("category") or {}
    leg = {"sport": sport, "home": event.get("homeTeamName"), "away": event.get("awayTeamName"),
           "kickoff": datetime.fromtimestamp(ko / 1000, tz=UTC).strftime("%Y-%m-%dT%H:%MZ") if ko else None,
           "competition": f"{cat.get('name', '')} · {(cat.get('tournament') or {}).get('name', '')}".strip(" ·"),
           "market": "other", "selection": None, "line": None, "team": None, "price": price,
           "text": f"{m.get('desc')}: {desc}" + (f" [{spec}]" if spec else ""),
           "sb": {"event": event.get("eventId"), "market": mid, "spec": spec,
                  "open": m.get("status") in (None, 0, "0") and o.get("isActive") in (None, 1, "1")}}
    leg.update(_vocab(sport, mid, spec, desc))
    return leg


def _vocab(sport: str, mid: str, spec: str, desc: str) -> dict:
    """The vocabulary fields of one SportyBet market + outcome ({} = "other")."""
    out: dict = {}
    num = re.search(r"(?:total|hcp)=(-?\d+(?:\.\d+)?)", spec)
    first = desc.split(" ")[0].lower() if desc else ""
    if sport == "football":
        if mid == "1" and first in ("home", "draw", "away"):
            out.update(market="1x2", selection=first)
        elif mid == "10" and desc in DC:
            out.update(market="dc", selection=DC[desc])
        elif mid == "11" and first in ("home", "away"):
            out.update(market="dnb", selection=first)
        elif mid == "18" and num and first in ("over", "under"):
            out.update(market="ou", selection=first, line=float(num.group(1)))
        elif mid == "29" and first in ("yes", "no"):
            out.update(market="btts", selection=first)
        elif mid == "16" and first in ("home", "away"):
            h = re.search(r"\(([-+]?\d+(?:\.\d+)?)\)", desc)
            if h:
                out.update(market="ah", selection=first, line=float(h.group(1)))
        elif mid in ("19", "20") and num and first in ("over", "under"):
            out.update(market="team_total", selection=first, line=float(num.group(1)),
                       team="home" if mid == "19" else "away")
        elif mid in UP and first in ("home", "draw", "away"):
            out.update(market=UP[mid], selection=first)
        elif mid == "60110" and desc in DC:
            out.update(market="dc_1up", selection=DC[desc])
        elif mid in OR_OVER and num and first in ("yes", "no"):
            out.update(market="or_over", selection=first, line=float(num.group(1)), team=OR_OVER[mid])
        elif mid in EITHER_HALF and first in ("yes", "no"):
            out.update(market="win_either_half", selection=first, team=EITHER_HALF[mid])
        elif mid in RUN3 and first in ("yes", "no"):
            out.update(market="run3", selection=first, team=RUN3[mid])
    elif sport == "basketball":
        if mid == "219" and first in ("home", "away"):
            out.update(market="win", selection=first)
        elif mid == "225" and num and first in ("over", "under"):
            out.update(market="total", selection=first, line=float(num.group(1)))
        elif mid == "223" and first in ("home", "away"):
            h = re.search(r"\(([-+]?\d+(?:\.\d+)?)\)", desc)
            if h:
                out.update(market="spread", selection=first, line=float(h.group(1)))
        elif mid in ("227", "228") and num and first in ("over", "under"):
            out.update(market="team_total", selection=first, line=float(num.group(1)),
                       team="home" if mid == "227" else "away")
    return out


def remap(leg: dict) -> dict:
    """A leg decoded before its market was in the vocabulary, mapped again from
    the SportyBet market id and outcome it kept ("sb", "text")."""
    sb = leg.get("sb") or {}
    if leg.get("market") != "other" or not sb.get("market") or ": " not in (leg.get("text") or ""):
        return leg
    desc = leg["text"].split(" [")[0].rsplit(": ", 1)[1].strip()
    return {**leg, **_vocab(leg.get("sport") or "", str(sb["market"]), sb.get("spec") or "", desc)}


# Leg classes (Architect 2026-10-08: "slips are often mostly right but add a
# few very risky legs that sink the acca" — learn at LEG level):
#   aligned  — a plain market priced at 60%+ implied (<= 1.67): the double
#              chance / favourite / goals-line legs our own rules F8/F1/F2/B1 bet
#   risky    — a long price (> 2.00) or a market we can't read ("other")
#   special  — a SportyBet special we grade (1UP/2UP early payout, "or Over 2.5",
#              win either half, 3 goals in a row) at 2.00 or shorter: kept apart
#              so these short-priced favourites' legs don't blur aligned vs risky
#   middle   — everything else
PLAIN = {"1x2", "dc", "dnb", "ou", "btts", "ah", "team_total", "win", "total", "spread"}
SPECIAL = {"1up", "2up", "dc_1up", "or_over", "win_either_half", "run3"}


def leg_class(leg: dict) -> str:
    price, m = leg.get("price") or 0.0, leg.get("market")
    if (m not in PLAIN and m not in SPECIAL) or price > 2.00:
        return "risky"
    if m in SPECIAL:
        return "special"
    return "aligned" if 0 < price <= 1 / 0.60 else "middle"


def decode_code(code: str, country: str = "ng") -> tuple[list[dict], str]:
    """(legs, status) for a SportyBet booking code: status "ok" or the reason it failed."""
    url = _SHARE.format(cc=(country or "ng").lower(), code=code)
    try:
        req = urllib.request.Request(url, headers=_UA)  # noqa: S310 (fixed https URL)
        with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310 (fixed https URL)
            blob = json.loads(r.read())
    except Exception as e:  # noqa: BLE001 — retried on the next run
        return [], f"lookup failed ({str(e)[:60]})"
    if blob.get("bizCode") != 10000:
        return [], f"SportyBet: {blob.get('message') or blob.get('bizCode')}"
    data = blob.get("data") or {}
    return [map_leg(e) for e in data.get("outcomes") or []], "ok"


def decode_pending(folder: Path, now: datetime) -> list[str]:
    """Decode every SportyBet slip not decoded yet (one lookup per distinct code)."""
    notes, done, cache = [], _done(folder, "decoded"), {}
    for s in load_slips(folder):
        if s.get("book") != "sportybet" or s.get("legs") or slip_key(s) in done or not s.get("code"):
            continue
        key = (s["code"].upper(), (s.get("country") or "ng").lower())
        if key not in cache:
            cache[key] = decode_code(*key)
        legs, status = cache[key]
        if status.startswith("lookup failed"):
            notes.append(f"{s['code']}: {status} — retried next run")
            continue
        price = 1.0
        for leg in legs:
            price *= leg["price"] or 1.0
        _append(folder, "decoded", (s.get("posted_at") or now.isoformat())[:10],
                {"post_url": slip_key(s), "code": s["code"], "status": status, "legs": legs,
                 "decoded_odds": round(price, 2) if legs else None,
                 "decoded_at": now.strftime("%Y-%m-%dT%H:%MZ")})
        notes.append(f"{s['code']}: {status}, {len(legs)} legs")
    return notes


# ── settling ─────────────────────────────────────────────────────────────────
def _yes(cond: bool | None, sel: str | None) -> str | None:
    return None if cond is None else "win" if cond == (sel == "yes") else "lose"


def _run3(team: str, h: int, a: int, goals: list | None) -> bool | None:
    """Did `team` ("home" | "away" | "any") score 3+ goals in a row (no opponent goal between)?"""
    sides = ("h", "a") if team == "any" else (team[0],)
    if all((h if s == "h" else a) < 3 for s in sides):
        return False
    if goals is None:
        return None
    run, last = 0, None
    for _minute, who in goals:
        run = run + 1 if who == last else 1
        last = who
        if run >= 3 and who in sides:
            return True
    return False


def settle(leg: dict, h: int, a: int, ht: list | None = None, goals: list | None = None) -> str | None:
    """'win' | 'lose' | 'push' | 'half_win' | 'half_lose' for a leg, or None (can't settle).
    ht: the half-time score; goals: the 90-minute goals in order, [[minute, "h" | "a"], ...]
    (engine.universe.up_won) — needed only by the TIMELINE markets, and only when
    the final score can't settle them alone."""
    m, sel, line = leg.get("market"), leg.get("selection"), leg.get("line")
    if m in ("1up", "2up"):
        if sel == "draw":
            return "win" if h == a else "lose"
        w = up_won(int(m[0]), sel, h, a, goals) if sel in ("home", "away") else None
        return None if w is None else "win" if w else "lose"
    if m == "dc_1up":                                  # the double chance, or the 1UP early payout
        if (sel == "1x" and h >= a) or (sel == "x2" and h <= a) or (sel == "12" and h != a):
            return "win"
        if sel == "12":
            return "win" if h + a else "lose"         # any scored draw had a 1-goal lead first
        w = up_won(1, "home" if sel == "1x" else "away", h, a, goals)
        return None if w is None else "win" if w else "lose"
    if m == "or_over" and line is not None:
        team_won = (h > a) if leg.get("team") == "home" else (a > h)
        return _yes(team_won or h + a > line, sel)
    if m == "win_either_half":
        if not ht or None in ht:
            return None
        o1, p1 = (ht[0], ht[1]) if leg.get("team") == "home" else (ht[1], ht[0])
        o2, p2 = ((h, a) if leg.get("team") == "home" else (a, h))
        return _yes(o1 > p1 or o2 - o1 > p2 - p1, sel)
    if m == "run3":
        return _yes(_run3(leg.get("team") or "any", h, a, goals), sel)

    def cmp(x: float) -> str:
        return "win" if x > 0 else "lose" if x < 0 else "push"

    def handicap(margin: float, ln: float) -> str:
        if (ln * 4) % 2 == 1:                       # quarter line: half on each neighbour
            lo, hi = cmp(margin + ln - 0.25), cmp(margin + ln + 0.25)
            if lo == hi:
                return lo
            return "half_win" if "win" in (lo, hi) else "half_lose"
        return cmp(margin + ln)
    if m == "1x2":
        return "win" if (sel == "home" and h > a) or (sel == "draw" and h == a) or (sel == "away" and h < a) else "lose"
    if m == "dc":
        return "win" if (sel == "1x" and h >= a) or (sel == "12" and h != a) or (sel == "x2" and h <= a) else "lose"
    if m == "dnb":
        return "push" if h == a else ("win" if (sel == "home") == (h > a) else "lose")
    if m in ("ou", "total") and line is not None:
        return cmp((h + a - line) * (1 if sel == "over" else -1))
    if m == "btts":
        return "win" if (h > 0 and a > 0) == (sel == "yes") else "lose"
    if m in ("ah", "spread") and line is not None and sel in ("home", "away"):
        return handicap((h - a) if sel == "home" else (a - h), line)
    if m == "team_total" and line is not None:
        pts = h if leg.get("team") == "home" else a
        return cmp((pts - line) * (1 if sel == "over" else -1))
    if m == "win":
        return "win" if (sel == "home") == (h > a) else "lose"
    return None


FACTOR = {"lose": 0.0, "push": 1.0, "half_lose": 0.5}


def leg_factor(result: str, price: float) -> float:
    if result == "win":
        return price
    if result == "half_win":
        return (1 + price) / 2
    return FACTOR[result]


def _kickoff(leg: dict, posted: datetime) -> datetime:
    """A leg's kick-off; the post time when it is missing or not a date (a
    collector-read race card says "Newmarket 1:15")."""
    try:
        return datetime.fromisoformat(leg["kickoff"].replace("Z", "+00:00"))
    except (KeyError, AttributeError, ValueError):
        return posted


def grade_due(folder: Path, index: dict, now: datetime,
              timeline: Callable[[str, str, str], dict | None] | None = None) -> list[str]:
    """Grade every decoded slip whose games are all 3 h past kick-off.
    timeline(home, away, ko) -> {goals, ht} (data.fotmob.Timelines.find) settles
    the TIMELINE markets the final score can't; if it fails the slip waits."""
    notes, graded, decoded = [], _done(folder, "graded"), _done(folder, "decoded")
    for s in load_slips(folder):
        key = slip_key(s)
        if key in graded:
            continue
        legs = [remap(leg) for leg in s.get("legs") or (decoded.get(key) or {}).get("legs") or []]
        if not legs:
            continue
        posted = datetime.fromisoformat((s.get("posted_at") or now.isoformat()).replace("Z", "+00:00"))
        kos = [_kickoff(leg, posted) for leg in legs]
        if now - max(kos) < GRADE_AFTER:
            continue
        out_legs, factor, unknown = [], 1.0, []
        for leg, ko in zip(legs, kos, strict=True):
            hit = None
            idx = index.get(leg.get("sport"))
            if idx is not None and leg.get("home") and leg.get("away"):
                hit = idx.find(leg["home"], leg["away"], ko.strftime("%Y-%m-%dT%H:%MZ"))
            res = None
            if hit is not None and not (leg.get("sport") == "football" and hit.get("finished_other")):
                h, a = hit["fthg"], hit["ftag"]
                ht = [hit.get("fh_home"), hit.get("fh_away")]
                res = settle(leg, h, a, ht)
                if res is None and leg.get("market") in TIMELINE and timeline is not None:
                    try:
                        tl = timeline(leg["home"], leg["away"], ko.strftime("%Y-%m-%dT%H:%MZ"))
                    except Exception:  # noqa: BLE001 — FotMob down: the slip waits for the next run
                        tl = None
                    if tl and len(tl["goals"]) == h + a:          # a timeline that disagrees with the score is not used
                        res = settle(leg, h, a, tl.get("ht") if None in ht else ht, tl["goals"])
            out_legs.append({**leg, "result": res, "score": [hit["fthg"], hit["ftag"]] if hit else None})
            if res is None:
                unknown.append(leg.get("text") or leg.get("market"))
            else:
                factor *= leg_factor(res, leg["price"] or 1.0)
        lost = any(leg["result"] == "lose" for leg in out_legs)
        if unknown and not lost and now - max(kos) < GIVE_UP_AFTER:
            continue                                   # wait for the missing result(s)
        status = "lost" if lost else ("won" if not unknown else "ungradable")
        implied = 1.0
        for leg in legs:
            implied *= 1 / leg["price"] if leg.get("price") else 1.0
        _append(folder, "graded", (s.get("posted_at") or now.isoformat())[:10], {
            "post_url": key, "poster": s.get("poster"), "official": bool(s.get("official")),
            "book": s.get("book"), "posted_at": s.get("posted_at"), "stated_odds": s.get("stated_odds"),
            "status": status, "payout": round(factor, 4) if status != "ungradable" else None,
            "implied": implied, "legs": out_legs, "unknown": unknown,
            "graded_at": now.strftime("%Y-%m-%dT%H:%MZ")})
        notes.append(f"{s.get('code') or s.get('link')}: {status}")
    return notes


def load_graded(folder: Path) -> list[dict]:
    return list(_done(folder, "graded").values())
