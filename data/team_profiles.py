"""
TEAM PROFILES — every team in every covered competition: squad, coach,
formation, and its season numbers ranked inside its league (Architect
2026-10-13: "create a database for the current season ... all the players in
their current team and their current position ... their tactical profile,
what they do, how they play, how they defend, their structure ... and refer
to it when you need it").

Source: FotMob (free, no key). One league page lists the teams; each team page
gives the squad (name, position, age, market value, season rating, goals,
assists, injury), the coach, the last lineup's formation, recent form and ~30
season stats with the team's rank in its league: goals and xG for and
against, possession, shots on target, big chances, box touches, tackles,
interceptions, possession won in the final third, clearances, saves, set-piece
goals, distance covered, cards.

From those numbers each team gets a STYLE READ (attack, defence, possession,
press — each strong / average / weak against its own league), and a fixture
gets a PROFILE READ: the goals both sides' attack and defence numbers point
to, and which way that leans (BTTS / Over, or Under / double chance).

A label, never a selector: nothing here picks, stakes or blocks. It becomes a
rule only once a walk-forward test shows it beats SportyBet's own price, and
only by the Architect. That test needs profiles as they stood BEFORE each
match, so every run keeps a dated snapshot (data/teams/profiles_<date>.json.gz) — today's
numbers can't be used to judge last week's games. A stat FotMob doesn't
publish is absent, never 0 (HR35).

    python data/team_profiles.py                 # every covered competition
    python data/team_profiles.py "Premier League" "Championship"
"""
from __future__ import annotations

import gzip
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from data import fotmob as fm  # noqa: E402
from data import league_strength as ls  # noqa: E402

TEAMS_DIR = ROOT / "data" / "teams"
_LEAGUE = "https://www.fotmob.com/api/data/leagues?id={lid}"
_TEAM = "https://www.fotmob.com/api/data/teams?id={tid}"

# Framework competition -> FotMob league id (each checked against FotMob's own
# league name and country, 2026-10-13).
FOTMOB_LEAGUE = {
    "Premier League": 47, "Championship": 48, "League One": 108, "League Two": 109,
    "National League": 117, "La Liga": 87, "La Liga 2": 140, "Serie A": 55, "Serie B": 86,
    "Bundesliga": 54, "2. Bundesliga": 146, "Ligue 1": 53, "Ligue 2": 110, "Eredivisie": 57,
    "Primeira Liga": 61, "Scottish Premiership": 64, "Belgian Pro League": 40,
    "Turkish Super Lig": 71, "Greek Super League": 135, "Austrian Bundesliga": 38,
    "Swiss Super League": 69, "Danish Superliga": 46, "Ekstraklasa": 196, "Eliteserien": 59,
    "Allsvenskan": 67, "HNL": 252, "Champions League": 42, "Europa League": 73,
    "Conference League": 10216,
}

# Continental competitions: a team's stats are its domestic league's, so its
# style is set against its own league (collected first, below), not Europe.
EUROPEAN = {"Champions League", "Europa League", "Conference League"}

# FotMob team-stat header -> our key. "_pm" = already per match.
STAT_KEYS = {
    "Goals per match": "goals_pm", "Goals conceded per match": "conceded_pm",
    "Expected goals": "xg", "xG conceded": "xga", "Average possession": "possession",
    "Shots on target per match": "sot_pm", "Big chances": "big_chances",
    "Big chances missed": "big_missed", "Touches in opposition box": "box_touches",
    "Tackles per match": "tackles_pm", "Interceptions per match": "interceptions_pm",
    "Possession won final 3rd per match": "high_turnovers_pm", "Clearances per match": "clearances_pm",
    "Saves per match": "saves_pm", "Clean sheets": "clean_sheets", "Set piece goals": "setpiece_goals",
    "Set piece goals conceded": "setpiece_conceded", "Distance per match": "distance_pm",
    "Accurate passes per match": "passes_pm", "Accurate long balls per match": "long_balls_pm",
    "Accurate crosses per match": "crosses_pm", "Corners": "corners", "Fouls per match": "fouls_pm",
    "Yellow cards": "yellow", "Red cards": "red", "FotMob rating": "rating",
}


