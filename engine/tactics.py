"""
TACTICAL PROFILES + MATCHUP READ (Architect 2026-10-26: "understand the
formation, understand how each tactics interacts with each other ... we should
be able to now tell that this team can be able to do this thing ... with that
team, and this other team can be able to protect themselves ... the maths and
the tactical profile and everything needs to correlate").

Three parts, all built from data/match_study (one FotMob row per match, every
match of the covered competitions, bet on or not):

1. PROFILE — per team, rebuilt after every match it plays, from the matches
   BEFORE a given moment only (`as_of`), so the same code is the walk-forward
   test: formations, PPDA proxy (pressing), opponents caught offside (the
   defensive-line proxy), possession and field tilt, xG for / against by
   situation (open play, counter, set piece, penalty, headers = the cross /
   aerial proxy), home and away xG splits, game state (xG for / against per 90
   while level, leading, trailing), corners, BTTS rate, the last-5 trend, and
   style labels set against the team's own league.

2. MATCHUP — expected goals of each side = league rate x the side's attack x
   the opponent's defence (each shrunk toward the league, home/away aware,
   moved by the cross-league strength gap), then the proven tactical lessons
   (counter side v high line, set-piece threat v set-piece weakness, aerial
   threat, press v build-up ...). From the two rates: a scoreline grid, so the
   read prices ANY market the board scores (BTTS, Over/Under lines, team
   goals ...), and expected corners as a note. The read is stated in a line
   ("both high lines + elite attacks -> BTTS & goals") with numbers.

3. ADJUSTMENT — the board's chance for an outcome moves toward the matchup's
   chance by WEIGHT (fitted on matches the fit had not seen; 0 = label only),
   capped at +/-CAP pts. When a market from another family fits the matchup
   better than the pick (in band, >= 50%, priced above the matchup's fair
   odds), the board is told so ("MATCHUP: BTTS Yes fits better ...").

Lessons (memory/tactics_lessons.json) change the rates only once PROVEN on
matches they had not seen (engine/tactics_study.py). Missing data -> no read
(None), never a guess (HR35).
"""
from __future__ import annotations

import json
import math
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import numpy as np

ROOT = Path(__file__).parent.parent
PROFILES = ROOT / "data" / "tactics" / "profiles.json"
LESSONS = ROOT / "memory" / "tactics_lessons.json"
CALIB = ROOT / "data" / "tactics" / "calibration.json"

EUROPEAN_IDS = {42, 73, 10216}          # UCL, UEL, UECL (FotMob ids)
HALF_LIFE_DAYS = 60.0                   # recent matches count more (a season is short)
PRIOR_MATCHES = 4.0                     # shrink toward the league until a team has data
MIN_MATCHES = 3                         # fewer -> no profile (PENDING)
CAP = 0.05                              # largest move of a board chance, +/- 5 pts
# BTTS, match total goals, home / away team goals (SportyBet market ids)
GOALS_MARKETS = ("SB:29|", "SB:18|", "SB:19|", "SB:20|")
SITUATIONS = ("open", "counter", "set_piece", "penalty", "header")


def _ts(ko: str) -> datetime:
    return datetime.fromisoformat((ko or "1970-01-01T00:00")[:16])


def _sides(row: dict):
    """(team side, opponent side, venue) twice per match."""
    yield row["home"], row["away"], "home"
    yield row["away"], row["home"], "away"


