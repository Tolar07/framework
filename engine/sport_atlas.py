"""
SPORT ATLAS - the trend search for every sport we have history for, and the price test for every sport we have
prices for. Football has its own, larger version (engine/trend_atlas.py); this module covers the rest and the
"record against the price" trends for all of them.

The Architect, 2026-11-12: "It should cover the entire betting market for all sports."

Datasets (each row has: sport, league, season key sk, date, home/away names, team keys hk/ak, the result, and the
pre-match prices where a source keeps them):
  us        data/sports_history/   (data/espn_sports_history.py) NBA, WNBA, NCAA men's basketball, NHL, MLB, NFL,
                                   college football: period scores + ESPN's pre-game total / spread / moneyline
  tennis    tennis-data.co.uk      (backtest/tennis_backtest.py) ATP + WTA 2019-2025: set scores + Pinnacle close
  sportybet data/universe          SportyBet's own last price for every football and basketball game it listed
                                   (8 Oct 2026 on), graded: worldwide basketball and football against SportyBet

Two kinds of trend, for every market:
  STAT TREND        "this team goes over / covers / wins its first half often" (markets in SPORT_MARKETS)
  PRICE TREND       "this team beats the price": its past games' outcome minus the market's own chance, i.e. its
                    record against the spread, over/under against the posted total, wins against the moneyline.
                    A team whose price trend repeats would be a market the bookmaker misprices.
RECORD ONLY: nothing here picks, stakes or blocks. backtest/sport_atlas_study.py runs the tests.
"""
from __future__ import annotations

import gzip
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TENNIS_NOTE = ""          # why tennis is missing from a run, when it is (HR35: a gap is named, never silent)


# ---------------------------------------------------------------- markets (yes = 1.0, no = 0.0, unknown = None)
def _tot(m):
    return m["ft"][0] + m["ft"][1]


def _ot(m):
    p = m.get("periods")
    return None if not p else float(len(p) > m.get("regulation", len(p)))


def _p1(m):
    p = m.get("periods")
    return None if not p else p[0]


def _half(m):
    p = m.get("periods")
    reg = m.get("regulation")
    if not p or not reg or reg % 2:
        return None
    k = reg // 2
    return [sum(x[0] for x in p[:k]), sum(x[1] for x in p[:k])]


def _over_posted(m):
    pr = m.get("prices") or {}
    if pr.get("total") is None or _tot(m) == pr["total"]:
        return None
    return float(_tot(m) > pr["total"])


def _home_covers(m):
    pr = m.get("prices") or {}
    if pr.get("spread") is None:
        return None
    d = m["ft"][0] + pr["spread"] - m["ft"][1]
    return None if d == 0 else float(d > 0)


def _home_win(m):
    return None if m["ft"][0] == m["ft"][1] else float(m["ft"][0] > m["ft"][1])


def _cmp(f, i, j):
    def g(m):
        v = f(m)
        return None if v is None or v[i] == v[j] else float(v[i] > v[j])
    return g


def _over(f, ln):
    def g(m):
        v = f(m)
        return None if v is None else float((v[0] + v[1] if isinstance(v, list) else v) > ln)
    return g


