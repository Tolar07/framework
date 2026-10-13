"""
LEAGUE STRENGTH — one rating per FotMob league, so a team profile built in
one league can be read against a team from another (Architect 2026-10-13:
"do the strength adjustment").

A team's season numbers (xG for and against per match) are measured against
its own league. Viking's 1.6 xG a game in Norway is not Bayern's 1.6 in the
Bundesliga. The ratings put the leagues on one scale the way
engine/cross_league.py does for the goals model: matches BETWEEN leagues are
the bridges. Here they come from FotMob's own pages:
  - the European competitions and their qualifying rounds (and the other
    continents' club competitions), which link the countries;
  - the domestic cups, which link a country's divisions.

The fit: for every finished match, goal difference (capped at ±3) =
rating(home team's league) − rating(away team's league) + home advantage,
least squares with a small ridge (RIDGE matches' worth of pull to 0), in two
stages: first the club competitions' main stages alone (the strong leagues
meeting each other) fix those leagues' ratings; then every other league is
rated against them (lower divisions via the cups, small countries via the
qualifiers). One stage was tried first: small countries met only in
qualifiers were pulled to the average and flattered whoever beat them
(Denmark came out level with the Bundesliga). A
rating is goals per match against an average league in the fit; only the
DIFFERENCE between two leagues is used. A league with fewer than MIN_N
matches against other leagues is not rated (HR35: its games read PENDING,
never a guess).

Known limit: a team is put in the league it plays in NOW (FotMob's team page),
so last season's matches of promoted / relegated teams count for the wrong
league; last season weighs LAST_SEASON_WEIGHT against this one's 1.0.

    python data/league_strength.py      → data/teams/league_strength.json
"""
from __future__ import annotations

import json
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from data import fotmob as fm  # noqa: E402

OUT = ROOT / "data" / "teams" / "league_strength.json"
TEAM_LEAGUES = ROOT / "data" / "teams" / "team_leagues.json"
_ALL = "https://www.fotmob.com/api/data/allLeagues"
_LEAGUE = "https://www.fotmob.com/api/data/leagues?id={lid}&season={season}"
_TEAM = "https://www.fotmob.com/api/data/teams?id={tid}"
GD_CAP = 3
RIDGE = 1.0
MIN_N = 8
LAST_SEASON_WEIGHT = 0.5
SEASONS = 2

_CLUB_COMP = re.compile(r"champions league|europa league|conference league|libertadores|sudamericana|"
                        r"concacaf champions|leagues cup|caf confed|club world cup|intercontinental", re.I)
_CUP = re.compile(r"\b(cup|cupen|pokal|pokalen|copa del rey|coppa italia|coupe de france|beker|taça|"
                  r"kupa|kupası|kupasi|puchar|pohár|pohar|kup|kupen|bikar)\b", re.I)
_NOT = re.compile(r"women|femin|fémin|femenin|frauen|\(w\)|\bw\b|u1\d|u2\d|youth|super ?cup|supercup|supercoppa|recopa|"
                  r"olympic|(?<!club )world cup|nations|\bEURO\b|gold cup|asian cup|africa cup|swf|swpl", re.I)
EUROPE = {"England", "Spain", "Germany", "Italy", "France", "Netherlands", "Portugal", "Scotland", "Belgium",
          "Turkey", "Türkiye", "Turkiye", "Greece", "Austria", "Switzerland", "Denmark", "Poland", "Norway",
          "Sweden", "Croatia", "Czechia", "Czech Republic", "Serbia", "Ukraine", "Romania", "Hungary", "Slovakia",
          "Slovenia", "Bulgaria", "Cyprus", "Israel", "Wales", "Northern Ireland", "Ireland", "Finland",
          "Iceland", "Russia"}


