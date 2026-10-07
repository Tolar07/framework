"""
PAPER BOOK — the system bets on paper, on every game it watches, and learns
from the outcome (Architect 2026-10-07: "place bets within yourself and see
how the outcome is ... teaching yourself how to do it better").

Each STRATEGY below is a fixed betting rule, written down BEFORE any result
is seen (none is tuned to past results — a rule fitted to the past only
learns the past). For every graded game in the universe (engine/universe.py:
every SportyBet football and basketball game, covered or not) each rule that
fires places a £1 paper bet at the FIRST price the sweep saw — the price the
board would have had to act on — and is settled from the real result.

Two scores per rule:
  return  — profit per £1, with its standard error (luck shrinks as bets grow);
  CLV     — first price / last pre-kick-off price − 1: did the market move
            towards the bet? The sharpest early sign of a real edge.
A rule is READY TO PROPOSE only with 100+ bets, a return two standard errors
above zero AND a positive average CLV. It is then shown to the Architect as a
proposal; nothing here ever selects a real pick or stakes money (the capital
bright line). Every bet is reproducible from data/universe/ — no extra store.
"""
from __future__ import annotations

from collections.abc import Callable
from math import sqrt

from engine import universe as uv

Bet = tuple[str, int, float]          # (outcome key as engine.universe.outcomes names it, side index, price)
MIN_BETS, SE_BAR = 100, 2.0


def _between(p: float, lo: float, hi: float) -> bool:
    return lo <= p < hi


def _fav(prices: list[float]) -> int:
    return min(range(len(prices)), key=lambda i: prices[i])


def f_short_fav(p: dict) -> list[Bet]:
    x = p.get("1x2")
    if not x:
        return []
    i = _fav(x)
    return [(("1x2:home", "1x2:draw", "1x2:away")[i], i, x[i])] if i != 1 and _between(x[i], 1.20, 1.50) else []


def f_mid_fav(p: dict) -> list[Bet]:
    x = p.get("1x2")
    if not x:
        return []
    i = _fav(x)
    return [(("1x2:home", "1x2:draw", "1x2:away")[i], i, x[i])] if i != 1 and _between(x[i], 1.50, 2.00) else []


def f_home_dog(p: dict) -> list[Bet]:
    x = p.get("1x2")
    return [("1x2:home", 0, x[0])] if x and _between(x[0], 2.50, 5.00) else []


def f_tight_draw(p: dict) -> list[Bet]:
    x = p.get("1x2")
    return [("1x2:draw", 1, x[1])] if x and max(x[0], x[2]) / min(x[0], x[2]) < 1.25 else []


def f_over_fav(p: dict) -> list[Bet]:
    x = p.get("ou2.5")
    return [("o/u2.5:over", 0, x[0])] if x and x[0] < x[1] else []


def f_under_fav(p: dict) -> list[Bet]:
    x = p.get("ou2.5")
    return [("o/u2.5:under", 1, x[1])] if x and x[1] < x[0] else []


def f_btts_no(p: dict) -> list[Bet]:
    x = p.get("btts")
    return [("btts:no", 1, x[1])] if x and _between(x[1], 1.50, 2.00) else []


def f_safe_dc(p: dict) -> list[Bet]:
    x = p.get("dc")
    if not x:
        return []
    i = _fav(x)
    return [(("dc:1x", "dc:12", "dc:x2")[i], i, x[i])] if _between(x[i], 1.20, 1.40) else []


def b_home_fav(p: dict) -> list[Bet]:
    x = p.get("win")
    return [("win:home", 0, x[0])] if x and _between(x[0], 1.20, 1.60) else []


def b_away_dog(p: dict) -> list[Bet]:
    x = p.get("win")
    return [("win:away", 1, x[1])] if x and _between(x[1], 2.00, 3.50) else []


def b_under(p: dict) -> list[Bet]:
    x = p.get("total")
    return [("total:under", 1, x[2])] if x else []


def b_over(p: dict) -> list[Bet]:
    x = p.get("total")
    return [("total:over", 0, x[1])] if x else []


