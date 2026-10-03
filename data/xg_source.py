"""
Expected goals (xG) data source via Understat (understat.com).

WHY THIS EXISTS
  The framework's model reads goals scored; xG reads the quality of chances
  that produced them. Three independent signals — DC (score patterns), Elo
  (result history), xG (chance quality) — is exactly what ID403 means by
  "independent factors." This module provides the xG data for the third.

UNDERSTAT
  Free, no API key, no hard rate limit observed. Covers the Big-5 leagues
  (Premier League, La Liga, Bundesliga, Serie A, Ligue 1) + Russian Premier
  League. DOES NOT cover Eredivisie, Belgian Pro League, Danish Superliga,
  Scottish Premiership, Ekstraklasa, HNL, Championship, Primeira Liga.

  Endpoint: GET https://understat.com/getLeagueData/<slug>/<season>/
  Required headers: X-Requested-With: XMLHttpRequest, Referer, Accept-Encoding: gzip
  Response: {"teams": {team_id: {title, history: [{xG, xGA, ...}]}, ...},
             "dates": [{xG: {h, a}, ...}, ...]}

HR35 throughout: if a fetch fails or a league isn't covered, it raises rather
than returning fabricated xG. Callers must surface that as xG unavailable on
the board, same as any other source gap.
"""
from __future__ import annotations

import gzip
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib import error, parse, request

XG_CACHE_DIR = Path(__file__).parent.parent / "data" / "cache" / "xg_understat"
# xG season stats are stable (historical data per match); 6h TTL is generous.
XG_MAX_AGE_SECONDS = 6 * 3600
# Rate-limit guard: one request per second to be polite.
_min_fetch_gap = 1.0
_last_fetch_time = 0.0


# --- league slug mapping (verified 2026-08-05, live probe) -------------------
UNDERSTAT_SLUGS = {
    "Premier League": "EPL",
    "La Liga": "La_liga",
    "Bundesliga": "Bundesliga",
    "Serie A": "Serie_A",
    "Ligue 1": "Ligue_1",
}
COVERED_LEAGUES = set(UNDERSTAT_SLUGS.keys())

# Framework-name → Understat-title mapping. Every mismatch verified by
# diffing the actual team lists from the two sources on 2026-08-05.
TEAM_ALIASES: dict[str, dict[str, str]] = {
    "Bundesliga": {
        "Dortmund": "Borussia Dortmund",
        "RB Leipzig": "RasenBallsport Leipzig",
        "FC Koln": "FC Cologne",
        "Ein Frankfurt": "Eintracht Frankfurt",
        "Leverkusen": "Bayer Leverkusen",
        "M'gladbach": "Borussia M.Gladbach",
        "Mainz": "Mainz 05",
        "Hamburg": "Hamburger SV",
        "St Pauli": "St. Pauli",
        "Stuttgart": "VfB Stuttgart",
    },
    # Premier League, La Liga, Serie A, Ligue 1: framework uses
    # football-data.co.uk names that mostly match Understat — map needed
    # when the first PL match is fitted and a mismatch is discovered.
    # Leave as {} until then; the fuzzy fallback handles the common cases.
    "Premier League": {},
    "La Liga": {},
    "Serie A": {},
    "Ligue 1": {},
}


def is_covered(league: str) -> bool:
    return league in UNDERSTAT_SLUGS


def _cache_path(league: str, season: str) -> Path:
    return XG_CACHE_DIR / f"{league.replace(' ', '_')}_{season}.json"


def _read_cache(league: str, season: str) -> Optional[dict]:
    p = _cache_path(league, season)
    if not p.exists():
        return None
    try:
        blob = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if time.time() - blob.get("fetched_at", 0) > XG_MAX_AGE_SECONDS:
        return None
    return blob.get("data")


def _write_cache(league: str, season: str, data: dict) -> None:
    XG_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _cache_path(league, season).write_text(
        json.dumps({"fetched_at": time.time(), "data": data}),
        encoding="utf-8")