def competitions() -> dict[int, str]:
    """The FotMob competitions that link leagues: club competitions between
    countries, and the domestic cups of the European countries."""
    blob = fm._get(_ALL)
    out = {}
    for sec in ("international", "countries"):
        for c in blob.get(sec, []):
            for lg in c.get("leagues", []):
                name, country = lg.get("name", ""), c.get("name", "")
                if _NOT.search(name):
                    continue
                if (sec == "international" and _CLUB_COMP.search(name)) or (country in EUROPE and _CUP.search(name)):
                    out[int(lg["id"])] = f"{country} — {name}"
    return out


def _score(m: dict) -> tuple[int, int] | None:
    st = m.get("status") or {}
    if not st.get("finished") or st.get("cancelled") or st.get("awarded"):
        return None
    nums = re.findall(r"\d+", st.get("scoreStr") or "")
    return (int(nums[0]), int(nums[1])) if len(nums) >= 2 else None


def comp_matches(lid: int, pause: float = 0.3) -> list[dict]:
    """Finished matches of a competition's last SEASONS seasons (newest first)."""
    first = fm._get(_LEAGUE.format(lid=lid, season=""))
    seasons = (first.get("allAvailableSeasons") or [])[:SEASONS]
    out = []
    for i, season in enumerate(seasons):
        blob = first if i == 0 else fm._get(_LEAGUE.format(lid=lid, season=season.replace("/", "%2F")))
        for m in (blob.get("fixtures") or {}).get("allMatches") or []:
            sc = _score(m)
            h, a = (m.get("home") or {}).get("id"), (m.get("away") or {}).get("id")
            if sc and h and a:
                out.append({"h": str(h), "a": str(a), "hg": sc[0], "ag": sc[1], "w": 1.0 if i == 0 else LAST_SEASON_WEIGHT,
                            "comp": lid})
        time.sleep(pause)
    return out


def team_leagues(ids: set[str], pause: float = 0.3) -> dict[str, list]:
    """{team id: [league id, league name]} — the league each team plays in now,
    from its FotMob page; cached in data/teams/team_leagues.json."""
    known = json.loads(TEAM_LEAGUES.read_text(encoding="utf-8")) if TEAM_LEAGUES.exists() else {}
    for n, tid in enumerate(sorted(ids - set(known))):
        try:
            d = (fm._get(_TEAM.format(tid=tid)).get("details") or {})
            known[tid] = [d.get("primaryLeagueId"), d.get("primaryLeagueName")]
        except Exception:  # noqa: BLE001, S112 — a missing page leaves the team unplaced
            continue
        time.sleep(pause)
        if n % 100 == 99:
            TEAM_LEAGUES.write_text(json.dumps(known, ensure_ascii=False), encoding="utf-8")
    TEAM_LEAGUES.parent.mkdir(parents=True, exist_ok=True)
    TEAM_LEAGUES.write_text(json.dumps(known, ensure_ascii=False), encoding="utf-8")
    return known


def _solve(rows: list[tuple], fixed: dict[str, float], ridge: float) -> tuple[dict[str, float], float, dict]:
    """Least squares of capped goal difference on league ratings + home
    advantage, with the `fixed` leagues' ratings held as known."""
    import numpy as np
    free = sorted({x for r in rows for x in r[:2]} - set(fixed))
    ix = {lg: i for i, lg in enumerate(free)}
    k = len(free)
    a = np.zeros((len(rows), k + 1))
    y = np.zeros(len(rows))
    sw = np.zeros(len(rows))
    cross: dict[str, float] = {}
    for i, (lh, la, gd, wt) in enumerate(rows):
        y[i] = gd - fixed.get(lh, 0.0) + fixed.get(la, 0.0)
        if lh in ix:
            a[i, ix[lh]] += 1
        if la in ix:
            a[i, ix[la]] -= 1
        a[i, k] = 1.0                       # home advantage
        sw[i] = wt ** 0.5
        if lh != la:
            cross[lh] = cross.get(lh, 0) + 1
            cross[la] = cross.get(la, 0) + 1
    aw = a * sw[:, None]
    coef = np.linalg.solve(aw.T @ aw + np.diag([ridge] * k + [0.0]), aw.T @ (y * sw))
    return {lg: float(coef[ix[lg]]) for lg in free}, float(coef[k]), cross


