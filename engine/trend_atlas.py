"""
TREND ATLAS - every market's rate, league by league, team by team, season by season, for all of football.

The Architect, 2026-11-12: "look for the trends for every market ... goals over and under 1.5, 2.5, 3.5, 4.5 ...
cards over and under, both teams to score yes or no, first half wins, first half goals ... league by league, team
by team, year by year ... early goals, late goals ... cover the entire football, FIFA events, any event ... There you
will find certain edges ... You test it, then you bring it up, then we deploy it."

Sources (all fetched by the framework, HR59):
  data/espn_matches/   (data/espn_history.py)  every competition ESPN lists, worldwide, July 2023 on: goal and card
                        minutes, corners, fouls, shots
  data/world_facts/    (engine/world_facts.py) every Flashscore match from 12 Nov 2026: result + half-time score
  martj42 international results (data/international_source.py): every men's international, full-time score only

MARKETS below is the search grid. Each market is a yes/no outcome of one match (markets are yes/no: both sides are
the same row, 'under' = 1 - 'over'). A market whose input is missing for a match is PENDING for that match, never 0.

build() -> {"markets": [...], "leagues": {market: [rows]}, "teams": {market: [rows]}} where a league row is
(league, season, games, rate) and a team row is (team, league, season, venue, games, rate). RECORD ONLY: nothing
here picks, stakes or blocks; backtest/trend_atlas_study.py tests which trends repeat and which beat the price.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "trend_atlas" / "atlas.json"


def _goals(m):
    return m["ft"][0] + m["ft"][1]


def _ht(m):
    return None if not m.get("ht") else m["ht"][0] + m["ht"][1]


def _h2(m):
    return None if not m.get("ht") else _goals(m) - _ht(m)


def _cards(m):
    c = m.get("cards")
    return None if c is None else len(c)


def _yellows(m):
    c = m.get("cards")
    return None if c is None else sum(1 for x in c if x[2] == "Y")


def _corners(m):
    c = m.get("corners")
    return None if not c else c[0] + c[1]


def _goal_in(m, lo, hi):
    g = m.get("goals")
    return None if g is None else float(any(lo <= x[0] <= hi for x in g))


def _ou(f, line):
    def g(m):
        v = f(m)
        return None if v is None else float(v > line)
    return g


MARKETS: dict = {}
for ln in (0.5, 1.5, 2.5, 3.5, 4.5):
    MARKETS[f"goals over {ln}"] = _ou(_goals, ln)
MARKETS["BTTS yes"] = lambda m: float(m["ft"][0] > 0 and m["ft"][1] > 0)
MARKETS["home win"] = lambda m: float(m["ft"][0] > m["ft"][1])
MARKETS["draw"] = lambda m: float(m["ft"][0] == m["ft"][1])
MARKETS["away win"] = lambda m: float(m["ft"][0] < m["ft"][1])
MARKETS["home scores"] = lambda m: float(m["ft"][0] > 0)
MARKETS["away scores"] = lambda m: float(m["ft"][1] > 0)
MARKETS["1st half home win"] = lambda m: None if not m.get("ht") else float(m["ht"][0] > m["ht"][1])
MARKETS["1st half draw"] = lambda m: None if not m.get("ht") else float(m["ht"][0] == m["ht"][1])
MARKETS["1st half away win"] = lambda m: None if not m.get("ht") else float(m["ht"][0] < m["ht"][1])
for ln in (0.5, 1.5, 2.5):
    MARKETS[f"1st half goals over {ln}"] = _ou(_ht, ln)
for ln in (0.5, 1.5, 2.5):
    MARKETS[f"2nd half goals over {ln}"] = _ou(_h2, ln)
MARKETS["2nd half more goals than 1st"] = lambda m: None if not m.get("ht") else float(_h2(m) > _ht(m))
MARKETS["early goal (0-15 min)"] = lambda m: _goal_in(m, 0, 15)
MARKETS["goal 76 min on"] = lambda m: _goal_in(m, 76, 200)
MARKETS["goal 80 min on"] = lambda m: _goal_in(m, 80, 200)
for ln in (7.5, 8.5, 9.5, 10.5, 11.5, 12.5):
    MARKETS[f"corners over {ln}"] = _ou(_corners, ln)
for ln in (2.5, 3.5, 4.5, 5.5):
    MARKETS[f"cards over {ln}"] = _ou(_cards, ln)
for ln in (2.5, 3.5, 4.5):
    MARKETS[f"yellow cards over {ln}"] = _ou(_yellows, ln)

TEAM_MIN = 6        # a team-venue-season row needs this many games to be listed
LEAGUE_MIN = 30


def norm(m: dict, src: str) -> dict:
    """One common row from any source: league key, season key, team keys."""
    if src == "espn":
        lk = f"espn:{m.get('lid')}"
        return {**m, "lk": lk, "sk": str(m.get("year") or m.get("season") or ""), "hk": f"espn:{m.get('hid')}",
                "ak": f"espn:{m.get('aid')}"}
    if src == "wf":
        return {**m, "date": m["ko"], "lk": f"fs:{m['league']}", "sk": m["ko"][:4], "hk": f"fs:{m['home']}",
                "ak": f"fs:{m['away']}", "goals": None, "cards": None, "corners": None}
    if src == "int":
        return {**m, "lk": f"int:{m['league']}", "sk": m["date"][:4], "hk": f"int:{m['home']}", "ak": f"int:{m['away']}",
                "ht": None, "goals": None, "cards": None, "corners": None}
    raise ValueError(src)


def load_all(root: Path = ROOT, espn_dirs: list[Path] | None = None, internationals: bool = True,
             since_year: int = 2010, wf_dir: Path | None = None) -> list[dict]:
    rows = []
    from data import espn_history
    for d in espn_dirs or [root / "data" / "espn_matches"]:
        rows += [norm(m, "espn") for m in espn_history.load(d)]
    wf = wf_dir or root / "data" / "world_facts"
    for p in sorted(wf.glob("*.jsonl")) if wf.exists() else []:
        for line in p.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(norm(json.loads(line), "wf"))
            except (ValueError, KeyError):
                continue
    if internationals:
        rows += [norm(m, "int") for m in international_rows(since_year)]
    rows.sort(key=lambda m: m["date"])
    return rows


def international_rows(since_year: int = 2010) -> list[dict]:
    """martj42 results (every men's international). Full-time score only."""
    import csv
    import io
    import urllib.request
    from data import international_source as isrc
    try:
        req = urllib.request.Request(isrc.RESULTS_URL, headers={"User-Agent": "Mozilla/5.0"})  # noqa: S310
        with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310 (fixed https URL)
            txt = r.read().decode("utf-8")
    except Exception:  # noqa: BLE001 - source down: internationals PENDING this run
        return []
    out = []
    for r in csv.DictReader(io.StringIO(txt)):
        try:
            if int(r["date"][:4]) < since_year:
                continue
            out.append({"id": f"int:{r['date']}:{r['home_team']}:{r['away_team']}", "date": r["date"] + "T00:00Z",
                        "league": r["tournament"], "home": r["home_team"], "away": r["away_team"],
                        "ft": [int(r["home_score"]), int(r["away_score"])], "neutral": r.get("neutral") == "TRUE"})
        except (KeyError, ValueError):
            continue
    return out


def league_names(rows: list[dict]) -> dict:
    names = defaultdict(lambda: defaultdict(int))
    for m in rows:
        names[m["lk"]][m.get("league") or m["lk"]] += 1
    return {k: max(v, key=v.get) for k, v in names.items()}


def build(rows: list[dict]) -> dict:
    lname = league_names(rows)
    tname = {}
    lg = defaultdict(lambda: [0, 0.0])          # (market, lk, sk) -> [n, sum]
    tm = defaultdict(lambda: [0, 0.0])          # (market, team, lk, sk, venue) -> [n, sum]
    for m in rows:
        tname[m["hk"]], tname[m["ak"]] = m["home"], m["away"]
        for mk, f in MARKETS.items():
            v = f(m)
            if v is None:
                continue
            a = lg[(mk, m["lk"], m["sk"])]
            a[0] += 1
            a[1] += v
            for team, venue in ((m["hk"], "home"), (m["ak"], "away")):
                b = tm[(mk, team, m["lk"], m["sk"], venue)]
                b[0] += 1
                b[1] += v
    out = {"markets": list(MARKETS), "matches": len(rows), "leagues": {}, "teams": {}}
    for (mk, lk, sk), (n, s) in lg.items():
        if n >= LEAGUE_MIN:
            out["leagues"].setdefault(mk, []).append([lname.get(lk, lk), lk, sk, n, round(s / n, 4)])
    for (mk, team, lk, sk, venue), (n, s) in tm.items():
        if n >= TEAM_MIN:
            out["teams"].setdefault(mk, []).append([tname.get(team, team), team, lname.get(lk, lk), sk, venue, n, round(s / n, 4)])
    for d in (out["leagues"], out["teams"]):
        for mk in d:
            d[mk].sort(key=lambda r: -r[-1])
    return out


class Predictor:
    """The trend's own chance for a market in a match, from earlier games only: the home side's rate at home and
    the away side's rate away this season, each shrunk toward the league's rate (last season and this season so
    far, LEAGUE_PRIOR games of weight), averaged. Feed matches in date order with see(); ask with chance() first."""

    SHRINK = 8.0          # games of weight the league rate gets against a team's own record
    LEAGUE_PRIOR = 60.0

    def __init__(self, markets: list[str], table: dict | None = None):
        self.markets = markets
        self.table = table if table is not None else MARKETS     # any sport's market functions (engine/sport_atlas.py)
        self.team = defaultdict(lambda: [0, 0.0])     # (mk, team, venue, sk) -> [n, sum]
        self.league = defaultdict(lambda: [0, 0.0])   # (mk, lk, sk) -> [n, sum]
        self.glob = defaultdict(lambda: [0, 0.0])     # mk -> [n, sum]

    def _league_rate(self, mk, lk, sk):
        g = self.glob[mk]
        base = g[1] / g[0] if g[0] else None
        if base is None:
            return None, 0
        try:
            prev = str(int(sk) - 1)
        except ValueError:
            prev = None
        cur = self.league[(mk, lk, sk)]
        old = self.league[(mk, lk, prev)] if prev else [0, 0.0]
        n, s = cur[0] + old[0], cur[1] + old[1]
        return (s + self.LEAGUE_PRIOR * base) / (n + self.LEAGUE_PRIOR), n

    def chance(self, mk, m, min_team=4):
        lr, ln = self._league_rate(mk, m["lk"], m["sk"])
        if lr is None:
            return None
        h = self.team[(mk, m["hk"], "home", m["sk"])]
        a = self.team[(mk, m["ak"], "away", m["sk"])]
        if h[0] < min_team or a[0] < min_team:
            return None
        ph = (h[1] + self.SHRINK * lr) / (h[0] + self.SHRINK)
        pa = (a[1] + self.SHRINK * lr) / (a[0] + self.SHRINK)
        return {"p": (ph + pa) / 2, "league": lr, "league_n": ln, "home_n": h[0], "away_n": a[0]}

    def see(self, m):
        for mk in self.markets:
            v = self.table[mk](m)
            if v is None:
                continue
            for k in ((mk, m["hk"], "home", m["sk"]), (mk, m["ak"], "away", m["sk"])):
                self.team[k][0] += 1
                self.team[k][1] += v
            self.league[(mk, m["lk"], m["sk"])][0] += 1
            self.league[(mk, m["lk"], m["sk"])][1] += v
            self.glob[mk][0] += 1
            self.glob[mk][1] += v


def write(atlas: dict, path: Path = OUT, top: int = 30) -> Path:
    """The atlas for the app and the Architect: per market the top and bottom leagues and teams (latest season
    first), with games counted, so nobody reads a 6-game rate as a law."""
    slim = {"markets": atlas["markets"], "matches": atlas["matches"], "leagues": {}, "teams": {}}
    for kind in ("leagues", "teams"):
        for mk, rows in atlas[kind].items():
            latest = max(r[-3 if kind == "leagues" else -4] for r in rows)
            cur = [r for r in rows if r[-3 if kind == "leagues" else -4] == latest]
            slim[kind][mk] = {"season": latest, "top": cur[:top], "bottom": cur[-top:][::-1]}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(slim, ensure_ascii=False), encoding="utf-8")
    return path
