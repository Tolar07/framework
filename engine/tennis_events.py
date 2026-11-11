"""
Tennis match events (framework #559, Event models #5). RECORD-ONLY / SHADOW.

For a tennis match: the chance of each set score, total games over / under at any line, a tie-break in the match,
and the expected games, all from a POINT-LEVEL serve / return model (engine/format_prob.py: point -> game -> set ->
match). It picks nothing, stakes nothing and moves no other number.

**It agrees with the framework by construction.** The match win chance is the board's own (SportyBet two-way price,
margin removed, as the tennis board uses it). The model finds the one per-point edge `d` that reproduces exactly that
win chance in the match's format (best of 3 or 5), so P(win) of the event model == the board's chance (test).
Everything else (set scores, games, tie-break) follows from `d` and the tour's serve level.

Not built, and why: aces and double faults per player. The source the issue names (Jeff Sackmann's match files,
github.com/JeffSackmann/tennis_atp / tennis_wta) returned 404 on 2026-11-11, and tennis-data.co.uk carries no serve
statistics, so there is no free serve data to fit or grade them. They read PENDING (HR35); nothing is invented (HR59).

The serve level (chance the server wins a point between equals) is a fitted number per tour: backtest/
tennis_events_study.py picks it walk-forward and writes it to backtest/TENNIS_EVENTS_STUDY.md; until then the
format_prob default is used and every output says `shadow`.
"""
from __future__ import annotations

import re
from functools import lru_cache

from engine import format_prob as fp

SERVE = {"ATP": fp.TOUR_SERVE, "WTA": 0.57}      # chance the server wins a point between equals (study refits)
SLAMS = ("australian open", "french open", "roland garros", "wimbledon", "us open")
LINES_DEFAULT = (18.5, 19.5, 20.5, 21.5, 22.5, 23.5, 24.5, 25.5)


# ── format ────────────────────────────────────────────────────────────────────────────────

def tour_of(comp: str | None) -> str:
    c = (comp or "").lower()
    return "WTA" if ("wta" in c or "women" in c or "ladies" in c) else "ATP"


def best_of(comp: str | None) -> int:
    """5 for a men's Grand Slam singles match, else 3. Doubles are best of 3 with a match tie-break; not modelled."""
    c = (comp or "").lower()
    if "women" in c or "double" in c or "wta" in c:
        return 3
    return 5 if any(s in c for s in SLAMS) and "men" in c and "challenger" not in c and "itf" not in c else 3


def is_doubles(comp: str | None, home: str | None = "") -> bool:
    return "double" in (comp or "").lower() or "/" in (home or "")


# ── set and match distributions ───────────────────────────────────────────────────────────

@lru_cache(maxsize=4096)
def _set_dist(sa: float, sb: float) -> tuple:
    """((games_a, games_b, probability), ...) for one set when A wins a service point with `sa` on his serve and
    B with `sb` on his; the first server is averaged 50/50 (as format_prob.tennis_set). Tie-break at 6-6."""
    ha, hb = fp.hold_game(sa), fp.hold_game(sb)
    out: dict[tuple[int, int], float] = {}
    for a_first in (True, False):
        states = {(0, 0): 1.0}
        while states:
            nxt: dict[tuple[int, int], float] = {}
            for (a, b), pr in states.items():
                if (a >= 6 and a - b >= 2) or a == 7:
                    out[(a, b)] = out.get((a, b), 0.0) + 0.5 * pr
                    continue
                if (b >= 6 and b - a >= 2) or b == 7:
                    out[(a, b)] = out.get((a, b), 0.0) + 0.5 * pr
                    continue
                if a == 6 and b == 6:
                    t = fp.tiebreak(sa, sb, ((a + b) % 2 == 0) == a_first)
                    nxt[(7, 6)] = nxt.get((7, 6), 0.0) + pr * t
                    nxt[(6, 7)] = nxt.get((6, 7), 0.0) + pr * (1 - t)
                    continue
                a_serving = ((a + b) % 2 == 0) == a_first
                h = ha if a_serving else 1.0 - hb
                nxt[(a + 1, b)] = nxt.get((a + 1, b), 0.0) + pr * h
                nxt[(a, b + 1)] = nxt.get((a, b + 1), 0.0) + pr * (1 - h)
            states = nxt
    return tuple((a, b, p) for (a, b), p in out.items())