COMMON = {"home win": _home_win, "over the posted total": _over_posted, "home covers the spread": _home_covers}
SPORT_MARKETS = {
    "basketball": {**COMMON, "1st half home win": _cmp(_half, 0, 1), "1st quarter home win": _cmp(_p1, 0, 1),
                   "overtime": _ot},
    "hockey": {**COMMON, "overtime / shoot-out": _ot, "total over 5.5": _over(_tot, 5.5), "total over 6.5": _over(_tot, 6.5),
               "1st period home win": _cmp(_p1, 0, 1), "1st period over 1.5": _over(_p1, 1.5),
               "1st period both score": lambda m: None if not _p1(m) else float(_p1(m)[0] > 0 and _p1(m)[1] > 0)},
    "baseball": {**COMMON, "total over 7.5": _over(_tot, 7.5), "total over 8.5": _over(_tot, 8.5),
                 "total over 9.5": _over(_tot, 9.5),
                 "home wins by 2+": lambda m: float(m["ft"][0] - m["ft"][1] >= 2)},
    "american football": {**COMMON, "1st half home win": _cmp(_half, 0, 1), "overtime": _ot,
                          "margin 3 or less": lambda m: float(abs(m["ft"][0] - m["ft"][1]) <= 3),
                          "1st quarter home win": _cmp(_p1, 0, 1)},
    "tennis": {"first-named player wins": lambda m: float(m["ft"][0] > m["ft"][1]),
               "deciding set played": lambda m: None if m.get("best_of") is None else float(m["ft"][0] + m["ft"][1] == m["best_of"]),
               "total games over 22.5 (best of 3)": lambda m: None if m.get("games") is None or m.get("best_of") != 3 else float(m["games"] > 22.5),
               "first set won by the match winner": lambda m: None if not m.get("periods") else float((m["periods"][0][0] > m["periods"][0][1]) == (m["ft"][0] > m["ft"][1]))},
    "sportybet basketball": {"home win": _home_win, "over SportyBet's main total": _over_posted,
                             "home covers SportyBet's main handicap": _home_covers},
    "sportybet football": {"home win": lambda m: float(m["ft"][0] > m["ft"][1]),
                           "over SportyBet's 2.5": lambda m: float(_tot(m) > 2.5),
                           "BTTS yes": lambda m: float(m["ft"][0] > 0 and m["ft"][1] > 0)},
}
SPORT_OF_LEAGUE = {"nba": "basketball", "wnba": "basketball", "mens-college-basketball": "basketball",
                   "nhl": "hockey", "mlb": "baseball", "nfl": "american football", "college-football": "american football"}

# markets with a price: market -> function(row) -> (yes price, no price) or None
def _pp(a, b):
    def g(m):
        pr = m.get("prices") or {}
        return (pr[a], pr[b]) if pr.get(a) and pr.get(b) else None
    return g


PRICED = {"home win": _pp("ml_home", "ml_away"), "over the posted total": _pp("over", "under"),
          "home covers the spread": _pp("sp_home", "sp_away"), "first-named player wins": _pp("pa", "pb"),
          "over SportyBet's main total": _pp("over", "under"), "home covers SportyBet's main handicap": _pp("sp_home", "sp_away"),
          "over SportyBet's 2.5": _pp("o25", "u25"), "BTTS yes": _pp("by", "bn")}


# ---------------------------------------------------------------- loaders
def us_rows(folder: Path) -> list[dict]:
    from data import espn_sports_history as es
    out = []
    for g in es.load(folder):
        sport = SPORT_OF_LEAGUE.get(g["league"])
        if not sport:
            continue
        out.append({**g, "sport": sport, "lk": g["league"], "sk": str(g.get("season")), "hk": f"{g['league']}:{g['hid']}",
                    "ak": f"{g['league']}:{g['aid']}"})
    out.sort(key=lambda m: m["date"])
    return out


