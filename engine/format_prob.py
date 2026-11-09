"""
Format maths for the multi-sport board (framework#380; record-only, no pick / stake / bar / live switch uses it).

A per-unit chance p (a point, rally, leg or frame) becomes the exact chance of winning the match for the event's FORMAT,
and the inverse backs a per-unit chance out of a match price. Pure arithmetic: no network, no data, nothing invented
(HR59). Independence of units and the tour-average serve chance TOUR_SERVE are assumptions, PENDING a grade (HR35).

  race(p, need_a, need_b)           first to n (legs / frames / sets): sum_k C(n-1+k, k) p^n (1-p)^k
  win_by_two(p, to)                 game to `to` points, win by two (table tennis 11, volleyball 25, tiebreak 7)
  tennis_match(d, best_of, ...)     hold/break Markov chain with tiebreak; one edge d for every point (see below)
  volleyball_match(p, best_of)      sets to 25 (decider to 15), win by two
  solve(fn, target)                 the edge / chance whose match chance equals a price (bisection; fn must increase)
"""
from __future__ import annotations

from functools import lru_cache
from math import comb

TOUR_SERVE = 0.64  # assumed chance the server wins a point between equals (ATP ~0.64, WTA ~0.57), PENDING a grade


def race(p: float, need_a: int, need_b: int | None = None) -> float:
    """Chance A reaches `need_a` units before B reaches `need_b` (default same), A winning each unit with chance p."""
    need_b = need_a if need_b is None else need_b
    if not 0.0 <= p <= 1.0:
        raise ValueError("p must be in [0, 1]")
    if need_a < 1 or need_b < 1:
        raise ValueError("need must be >= 1")
    q = 1.0 - p
    return sum(comb(need_a - 1 + k, k) * p**need_a * q**k for k in range(need_b))


def best_of_win(p: float, best_of: int) -> float:
    if best_of < 1 or best_of % 2 == 0:
        raise ValueError("best_of must be odd")
    n = best_of // 2 + 1
    return race(p, n, n)


def win_by_two(p: float, to: int) -> float:
    """Chance to win a game to `to` points, win by two, each point won with chance p (independent)."""
    if not 0.0 <= p <= 1.0:
        raise ValueError("p must be in [0, 1]")
    q = 1.0 - p
    clean = sum(comb(to - 1 + k, k) * p**to * q**k for k in range(to - 1))   # win to `to`, loser on 0..to-2
    tie = comb(2 * (to - 1), to - 1) * (p * q) ** (to - 1)                    # reach (to-1)-(to-1)
    deuce = 0.5 if p == q else p * p / (p * p + q * q)
    return clean + tie * deuce


def _score_dist(g: float, need: int) -> dict[tuple[int, int], float]:
    out: dict[tuple[int, int], float] = {}
    for lost in range(need):
        out[(need, lost)] = comb(need - 1 + lost, lost) * g**need * (1 - g) ** lost
        out[(lost, need)] = comb(need - 1 + lost, lost) * (1 - g) ** need * g**lost
    return out


def volleyball_dist(p: float, best_of: int = 5) -> dict[tuple[int, int], float]:
    """Exact set-score distribution: sets to 25 win by two, a deciding set to 15 (best of 5; best of 3 has no short set)."""
    if best_of not in (3, 5):
        raise ValueError("best_of must be 3 or 5")
    g = win_by_two(p, 25)
    gd = win_by_two(p, 15) if best_of == 5 else g
    need = best_of // 2 + 1
    out: dict[tuple[int, int], float] = {}
    for a in range(need + 1):
        for b in range(need + 1):
            if (a == need) == (b == need):
                continue
            lost = b if a == need else a       # the decider is played only from (need-1, need-1)
            if lost < need - 1:
                pr = comb(need - 1 + lost, lost) * (g**need * (1 - g) ** lost if a == need else (1 - g) ** need * g**lost)
            else:
                pre = comb(2 * (need - 1), need - 1) * (g * (1 - g)) ** (need - 1)
                pr = pre * (gd if a == need else 1 - gd)
            out[(a, b)] = pr
    return out


def volleyball_match(p: float, best_of: int = 5) -> float:
    need = best_of // 2 + 1
    return sum(v for (a, _b), v in volleyball_dist(p, best_of).items() if a == need)


def hold_game(p: float) -> float:
    """Chance the server wins a tennis game (to 4, win by two) when winning each point with chance p."""
    return win_by_two(p, 4)