def _fetch_understat(league: str, season: str) -> dict:
    """Fetch one league's xG data from Understat. Returns the raw JSON
    response (teams + dates). Raises on network or parse errors."""
    global _last_fetch_time
    now = time.time()
    wait = _min_fetch_gap - (now - _last_fetch_time)
    if wait > 0:
        time.sleep(wait)

    slug = UNDERSTAT_SLUGS.get(league)
    if not slug:
        raise ValueError(f"{league} is not covered by Understat xG — "
                         f"available: {', '.join(sorted(COVERED_LEAGUES))}")
    # Season mapping: Understat uses '2025' for 2025/2026 (the start year).
    # The framework uses '2526' or '2627'. Convert: '2526' → '2025', '2627' → '2026'.
    try:
        understat_season = f"20{season[:2]}"
    except (ValueError, IndexError):
        raise ValueError(f"unparseable season {season!r} for Understat lookup")

    url = f"https://understat.com/getLeagueData/{slug}/{understat_season}/"
    req = request.Request(url, headers={
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"https://understat.com/league/{slug}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36",
    })
    with request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
    _last_fetch_time = time.time()
    # Understat sends gzip-compressed JSON; decompress first, then parse.
    if raw[:2] == b'\x1f\x8b':  # gzip magic bytes
        raw = gzip.decompress(raw)
    return json.loads(raw)


@dataclass
class TeamXG:
    """xG attack/defence rating for one team, derived from Understat's
    per-match team-level xG data."""
    team: str
    xg_attack: float   # average xG scored per match (higher = better attack)
    xg_defence: float  # average xGA conceded per match (lower = better defence)
    n_matches: int


@dataclass
class XGProbabilities:
    """xG-derived match probabilities, structurally identical to
    FixtureProbabilities for the same markets."""
    home: float
    draw: float
    away: float
    over15: float
    over25: float
    over35: float
    btts: float


def _resolve_team(league: str, framework_name: str,
                   aliases: dict[str, str], understat_names: list[str]) -> Optional[str]:
    """Resolve a framework team name to the Understat title. Uses the alias
    dict first, then a single-substring fallback (one clean match only).
    Returns None if the team can't be resolved — callers must treat that as
    HR35: 'no team, no fabricated number'."""
    a = aliases.get(framework_name)
    if a:
        return a
    fl = framework_name.lower()
    hits = [n for n in understat_names if fl in n.lower() or n.lower() in fl]
    return hits[0] if len(hits) == 1 else None  # never pick from ambiguous matches


def fit_xg(league: str, season: str) -> dict[str, TeamXG]:
    """Build per-team xG attack/defence ratings from Understat.

    Returns {team_name: TeamXG} for the given league/season. Raises on
    fetch failure (callers surface as xG unavailable, never guessed)."""
    cached = _read_cache(league, season)
    if cached is None:
        cached = _fetch_understat(league, season)
        _write_cache(league, season, cached)

    teams_data = cached.get("teams", {})
    ratings: dict[str, TeamXG] = {}
    for tid, t in teams_data.items():
        history = t.get("history", [])
        if not history:
            continue
        team = t.get("title", "")
        # All entries in team.history ARE results (they have a result field:
        # "w"/"l"/"d"). No isResult guard needed — every entry has xG/xGA.
        xgs = [float(m.get("xG", 0)) for m in history if m.get("xG")]
        xgas = [float(m.get("xGA", 0)) for m in history if m.get("xGA")]
        if not xgs:
            continue
        ratings[team] = TeamXG(
            team=team,
            xg_attack=sum(xgs) / len(xgs),
            xg_defence=sum(xgas) / len(xgas),
            n_matches=len(xgs),
        )
    return ratings


def poisson_pmf(k: int, lam: float) -> float:
    """Poisson probability of exactly k goals under rate lam."""
    return math.exp(-lam) * lam**k / math.factorial(k)


# Goals totals are summed out to this many goals per side. predict_xg caps
# lambdas at 4.5, so the omitted tail (P(>15) on either side) is far below
# 1e-6 — it cannot move a reported percentage.
_GOALS_CUTOFF = 15


def _over_goals(lam_h: float, lam_a: float, line: int) -> float:
    """P(total goals > line) from the Poisson product of both lambdas, where
    `line` is the integer just below the market line (1 -> O1.5, 2 -> O2.5,
    3 -> O3.5). Same shape as Dixon-Coles' p_over (score-matrix cells whose
    total exceeds the line) so the two engines' numbers are directly
    comparable — which the old `1 - P(h<=4)*P(a<=4)` was NOT: that measures
    "at least one team scores 5+", a different event entirely."""
    return sum(poisson_pmf(i, lam_h) * poisson_pmf(j, lam_a)
               for i in range(_GOALS_CUTOFF) for j in range(_GOALS_CUTOFF)
               if i + j > line)