def match_dist(d: float, bo: int = 3, serve: float = fp.TOUR_SERVE) -> dict:
    """Full distribution for the player A who wins each point `d` more often than between equals.

    Returns {"win": P(A wins), "sets": {"2-0": p, ...} (A's sets first), "games": {total_games: p},
             "tiebreak": P(at least one tie-break), "n": paths checked}."""
    sa, sb = min(1.0, max(0.0, serve + d)), min(1.0, max(0.0, serve - d))
    sets = _set_dist(sa, sb)
    need = bo // 2 + 1
    states = {(0, 0, 0, 0): 1.0}          # (sets A, sets B, games, tie-breaks) -> probability
    done: dict[tuple[int, int, int, int], float] = {}
    while states:
        nxt: dict[tuple[int, int, int, int], float] = {}
        for (xa, xb, g, tb), pr in states.items():
            if xa == need or xb == need:
                done[(xa, xb, g, tb)] = done.get((xa, xb, g, tb), 0.0) + pr
                continue
            for ga, gb, p in sets:
                k = (xa + (ga > gb), xb + (gb > ga), g + ga + gb, tb + (ga + gb == 13))
                nxt[k] = nxt.get(k, 0.0) + pr * p
        states = nxt
    win = sum(p for (xa, xb, _, _), p in done.items() if xa == need)
    score: dict[str, float] = {}
    games: dict[int, float] = {}
    tbp = 0.0
    for (xa, xb, g, tb), p in done.items():
        score[f"{xa}-{xb}"] = score.get(f"{xa}-{xb}", 0.0) + p
        games[g] = games.get(g, 0.0) + p
        tbp += p if tb else 0.0
    return {"win": win, "sets": score, "games": games, "tiebreak": tbp, "n": len(done)}


def over_prob(games: dict[int, float], line: float) -> float:
    return sum(p for g, p in games.items() if g > line)


# ── one match ─────────────────────────────────────────────────────────────────────────────

def devig(price_a: float | None, price_b: float | None) -> float | None:
    if not price_a or not price_b or price_a <= 1 or price_b <= 1:
        return None
    x, y = 1 / price_a, 1 / price_b
    return x / (x + y)


def predict(p_home: float | None, comp: str = "", lines=LINES_DEFAULT, serve: dict | None = None,
            home: str = "") -> dict | None:
    """Event numbers for a match from the board's home win chance. None (PENDING, HR35) when the chance is missing,
    outside the solvable range, or the match is doubles (a different format, not modelled)."""
    if p_home is None or is_doubles(comp, home):
        return None
    bo, tour = best_of(comp), tour_of(comp)
    s = (serve or SERVE).get(tour, fp.TOUR_SERVE)
    d = fp.tennis_edge(p_home, bo, s)
    if d is None:
        return None
    m = match_dist(d, bo, s)
    return {"tour": tour, "best_of": bo, "serve": s, "edge_per_point": round(d, 4),
            "win_home": round(m["win"], 4),
            "set_scores": {k: round(v, 4) for k, v in sorted(m["sets"].items())},
            "expected_games": round(sum(g * p for g, p in m["games"].items()), 2),
            "over": {str(ln): round(over_prob(m["games"], ln), 4) for ln in lines},
            "tiebreak": round(m["tiebreak"], 4),
            "aces": "PENDING (no free serve data; source 404)", "double_faults": "PENDING (no free serve data)"}


# ── helpers for the runner and the study ──────────────────────────────────────────────────

def home_chance(sides: dict) -> float | None:
    """Board win chance for the home side from the latest two-way match-winner prices (margin removed)."""
    def last(key):
        s = sides.get(key) or {}
        return (s.get("last") or s.get("first") or {}).get("price")
    return devig(last("tennis:186||Home"), last("tennis:186||Away"))


def total_lines(sides: dict) -> list[float]:
    out = set()
    for k in sides:
        m = re.match(r"tennis:189\|total=([\d.]+)\|", k)
        if m:
            out.add(float(m.group(1)))
    return sorted(out)


def games_from_periods(periods) -> tuple[int, int, bool] | None:
    """(total games, sets played, any tie-break) from [[6,4],[7,6],...]; None if there are no sets."""
    if not periods or len(periods) < 2:
        return None
    return (sum(a + b for a, b in periods), len(periods), any(a + b == 13 for a, b in periods))