def league_rates(rows: list[dict]) -> dict:
    """Per competition: average xG of the home and of the away side, goals,
    and the league's average of each style stat (for the labels)."""
    acc: dict = {}
    for r in rows:
        lid = r.get("league_id")
        h, a = r["home"], r["away"]
        if h.get("xg") is None or a.get("xg") is None:
            continue
        d = acc.setdefault(lid, {"n": 0, "hxg": 0.0, "axg": 0.0, "goals": 0.0, "corners": 0.0, "nc": 0})
        d["n"] += 1
        d["hxg"] += h["xg"]
        d["axg"] += a["xg"]
        d["goals"] += (h.get("goals") or 0) + (a.get("goals") or 0)
        if h.get("corners") is not None and a.get("corners") is not None:
            d["corners"] += h["corners"] + a["corners"]
            d["nc"] += 1
    out = {}
    for lid, d in acc.items():
        if d["n"]:
            out[lid] = {"n": d["n"], "home_xg": d["hxg"] / d["n"], "away_xg": d["axg"] / d["n"],
                        "goals": d["goals"] / d["n"], "corners": (d["corners"] / d["nc"]) if d["nc"] else None}
    return out


def _wmean(pairs: list[tuple[float, float]]) -> Optional[float]:
    num = sum(w * v for w, v in pairs if v is not None)
    den = sum(w for w, v in pairs if v is not None)
    return num / den if den > 0 else None


def build_profiles(rows: list[dict], as_of: Optional[datetime] = None) -> dict:
    """Every team's tactical profile from the matches that kicked off before
    `as_of` (default: all). Keyed by FotMob team id (str)."""
    rows = [r for r in rows if as_of is None or _ts(r.get("ko", "")) < as_of]
    if not rows:
        return {"teams": {}, "leagues": {}}
    now = as_of or max(_ts(r["ko"]) for r in rows) + timedelta(hours=1)
    per: dict[str, list] = {}
    for r in rows:
        for me, opp, venue in _sides(r):
            per.setdefault(str(me.get("id")), []).append((r, me, opp, venue))
    teams = {}
    for tid, games in per.items():
        games.sort(key=lambda g: g[0]["ko"])
        if len(games) < MIN_MATCHES:
            continue
        ws = [0.5 ** ((now - _ts(g[0]["ko"])).total_seconds() / 86400 / HALF_LIFE_DAYS) for g in games]

        def wm(fn, _games=games, _ws=ws):
            return _wmean([(w, fn(g)) for w, g in zip(_ws, _games)])

        def sit(side_key, kind):
            def f(g):
                st = g[1 if side_key == "for" else 2].get("shot_types")
                return st["xg"].get(kind) if st else None
            return wm(f)

        def state_rate(state, which):
            num = sum(w * g[1]["state"][state][which] for w, g in zip(ws, games) if g[1].get("state"))
            mins = sum(w * g[1]["state"][state]["min"] for w, g in zip(ws, games) if g[1].get("state"))
            return (round(num / mins * 90, 3), round(mins / sum(ws), 1)) if mins >= 30 else (None, round(mins / sum(ws), 1))

        domestic = Counter(g[0].get("league_id") for g in games if g[0].get("league_id") not in EUROPEAN_IDS)
        venue = {}
        for v in ("home", "away"):
            vg = [(w, g) for w, g in zip(ws, games) if g[3] == v]
            venue[v] = {"n": len(vg), "xg_for": _wmean([(w, g[1].get("xg")) for w, g in vg]),
                        "xg_against": _wmean([(w, g[2].get("xg")) for w, g in vg])}
        last5 = games[-5:]
        forms = Counter(g[1].get("formation") for g in games[-8:] if g[1].get("formation"))
        p = {
            "id": tid, "name": games[-1][1].get("name"), "n": len(games),
            "league_id": (domestic.most_common(1)[0][0] if domestic else games[-1][0].get("league_id")),
            "coach": games[-1][1].get("coach"), "last_ko": games[-1][0]["ko"],
            "formations": [f"{f} x{c}" for f, c in forms.most_common(2)],
            "xg_for": wm(lambda g: g[1].get("xg")), "xg_against": wm(lambda g: g[2].get("xg")),
            "goals_for": wm(lambda g: g[1].get("goals")), "goals_against": wm(lambda g: g[2].get("goals")),
            "for_by": {k: sit("for", k) for k in SITUATIONS}, "against_by": {k: sit("against", k) for k in SITUATIONS},
            "possession": wm(lambda g: g[1].get("possession")), "field_tilt": wm(lambda g: g[1].get("field_tilt")),
            "ppda_proxy": wm(lambda g: g[1].get("ppda_proxy")), "line_proxy": wm(lambda g: g[1].get("opp_offsides")),
            "crosses": wm(lambda g: g[1].get("crosses")), "long_balls": wm(lambda g: g[1].get("long_balls")),
            "big_chances": wm(lambda g: g[1].get("big_chances")),
            "corners_for": wm(lambda g: g[1].get("corners")), "corners_against": wm(lambda g: g[2].get("corners")),
            "btts_rate": wm(lambda g: float((g[1].get("goals") or 0) > 0 and (g[2].get("goals") or 0) > 0)),
            "state": {s: dict(zip(("xg_for_p90", "min_pm"), state_rate(s, "xg_for")),
                              xg_against_p90=state_rate(s, "xg_against")[0]) for s in ("level", "leading", "trailing")},
            "venue": venue,
            "trend": {"xg_for_last5": _wmean([(1.0, g[1].get("xg")) for g in last5]),
                      "xg_against_last5": _wmean([(1.0, g[2].get("xg")) for g in last5])},
            "reds_last5": sum(len(g[1].get("reds") or []) for g in last5),
        }
        teams[tid] = p
    leagues = league_rates(rows)
    _label(teams)
    return {"teams": teams, "leagues": {str(k): v for k, v in leagues.items()}, "as_of": now.isoformat()[:16]}