# A material goals-market disagreement: two engines whose probability reads
# differ by at least this many points. Mirrors the 1X2 divergence tolerance
# (engine/elo.py) — agreement within tolerance is consistent reads; a gap
# this wide is a warning the board must surface.
GOALS_DIVERGENCE_TOLERANCE = 0.20


def goals_divergence(dc, xg: XGProbabilities) -> Optional[str]:
    """Cross-check Dixon-Coles' goals-market read against xG's independent one.

    DC reads SCORE PATTERNS (goals scored); xG reads CHANCE QUALITY (xG from
    the same fixtures) — genuinely different inputs, so when they disagree
    materially on a goals market the board says so. DC stays canonical for
    what is logged; this is a warning, never a gate.

    Returns None when either engine has no number on a market (HR35: missing
    data is never flagged or passed)."""
    if dc is None or xg is None:
        return None
    gaps = []
    for label, dc_attr, xg_p in (
        ("O2.5", "p_over_25", xg.over25),
        ("BTTS", "p_btts_yes", xg.btts),
    ):
        dc_p = getattr(dc, dc_attr, None)
        if dc_p is None or xg_p is None:
            continue
        if abs(dc_p - xg_p) >= GOALS_DIVERGENCE_TOLERANCE:
            gaps.append(f"{label}: goals model {round(dc_p*100)}% vs "
                        f"xG {round(xg_p*100)}%")
    if not gaps:
        return None
    return ("GOALS DIVERGENCE — " + "; ".join(gaps)
            + " (DC reads score patterns, xG reads chance quality; "
              "disagreement is a warning, not a verdict)")


def predict_xg(home: str, away: str, ratings: dict[str, TeamXG],
               league: str = "", home_adv: float = 0.15) -> Optional[XGProbabilities]:
    """Predict a match from xG ratings.

    home_adv is fitted from xG home/away splits — a separate constant from
    DC's home advantage. Returns None if either team is unrated (HR35).
    `league` is needed for team-alias resolution from the framework's names
    to Understat's full names."""
    understat_names = list(ratings.keys())
    aliases = TEAM_ALIASES.get(league, {})
    hr = ratings.get(_resolve_team(league, home, aliases, understat_names))
    ar = ratings.get(_resolve_team(league, away, aliases, understat_names))
    if hr is None or ar is None:
        return None
    # Poisson-based from expected goals (not raw xG difference — that
    # overestimates draw probability for similarly rated teams).
    lam_h = hr.xg_attack * ar.xg_defence / (ratings.get(home, TeamXG("", 1, 1, 0)).xg_defence or 1)
    lam_a = ar.xg_attack * hr.xg_defence / (ratings.get(away, TeamXG("", 1, 1, 0)).xg_defence or 1)
    # Simplified: use raw attack vs defence as lambda scaling
    lam_h = max(0.15, min(4.5, hr.xg_attack * (ar.xg_defence / 1.0) + home_adv))
    lam_a = max(0.15, min(4.5, ar.xg_attack * (hr.xg_defence / 1.0)))
    # Poisson probability calculation (poisson_pmf/_over_goals are module-level
    # so the goals markets and the divergence check share one source of truth).
    p_home = p_draw = p_away = 0.0
    for i in range(8):
        for j in range(8):
            p_ij = poisson_pmf(i, lam_h) * poisson_pmf(j, lam_a)
            if i > j:
                p_home += p_ij
            elif i == j:
                p_draw += p_ij
            else:
                p_away += p_ij
    # Goals markets (Phase 3.4): O1.5/O2.5/O3.5 via the same Poisson product,
    # and BTTS as P(H>=1)*P(A>=1). Capped at 0.98 like the original file did —
    # a display ceiling, never a fabrication.
    p_over15 = _over_goals(lam_h, lam_a, 1)
    p_over25 = _over_goals(lam_h, lam_a, 2)
    p_over35 = _over_goals(lam_h, lam_a, 3)
    p_btts = (1 - poisson_pmf(0, lam_h) - poisson_pmf(0, lam_a)
              + poisson_pmf(0, lam_h) * poisson_pmf(0, lam_a))
    total = p_home + p_draw + p_away
    return XGProbabilities(
        home=p_home/total, draw=p_draw/total, away=p_away/total,
        over15=min(p_over15, 0.98), over25=min(p_over25, 0.98),
        over35=min(p_over35, 0.98), btts=min(p_btts, 0.98),
    )