def tennis_rows() -> list[dict]:
    """tennis-data.co.uk, ATP + WTA: sets won, set scores, Pinnacle close. The two players are put in name order
    (as backtest/tennis_backtest.py does), so 'home' = the first-named player; nothing about venue."""
    import re
    sys.path.insert(0, str(ROOT / "backtest"))
    import tennis_backtest as tb
    global TENNIS_NOTE
    try:
        page = tb.fetch(tb.SITE + "alldata.php").decode("latin-1", "replace")
    except Exception as ex:  # noqa: BLE001 - tennis PENDING this run, with the reason
        TENNIS_NOTE = f"tennis-data.co.uk not reached this run ({type(ex).__name__}: {str(ex)[:60]})"
        print(TENNIS_NOTE, file=sys.stderr)
        return []
    out = []
    from datetime import datetime, timedelta
    for tour, suffix in (("ATP", ""), ("WTA", "w")):
        for y in tb.YEARS:
            mt = re.search(r'HREF="([^"]*/%d%s/%d\.xlsx)"' % (y, suffix, y), page, re.I)
            if not mt:
                continue
            try:
                rows = tb.read_xlsx(tb.fetch(tb.SITE + mt.group(1)))
            except Exception:  # noqa: BLE001 - a year that will not load is PENDING
                continue
            for r in rows:
                d, w, lo = tb.num(r.get("Date")), r.get("Winner"), r.get("Loser")
                if d is None or not w or not lo or str(r.get("Comment", "Completed")).strip().lower() != "completed":
                    continue
                ws, ls = tb.num(r.get("Wsets")), tb.num(r.get("Lsets"))
                if ws is None or ls is None:
                    continue
                sets = []
                for i in range(1, 6):
                    a_, b_ = tb.num(r.get(f"W{i}")), tb.num(r.get(f"L{i}"))
                    if a_ is None or b_ is None:
                        break
                    sets.append([int(a_), int(b_)])
                pw, pl = tb.num(r.get("PSW")), tb.num(r.get("PSL"))
                first = str(w) < str(lo)
                flip = (lambda x: x) if first else (lambda x: [x[1], x[0]])
                day = (datetime(1899, 12, 30) + timedelta(days=d)).strftime("%Y-%m-%dT12:00Z")
                out.append({"sport": "tennis", "league": f"{tour} {r.get('Series', '')}".strip(), "lk": tour, "sk": str(y),
                            "date": day, "home": str(w) if first else str(lo), "away": str(lo) if first else str(w),
                            "hk": f"t:{w if first else lo}", "ak": f"t:{lo if first else w}",
                            "ft": flip([int(ws), int(ls)]), "periods": [flip(s) for s in sets] or None,
                            "games": sum(a + b for a, b in sets) if sets else None,
                            "best_of": int(tb.num(r.get("Best of")) or 3),
                            "prices": {"pa": pw if first else pl, "pb": pl if first else pw} if pw and pl and pw > 1 and pl > 1 else None})
    out.sort(key=lambda m: m["date"])
    return out


def _main_line(lines: dict, kind: str, a: str, b: str):
    """The line whose two prices are closest to each other (SportyBet's main line)."""
    best = None
    for k in lines:
        parts = k.split("|")
        if len(parts) != 3 or parts[0] != kind or parts[2] != a:
            continue
        ln = parts[1]
        x, y = lines.get(f"{kind}|{ln}|{a}"), lines.get(f"{kind}|{ln}|{b}")
        if x and y and (best is None or abs(x - y) < best[0]):
            best = (abs(x - y), float(ln), x, y)
    return best


def sportybet_rows(folder: Path) -> list[dict]:
    """SportyBet's universe archive: one row per graded game, its last price before kick-off."""
    out = []
    for f in sorted(folder.glob("graded_*.jsonl.gz")):
        with gzip.open(f, "rt", encoding="utf-8") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                res = r.get("result")
                if not res or res.get("after_90"):
                    continue
                p = (r.get("last") or {}).get("p") or {}
                lk = f"sb:{r.get('country')}|{r.get('comp')}"
                base = {"date": r["ko"], "league": f"{r.get('country')} {r.get('comp')}", "lk": lk, "sk": r["ko"][:4],
                        "home": r["home"], "away": r["away"], "hk": f"sb:{r['home']}", "ak": f"sb:{r['away']}",
                        "ft": [res["h"], res["a"]], "id": r.get("id")}
                if r.get("sport") == "basketball":
                    lines = p.get("lines") or {}
                    pr = {}
                    t = _main_line(lines, "total", "over", "under")
                    if t:
                        pr.update({"total": t[1], "over": t[2], "under": t[3]})
                    h = _main_line(lines, "hcp", "home", "away")
                    if h:
                        pr.update({"spread": h[1], "sp_home": h[2], "sp_away": h[3]})
                    if p.get("1x2") and len(p["1x2"]) == 2:
                        pr.update({"ml_home": p["1x2"][0], "ml_away": p["1x2"][1]})
                    out.append({**base, "sport": "sportybet basketball", "prices": pr or None})
                elif r.get("sport") == "football":
                    pr = {}
                    if p.get("ou2.5"):
                        pr.update({"o25": p["ou2.5"][0], "u25": p["ou2.5"][1]})
                    if p.get("btts"):
                        pr.update({"by": p["btts"][0], "bn": p["btts"][1]})
                    if p.get("1x2"):
                        h_, d_, a_ = p["1x2"]
                        s = 1 / h_ + 1 / d_ + 1 / a_
                        pr.update({"ml_home": h_, "ml_away": 1 / (s - 1 / h_) if s > 1 / h_ else None})
                    out.append({**base, "sport": "sportybet football", "prices": pr or None})
    out.sort(key=lambda m: m["date"])
    return out


