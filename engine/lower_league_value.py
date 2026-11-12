"""
LOWER-LEAGUE VALUE PAPER BOARD (framework #584) - PAPER ONLY: nothing is staked, no code is booked, nothing is
written where a bot reads (output/multisport/, output/picks/).

The Architect's video of 2026-11-12: "the value is in the games nobody watches ... we kept only the games where the
odds pay more than our model says" (BTTS No at 2.77 and 2.43, Under 2.5 at 2.55 against a 'fair' 1.60, Over 2.5 at
1.63). Push-back kept in the write-up: a fair 1.60 against a market 2.55 is a 59% edge; gaps that size in a priced
market nearly always mean the model is wrong (team news, 6-10 game samples), not the market. Our own record agrees:
longshots and drifters lose most (worldwide results, 10-11 Oct), singles at 2.00-2.99 are the worst odds band on
every account over 30 days. So this is graded on paper, split by the size of the claimed gap, before anyone decides.

How a game is rated (each 3-hour universe sweep, from SportyBet's own list and prices):
  universe   second-tier and lower men's league games SportyBet prices (LOWER pattern; youth, women, friendlies,
             cups out), with prices for both teams to score and over/under 1.5 / 2.5 / 3.5.
  model      goals Poisson fitted on every graded SportyBet game of the archive (data/universe/graded_*): each
             team's goals for / against per game shrunk to its league's mean (SHRINK pseudo-games), the league's
             home and away goal rates; both teams need MIN_TEAM graded games, else the game is skipped.
  pick       per game, the option whose model chance x price - 1 (its expected value on the price) is largest,
             at a price of PRICE_MIN-PRICE_MAX, when that value is above zero. The 'gap' band is that value.
Graded from the sweep's own result (90 minutes). Book: data/lower_league_value/book.json; day boards
output/lower_league_value/lower_<date>.json; running record output/lower_league_value/record.json by gap band
(under 5%, 5-10%, 10-20%, over 20%). READY TO PROPOSE only with 100+ graded picks in a band and a return whose
90% range clears zero; then it goes to the Architect, whose decision it stays.
"""
from __future__ import annotations

import json
import math
import random
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOOK = ROOT / "data" / "lower_league_value" / "book.json"
OUT_DIR = ROOT / "output" / "lower_league_value"
SHRINK = 6.0
MIN_TEAM = 5
PRICE_MIN, PRICE_MAX = 1.30, 4.00
READY_N = 100
BANDS = (("under 5%", 0.0, 0.05), ("5-10%", 0.05, 0.10), ("10-20%", 0.10, 0.20), ("over 20%", 0.20, 99.0))

_SKIP = re.compile(r"women|female|\bu-?\d\d\b|under \d\d|youth|junior|reserve|amateur|futsal|beach|friendl|"
                   r"cup|copa|coupe|pokal|coppa|taca|beker|trophy|playoff|play-off|qualif|super ?cup", re.I)
_LOWER = re.compile(r"championship|league (one|two)|national league|\b(2|3|4)\. ?(liga|bundesliga)|regionalliga|"
                    r"serie [bcd]\b|ligue [23]\b|national\b|segunda|primera (federacion|rfef)|tercera|liga (2|3)\b|"
                    r"\b(1st|2nd|3rd) (division|league)|division [123]\b|first division|second (division|league)|"
                    r"eerste divisie|tweede divisie|challenger? (pro )?league|superettan|ettan|obos|\bnb (ii|iii)\b|"
                    r"\bii\.? ?liga|\b1\. ?liga|i liga|ii liga|prva liga|druga|super league 2|premier league 2|"
                    r"\bb\b ?(league|division)|lower|\b(1|2)\. (division|lig)|tff (1|2|3)|1\. lig|2\. lig|"
                    r"segunda (division|liga)|championnat national|landesliga|oberliga|isthmian|northern|southern",
                    re.I)
MARKETS = (("btts", 0, "BTTS Yes"), ("btts", 1, "BTTS No"), ("ou1.5", 0, "Over 1.5"), ("ou1.5", 1, "Under 1.5"),
           ("ou2.5", 0, "Over 2.5"), ("ou2.5", 1, "Under 2.5"), ("ou3.5", 0, "Over 3.5"), ("ou3.5", 1, "Under 3.5"))


def is_lower(row: dict) -> bool:
    comp = f"{row.get('comp', '')}"
    if row.get("sport", "football") != "football" or _SKIP.search(comp) or _SKIP.search(row.get("country", "")):
        return False
    return bool(_LOWER.search(comp))


