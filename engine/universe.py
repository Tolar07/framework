"""
UNIVERSE — every SportyBet football and basketball game, covered or not,
priced before kick-off and graded after (Architect 2026-10-07: "learn ...
how the game is played, how the betting goes on them and how it can learn
and improve its own prediction model").

The board only sees the leagues it covers. This sees all of them: every
sweep (monitor/universe_sweep.py) reads SportyBet's whole upcoming list
for both sports and keeps, per game, the FIRST and LAST price seen before
kick-off (how the betting moved) and whether the framework covers it. After
the game, its result is matched from Flashscore with the same strict rule
as grading (both names, unambiguous — a loose match would teach the wrong
lesson, ID48) and the game is written once to data/universe/graded_<month>.jsonl.
backtest/universe_study.py turns that into what the market gets right and
wrong, league by league and market by market.

Prices kept (raw SportyBet decimals, so returns can be measured):
  football    1X2 (1), Over/Under 1.5 / 2.5 / 3.5 (18), BTTS (29), Double Chance (10),
              1X2 - 2UP (60100) and 1X2 - 1UP (60200): SportyBet's early payout — the
              team's bet pays as soon as it leads by 2 (1), else as a plain 1X2
  basketball  winner incl. OT (219), the main total (225) and main handicap (223):
              the line SportyBet prices closest to even
Football bets settle on 90 minutes: a game decided after extra time keeps
its result but is flagged and never read as a 90-minute score. An early-payout
bet the final score can't settle (the team scored enough to have led, but
didn't win) needs the goal times: the sweep adds them from FotMob
(data.fotmob.goal_timeline) as result["goals"]; without them that side is
left unsettled, never guessed.
"""
from __future__ import annotations

import gzip
import json
import re
import unicodedata
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
PENDING = ROOT / "data" / "cache" / "universe" / "pending.json.gz"   # Actions cache, not git
GRADED_DIR = ROOT / "data" / "universe"
SPORTS = {"football": ("sr:sport:1", "1,18,29,10,60100,60200", 1),"basketball": ("sr:sport:2", "219,225,223", 3)}
GRADE_AFTER = timedelta(hours=3)        # a game is looked up 3 h after kick-off
GIVE_UP_AFTER = timedelta(days=7)       # Flashscore keeps 7 days
OU_LINES = ("1.5", "2.5", "3.5")
UP = {"60100": ("2up", 2), "60200": ("1up", 1)}   # SportyBet market id -> (price key, lead that pays early)


def _f(x) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v > 1.0 else None


def _num(spec: str, key: str) -> str | None:
    m = re.search(rf"{key}=(-?\d+(?:\.\d+)?)", spec or "")
    return m.group(1) if m else None


def prices(sport: str, event: dict) -> dict:
    """The kept markets of one SportyBet event, raw decimal prices."""
    out: dict = {}
    main: dict[str, tuple[float, list]] = {}
    for m in event.get("markets", []):
        if m.get("status") not in (None, 0, "0"):
            continue                     # closed / suspended line: not a real offer
        mid, spec = str(m.get("id")), m.get("specifier") or ""
        px = {(o.get("desc") or "").strip(): _f(o.get("odds")) for o in m.get("outcomes", [])}
        if sport == "football":
            if mid == "1" and all(px.get(k) for k in ("Home", "Draw", "Away")):
                out["1x2"] = [px["Home"], px["Draw"], px["Away"]]
            elif mid == "18":
                line = _num(spec, "total")
                o, u = px.get(f"Over {line}"), px.get(f"Under {line}")
                if line in OU_LINES and o and u:
                    out[f"ou{line}"] = [o, u]
            elif mid == "29" and px.get("Yes") and px.get("No"):
                out["btts"] = [px["Yes"], px["No"]]
            elif mid == "10":
                dc = [px.get("Home or Draw") or px.get("1X"), px.get("Home or Away") or px.get("12"),
                      px.get("Draw or Away") or px.get("X2")]
                if all(dc):
                    out["dc"] = dc
            elif mid in UP and all(px.get(k) for k in ("Home", "Draw", "Away")):
                out[UP[mid][0]] = [px["Home"], px["Draw"], px["Away"]]
        else:
            if mid == "219" and px.get("Home") and px.get("Away"):
                out["win"] = [px["Home"], px["Away"]]
            elif mid in ("225", "223"):
                vals = [v for v in px.values() if v]
                if len(vals) != 2:
                    continue
                if mid == "225":
                    line = _num(spec, "total")
                    pair = [px.get(f"Over {line}"), px.get(f"Under {line}")]
                else:
                    line = _num(spec, "hcp")
                    pair = [next((v for k, v in px.items() if k.startswith("Home")), None),
                            next((v for k, v in px.items() if k.startswith("Away")), None)]
                first, second = pair
                if line is None or first is None or second is None:
                    continue
                gap = abs(1 / first - 1 / second)           # closest to even = main line
                key = "total" if mid == "225" else "hcp"
                if key not in main or gap < main[key][0]:
                    main[key] = (gap, [float(line), first, second])
    for key, (_g, row) in main.items():
        out[key] = row
    return out


