"""
WORLD VIEW - the framework's own number for any game the analyst's lists pick, worldwide, when the board does not
rate it. The Architect, 2026-11-13: "Fix the gap, the basketball list and first half corners, bookings, fix
everything. The framework only rates the leagues its model ... Add more leagues ... the trend is covering worldwide
coverage, so we are looking at worldwide coverage."

The board's model (Dixon-Coles, calibrated) rates only the leagues it covers. Everywhere else this module gives the
framework's view from its own archives, the same data the lists are built from:

  goals        full-time 1X2, both teams to score, over/under 2.5 - a goals Poisson per SportyBet league: each team's
               goals for / against per game shrunk to the league mean (engine/lower_league_value.Goals), fitted on
               every graded SportyBet game of the universe archive (SportyBet's own names, every country); where
               that archive is too young for the teams (it began 2026-10-07), the same Poisson on ESPN's archive
               this season, matched through the list rosters as below.
  first half   1st-half over/under lines - the same Poisson fitted on half-time scores (SportyBet, then ESPN).
  corners,     corners and bookings over/under lines - each team's corners and yellow cards for / against per game
  bookings     this season (ESPN's match archive, every competition ESPN lists, the lists' own source), matched to
               the SportyBet game through the list test's league rosters (both teams in one league's list, or no
               view); a negative binomial with the league's own spread (variance over mean) gives the line chance.
  basketball   the main total - each team's points for / against per game shrunk to the league mean (universe
               archive, overtime included as SportyBet settles it); normal with the league's own spread.

Every view says where it came from ("board", "world goals", "world first half", "world corners", "world bookings",
"world basketball"), so the analyst's record splits by source. RECORD ONLY here: this module prices, it never picks,
stakes or blocks. A team with too few games gives no view (HR35), never a guess.
"""
from __future__ import annotations

import gzip
import json
import math
from datetime import UTC, datetime
from pathlib import Path

from engine import list_picks as lp
from engine import lower_league_value as llv

ROOT = Path(__file__).resolve().parents[1]
MIN_GAMES = 5           # a team needs this many games in its league for any view
SHRINK = 6.0            # pseudo-games of the league mean added to each team's rates
BB_MIN, BB_SHRINK = 4, 4.0


# ---------------------------------------------------------------- pure maths
def poisson_grid(lh: float, la: float, n: int = 12) -> list[list[float]]:
    ph = [math.exp(-lh) * lh ** k / math.factorial(k) for k in range(n)]
    pa = [math.exp(-la) * la ** k / math.factorial(k) for k in range(n)]
    return [[ph[i] * pa[j] for j in range(n)] for i in range(n)]


def goals_markets(lh: float, la: float) -> dict[str, float]:
    g = poisson_grid(lh, la)
    n = len(g)
    home = sum(g[i][j] for i in range(n) for j in range(n) if i > j)
    away = sum(g[i][j] for i in range(n) for j in range(n) if j > i)
    draw = 1 - home - away
    yes = (1 - sum(g[0])) * (1 - sum(g[i][0] for i in range(n)))
    over25 = sum(g[i][j] for i in range(n) for j in range(n) if i + j > 2)
    return {"win_home": home, "win_away": away, "draw": draw, "dc_home": home + draw, "dc_away": away + draw,
            "btts_yes": yes, "btts_no": 1 - yes, "over25": over25}


def poisson_over(mean: float, line: float) -> float:
    k = int(math.floor(line))
    return 1 - sum(math.exp(-mean) * mean ** i / math.factorial(i) for i in range(k + 1))


def negbin_over(mean: float, line: float, disp: float) -> float:
    """P(count > line) for a count with this mean and variance = disp x mean (Poisson when disp <= 1)."""
    if disp <= 1.02:
        return poisson_over(mean, line)
    r = mean / (disp - 1)
    p = r / (r + mean)
    k = int(math.floor(line))
    cdf, pmf = 0.0, p ** r
    for i in range(k + 1):
        cdf += pmf
        pmf *= (i + r) / (i + 1) * (1 - p)
    return max(0.0, min(1.0, 1 - cdf))