def _tier(value, peers: list[float], high: str, low: str, mid: str = "average") -> str:
    vals = [v for v in peers if v is not None]
    if value is None or len(vals) < 6:
        return "PENDING"
    r = sum(v > value for v in vals) / len(vals)        # share of the league above
    return high if r < 1 / 3 else low if r >= 2 / 3 else mid


def _share(p: dict, key: str) -> Optional[float]:
    tot = p.get("xg_for")
    v = (p.get("for_by") or {}).get(key)
    return v / tot if v is not None and tot else None


def _share_against(p: dict, key: str) -> Optional[float]:
    tot = p.get("xg_against")
    v = (p.get("against_by") or {}).get(key)
    return v / tot if v is not None and tot else None


def _label(teams: dict) -> None:
    """Style labels against the team's own league (top / bottom third)."""
    by_league: dict = {}
    for t in teams.values():
        by_league.setdefault(t["league_id"], []).append(t)
    for peers in by_league.values():
        def col(fn, _peers=peers):
            return [fn(x) for x in _peers]
        for t in peers:
            t["style"] = {
                "attack": _tier(t["xg_for"], col(lambda x: x["xg_for"]), "elite", "blunt"),
                "defence": _tier(-(t["xg_against"] or 0) if t["xg_against"] is not None else None,
                                 col(lambda x: -(x["xg_against"] or 0) if x["xg_against"] is not None else None),
                                 "tight", "leaky"),
                "possession": _tier(t["possession"], col(lambda x: x["possession"]), "dominant", "low block"),
                # low PPDA = more pressing: rank the negative
                "press": _tier(-t["ppda_proxy"] if t["ppda_proxy"] is not None else None,
                               col(lambda x: -x["ppda_proxy"] if x["ppda_proxy"] is not None else None),
                               "high press", "passive"),
                "line": _tier(t["line_proxy"], col(lambda x: x["line_proxy"]), "high line", "deep line"),
                "counter": _tier(_share(t, "counter"), col(lambda x: _share(x, "counter")), "counter threat", "rarely counters"),
                "set_piece_threat": _tier((t["for_by"] or {}).get("set_piece"),
                                          col(lambda x: (x["for_by"] or {}).get("set_piece")), "strong", "weak"),
                "set_piece_defence": _tier(-(t["against_by"] or {}).get("set_piece", 0)
                                           if (t["against_by"] or {}).get("set_piece") is not None else None,
                                           col(lambda x: -(x["against_by"] or {}).get("set_piece", 0)
                                               if (x["against_by"] or {}).get("set_piece") is not None else None),
                                           "solid", "vulnerable"),
                "aerial": _tier((t["for_by"] or {}).get("header"), col(lambda x: (x["for_by"] or {}).get("header")),
                                "aerial threat", "rarely heads"),
                "counter_exposure": _tier(_share_against(t, "counter"), col(lambda x: _share_against(x, "counter")),
                                          "exposed to counters", "protected"),
            }