def event_row(sport: str, event: dict, tournament: dict, covered_ids: set[str], now: datetime) -> dict:
    cat = (event.get("sport") or {}).get("category") or {}
    ko = datetime.fromtimestamp(event["estimateStartTime"] / 1000, tz=UTC)
    snap = {"at": now.strftime("%Y-%m-%dT%H:%MZ"), "p": prices(sport, event)}
    return {"sport": sport, "id": event.get("eventId"), "country": cat.get("name"),
            "comp": tournament.get("name"), "tid": tournament.get("id"),
            "covered": tournament.get("id") in covered_ids,
            "ko": ko.strftime("%Y-%m-%dT%H:%MZ"), "home": event.get("homeTeamName"),
            "away": event.get("awayTeamName"), "first": snap, "last": snap, "looks": 1}


def update(pending: dict, rows: list[dict]) -> int:
    """Merge a sweep into `pending` ({event id: row}); the first look is kept,
    the last look replaced. Returns how many games were new."""
    new = 0
    for r in rows:
        if not r["id"] or not r["last"]["p"]:
            continue
        old = pending.get(r["id"])
        if old is None:
            pending[r["id"]] = r
            new += 1
        else:
            old["last"], old["looks"], old["ko"] = r["last"], old["looks"] + 1, r["ko"]
    return new


# ── results ──────────────────────────────────────────────────────────────────
def _norm(name: str) -> str:
    n = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9 ]", " ", n)


def _tokens(name: str) -> set[str]:
    return {t for t in _norm(name).split() if len(t) >= 3}


class ResultIndex:
    """Flashscore results indexed by date and name word, so thousands of games
    match in seconds; the match itself is flashscore_results' strict rule."""

    def __init__(self, events: list[dict]):
        self.by_key: dict[tuple[str, str], list[dict]] = {}
        for e in events:
            if not (e.get("finished_regular") or e.get("finished_other")) or e.get("fthg") is None:
                continue
            d = (e.get("kickoff_utc") or "")[:10]
            for t in _tokens(e.get("home", "")) | _tokens(e.get("away", "")):
                self.by_key.setdefault((d, t), []).append(e)

    def find(self, home: str, away: str, ko: str) -> dict | None:
        from data import flashscore_results as fr
        d0 = datetime.fromisoformat(ko[:10])
        cands: dict[int, dict] = {}
        for off in (-1, 0, 1):
            d = (d0 + timedelta(days=off)).strftime("%Y-%m-%d")
            for t in _tokens(home) | _tokens(away):
                for e in self.by_key.get((d, t), []):
                    cands[id(e)] = e
        return fr.find_result(list(cands.values()), home, away, ko[:10]) if cands else None


def result_of(sport: str, e: dict) -> dict:
    if sport == "football":
        return {"h": e["fthg"], "a": e["ftag"], "ht": [e.get("fh_home"), e.get("fh_away")],
                "after_90": bool(e.get("finished_other"))}
    return {"h": e["fthg"], "a": e["ftag"]}


def grade(pending: dict, index: dict[str, ResultIndex], now: datetime,
          goals_of: Callable[[dict], list | None] | None = None) -> tuple[list[dict], int]:
    """(graded rows to archive, games given up on). Graded and given-up games
    leave `pending`; a game too recent to look up stays. `goals_of(row)` gives
    a game's 90-minute goal times (None: the source doesn't have the game) for
    the early-payout bets the score alone can't settle; when it raises (source
    down) the game waits for the next sweep."""
    done, gave_up = [], 0
    for eid in list(pending):
        r = pending[eid]
        ko = datetime.fromisoformat(r["ko"].replace("Z", "+00:00"))
        if now - ko < GRADE_AFTER:
            continue
        hit = index[r["sport"]].find(r["home"], r["away"], r["ko"])
        if hit is not None:
            res = result_of(r["sport"], hit)
            if goals_of is not None and needs_goals(r, res):
                try:
                    goals = goals_of(r)
                except Exception:  # noqa: BLE001 — source down: retried next sweep
                    if now - ko < GIVE_UP_AFTER:
                        continue
                    goals = None
                if goals is not None and len(goals) == res["h"] + res["a"]:
                    res["goals"] = goals          # a timeline that disagrees with the score is not used
            done.append({**r, "result": res, "graded_at": now.strftime("%Y-%m-%dT%H:%MZ")})
            del pending[eid]
        elif now - ko > GIVE_UP_AFTER:
            done.append({**r, "result": None, "graded_at": now.strftime("%Y-%m-%dT%H:%MZ")})
            gave_up += 1
            del pending[eid]
    return done, gave_up


# ── storage ──────────────────────────────────────────────────────────────────
def load_pending(path: Path = PENDING) -> dict:
    if not path.exists():
        return {}
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)


def save_pending(pending: dict, path: Path = PENDING) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(pending, f, separators=(",", ":"))