def normal_over(mean: float, sd: float, line: float) -> float:
    return 0.5 * math.erfc((line - mean) / (sd * math.sqrt(2)))


# ---------------------------------------------------------------- the three archives
class Counts:
    """Per (league, team): games, for, against of one count stat; league totals for mean and spread."""

    def __init__(self):
        self.tm: dict = {}
        self.lg: dict = {}

    def add(self, league, home, away, h: float, a: float) -> None:
        lg = self.lg.setdefault(league, [0, 0.0, 0.0, 0.0])     # games, sum of home, sum of away, sum of total^2
        lg[0] += 1
        lg[1] += h
        lg[2] += a
        lg[3] += (h + a) ** 2
        for t, f, x in ((home, h, a), (away, a, h)):
            s = self.tm.setdefault((league, t), [0, 0.0, 0.0])
            s[0] += 1
            s[1] += f
            s[2] += x

    def expected(self, league, home, away, min_games: int = MIN_GAMES, shrink: float = SHRINK):
        """(expected total, league variance / mean, league sd of the total) or None."""
        lg = self.lg.get(league)
        th, ta = self.tm.get((league, home)), self.tm.get((league, away))
        if not lg or lg[0] < 20 or not th or not ta or min(th[0], ta[0]) < min_games:
            return None
        n = lg[0]
        side = (lg[1] + lg[2]) / (2 * n)                        # one side's mean count
        mean_t = (lg[1] + lg[2]) / n
        var_t = max(lg[3] / n - mean_t ** 2, 1e-6)

        def rate(s, i):
            return (s[i] + shrink * side) / (s[0] + shrink)
        exp_home = (rate(th, 1) + rate(ta, 2)) / 2
        exp_away = (rate(ta, 1) + rate(th, 2)) / 2
        return exp_home + exp_away, var_t / max(mean_t, 1e-6), math.sqrt(var_t)


def _universe_rows(folder: Path):
    seen = set()
    for f in sorted(Path(folder).glob("graded_*.jsonl.gz")):
        try:
            with gzip.open(f, "rt", encoding="utf-8") as fh:
                for line in fh:
                    try:
                        g = json.loads(line)
                    except ValueError:
                        continue
                    if g.get("id") in seen:
                        continue
                    seen.add(g.get("id"))
                    yield g
        except OSError:
            continue


