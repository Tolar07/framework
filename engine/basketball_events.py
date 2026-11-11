"""
Basketball player events (framework #558, Event models #4). RECORD-ONLY / SHADOW.

For every NBA game: each available player's expected points, rebounds, assists and threes, with the
Over / Under chance at the line SportyBet lists (markets 921-924). It picks nothing, stakes nothing and moves
no other number. The twin of engine/player_model.py (football).

How:
- History: data/nba_lineups/player_stats.jsonl, one row per player per finished regular-season game: minutes,
  points, rebounds, assists, threes (ESPN box score, the same source as data/nba_players.py).
- Expected minutes: 0.6 x last-10 + 0.4 x season average (the engine/nba_projection.py rule); a player the injury
  list calls Out is removed, Doubtful / Questionable / Day-To-Day are weighted by their chance of playing.
- Rate per minute: the player's own, shrunk toward the league rate with SHRINK_MIN pseudo-minutes.
- **Agrees with the framework:** the points of the players are scaled so that they add up to the team's projected
  points of engine/nba_projection.py (tests/basketball_events_test.py checks the sums).
- Counts (rebounds, assists, threes) and points are spread wider than a Poisson: negative binomial with the
  variance-to-mean ratio measured by backtest/basketball_events_study.py (DISP in its report).
- Nothing is believed until that study (walk-forward, beats each player's last-10 average) lets a stat through;
  every output is labelled `shadow` until then. Missing data reads PENDING (HR35), nothing is invented.
"""
from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from pathlib import Path

from data import nba_players as npl

ROOT = Path(__file__).resolve().parent.parent
STATS_LOG = npl.DIR / "player_stats.jsonl"
STATS = ("pts", "reb", "ast", "tpm")
LABEL = {"pts": "points", "reb": "rebounds", "ast": "assists", "tpm": "threes"}
MARKET = {"921": "pts", "922": "ast", "923": "reb", "924": "tpm"}      # SportyBet over/under markets
SHRINK_MIN = 100.0         # pseudo-minutes at the league rate behind every player rate
MIN_GAMES = 5              # fewer played games than this and the player reads PENDING
MIN_EXPECTED = 8.0         # expected minutes below this: not listed (garbage-time player)
LAST_N = 10
SCALE_CLIP = (0.7, 1.4)    # player points never scaled by more than this to meet the team total
DEFAULT_DISP = {"pts": 3.5, "reb": 1.6, "ast": 1.8, "tpm": 1.4}   # used only until the study writes its own


# ── data ──────────────────────────────────────────────────────────────────────────────────

def _int(x) -> int | None:
    try:
        return int(str(x).split("-")[0])
    except (ValueError, TypeError):
        return None


def stat_rows(g, blob: dict) -> list[dict]:
    """One row per player who played (DNP skipped) from an ESPN summary. [] when the box score is missing."""
    rows = []
    for side in (blob.get("boxscore") or {}).get("players") or []:
        team = (side.get("team") or {}).get("abbreviation")
        if team not in (g.home, g.away):
            continue
        for st in side.get("statistics") or []:
            keys = st.get("keys") or []
            need = {"m": "minutes", "pts": "points", "reb": "rebounds", "ast": "assists",
                    "tpm": "threePointFieldGoalsMade-threePointFieldGoalsAttempted"}
            if not all(k in keys for k in need.values()):
                continue
            ix = {k: keys.index(v) for k, v in need.items()}
            for a in st.get("athletes") or []:
                stats, ath = a.get("stats") or [], a.get("athlete") or {}
                if a.get("didNotPlay") or not stats:
                    continue
                vals = {k: _int(stats[i]) for k, i in ix.items()}
                if any(v is None for v in vals.values()) or not vals["m"]:
                    continue
                rows.append({"g": g.id, "d": g.date, "t": team, "p": str(ath.get("id")),
                             "n": ath.get("displayName", ""), "s": int(bool(a.get("starter"))), **vals})
    return rows


def load_stats(path: Path = STATS_LOG) -> list[dict]:
    return npl.load_log(path)


def update_stats(fetch=None, log: Path = STATS_LOG, team_log: Path = npl.TEAM_LOG) -> list[str]:
    """Add every game of the team log that has no rows yet (cached summary, else one ESPN call). Missing box
    score = skipped and retried next run. Existing rows are never changed."""
    from data import nba_source as ns
    fetch = fetch or ns._get
    have = {r["g"] for r in load_stats(log)}
    games = {}
    for r in npl.load_log(team_log):
        games.setdefault(r["g"], {"d": r["d"], "tip": r.get("tip", "")})["home" if r["h"] else "away"] = r["t"]
    new, notes = [], []
    for gid, x in sorted(games.items(), key=lambda kv: kv[1]["d"]):
        if gid in have or "home" not in x or "away" not in x:
            continue
        blob = npl.summary(gid, True, fetch)
        g = ns.Game(gid, x["d"], 0, 2, x["home"], x["away"], None, None, True, tip=x["tip"])
        rows = stat_rows(g, blob or {})
        if rows:
            new += rows
        else:
            notes.append(f"{x['away']} @ {x['home']} {x['d']}: no box score")
    npl._append(log, new)
    return notes + ([f"{len(new)} player-stat rows added"] if new else [])