def league_of(row: dict) -> str:
    return f"{row.get('country', '')}: {row.get('comp', '')}"


class Goals:
    """Team goals for / against per game, shrunk to the league; league home / away rates."""

    def __init__(self):
        self.lg: dict[str, list] = {}
        self.tm: dict[tuple, list] = {}

    def add(self, league: str, home: str, away: str, hg: int, ag: int) -> None:
        g = self.lg.setdefault(league, [0, 0, 0])
        g[0] += 1
        g[1] += hg
        g[2] += ag
        for t, f, a in ((home, hg, ag), (away, ag, hg)):
            x = self.tm.setdefault((league, t), [0, 0, 0])
            x[0] += 1
            x[1] += f
            x[2] += a

    def games(self, league: str, team: str) -> int:
        return self.tm.get((league, team), [0])[0]

    def lambdas(self, league: str, home: str, away: str) -> tuple[float, float] | None:
        g = self.lg.get(league)
        if not g or g[0] < 20 or min(self.games(league, home), self.games(league, away)) < MIN_TEAM:
            return None
        lh, la = max(g[1] / g[0], 0.2), max(g[2] / g[0], 0.2)
        mean = (lh + la) / 2

        def rate(team: str) -> tuple[float, float]:
            n, f, a = self.tm[(league, team)]
            return (f + SHRINK * mean) / (n + SHRINK) / mean, (a + SHRINK * mean) / (n + SHRINK) / mean
        ah, dh = rate(home)
        aa, da = rate(away)
        return lh * ah * da, la * aa * dh


def probs(lh: float, la: float) -> dict[str, float]:
    ph = [math.exp(-lh) * lh ** k / math.factorial(k) for k in range(12)]
    pa = [math.exp(-la) * la ** k / math.factorial(k) for k in range(12)]
    tot = [sum(ph[i] * pa[n - i] for i in range(n + 1) if i < 12 and n - i < 12) for n in range(12)]
    under = lambda line: sum(tot[: int(line) + 1])  # noqa: E731
    yes = (1 - ph[0]) * (1 - pa[0])
    return {"BTTS Yes": yes, "BTTS No": 1 - yes,
            "Over 1.5": 1 - under(1.5), "Under 1.5": under(1.5), "Over 2.5": 1 - under(2.5),
            "Under 2.5": under(2.5), "Over 3.5": 1 - under(3.5), "Under 3.5": under(3.5)}


def won(option: str, hg: int, ag: int) -> bool:
    t = hg + ag
    return {"BTTS Yes": hg > 0 and ag > 0, "BTTS No": not (hg > 0 and ag > 0),
            "Over 1.5": t > 1, "Under 1.5": t < 2, "Over 2.5": t > 2, "Under 2.5": t < 3,
            "Over 3.5": t > 3, "Under 3.5": t < 4}[option]


def best_option(model: Goals, row: dict, prices: dict) -> dict | None:
    lam = model.lambdas(league_of(row), row["home"], row["away"])
    if not lam:
        return None
    pr = probs(*lam)
    best = None
    for mkt, i, opt in MARKETS:
        pair = prices.get(mkt) or []
        if len(pair) != 2 or not pair[0] or not pair[1]:
            continue
        price = float(pair[i])
        if not (PRICE_MIN <= price <= PRICE_MAX):
            continue
        fair_mkt = (1 / price) / (1 / float(pair[0]) + 1 / float(pair[1]))
        ev = pr[opt] * price - 1
        if ev > 0 and (best is None or ev > best["value"]):
            best = {"option": opt, "price": price, "model_p": round(pr[opt], 4),
                    "fair_odds": round(1 / pr[opt], 2), "market_p": round(fair_mkt, 4), "value": round(ev, 4),
                    "home_games": model.games(league_of(row), row["home"]),
                    "away_games": model.games(league_of(row), row["away"])}
    return best


def band(value: float) -> str:
    return next(name for name, lo, hi in BANDS if lo <= value < hi)


def fit(graded_rows: list[dict], before: str | None = None) -> Goals:
    m = Goals()
    for r in graded_rows:
        if before and (r.get("ko") or "") >= before:
            continue
        m.add(league_of(r), r["home"], r["away"], r["hg"], r["ag"])
    return m


def load_book(path: Path = BOOK) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"picks": {}}


