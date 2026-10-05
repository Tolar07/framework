"""
AUTOMATIC LEARNING FROM RESULTS (improvement #6, Architect 2026-10-02).

Every graded single in the picks ledger says how often a pick we called at
X% actually won. This module turns that record into a correction the next
board applies automatically, per MARKET FAMILY (Home win, Double chance,
handicap, team goals, ...) and per LEAGUE:

  shift = (wins - expected wins) / (n + SHRINK)

expected wins = the sum of the chances we stated. A family whose picks won
less often than we said gets its chances cut; one that beat them gets a
small lift. SHRINK keeps a handful of results from swinging anything — the
shift only reaches its full size after many picks — and a segment needs
MIN_N graded picks spread over MIN_DAYS match days before it counts at all
(Architect 2026-10-04: one good day — Double chance 22/23 on 3 Oct — must not
turn the next whole board into one market). The total shift per pick is
capped at MAX_SHIFT, so learning can steer selection but never invent
certainty.

A segment counts only with MIN_N results over MIN_DAYS match days and a gap
of Z_MIN standard deviations; league corrections are measured after the
family correction, and learning reads each pick's chance before any learned
shift (`chance_raw`) — all 2026-10-05.

The shifted chance is what ranks the candidates and what must clear the 50%
floor, so a market family that keeps losing drops off the board on its own
and one that keeps winning rises. Results are never guessed (HR35): only
won/lost singles count; voids and ungraded picks are ignored.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Optional

WINDOW_DAYS = 90
# 2026-10-05 (Architect: "learning needs more evidence"): 10 results let one
# weekend move a whole market. A segment now needs 50 results over 5 match days
# AND a gap between wins and expected wins of at least Z_MIN standard
# deviations (sd = sqrt(sum c(1-c))) — chance alone rarely gets that far.
MIN_N = 50
MIN_DAYS = 5        # distinct match days a segment's results must span
Z_MIN = 2.0
SHRINK = 30
MAX_SHIFT = 0.10

# Readable names for the market families on the board / heartbeat.
_SB_NAMES = {"1": "1X2", "10": "Double chance", "11": "Draw no bet",
             "12": "Home no bet", "13": "Away no bet", "14": "European handicap",
             "16": "Asian handicap", "18": "Over/Under", "19": "Home goals",
             "20": "Away goals", "21": "Goal range", "23": "Home multigoals",
             "24": "Away multigoals", "25": "Goal range", "26": "Odd/Even",
             "29": "BTTS", "30": "Which team scores", "31": "Home clean sheet",
             "32": "Away clean sheet", "33": "Home win to nil", "34": "Away win to nil",
             "36": "Total & BTTS", "37": "Result & total", "546": "DC & BTTS",
             "547": "DC & total", "548": "Multigoals"}
_LEGACY = {"HOME": "1X2", "AWAY": "1X2", "DRAW": "1X2", "DC": "Double chance",
           "OVER": "Over/Under", "UNDER": "Over/Under", "BTTS": "BTTS", "DNB": "Draw no bet"}


def family(key: Optional[str]) -> str:
    """Market family of a pick key ('SB:16|hcp=-1|Home' -> 'Handicap')."""
    if not key:
        return "?"
    if key.startswith("SB:"):
        mid = key[3:].split("|", 1)[0]
        return _SB_NAMES.get(mid, f"market {mid}")
    head = key.split("_", 1)[0].upper()
    return _LEGACY.get(head, head)


def league_of(fixture: str) -> str:
    return fixture.rsplit("(", 1)[-1].rstrip(")").strip() if "(" in fixture else "?"


def _seg(rows: list) -> dict:
    n = len(rows)
    wins = sum(won for won, _c, _p, _d in rows)
    exp = sum(c for _w, c, _p, _d in rows)
    sd = sum(c * (1 - c) for _w, c, _p, _d in rows) ** 0.5
    pl = sum(((p or 1.0) - 1.0) if won else -1.0 for won, _c, p, _d in rows)
    days = len({d for _w, _c, _p, d in rows})
    z = (wins - exp) / sd if sd > 0 else 0.0
    counts = n >= MIN_N and days >= MIN_DAYS and abs(z) >= Z_MIN
    shift = (wins - exp) / (n + SHRINK) if counts else 0.0
    return {"n": n, "wins": wins, "expected": round(exp, 2), "roi": pl / n if n else 0.0,
            "days": days, "z": round(z, 2), "shift": round(shift, 4)}


def learn(ledger_dir, today: Optional[str] = None) -> dict:
    """{'family': {name: seg}, 'league': {name: seg}} from graded singles."""
    today = today or date.today().isoformat()
    since = (date.fromisoformat(today) - timedelta(days=WINDOW_DAYS)).isoformat()
    picks = []
    for path in sorted(ledger_dir.glob("picks_*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        if not (since <= doc["date"] < today):
            continue
        for s in doc["singles"]:
            if s.get("result") not in ("won", "lost") or s.get("chance") is None:
                continue
            # Learn from the chance BEFORE any learned correction (2026-10-05):
            # learning from already-shifted chances re-measured its own shift.
            c = s.get("chance_raw", s["chance"])
            picks.append((family(s.get("market")), s.get("league") or "?",
                          (s["result"] == "won", float(c), s.get("price"),
                           (s.get("kickoff") or doc["date"])[:10])))
    fam: dict = {}
    for f, _l, row in picks:
        fam.setdefault(f, []).append(row)
    fam_seg = {k: _seg(v) for k, v in fam.items()}
    # League corrections are measured AFTER the market-family correction, so a
    # pick is not counted twice (2026-10-05: family + league were added up).
    lg: dict = {}
    for f, league, (won, c, price, day) in picks:
        c2 = min(0.999, max(0.001, c + fam_seg[f]["shift"]))
        lg.setdefault(league, []).append((won, c2, price, day))
    return {"family": fam_seg, "league": {k: _seg(v) for k, v in lg.items()}}


def shift(model: dict, key: Optional[str], league: str) -> float:
    """Learned correction (probability points) for one candidate pick."""
    if not model:
        return 0.0
    s = (model.get("family", {}).get(family(key), {}).get("shift", 0.0)
         + model.get("league", {}).get(league, {}).get("shift", 0.0))
    return max(-MAX_SHIFT, min(MAX_SHIFT, s))


def summary(model: dict, top: int = 4) -> str:
    """One heartbeat line: the biggest learned corrections in force."""
    segs = [(abs(v["shift"]), kind, name, v)
            for kind in ("family", "league") for name, v in model.get(kind, {}).items()
            if v["shift"]]
    graded = sum(v["n"] for v in model.get("family", {}).values())
    if not segs:
        return (f"Learning: {graded} graded single(s) so far — corrections start once a "
                f"market family or league has {MIN_N}+ results over {MIN_DAYS}+ match days "
                f"and its results are clearly off its stated chances.")
    segs.sort(key=lambda x: (-x[0], x[1], x[2]))
    parts = [f"{name} {v['shift']*100:+.1f}pp ({v['wins']}/{v['n']} won vs "
             f"{v['expected']:.1f} expected)" for _a, _k, name, v in segs[:top]]
    return f"Learning from {graded} graded singles: " + " · ".join(parts)