def archive(rows: list[dict], folder: Path = GRADED_DIR, now: datetime | None = None) -> int:
    """Write one sweep's graded games to data/universe/graded_<UTC date>_<HHMM>.jsonl.gz.
    One small compressed file per sweep, never rewritten: ~1,900 games a day as
    plain text would grow the repo by ~1 MB a day."""
    if not rows:
        return 0
    now = now or datetime.now(UTC)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"graded_{now:%Y-%m-%d_%H%M}.jsonl.gz"
    with gzip.open(path, "at", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, separators=(",", ":")) + "\n")
    return len(rows)


def load_graded(folder: Path = GRADED_DIR) -> list[dict]:
    """Every graded game: the compressed per-sweep files and the plain monthly
    file of the first desktop sweep (2026-10-07)."""
    rows = []
    for path in sorted(folder.glob("graded_*.jsonl*")):
        if path.suffix == ".gz":
            with gzip.open(path, "rt", encoding="utf-8") as f:
                text = f.read()
        else:
            text = path.read_text(encoding="utf-8")
        rows += [json.loads(x) for x in text.splitlines() if x.strip()]
    return rows


# ── early payout (1X2 - 1UP / 2UP) ───────────────────────────────────────────
def up_won(n: int, side: str, h: int, a: int, goals: list | None = None) -> int | None:
    """1 / 0 for `side` ("home" | "away") on a 1X2 nUP bet, or None when only the
    goal times could tell. It pays if the team wins after 90 minutes OR leads
    by n at any moment of the 90 (stoppage time included, extra time not).
    `goals`: the 90-minute goals in order, [[minute, "h" | "a"], ...]."""
    own, opp = (h, a) if side == "home" else (a, h)
    if own > opp:
        return 1
    if own < n:
        return 0                                  # never scored enough to lead by n
    if goals is None:
        return None
    lead = 0
    for _minute, who in goals:
        lead += 1 if who == side[0] else -1
        if lead >= n:
            return 1
    return 0


def needs_goals(row: dict, res: dict) -> bool:
    """Does settling this graded football game's early-payout prices need the goal times?"""
    p = row.get("first", {}).get("p", {})
    if row.get("sport") != "football" or res.get("after_90") or not any(k in p for k, _n in UP.values()):
        return False
    return any(up_won(n, side, res["h"], res["a"]) is None
               for k, n in UP.values() if k in p for side in ("home", "away"))


# ── settlement of the kept markets (for the study) ───────────────────────────
def outcomes(sport: str, prices_: dict, res: dict) -> list[tuple[str, int, float, list[float]]]:
    """[(market:side, won 0/1, price taken, the market's prices)] for one graded
    game — every side of every kept market. Football reads the 90-minute score
    only (after_90 games are skipped); basketball totals/handicaps include OT
    and a whole line that lands exactly is skipped (a push)."""
    out: list[tuple[str, int, float, list[float]]] = []
    if not res:
        return out
    h, a = res["h"], res["a"]
    if sport == "football":
        if res.get("after_90"):
            return out
        if "1x2" in prices_:
            p = prices_["1x2"]
            won = [h > a, h == a, h < a]
            out += [(f"1x2:{s}", int(w), x, p) for s, w, x in zip(("home", "draw", "away"), won, p, strict=True)]
        for line in OU_LINES:
            if f"ou{line}" in prices_:
                p = prices_[f"ou{line}"]
                over = h + a > float(line)
                out += [(f"o/u{line}:over", int(over), p[0], p), (f"o/u{line}:under", int(not over), p[1], p)]
        if "btts" in prices_:
            p = prices_["btts"]
            y = h > 0 and a > 0
            out += [("btts:yes", int(y), p[0], p), ("btts:no", int(not y), p[1], p)]
        if "dc" in prices_:
            p = prices_["dc"]
            won = [h >= a, h != a, h <= a]
            out += [(f"dc:{s}", int(w), x, p) for s, w, x in zip(("1x", "12", "x2"), won, p, strict=True)]
        for key, n in UP.values():
            if key not in prices_:
                continue
            p = prices_[key]
            for side, x in (("home", p[0]), ("away", p[2])):
                w = up_won(n, side, h, a, res.get("goals"))
                if w is not None:                 # goal times missing: that side stays unsettled
                    out.append((f"{key}:{side}", w, x, p))
            out.append((f"{key}:draw", int(h == a), p[1], p))
    else:
        if "win" in prices_:
            p = prices_["win"]
            out += [("win:home", int(h > a), p[0], p), ("win:away", int(a > h), p[1], p)]
        if "total" in prices_:
            line, o, u = prices_["total"]
            if h + a != line:
                out += [("total:over", int(h + a > line), o, [o, u]), ("total:under", int(h + a < line), u, [o, u])]
        if "hcp" in prices_:
            line, ph, pa = prices_["hcp"]
            if h - a + line != 0:
                cov = h - a + line > 0
                out += [("hcp:home", int(cov), ph, [ph, pa]), ("hcp:away", int(not cov), pa, [ph, pa])]
    return out