STRATEGIES: dict[str, tuple[str, str, Callable[[dict], list[Bet]]]] = {
    "F1 short favourite": ("football", "1X2 favourite at 1.20–1.50", f_short_fav),
    "F2 mid favourite": ("football", "1X2 favourite at 1.50–2.00", f_mid_fav),
    "F3 home underdog": ("football", "home win at 2.50–5.00", f_home_dog),
    "F4 draw, tight game": ("football", "draw when the two win prices are within 25%", f_tight_draw),
    "F5 over 2.5 when favoured": ("football", "Over 2.5 when priced shorter than Under", f_over_fav),
    "F6 under 2.5 when favoured": ("football", "Under 2.5 when priced shorter than Over", f_under_fav),
    "F7 BTTS no": ("football", "both teams to score — no, at 1.50–2.00", f_btts_no),
    "F8 safe double chance": ("football", "the shortest double chance at 1.20–1.40", f_safe_dc),
    "B1 home favourite": ("basketball", "home winner at 1.20–1.60", b_home_fav),
    "B2 away underdog": ("basketball", "away winner at 2.00–3.50", b_away_dog),
    "B3 main total under": ("basketball", "Under the main total line", b_under),
    "B4 main total over": ("basketball", "Over the main total line", b_over),
}


def bets(row: dict) -> list[dict]:
    """Every paper bet the rules place on one graded game, settled."""
    if not row.get("result"):
        return []
    first, last = row["first"]["p"], row["last"]["p"]
    won = {k: w for k, w, _x, _m in uv.outcomes(row["sport"], first, row["result"])}
    last_px = {k: x for k, _w, x, _m in uv.outcomes(row["sport"], last, row["result"])}
    out = []
    for name, (sport, _desc, rule) in STRATEGIES.items():
        if sport != row["sport"]:
            continue
        for key, _i, price in rule(first):
            if key not in won:                 # e.g. a football game decided after 90'
                continue
            close = last_px.get(key)
            if key.startswith("total:") and (first.get("total") or [None])[0] != (last.get("total") or [None])[0]:
                close = None                   # the main line moved: prices of two lines don't compare
            out.append({"strategy": name, "game": f"{row['home']} v {row['away']}", "comp": row.get("comp"),
                        "covered": row.get("covered"), "market": key, "price": price,
                        "won": won[key], "pnl": won[key] * price - 1,
                        "clv": (price / close - 1) if close else None})
    return out


class Score:
    def __init__(self) -> None:
        self.n = self.won = 0
        self.pnl = self.pnl2 = 0.0
        self.clv: list[float] = []

    def add(self, b: dict) -> None:
        self.n += 1
        self.won += b["won"]
        self.pnl += b["pnl"]
        self.pnl2 += b["pnl"] ** 2
        if b["clv"] is not None:
            self.clv.append(b["clv"])

    def roi(self) -> float:
        return self.pnl / self.n if self.n else 0.0

    def se(self) -> float:
        if self.n < 2:
            return float("inf")
        m = self.roi()
        return sqrt(max(self.pnl2 / self.n - m * m, 0.0) / (self.n - 1))

    def avg_clv(self) -> float | None:
        return sum(self.clv) / len(self.clv) if self.clv else None

    def verdict(self) -> str:
        c = self.avg_clv()
        if self.n < MIN_BETS:
            return f"learning ({self.n}/{MIN_BETS} bets)"
        if self.roi() > SE_BAR * self.se() and c is not None and c > 0:
            return "READY TO PROPOSE"
        if self.roi() < -SE_BAR * self.se():
            return "losing — avoid"
        return "no edge shown"


def score(rows: list[dict]) -> dict[str, dict[str, Score]]:
    """{strategy: {"all" | "covered" | "not covered": Score}}."""
    out: dict[str, dict[str, Score]] = {n: {"all": Score(), "covered": Score(), "not covered": Score()}
                                        for n in STRATEGIES}
    for row in rows:
        for b in bets(row):
            s = out[b["strategy"]]
            s["all"].add(b)
            s["covered" if b["covered"] else "not covered"].add(b)
    return out