# ── matchup ──────────────────────────────────────────────────────────────


def _ratio(team_v, league_v, n) -> float:
    """Team value over the league's, shrunk toward 1 by PRIOR_MATCHES."""
    if team_v is None or not league_v:
        return 1.0
    return (team_v / league_v * n + PRIOR_MATCHES) / (n + PRIOR_MATCHES)


def _tags(att: dict, dfn: dict) -> list[str]:
    """The tactical situations of one attack meeting one defence."""
    a, d = att.get("style", {}), dfn.get("style", {})
    tags = []
    if a.get("counter") == "counter threat" and (d.get("line") == "high line" or d.get("possession") == "dominant"):
        tags.append("counter side v high line")
    if a.get("set_piece_threat") == "strong" and d.get("set_piece_defence") == "vulnerable":
        tags.append("set-piece threat v weak set-piece defence")
    if a.get("aerial") == "aerial threat" and d.get("set_piece_defence") == "vulnerable":
        tags.append("aerial threat v weak in the air")
    if a.get("press") == "high press" and d.get("possession") == "dominant":
        tags.append("high press v build-up side")
    if a.get("possession") == "dominant" and d.get("possession") == "low block":
        tags.append("possession side v low block")
    if a.get("attack") == "elite" and d.get("defence") == "leaky":
        tags.append("elite attack v leaky defence")
    if a.get("attack") == "blunt" and d.get("defence") == "tight":
        tags.append("blunt attack v tight defence")
    if d.get("counter_exposure") == "exposed to counters" and a.get("counter") == "counter threat":
        tags.append("counter side v counter-exposed")
    return tags


def load_lessons(path: Path = LESSONS) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"lessons": {}}


def proven_effects(lessons: Optional[dict] = None) -> dict[str, float]:
    """tag -> xG per match added to the attacking side, for PROVEN lessons only."""
    lessons = load_lessons() if lessons is None else lessons
    return {tag: float(x["effect"]) for tag, x in (lessons.get("lessons") or {}).items()
            if x.get("status") == "proven"}