# ---------------------------------------------------------------- the price trend (record against the price)
def fair_yes(prices) -> float | None:
    if not prices:
        return None
    y, n = prices
    return (1 / y) / (1 / y + 1 / n)


class PriceTrend:
    """A team's record against the price this season: the sum of (outcome - market chance) over its earlier games
    in this market, for the side it was on. Feed rows in date order with see(); ask signal() first."""

    def __init__(self):
        self.r = defaultdict(lambda: [0, 0.0])        # (market, team, sk) -> [n, sum residual]

    def signal(self, mk, m, min_games=5):
        """The yes side's expected residual from both teams' records (home record as the 'yes' team, away record
        counted against it), or None before both have min_games."""
        h = self.r[(mk, m["hk"], m["sk"])]
        a = self.r[(mk, m["ak"], m["sk"])]
        if h[0] < min_games or a[0] < min_games:
            return None
        if mk.startswith("over"):          # totals: both teams' 'over' records point the same way
            return (h[1] / h[0] + a[1] / a[0]) / 2
        return (h[1] / h[0] - a[1] / a[0]) / 2

    def see(self, mk, m, y, q):
        res = y - q
        if mk.startswith("over"):
            for t in (m["hk"], m["ak"]):
                self.r[(mk, t, m["sk"])][0] += 1
                self.r[(mk, t, m["sk"])][1] += res
        else:
            self.r[(mk, m["hk"], m["sk"])][0] += 1
            self.r[(mk, m["hk"], m["sk"])][1] += res
            self.r[(mk, m["ak"], m["sk"])][0] += 1
            self.r[(mk, m["ak"], m["sk"])][1] -= res     # the away side's record: it 'won' when the yes side lost


SPORTS_REGISTRY = [
    # sport, history in the framework, prices for a money test, status
    ("football", "ESPN all competitions since 2023-07 (97k), Flashscore world facts, internationals since 2010, football-data 10 seasons",
     "football-data average + best price (22 leagues, 10 seasons); SportyBet worldwide since 8 Oct 2026; corners/cards lines since 12 Nov 2026",
     "engine/trend_atlas.py"),
    ("basketball (NBA, WNBA, NCAA)", "ESPN since 2023-07, quarter scores", "ESPN pre-game total / spread / moneyline", "this module"),
    ("basketball (world)", "SportyBet universe archive since 8 Oct 2026", "SportyBet's own main total / handicap / moneyline", "this module"),
    ("ice hockey (NHL)", "ESPN since 2023-07, period scores", "ESPN pre-game total / puck line / moneyline", "this module"),
    ("baseball (MLB)", "ESPN since 2023-07, final score (innings PENDING)", "ESPN pre-game total / run line / moneyline", "this module"),
    ("American football (NFL, college)", "ESPN since 2023-07, quarter scores", "ESPN pre-game total / spread / moneyline", "this module"),
    ("tennis (ATP, WTA)", "tennis-data.co.uk 2019-2025, set scores", "Pinnacle closing match price", "this module"),
    ("darts", "data/darts_results.py (+ majors, Premier League)", "PENDING: no price history; forward via the multisport board's SportyBet/Betfair prices", "PENDING"),
    ("snooker", "data/snooker_results.py", "PENDING: no price history", "PENDING"),
    ("cricket", "cricsheet (backtest/cricket_backtest.py)", "PENDING: no price history", "PENDING"),
    ("table tennis, volleyball, rugby, handball, esports, MMA/boxing", "Flashscore day feeds (7 days only) via the multisport board",
     "PENDING: no price history; the multisport board records SportyBet/Betfair prices for its picks", "PENDING"),
]