def add_picks(book: dict, pending: list[dict], now: datetime, model: Goals) -> int:
    n = 0
    stamp = now.strftime("%Y-%m-%dT%H:%MZ")
    for row in pending:
        gid = row.get("id")
        if not gid or gid in book["picks"] or not is_lower(row) or (row.get("ko") or "") <= stamp:
            continue
        prices = ((row.get("last") or row.get("first") or {}).get("p")) or {}
        pick = best_option(model, row, prices)
        if not pick:
            continue
        book["picks"][gid] = {"id": gid, "ko": row.get("ko"), "league": league_of(row), "home": row["home"],
                              "away": row["away"], **pick, "band": band(pick["value"]), "picked_at": stamp,
                              "paper": True}
        n += 1
    return n


def grade(book: dict, graded: list[dict]) -> int:
    n = 0
    for g in graded:
        p = book["picks"].get(g.get("id"))
        res = g.get("result") or {}
        if not p or "won" in p or res.get("h") is None or res.get("after_90"):
            continue
        p["result"] = [res["h"], res["a"]]
        p["won"] = won(p["option"], res["h"], res["a"])
        p["return"] = round(p["price"] if p["won"] else 0.0, 2)
        n += 1
    return n


def _ci(rets: list[float], boots: int = 400) -> tuple[float, float]:
    rng = random.Random(11)  # noqa: S311 - a bootstrap, not cryptography
    n = len(rets)
    sims = sorted(sum(rng.choices(rets, k=n)) / n for _ in range(boots))
    return sims[int(0.05 * boots)], sims[int(0.95 * boots) - 1]


def record(book: dict) -> dict:
    out = {}
    picks = list(book["picks"].values())
    for name, *_ in (("all", 0, 0), *BANDS):
        part = [p for p in picks if name == "all" or p["band"] == name]
        done = [p for p in part if "won" in p]
        rets = [p["return"] - 1 for p in done]
        r = {"picks": len(part), "graded": len(done), "won": sum(1 for p in done if p["won"]),
             "staked_units": len(done), "returned_units": round(sum(p["return"] for p in done), 2),
             "roi": round(sum(rets) / len(rets), 4) if rets else None}
        if len(rets) >= 30:
            r["roi_90"] = [round(x, 4) for x in _ci(rets)]
        r["ready_to_propose"] = bool(len(rets) >= READY_N and r.get("roi_90") and r["roi_90"][0] > 0)
        out[name] = r
    return out


def write(book: dict, now: datetime) -> None:
    BOOK.parent.mkdir(parents=True, exist_ok=True)
    BOOK.write_text(json.dumps(book, indent=1, ensure_ascii=False), encoding="utf-8")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    day = now.strftime("%Y-%m-%d")
    todays = sorted((p for p in book["picks"].values() if (p.get("ko") or "")[:10] == day),
                    key=lambda p: -p["value"])
    (OUT_DIR / f"lower_{day}.json").write_text(json.dumps(
        {"date": day, "paper": True, "built": now.strftime("%Y-%m-%dT%H:%MZ"),
         "note": "PAPER ONLY - never staked or booked (framework #584)", "picks": todays}, indent=1,
        ensure_ascii=False), encoding="utf-8")
    (OUT_DIR / "record.json").write_text(json.dumps(
        {"updated": now.strftime("%Y-%m-%dT%H:%MZ"), "paper": True, "ready_n": READY_N,
         "bands": record(book)}, indent=1, ensure_ascii=False), encoding="utf-8")


def attach(pending: dict, graded: list[dict], now: datetime) -> str:
    """The universe sweep's hook: fit on the graded archive, pick the listed lower-league games, grade, save."""
    from engine import stats_history as sh
    hist = sh.load_sportybet()
    model = Goals()
    for r in hist:
        model.add(f"{r['country']}: {r['comp']}", r["home"], r["away"], r["hg"], r["ag"])
    for g in graded:                                        # this sweep's results are not in the archive yet
        res = g.get("result") or {}
        if g.get("sport") == "football" and res.get("h") is not None and not res.get("after_90"):
            model.add(league_of(g), g["home"], g["away"], res["h"], res["a"])
    book = load_book()
    new = add_picks(book, list(pending.values()), now, model)
    done = grade(book, graded)
    if new or done or not BOOK.exists():
        write(book, now)
    rec = record(book)["all"]
    return f"lower-league paper: {new} new, {done} graded, {rec['graded']}/{rec['picks']} in the book"