def rates(home: dict, away: dict, leagues: dict, gap: Optional[float] = 0.0,
          effects: Optional[dict] = None) -> Optional[dict]:
    """Expected goals of each side (xG scale) + the tactical tags in play."""
    lg_h = leagues.get(str(home.get("league_id"))) or {}
    lg_a = leagues.get(str(away.get("league_id"))) or {}
    if not lg_h or not lg_a or gap is None:
        return None
    base_h = lg_h["home_xg"]
    base_a = (lg_h["away_xg"] if home.get("league_id") == away.get("league_id")
              else (lg_h["away_xg"] + lg_a["away_xg"]) / 2)
    team_avg_h = (lg_h["home_xg"] + lg_h["away_xg"]) / 2
    team_avg_a = (lg_a["home_xg"] + lg_a["away_xg"]) / 2

    def venue_val(p, venue, key, overall):
        v = (p.get("venue") or {}).get(venue) or {}
        if v.get(key) is None or not v.get("n"):
            return overall
        k = v["n"] / (v["n"] + 3.0)                   # venue split shrunk to the overall figure
        return k * v[key] + (1 - k) * overall
    h_att = _ratio(venue_val(home, "home", "xg_for", home["xg_for"]), team_avg_h, home["n"])
    a_def = _ratio(venue_val(away, "away", "xg_against", away["xg_against"]), team_avg_a, away["n"])
    a_att = _ratio(venue_val(away, "away", "xg_for", away["xg_for"]), team_avg_a, away["n"])
    h_def = _ratio(venue_val(home, "home", "xg_against", home["xg_against"]), team_avg_h, home["n"])
    lam_h = base_h * h_att * a_def + gap / 2
    lam_a = base_a * a_att * h_def - gap / 2
    effects = proven_effects() if effects is None else effects
    tags_h, tags_a = _tags(home, away), _tags(away, home)
    adj_h = sum(effects.get(t, 0.0) for t in tags_h)
    adj_a = sum(effects.get(t, 0.0) for t in tags_a)
    lam_h, lam_a = max(0.15, lam_h + adj_h), max(0.15, lam_a + adj_a)
    return {"home": round(lam_h, 3), "away": round(lam_a, 3), "tags_home": tags_h, "tags_away": tags_a,
            "lesson_adj": [round(adj_h, 3), round(adj_a, 3)]}


def grid(lam_h: float, lam_a: float, n: int = 11) -> np.ndarray:
    """Independent Poisson scoreline grid (rows home goals, cols away)."""
    ph = np.array([math.exp(-lam_h) * lam_h ** k / math.factorial(k) for k in range(n)])
    pa = np.array([math.exp(-lam_a) * lam_a ** k / math.factorial(k) for k in range(n)])
    m = np.outer(ph, pa)
    return m / m.sum()


def headline(m: np.ndarray) -> dict:
    """The goals markets the read states up front."""
    h, a = np.indices(m.shape)
    tot = h + a

    def p(mask):
        return round(float(m[mask].sum()), 3)
    return {"btts": p((h > 0) & (a > 0)), "over15": p(tot >= 2), "over25": p(tot >= 3), "over35": p(tot >= 4),
            "home": p(h > a), "draw": p(h == a), "away": p(h < a),
            "home_scores": p(h > 0), "away_scores": p(a > 0)}


def _say(home: dict, away: dict, r: dict, hl: dict) -> str:
    """The stated expectation, in one line."""
    hs, as_ = home.get("style", {}), away.get("style", {})
    bits = []
    lines = [s for s in (hs, as_) if s.get("line") == "high line"]
    elite = [s for s in (hs, as_) if s.get("attack") == "elite"]
    if len(lines) == 2 and elite:
        bits.append("both high lines + an elite attack")
    for tag in r["tags_home"]:
        bits.append(f"{home['name']}: {tag}")
    for tag in r["tags_away"]:
        bits.append(f"{away['name']}: {tag}")
    if hl["btts"] >= 0.58 and hl["over25"] >= 0.58:
        lean = "BTTS & goals"
    elif hl["btts"] >= 0.58:
        lean = "BTTS"
    elif hl["over25"] <= 0.42 and hl["btts"] <= 0.45:
        lean = "unders / one side blank"
    elif min(hl["home_scores"], hl["away_scores"]) <= 0.55:
        side = home["name"] if hl["home_scores"] < hl["away_scores"] else away["name"]
        lean = f"{side} may not score"
    else:
        lean = "no strong goals lean"
    return f"{'; '.join(bits) or 'no tactical clash flagged'} -> {lean}"