def tiebreak(pa_serve: float, pb_serve: float, a_serves_first: bool, to: int = 7) -> float:
    """Chance A wins a tiebreak to `to`, win by two. First server serves 1 point, then each serves 2 in turn."""
    @lru_cache(maxsize=None)
    def go(a: int, b: int) -> float:
        if a >= to and a - b >= 2:
            return 1.0
        if b >= to and b - a >= 2:
            return 0.0
        if a >= to - 1 and b >= to - 1 and a == b:           # level at the deuce zone: reduce to win-by-two pairs
            return _tb_deuce(a + b)
        n = a + b
        a_serving = ((n + 1) // 2) % 2 == 0
        a_serving = a_serving if a_serves_first else not a_serving
        p = pa_serve if a_serving else 1.0 - pb_serve
        return p * go(a + 1, b) + (1.0 - p) * go(a, b + 1)

    def _tb_deuce(n: int) -> float:
        # from level, two consecutive points are one serve each (serve switches every 2, pairs stay balanced)
        a_serving = ((n + 1) // 2) % 2 == 0
        a_serving = a_serving if a_serves_first else not a_serving
        s1 = pa_serve if a_serving else 1.0 - pb_serve
        s2 = 1.0 - pb_serve if a_serving else pa_serve
        up, down = s1 * s2, (1 - s1) * (1 - s2)
        return up / (up + down)

    return go(0, 0)


def tennis_set(pa_serve: float, pb_serve: float, tb_at_six: bool = True) -> float:
    """Chance A wins a set; averaged over who serves first. Serve alternates each game; tiebreak at 6-6 or play on."""
    ha, hb = hold_game(pa_serve), hold_game(pb_serve)

    def one(a_first: bool) -> float:
        @lru_cache(maxsize=None)
        def go(a: int, b: int) -> float:
            if a >= 6 and a - b >= 2:
                return 1.0
            if b >= 6 and b - a >= 2:
                return 0.0
            if a == 7:
                return 1.0
            if b == 7:
                return 0.0
            if a == 6 and b == 6:
                if tb_at_six:
                    return tiebreak(pa_serve, pb_serve, ((a + b) % 2 == 0) == a_first)
                x, y = ha * (1 - hb), (1 - ha) * hb      # a pair of games (one serve each): +2, -2 or level again
                return x / (x + y)
            a_serving = ((a + b) % 2 == 0) == a_first
            h = ha if a_serving else 1.0 - hb
            return h * go(a + 1, b) + (1 - h) * go(a, b + 1)
        return go(0, 0)

    return 0.5 * (one(True) + one(False))


def tennis_match(d: float, best_of: int = 3, serve: float = TOUR_SERVE, final_set_tb: bool = True) -> float:
    """Match chance for A when A wins every point (on either serve) `d` more often than between equals.

    The server wins a point with `serve` between equals; A serving wins it with serve + d, B serving wins it with
    serve - d. Sets are independent; the final set may be play-on (no tiebreak, as at some Slams)."""
    sa, sb = min(1.0, max(0.0, serve + d)), min(1.0, max(0.0, serve - d))
    s_tb = tennis_set(sa, sb, True)
    if final_set_tb:
        return best_of_win(s_tb, best_of)
    s_final = tennis_set(sa, sb, False)
    need = best_of // 2 + 1
    # the decider is reached at (need-1, need-1)
    pre = comb(2 * (need - 1), need - 1) * (s_tb * (1 - s_tb)) ** (need - 1)
    clean = sum(comb(need - 1 + k, k) * s_tb**need * (1 - s_tb) ** k for k in range(need - 1))
    return clean + pre * s_final


def solve(fn, target: float, lo: float, hi: float) -> float | None:
    """Value x in [lo, hi] with fn(x) == target (bisection; fn must increase). None if the target is outside the range."""
    if not 0.0 < target < 1.0:
        return None
    if fn(lo) > target or fn(hi) < target:
        return None
    for _ in range(60):
        mid = (lo + hi) / 2
        if fn(mid) < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def tennis_edge(match_p: float, best_of: int = 3, serve: float = TOUR_SERVE) -> float | None:
    """Per-point edge d that reproduces a match price in the given format (PENDING None when outside)."""
    return solve(lambda x: tennis_match(x, best_of, serve), match_p, -0.30, 0.30)


def convert_tennis(match_p: float, from_best_of: int, to_best_of: int, serve: float = TOUR_SERVE) -> float | None:
    """The same players, another format: a best-of-3 price restated as best-of-5 (or back). None when out of range."""
    d = tennis_edge(match_p, from_best_of, serve)
    return None if d is None else tennis_match(d, to_best_of, serve)


def convert_units(match_p: float, from_n: int, to_n: int) -> float | None:
    """First-to-n race (legs / frames) restated for another n with the same per-unit chance."""
    p = solve(lambda x: race(x, from_n), match_p, 0.0, 1.0)
    return None if p is None else race(p, to_n)
