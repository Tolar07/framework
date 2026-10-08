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
    settled = uv.outcomes(row["sport"], first, row["result"])
    won = {k: w for k, w, _x, _m in settled}
    market = {k: m for k, _w, _x, m in settled}
    last_px = {k: x for k, _w, x, _m in uv.outcomes(row["sport"], last, row["result"])}
    res = row["result"]
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
            line = (first["total"][0] if key.startswith("total:") else
                    float(key.split(":")[0][3:]) if key.startswith("o/u") else None)
            out.append({"strategy": name, "game": f"{row['home']} v {row['away']}", "comp": row.get("comp"),
                        "covered": row.get("covered"), "market": key, "price": price,
                        # a double chance's three outcomes cover each result twice: chances sum to 2
                        "fair": (2 if key.startswith("dc:") else 1) * (1 / price) / sum(1 / p for p in market[key]),
                        "won": won[key], "pnl": won[key] * price - 1,
                        "clv": (price / close - 1) if close else None,
                        "id": row.get("id"), "day": (row.get("ko") or "")[:10],
                        "score": [res["h"], res["a"]], "line": line})
    return out


def why(rule_bets: list[dict]) -> str:
    """How a rule's bets were won and lost — not just whether."""
    if not rule_bets:
        return "—"
    lost = [b for b in rule_bets if not b["won"]]
    m = rule_bets[0]["market"]
    if m.startswith("1x2:") and m != "1x2:draw":
        draws = sum(1 for b in lost if b["score"][0] == b["score"][1])
        return f"lost {len(lost)}: {draws} draw(s), {len(lost) - draws} beaten" if lost else "no loss yet"
    if m.startswith(("o/u", "total:")):
        def margin(b: dict) -> float:
            return b["score"][0] + b["score"][1] - b["line"]
        w = [margin(b) for b in rule_bets if b["won"]]
        lo = [margin(b) for b in lost]
        unit = "pts" if m.startswith("total:") else "goals"
        def avg(xs: list[float]) -> str:
            return f"{sum(xs) / len(xs):+.1f}" if xs else "—"
        return f"total vs line ({unit}): wins {avg(w)}, losses {avg(lo)}"
    if m.startswith("win:"):
        gap = [abs(b["score"][0] - b["score"][1]) for b in lost]
        return f"lost {len(lost)} by {sum(gap) / len(gap):.0f} pts on average" if gap else "no loss yet"
    if m in ("1x2:draw", "btts:no", "btts:yes") or m.startswith("dc:"):
        goals = [b["score"][0] + b["score"][1] for b in lost]
        return f"lost {len(lost)}; goals in those games avg {sum(goals) / len(goals):.1f}" if goals else "no loss yet"
    return "—"


# ── paper ACCAS: fixed 3-leg combinations a day, graded like the singles ─────
# Each takes, per kick-off day, the 3 legs with the highest fair chance from the
# named rules (one leg per game). The acca wins only if every leg wins; its
# price is the product of the legs' first prices; "expected" = the product of
# their fair chances — so the book learns how accas really land against what
# their prices promised.
ACCAS: dict[str, tuple[str, tuple[str, ...]]] = {
    "A1 three safe double chances": ("3 legs from F8", ("F8 safe double chance",)),
    "A2 three favourites": ("3 legs from F1 + F2", ("F1 short favourite", "F2 mid favourite")),
    "A3 mixed safe": ("3 legs from F8 + F1 + B1", ("F8 safe double chance", "F1 short favourite",
                                                    "B1 home favourite")),
}
ACCA_LEGS = 3


def accas(rows: list[dict]) -> list[dict]:
    """Every paper acca the acca rules build, settled."""
    by_day: dict[str, list[dict]] = {}
    for row in rows:
        for b in bets(row):
            by_day.setdefault(b["day"], []).append(b)
    out = []
    for day in sorted(by_day):
        for name, (_desc, rules) in ACCAS.items():
            pool = sorted((b for b in by_day[day] if b["strategy"] in rules), key=lambda b: -b["fair"])
            legs, games = [], set()
            for b in pool:
                if b["id"] in games:
                    continue
                games.add(b["id"])
                legs.append(b)
                if len(legs) == ACCA_LEGS:
                    break
            if len(legs) < ACCA_LEGS:
                continue
            price = expected = 1.0
            for b in legs:
                price *= b["price"]
                expected *= b["fair"]
            won = int(all(b["won"] for b in legs))
            out.append({"acca": name, "day": day, "legs": [f"{b['game']}: {b['market']} @{b['price']:.2f}" for b in legs],
                        "price": round(price, 3), "expected": expected, "won": won, "pnl": won * price - 1,
                        "legs_won": sum(b["won"] for b in legs)})
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


def daily_note(rows: list[dict]) -> str:
    """A short Telegram note: what the paper book says this morning."""
    sc = score(rows)
    live = [(n, s["all"]) for n, s in sc.items() if s["all"].n]
    best = sorted(live, key=lambda x: -x[1].roi())[:3]
    worst = sorted(live, key=lambda x: x[1].roi())[:2]
    ready = [n for n, s in live if s.verdict() == "READY TO PROPOSE"]
    ac = accas(rows)

    def fmt(n: str, s: Score) -> str:
        return f"{n} {s.won}/{s.n} ({s.roi():+.0%})"
    lines = [f"📒 OLP XDV · PAPER BOOK — {len(rows)} games graded (paper only, nothing staked)",
             "Leading: " + ", ".join(fmt(n, s) for n, s in best) if best else "Leading: —",
             "Losing: " + ", ".join(fmt(n, s) for n, s in worst) if worst else "Losing: —"]
    if ac:
        w = sum(a["won"] for a in ac)
        exp = sum(a["expected"] for a in ac) / len(ac)
        lines.append(f"Paper accas: {w}/{len(ac)} landed (prices promised {exp:.0%})")
    lines.append("Ready to propose: " + (", ".join(ready) if ready else
                                         f"none yet (a rule needs {MIN_BETS}+ bets, return 2 se above zero, positive CLV)"))
    lines.append("Full table: backtest/PAPER_BOOK.md")
    return "\n".join(lines)