def read(home: dict, away: dict, db: dict, gap: Optional[float] = 0.0,
         effects: Optional[dict] = None) -> Optional[dict]:
    """The full matchup read of two profiles, or None (no guess)."""
    r = rates(home, away, db.get("leagues") or {}, gap, effects)
    if r is None:
        return None
    m = grid(r["home"], r["away"])
    hl = headline(m)
    corners = None
    if None not in (home.get("corners_for"), away.get("corners_against"), away.get("corners_for"),
                    home.get("corners_against")):
        corners = round((home["corners_for"] + away["corners_against"]) / 2
                        + (away["corners_for"] + home["corners_against"]) / 2, 1)
    return {"home": home["name"], "away": away["name"], "xg_home": r["home"], "xg_away": r["away"],
            "tags_home": r["tags_home"], "tags_away": r["tags_away"], "lesson_adj": r["lesson_adj"],
            "probs": hl, "corners": corners, "say": _say(home, away, r, hl),
            "style_home": home.get("style"), "style_away": away.get("style"),
            "formations": [home.get("formations"), away.get("formations")]}


# ── the board's side: profiles on disk, a fixture by names ────────────────


def save(db: dict, path: Path = PROFILES) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(db, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")


def load(path: Path = PROFILES) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"teams": {}, "leagues": {}}


def find(db: dict, name: str) -> Optional[dict]:
    """A team by name with the graders' strict rule; None when unsure."""
    from data import flashscore_results as fr
    best, score, second = None, 0.0, 0.0
    for t in (db.get("teams") or {}).values():
        s = fr._sim(name, t.get("name") or "")
        if s > score:
            best, score, second = t, s, score
        elif s > second:
            second = s
    if score < fr.MATCH_MIN or (score < 0.99 and second >= score - 0.02):
        return None
    return best


def fixture(home: str, away: str, db: Optional[dict] = None, strength: Optional[dict] = None,
            effects: Optional[dict] = None) -> Optional[dict]:
    """Matchup read of a board fixture by team names (None when unsure)."""
    db = load() if db is None else db
    th, ta = find(db, home), find(db, away)
    if not th or not ta or th is ta:
        return None
    if strength is None:
        from data import league_strength as ls
        strength = ls.load()
    from data import league_strength as ls
    return read(th, ta, db, ls.gap(strength or {}, th.get("league_id"), ta.get("league_id")), effects)


def calibration(path: Path = CALIB) -> dict:
    """{"weight": w, ...} fitted by engine/tactics_study.py on unseen matches; 0 when absent."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"weight": 0.0}


def adjustment(board_p: float, tactical_p: Optional[float], weight: float, cap: float = CAP) -> float:
    """The move of a board chance toward the matchup's, sized by the fitted
    weight and capped: weight x (tactical - board), within +/- cap."""
    if tactical_p is None or weight <= 0:
        return 0.0
    return round(max(-cap, min(cap, weight * (tactical_p - board_p))), 4)


def better_market(pick_key: str, pick_win: float, cands: list, tac_grid: np.ndarray, rules: dict,
                  family) -> Optional[str]:
    """When a GOALS outcome (BTTS, match goals, team goals — the markets a
    tactical clash speaks to) of another family fits the matchup better than
    the pick: matchup chance >= 55%, priced >= 5% above the matchup's fair
    odds, and rated by the matchup within 5 pts of the board's pick. Returns
    the note, or None."""
    from engine import full_markets as fmk
    best = None
    for c in cands:
        k, price = c[2], c[5].price
        if (k == pick_key or family(k) == family(pick_key) or k not in rules
                or not k.startswith(GOALS_MARKETS)):
            continue
        p = fmk.evaluate(tac_grid, rules[k])[0]
        if p < 0.55 or p * price < 1.05 or p < pick_win - 0.05:
            continue
        if best is None or p * price > best[1] * best[2]:
            best = (k, p, price)
    if best is None:
        return None
    k, p, price = best
    return f"{label(k)} fits the matchup better: matchup {p:.0%} @ {price:.2f} (value {p * price - 1:+.0%})"


def label(k: str, home: str = "Home", away: str = "Away") -> str:
    try:
        from engine import full_markets as fmk
        return fmk.display_key(k, home, away)
    except Exception:  # noqa: BLE001 — a label never breaks the board
        return k