def fit(matches: list[dict], league_of: dict[str, list], main_comps: set | None = None) -> dict:
    """Ratings in two stages (see the module doc). Stage 1 rates the leagues
    from the club competitions' MAIN stages (`main_comps`; all matches when
    None), where strong leagues meet each other. Stage 2 holds those fixed and
    rates every other league — lower divisions through the cups, small
    countries through the qualifiers — against them. A small country met only
    in qualifiers can't then pull a big league's level about."""
    rows, stage1 = [], []
    for m in matches:
        lh, la = (league_of.get(m["h"]) or [None])[0], (league_of.get(m["a"]) or [None])[0]
        if lh is None or la is None:
            continue
        r = (str(lh), str(la), max(-GD_CAP, min(GD_CAP, m["hg"] - m["ag"])), m["w"])
        rows.append(r)
        if main_comps is None or m.get("comp") in main_comps:
            stage1.append(r)
    r1, _h1, c1 = _solve(stage1, {}, RIDGE)
    fixed = {lg: v for lg, v in r1.items() if c1.get(lg, 0) >= MIN_N}
    r2, home, c2 = _solve(rows, fixed, RIDGE)
    names = {str(v[0]): v[1] for v in league_of.values() if v and v[0] is not None}
    group = _groups(rows)
    out = {}
    for lg in sorted(set(fixed) | set(r2)):
        n = int(c2.get(lg, 0))
        out[lg] = {"name": names.get(lg), "rating": round(fixed.get(lg, r2.get(lg, 0.0)), 3), "cross_matches": n,
                   "stage": 1 if lg in fixed else 2, "rated": lg in fixed or n >= MIN_N, "group": group.get(lg)}
    return {"home_advantage": round(home, 3), "leagues": out}


def _groups(rows: list[tuple]) -> dict[str, str]:
    """Leagues linked by matches into one group (union-find); a group is
    named after its smallest league id. Ratings compare only within a group."""
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        while parent.setdefault(x, x) != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for lh, la, _gd, _w in rows:
        a, b = find(lh), find(la)
        if a != b:
            parent[max(a, b)] = min(a, b)
    return {lg: find(lg) for lg in parent}


def main_competitions(comps: dict[int, str]) -> set[int]:
    """The club competitions' main stages: international, not qualifying."""
    return {lid for lid, name in comps.items()
            if name.startswith("International") and "qualif" not in name.lower()}


def build() -> dict:
    comps = competitions()
    matches = []
    for lid, name in comps.items():
        try:
            got = comp_matches(lid)
        except Exception as e:  # noqa: BLE001 — one page failing never stops the build
            print(f"  {name}: unavailable ({str(e)[:50]})")
            continue
        print(f"  {name}: {len(got)} matches")
        matches += got
    league_of = team_leagues({m["h"] for m in matches} | {m["a"] for m in matches})
    out = fit(matches, league_of, main_competitions(comps))
    out.update({"built_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%MZ"), "source": "FotMob",
                "competitions": len(comps), "matches": len(matches)})
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    rated = sum(v["rated"] for v in out["leagues"].values())
    print(f"league strength: {len(matches)} matches, {len(out['leagues'])} leagues, {rated} rated → {OUT.name}")
    return out


def load() -> dict:
    return json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}


def gap(table: dict, home_league, away_league) -> float | None:
    """Home league's rating minus away league's, in goals per match; 0.0 for
    the same league; None when either league isn't rated (PENDING)."""
    if home_league is None or away_league is None:
        return None
    if str(home_league) == str(away_league):
        return 0.0
    lg = table.get("leagues") or {}
    h, a = lg.get(str(home_league)), lg.get(str(away_league))
    if not h or not a or not h.get("rated") or not a.get("rated") or h.get("group") != a.get("group"):
        return None
    return round(h["rating"] - a["rating"], 3)


if __name__ == "__main__":
    build()