# ── model ─────────────────────────────────────────────────────────────────────────────────

def league_rates(rows: list[dict]) -> dict[str, float]:
    mins = sum(r["m"] for r in rows)
    return {s: (sum(r[s] for r in rows) / mins if mins else 0.0) for s in STATS}


def by_player(rows: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = defaultdict(list)
    for r in sorted(rows, key=lambda r: (r["d"], r["g"])):
        out[r["p"]].append(r)
    return out


def last10(games: list[dict], stat: str) -> float | None:
    g = games[-LAST_N:]
    return sum(r[stat] for r in g) / len(g) if g else None


def expected(games: list[dict], league: dict[str, float], chance: float = 1.0) -> dict | None:
    """Expected minutes and stats of one player from his played games (oldest first). None = PENDING."""
    if len(games) < MIN_GAMES:
        return None
    season_min = sum(r["m"] for r in games) / len(games)
    mins = (0.6 * last10(games, "m") + 0.4 * season_min) * chance
    tot = sum(r["m"] for r in games)
    out = {"min": round(mins, 1), "games": len(games)}
    for s in STATS:
        rate = (sum(r[s] for r in games) + SHRINK_MIN * league[s]) / (tot + SHRINK_MIN)
        out[s] = mins * rate
    return out


def baseline(games: list[dict], stat: str) -> float | None:
    """The plain baseline every prediction must beat: the player's last-10-games average."""
    return last10(games, stat) if len(games) >= MIN_GAMES else None


def scale_points(players: list[dict], team_pts: float | None) -> float | None:
    """Scale every player's expected points by one factor so that they add up to the team's projected points.
    Returns the factor (None = team projection missing: points left unscaled, flagged)."""
    raw = sum(p["pts"] for p in players)
    if not team_pts or raw <= 0:
        return None
    f = min(max(team_pts / raw, SCALE_CLIP[0]), SCALE_CLIP[1])
    for p in players:
        p["pts"] *= f
    return f


# ── chances ───────────────────────────────────────────────────────────────────────────────

def _nb_cdf(k: int, mean: float, disp: float) -> float:
    """P(X <= k) for a count with the given mean and variance = disp x mean (negative binomial; Poisson if disp<=1)."""
    if k < 0:
        return 0.0
    if mean <= 0:
        return 1.0
    if disp <= 1.0001:
        p, term = math.exp(-mean), math.exp(-mean)
        for i in range(1, k + 1):
            term *= mean / i
            p += term
        return min(p, 1.0)
    size = mean / (disp - 1)
    q = mean / (mean + size)                       # P(failure) per trial
    pmf = (1 - q) ** size
    total = pmf
    for i in range(1, k + 1):
        pmf *= (size + i - 1) / i * q
        total += pmf
    return min(total, 1.0)


def over_under(mean: float, line: float, disp: float) -> dict | None:
    """Both sides of a half line (Over 17.5 = 18 or more). Whole lines can push: not priced."""
    if line is None or float(line) == int(line):
        return None
    p_under = _nb_cdf(int(math.floor(line)), mean, disp)
    return {"line": line, "over": round(1 - p_under, 4), "under": round(p_under, 4)}


# ── SportyBet lines ───────────────────────────────────────────────────────────────────────

def norm_name(name: str) -> str:
    from engine import nba_markets as nm
    return nm.norm_name(name)


def player_lines(markets: list[dict]) -> dict[str, dict[str, dict]]:
    """{norm player name: {stat: {line, over_odds, under_odds}}} from one snapshot's market list (921-924)."""
    out: dict[str, dict[str, dict]] = {}
    for m in markets:
        stat = MARKET.get(str(m.get("id")))
        if not stat or not m.get("open"):
            continue
        mm = re.search(r"total=(\d+(?:\.\d+)?)", m.get("spec") or "")
        name = norm_name(re.split(r" total ", m.get("name") or "", maxsplit=1)[0])
        try:
            prices = {o[0].split(" ")[0]: float(o[1]) for o in m.get("outcomes") or []}
            line = float(mm.group(1))        # type: ignore[union-attr]
            row = {"line": line, "over_odds": prices["Over"], "under_odds": prices["Under"]}
        except (AttributeError, KeyError, TypeError, ValueError, IndexError):
            continue
        if line != int(line):
            out.setdefault(name, {})[stat] = row
    return out