def _num(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def league_teams(lid: int) -> list[dict]:
    """[{id, name, played}] from a FotMob league table (every group / phase)."""
    data = fm._get(_LEAGUE.format(lid=lid))
    out: dict[int, dict] = {}
    for block in data.get("table") or []:
        d = block.get("data") or {}
        tables = [d.get("table")] if d.get("table") else [t.get("table") for t in d.get("tables") or []]
        for tbl in tables:
            for row in (tbl or {}).get("all") or []:
                out[row["id"]] = {"id": row["id"], "name": row["name"], "played": row.get("played")}
    return list(out.values())


def parse_team(t: dict, fallback_played: int | None) -> dict:
    """One team page -> profile (squad, coach, formation, stats with league rank)."""
    ov = t.get("overview") or {}
    lineup = ov.get("lastLineupStats") or {}
    squad, coach = [], None
    for grp in (t.get("squad") or {}).get("squad") or []:
        for m in grp.get("members") or []:
            if grp.get("title") == "coach":
                coach = m.get("name")
                continue
            squad.append({"name": m.get("name"), "pos": m.get("positionIdsDesc") or grp.get("title"),
                          "age": m.get("age"), "value": m.get("transferValue"), "rating": m.get("rating"),
                          "goals": m.get("goals"), "assists": m.get("assists"),
                          "injured": bool(m.get("injury"))})
    stats = {}
    for x in (t.get("stats") or {}).get("teams") or []:
        key = STAT_KEYS.get(x.get("header"))
        p = x.get("participant") or {}
        if key and _num(p.get("value")) is not None:
            stats[key] = {"value": _num(p.get("value")), "rank": p.get("rank")}
    # FotMob's season stats are the team's PRIMARY (domestic) league totals, so
    # per-match values divide by the games played there — not by the games of
    # the competition we fetched it from (a Champions League side has played
    # 2 European games but 8 league games).
    stats_league = (t.get("stats") or {}).get("primaryLeagueId")
    played = None
    for block in t.get("table") or []:
        d = block.get("data") or {}
        if stats_league is not None and d.get("leagueId") != stats_league:
            continue
        for row in (d.get("table") or {}).get("all") or []:
            if row.get("id") == (t.get("details") or {}).get("id"):
                played = row.get("played")
    played = played or fallback_played
    if played:
        for tot, pm in (("xg", "xg_pm"), ("xga", "xga_pm"), ("big_chances", "big_chances_pm"),
                        ("box_touches", "box_touches_pm")):
            if tot in stats:
                stats[pm] = {"value": round(stats[tot]["value"] / played, 3), "rank": stats[tot]["rank"]}
    form = [f.get("resultString") for f in ov.get("teamForm") or []]
    det = t.get("details") or {}
    return {"id": det.get("id"), "name": det.get("name"), "short": det.get("shortName"),
            "country": det.get("country"), "played": played, "stats_league": stats_league, "coach": coach,
            "formation": lineup.get("formation"), "form": form,
            "last_lineup": [{"name": p.get("name"), "pos_id": p.get("usualPlayingPositionId"),
                             "value": p.get("marketValue")} for p in lineup.get("starters") or []],
            "squad": squad, "stats": stats}


def style(team: dict, league_teams: list[dict]) -> dict:
    """strong / average / weak per area: where the team's own value sits among
    its league's teams (top third / middle / bottom third). Computed from the
    values, not FotMob's rank (FotMob ranks conceded stats best-first).
    Absent stat -> PENDING (HR35)."""
    def tier(key: str, high_is_good: bool = True) -> str:
        mine = (team["stats"].get(key) or {}).get("value")
        vals = [v for v in ((t.get("stats") or {}).get(key, {}).get("value") for t in league_teams) if v is not None]
        if mine is None or len(vals) < 3:
            return "PENDING"
        better = sum((v > mine) if high_is_good else (v < mine) for v in vals)
        r = better / len(vals)                      # share of the league doing better
        return "strong" if r < 1 / 3 else "weak" if r >= 2 / 3 else "average"
    return {"attack": tier("xg_pm"), "finishing": tier("goals_pm"),
            "defence": tier("xga_pm", high_is_good=False), "possession": tier("possession"),
            "press": tier("high_turnovers_pm"), "set_pieces": tier("setpiece_goals")}


def profile_read(home: dict, away: dict, gap: float | None = 0.0) -> dict:
    """What the two sides' attack and defence numbers point to for this game.
    goals_hint = each side's xG per match averaged with what the opponent
    concedes; lean = BTTS/Over when both attacks meet leaky defences, Under /
    double chance when both defences are strong. A label only.

    gap = home league's strength minus away league's in goals per match
    (data/league_strength.py): 0.0 in the same league; across leagues each
    side's hint moves by half of it, and the lean reads the adjusted hints
    alone (the strong / weak tiers are league-relative and don't compare).
    None = across leagues with a league not rated -> PENDING, never a guess."""
    def g(t: dict, key: str) -> float | None:
        s = t["stats"].get(key)
        return s["value"] if s else None
    hx, ax, hxa, axa = g(home, "xg_pm"), g(away, "xg_pm"), g(home, "xga_pm"), g(away, "xga_pm")
    if None in (hx, ax, hxa, axa):
        return {"goals_hint": None, "lean": "PENDING — xG not published for one side"}
    if gap is None:
        return {"goals_hint": None, "lean": "PENDING — different leagues, one not rated for strength"}
    h_goals = max(0.15, (hx + axa) / 2 + gap / 2)
    a_goals = max(0.15, (ax + hxa) / 2 - gap / 2)
    if gap:
        if min(h_goals, a_goals) >= 1.25:
            lean = "BTTS yes / Over 2.5 — both expected to score"
        elif h_goals + a_goals <= 2.3:
            lean = "Under / double chance — goals look scarce"
        elif min(h_goals, a_goals) < 0.8:
            lean = "one side unlikely to score — BTTS no / win to nil"
        else:
            lean = "no clear lean"
        return {"home_goals_hint": round(h_goals, 2), "away_goals_hint": round(a_goals, 2),
                "total_hint": round(h_goals + a_goals, 2), "lean": lean, "league_gap": gap}
    hs, as_ = home.get("style", {}), away.get("style", {})
    leaky = [s for s in (hs, as_) if s.get("defence") == "weak"]
    sharp = [s for s in (hs, as_) if s.get("attack") == "strong"]
    solid = [s for s in (hs, as_) if s.get("defence") == "strong"]
    if min(h_goals, a_goals) >= 1.1 and (leaky or len(sharp) == 2):
        lean = "BTTS yes / Over 2.5 — both expected to score"
    elif h_goals + a_goals <= 2.3 and len(solid) >= 1:
        lean = "Under / double chance — goals look scarce"
    elif min(h_goals, a_goals) < 0.8:
        lean = "one side unlikely to score — BTTS no / win to nil"
    else:
        lean = "no clear lean"
    return {"home_goals_hint": round(h_goals, 2), "away_goals_hint": round(a_goals, 2),
            "total_hint": round(h_goals + a_goals, 2), "lean": lean}


def collect(leagues: list[str] | None = None, pause: float = 0.35) -> dict:
    """Fetch every team of the given (default: all covered) competitions and
    write data/teams/latest.json.gz plus a dated snapshot."""
    now = datetime.now(UTC)
    out: dict = {"fetched_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "source": "fotmob.com", "leagues": {}}
    for league in leagues or list(FOTMOB_LEAGUE):
        lid = FOTMOB_LEAGUE[league]
        try:
            teams = league_teams(lid)
        except Exception as e:  # noqa: BLE001 — one league failing never stops the rest
            out["leagues"][league] = {"error": str(e)[:120]}
            continue
        rows = []
        for t in teams:
            try:
                prof = parse_team(fm._get(_TEAM.format(tid=t["id"])), t.get("played"))
            except Exception as e:  # noqa: BLE001
                prof = {"id": t["id"], "name": t["name"], "error": str(e)[:120], "stats": {}}
            rows.append(prof)
            time.sleep(pause)
        for prof in rows:
            if "error" not in prof:
                prof["style"] = style(prof, [r for r in rows if r.get("stats_league") == prof.get("stats_league")]
                                      if league in EUROPEAN else rows)
        if league in EUROPEAN:          # tiers from the domestic league already collected
            domestic = {lb.get("fotmob_id"): lb.get("teams") or [] for lb in out["leagues"].values()}
            for prof in rows:
                peers = domestic.get(prof.get("stats_league"))
                if peers and "error" not in prof:
                    prof["style"] = style(prof, peers)
        out["leagues"][league] = {"fotmob_id": lid, "teams": rows}
        print(f"{league}: {len(rows)} teams", flush=True)
    TEAMS_DIR.mkdir(parents=True, exist_ok=True)
    blob = gzip.compress(json.dumps(out, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    (TEAMS_DIR / "latest.json.gz").write_bytes(blob)
    (TEAMS_DIR / f"profiles_{now.strftime('%Y-%m-%d')}.json.gz").write_bytes(blob)   # dated snapshot
    return out


def load(path: Path = TEAMS_DIR / "latest.json.gz") -> dict:
    return json.loads(gzip.decompress(path.read_bytes())) if path.exists() else {"leagues": {}}


def find(db: dict, name: str, league: str | None = None) -> dict | None:
    """A team by name, with the strict two-name rule the graders use."""
    from data import flashscore_results as fr
    best, score = None, 0.0
    for lg, block in db.get("leagues", {}).items():
        if league and lg != league:
            continue
        for t in block.get("teams") or []:
            s = max(fr._sim(name, t.get("name") or ""), fr._sim(name, t.get("short") or ""))
            if s > score:
                best, score = t, s
    return best if score >= fr.MATCH_MIN else None


if __name__ == "__main__":
    collect(sys.argv[1:] or None)


# ── every game, covered or not (Architect 2026-10-13: "this should be applied
# to the learning too ... teams that we're not involved in ... you need to
# understand how they operate too before you do the paper bet on them") ────
#
# The universe sweep (monitor/universe_sweep.py) reads every SportyBet game.
# Before kick-off each football game gets both teams' profiles — FotMob team
# pages, cached for a week in data/teams/team_cache.json.gz — and the fixture
# profile read, stored on the game's row. The row is archived with its
# result, so every graded game carries the profile as it stood BEFORE the
# match: the walk-forward evidence the paper book (engine/paper_book.py, P
# rules) and backtest/profile_study.py learn from. Style tiers are set against
# the other cached teams of the same domestic league.

TEAM_CACHE = TEAMS_DIR / "team_cache.json.gz"
CACHE_DAYS = 7
COMPACT = ("goals_pm", "conceded_pm", "xg_pm", "xga_pm", "possession", "sot_pm", "big_chances_pm",
           "box_touches_pm", "high_turnovers_pm", "tackles_pm", "interceptions_pm", "clearances_pm",
           "clean_sheets", "setpiece_goals", "saves_pm")


def compact(prof: dict) -> dict:
    """The few numbers a game row keeps for one team (squad left in the cache)."""
    return {"id": prof.get("id"), "name": prof.get("name"), "league": prof.get("stats_league"),
            "played": prof.get("played"), "coach": prof.get("coach"), "formation": prof.get("formation"),
            "form": (prof.get("form") or [])[-5:],
            "injured": sum(1 for p in prof.get("squad") or [] if p.get("injured")),
            "stats": {k: v["value"] for k, v in (prof.get("stats") or {}).items() if k in COMPACT}}


class TeamCache:
    """FotMob team pages by team id, kept CACHE_DAYS days; at most `budget`
    pages fetched per run (the sweep must finish well inside its job)."""

    def __init__(self, path: Path = TEAM_CACHE, budget: int = 250, pause: float = 0.3):
        self.path, self.budget, self.pause, self.fetched = path, budget, pause, 0
        self.data: dict = json.loads(gzip.decompress(path.read_bytes())) if path.exists() else {}

    def get(self, team_id, now: datetime) -> dict | None:
        key = str(team_id)
        hit = self.data.get(key)
        fresh = hit and (now - datetime.fromisoformat(hit["at"])).days < CACHE_DAYS
        if fresh or self.fetched >= self.budget:
            return hit["profile"] if hit else None
        try:
            prof = compact(parse_team(fm._get(_TEAM.format(tid=team_id)), None))
        except Exception:  # noqa: BLE001 — FotMob down: keep what we have
            return hit["profile"] if hit else None
        self.fetched += 1
        time.sleep(self.pause)
        self.data[key] = {"at": now.isoformat(), "profile": prof}
        return prof

    def peers(self, league_id) -> list[dict]:
        return [{"stats": {k: {"value": v} for k, v in h["profile"]["stats"].items()}}
                for h in self.data.values() if h["profile"].get("league") == league_id]

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_bytes(gzip.compress(json.dumps(self.data, separators=(",", ":"),
                                                       ensure_ascii=False).encode("utf-8")))


def game_profile(cache: TeamCache, home_id, away_id, now: datetime,
                 strength: dict | None = None) -> dict | None:
    """Both teams' compact profiles, their style against their own league, and
    the fixture profile read. None when either team can't be profiled."""
    h, a = cache.get(home_id, now), cache.get(away_id, now)
    if not h or not a:
        return None
    sides = []
    for t in (h, a):
        full = {"stats": {k: {"value": v} for k, v in t["stats"].items()}}
        peers = cache.peers(t.get("league"))
        full["style"] = style(full, peers) if len(peers) >= 6 else {}
        sides.append((t, full))
    return {"home": {**h, "style": sides[0][1]["style"]}, "away": {**a, "style": sides[1][1]["style"]},
            "read": profile_read(sides[0][1], sides[1][1], ls.gap(strength or {}, h.get("league"), a.get("league"))),
            "at": now.strftime("%Y-%m-%dT%H:%MZ")}


_NORDIC = str.maketrans({"ø": "oe", "Ø": "Oe", "å": "aa", "Å": "Aa", "æ": "ae", "Æ": "Ae"})
_YOUTH = ("u17", "u18", "u19", "u20", "u21", "u23", "youth", "reserve", "primavera", "junior")
_WOMEN = ("women", "femin", "frauen", "wsl", "liga f")


def _sim2(a: str, b: str) -> float:
    """Name similarity that also reads Nordic letters both ways
    ("Strømmen" = "Stroemmen", "Åsane" = "Aasane")."""
    return max(fr_sim(a, b), fr_sim(a, b.translate(_NORDIC)), fr_sim(a.translate(_NORDIC), b))


def fr_sim(a: str, b: str) -> float:
    from data import flashscore_results as fr
    return fr._sim(a, b)


def _kind(text: str) -> str:
    t = f" {(text or '').lower()} "
    if any(k in t for k in _WOMEN) or t.rstrip().endswith(" w"):
        return "women"
    if any(k in t for k in _YOUTH):
        return "youth"
    return "men"


def match_game(fixtures: list[dict], r: dict) -> dict | None:
    """The FotMob fixture of a SportyBet game, for its profile. Stricter in
    one way than grading's matcher (same kick-off within 30 min, same men's /
    youth / women's kind) and so it can accept one more case: one team's name
    exact, the only such fixture at that kick-off ("Man City v PSG" =
    "Manchester City v Paris Saint-Germain"). Never a guess between two."""
    from data import flashscore_results as fr
    ko = datetime.fromisoformat(r["ko"].replace("Z", "+00:00"))
    kind = _kind(f"{r.get('comp', '')} {r['home']} {r['away']}")
    cands = []
    for m in fixtures:
        k = m.get("kickoff_utc") or ""
        try:
            if abs((datetime.fromisoformat(k.replace("Z", "+00:00")) - ko).total_seconds()) > 1800:
                continue
        except ValueError:
            continue
        if _kind(f"{m.get('league', '')} {m['home']} {m['away']}") != kind:
            continue
        cands.append((_sim2(r["home"], m["home"]), _sim2(r["away"], m["away"]), m))
    both = sorted(cands, key=lambda c: -min(c[0], c[1]))
    if both and min(both[0][:2]) >= fr.MATCH_MIN and (len(both) < 2 or min(both[1][:2]) < min(both[0][:2]) - 0.02):
        return both[0][2]
    one = [c for c in cands if max(c[0], c[1]) >= 0.95 and min(c[0], c[1]) >= 0.2]
    return one[0][2] if len(one) == 1 else None


def attach(pending: dict, now: datetime, cache: TeamCache | None = None,
           horizon_h: int = 36) -> str:
    """Give every pending football game kicking off within horizon_h hours a
    pre-match profile (row["profile"]); soonest games first. Best effort: a
    game FotMob can't match unambiguously gets none (never a guess)."""
    cache = cache or TeamCache()
    strength = ls.load()
    games = sorted((r for r in pending.values() if r.get("sport") == "football" and "profile" not in r
                    and 0 <= (datetime.fromisoformat(r["ko"].replace("Z", "+00:00")) - now).total_seconds()
                    <= horizon_h * 3600), key=lambda r: r["ko"])
    by_day: dict[str, list] = {}
    done = unmatched = 0
    for r in games:
        day = r["ko"][:10]
        if day not in by_day:
            try:
                by_day[day] = fm.matches_on(day)
            except Exception:  # noqa: BLE001
                by_day[day] = []
        m = match_game(by_day[day], r)
        if not m or not m.get("home_id") or not m.get("away_id"):
            unmatched += 1
            continue
        prof = game_profile(cache, m["home_id"], m["away_id"], now, strength)
        if prof:
            r["profile"] = prof
            done += 1                    # over budget, get() serves only cached teams
    cache.save()
    return f"profiles: {done} games profiled, {unmatched} not matched on FotMob, {cache.fetched} team pages fetched"