class World:
    """The framework's worldwide view; each archive is read once, on first need."""

    def __init__(self, root: Path = ROOT, now: datetime | None = None):
        self.root, self.now = root, now or datetime.now(UTC)
        self._sb = None
        self._espn = None

    # SportyBet archive: football goals (full time, first half) and basketball points
    def _sportybet(self):
        if self._sb is None:
            ft, ht, bb = llv.Goals(), llv.Goals(), Counts()
            for g in _universe_rows(self.root / "data" / "universe"):
                res = g.get("result") or {}
                if res.get("h") is None or not g.get("home") or not g.get("away"):
                    continue
                league = f"{g.get('country', '')}: {g.get('comp', '')}"
                if g.get("sport") == "basketball":
                    bb.add(league, g["home"], g["away"], float(res["h"]), float(res["a"]))
                    continue
                if g.get("sport", "football") != "football" or res.get("after_90"):
                    continue
                ft.add(league, g["home"], g["away"], int(res["h"]), int(res["a"]))
                h1 = res.get("ht") or []
                if len(h1) == 2 and None not in h1:
                    ht.add(league, g["home"], g["away"], int(h1[0]), int(h1[1]))
            self._sb = (ft, ht, bb)
        return self._sb

    # ESPN archive (this season): corners and yellow cards, by ESPN league id and the team's list-roster name
    def _espn_stats(self):
        if self._espn is None:
            from data import espn_history
            from engine import stat_lists
            rows = stat_lists.season_rows(espn_history.load(self.root / "data" / "espn_matches"), self.now)
            corners, cards, ft, ht = Counts(), Counts(), llv.Goals(), llv.Goals()
            for m in rows:
                lid, h, a = str(m.get("lid")), lp.norm(m.get("home")), lp.norm(m.get("away"))
                g = m.get("ft")
                if isinstance(g, list) and len(g) == 2 and None not in g:
                    ft.add(lid, h, a, int(g[0]), int(g[1]))
                g = m.get("ht")
                if isinstance(g, list) and len(g) == 2 and None not in g:
                    ht.add(lid, h, a, int(g[0]), int(g[1]))
                c = m.get("corners")
                if isinstance(c, list) and len(c) == 2 and None not in c:
                    corners.add(lid, h, a, float(c[0]), float(c[1]))
                cs = m.get("cards")
                if isinstance(cs, list):
                    yh = sum(1 for x in cs if len(x) >= 3 and x[1] == 0 and x[2] == "Y")
                    ya = sum(1 for x in cs if len(x) >= 3 and x[1] == 1 and x[2] == "Y")
                    cards.add(lid, h, a, float(yh), float(ya))
            self._espn = (corners, cards, lp.load_index(self.root), ft, ht)
        return self._espn

    def _espn_game(self, home: str, away: str):
        """(lid, roster home, roster away): the ESPN competition whose list holds both teams, the names matching
        exactly before loosely, then the one where both have played most this season (a cup or a youth list that
        also holds them is passed over). None when no competition has both with MIN_GAMES games."""
        stats = self._espn_stats()
        idx, ft = stats[2], stats[3]
        h, a = lp.norm(home), lp.norm(away)
        best = None
        for lid in idx.rosters:
            th, ta = idx.roster_team(lid, h), idx.roster_team(lid, a)
            if th is None or ta is None or th == ta:
                continue
            n = min(ft.games(lid, th), ft.games(lid, ta))
            if n < MIN_GAMES:
                continue
            score = ((th == h) + (ta == a), n)
            if best is None or score > best[0]:
                best = (score, (lid, th, ta))
        return best[1] if best else None

    def _espn_goals(self, home: str, away: str, which: int):
        """Goals rates from ESPN's archive (3 full time, 4 half time) when SportyBet's archive is too young."""
        game = self._espn_game(home, away)
        return self._espn_stats()[which].lambdas(*game) if game else None

    def chance(self, pick: dict) -> tuple[float, str] | None:
        """The framework's worldwide chance for a list pick's outcome, with its source, or None (no view)."""
        key, home, away = pick.get("key") or "", pick.get("home") or "", pick.get("away") or ""
        league = f"{pick.get('country') or ''}: {pick.get('comp') or ''}"
        if key == "bb_over":
            line = _num(pick.get("line"))
            e = self._sportybet()[2].expected(league, home, away, BB_MIN, BB_SHRINK)
            if line is None or e is None:
                return None
            return normal_over(e[0], max(e[2], 6.0), line), "world basketball"
        if "|" in key:                                            # a line market: "corners|9.5|over"
            mkt, ln, side = key.split("|")
            line = _num(ln)
            if line is None:
                return None
            if mkt == "first_half":
                lam = self._sportybet()[1].lambdas(league, home, away) or self._espn_goals(home, away, 4)
                if not lam:
                    return None
                over = poisson_over(lam[0] + lam[1], line)
                src = "world first half"
            elif mkt in ("corners", "bookings"):
                game = self._espn_game(home, away)
                if game is None:
                    return None
                corners, cards = self._espn_stats()[:2]
                e = (corners if mkt == "corners" else cards).expected(*game)
                if e is None:
                    return None
                over = negbin_over(e[0], line, e[1])
                src = f"world {mkt}"
            else:
                return None
            return (over if side == "over" else 1 - over), src
        lam = self._sportybet()[0].lambdas(league, home, away) or self._espn_goals(home, away, 3)
        if not lam:
            return None
        p = goals_markets(*lam).get(key)
        return None if p is None else (p, "world goals")


def _num(x) -> float | None:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None
