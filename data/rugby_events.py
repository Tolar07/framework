"""
Rugby union halves, tries and penalty goals from ESPN's public scoreboard (site.api.espn.com, free, no key), framework #593.
RECORD ONLY: feeds engine/rugby_events.py and backtest/rugby_events_study.py; nothing here picks or stakes.

One row per finished game of the four leagues in backtest/rugby_backtest.py:
  {"day","league","home","away","h1":[h,a],"h2":[h,a],"tries":[h,a],"pens":[h,a],"conv":[h,a],"drops":[h,a],
   "pts":[h,a],"pt":[h,a]}
h1 / h2 = points in each half (from the period 1 / 2 line scores), tries = tries incl. penalty tries, pens = penalty goals,
conv = conversions, drops = drop goals, pt = penalty tries. A game is kept only when the half scores add up to the final
score and the first half is not 0-0 (ESPN has a real half split for 2014-15 only; later games put the whole score in
period 2, so they read PENDING rather than a fake 0-0 first half); try / penalty counts are kept only when 5*tries + 2*conv + 3*pens + 3*drops equals the final score (the check that
the counts are real). Anything else reads PENDING (None), never a guessed zero (HR35, HR59). Finished years are cached in
data/cache/rugby_events/<league>_<year>.json.
"""
from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

from backtest import rugby_backtest as rb

CACHE = Path(__file__).parent / "cache" / "rugby_events"
_UA = {"User-Agent": "olp-xdv-backtest", "Accept": "application/json"}
STATS = {"tries": "tries", "pens": "penaltyGoals", "conv": "conversionGoals", "drops": "dropGoalsConverted", "pt": "penaltyTries"}


def _get(lg: str, y: int) -> list[dict]:
    for attempt in range(3):
        try:
            req = urllib.request.Request(rb.API.format(lg=lg, y=y), headers=_UA)  # noqa: S310 - fixed https API
            with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310
                return json.loads(r.read().decode("utf-8")).get("events", [])
        except Exception:  # noqa: BLE001 - retried, then raised
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))
    return []


def _stat(c: dict, name: str) -> float | None:
    for s in c.get("statistics") or []:
        if s.get("name") == name:
            try:
                return float(s.get("displayValue"))
            except (TypeError, ValueError):
                return None
    return None


def _half(c: dict, period: int) -> float | None:
    for s in c.get("linescores") or []:
        if s.get("period") == period:
            try:
                return float(s["value"])
            except (KeyError, TypeError, ValueError):
                return None
    return None


def parse_game(e: dict, league: str) -> dict | None:
    """One game's halves (and counts when they reconcile). None unless completed and the halves add up to the final score."""
    try:
        comp = e["competitions"][0]
        if not e["status"]["type"]["completed"]:
            return None
        side = {c["homeAway"]: c for c in comp["competitors"]}
        h, a = side["home"], side["away"]
        pts = [float(h["score"]), float(a["score"])]
        row = {"day": e["date"][:10], "league": league, "home": h["team"]["displayName"], "away": a["team"]["displayName"],
               "pts": pts}
    except (KeyError, ValueError, TypeError, IndexError):
        return None
    halves = []
    for p in (1, 2):
        v = (_half(h, p), _half(a, p))
        if None in v:
            return None
        halves.append([v[0], v[1]])
    if [halves[0][0] + halves[1][0], halves[0][1] + halves[1][1]] != pts:
        return None                                        # extra time or a missing half: not a clean 80 minutes
    if halves[0] == [0.0, 0.0]:
        return None        # ESPN gives no half split for most games after 2015 (the whole score lands in period 2): not a real 0-0
    row["h1"], row["h2"] = halves
    row["r"] = halves                                      # [[h,a] x 2], the shape engine.baseball_events.Ratings reads
    counts = {}
    for key, name in STATS.items():
        v = (_stat(h, name), _stat(a, name))
        counts[key] = None if None in v else [v[0], v[1]]
    ok = all(counts[k] is not None for k in ("tries", "pens", "conv", "drops"))
    if ok:
        for i in (0, 1):
            if 5 * counts["tries"][i] + 2 * counts["conv"][i] + 3 * counts["pens"][i] + 3 * counts["drops"][i] != pts[i]:
                ok = False                                 # the counts do not rebuild the score: not trusted
    for k in ("tries", "pens", "conv", "drops", "pt"):
        row[k] = counts[k] if ok else None
    return row


def load(years=rb.YEARS, fetch=_get, use_cache: bool = True) -> list[dict]:
    """Every finished game of the four leagues, date order. A year that will not load is skipped, PENDING."""
    CACHE.mkdir(parents=True, exist_ok=True)
    games, seen = [], set()
    for lg, name in rb.LEAGUES.items():
        for y in years:
            f = CACHE / f"{lg}_{y}.json"
            rows = None
            if use_cache and f.exists():
                try:
                    rows = json.loads(f.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    rows = None
            if rows is None:
                try:
                    evs = fetch(lg, y)
                except Exception as ex:  # noqa: BLE001
                    print(f"{name} {y}: not loaded ({type(ex).__name__})")
                    continue
                rows = [g for g in (parse_game(e, name) for e in evs) if g]
                if y < 2026:                              # finished years only; the open year is re-read
                    f.write_text(json.dumps(rows), encoding="utf-8")
            for g in rows:
                key = (g["day"], g["home"], g["away"])
                if key not in seen:
                    seen.add(key)
                    games.append(g)
    games.sort(key=lambda g: (g["day"], g["home"]))
    return games
