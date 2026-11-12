"""
LEAGUE PROFILES (framework #581) - every league ranked by both-teams-to-score rate and by when its goals come.
RECORD ONLY: nothing here picks, stakes or blocks. The Architect posted a video on 2026-11-12 ranking 45 leagues
("Dutch second division 69.1% BTTS ... Premier League 49 ... Bundesliga 28.7% of goals from the 76th minute ...
only 2 of 45 leagues, both Scottish, score more before half-time than after"). Its figures are CLAIMS; these are
ours, each with the number of games behind it.

Per league (engine/stats_history.py rows):
  games, btts (both teams scored), o15 / o25 (over 1.5 / 2.5 goals), gpg (goals per game),
  fh_share (share of goals scored before half-time; needs the half-time score),
  fh_goal (share of games with a goal before half-time),
  late_share (share of goals from the 76th minute on; needs goal minutes, from the world-facts detail archive,
              else PENDING).
A rate is given only with MIN_GAMES games behind it, else PENDING (HR35).

Sources, in output order:
  football-data.co.uk  the current season and the last one (22 divisions with half-time scores);
  SportyBet sweep      every competition SportyBet listed since 2026-10-08 (500+), last WINDOW_DAYS days;
  world facts          goal minutes from data/world_facts_detail/ (Flashscore, since 2026-11-12).

Output: output/league_profiles/latest.json and league_profiles_<date>.json (the Control Room app lists it).
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "output" / "league_profiles"
DETAIL = ROOT / "data" / "world_facts_detail"
MIN_GAMES = 20
WINDOW_DAYS = 60
LATE_FROM = 76


def _rate(n: int, d: int) -> float | str:
    return round(n / d, 4) if d >= MIN_GAMES else "PENDING"


def profile(rows: list[dict]) -> dict:
    """One league's numbers from its rows."""
    g = len(rows)
    goals = sum(r["hg"] + r["ag"] for r in rows)
    ht = [r for r in rows if r.get("hthg") is not None and r.get("htag") is not None]
    ht_goals = sum(r["hthg"] + r["htag"] for r in ht)
    ht_all = sum(r["hg"] + r["ag"] for r in ht)
    out = {
        "games": g,
        "btts": _rate(sum(1 for r in rows if r["hg"] > 0 and r["ag"] > 0), g),
        "o15": _rate(sum(1 for r in rows if r["hg"] + r["ag"] > 1), g),
        "o25": _rate(sum(1 for r in rows if r["hg"] + r["ag"] > 2), g),
        "gpg": round(goals / g, 3) if g >= MIN_GAMES else "PENDING",
        "ht_games": len(ht),
        "fh_share": round(ht_goals / ht_all, 4) if len(ht) >= MIN_GAMES and ht_all else "PENDING",
        "fh_goal": _rate(sum(1 for r in ht if r["hthg"] + r["htag"] > 0), len(ht)),
    }
    out["more_before_ht"] = (out["fh_share"] > 0.5) if isinstance(out["fh_share"], float) else "PENDING"
    return out


def late_shares(detail_dir: Path = DETAIL) -> dict[str, dict]:
    """League -> {'games', 'late_share'} from goal minutes (only matches whose minutes add up to the score)."""
    acc: dict[str, list[int]] = {}
    for f in sorted(Path(detail_dir).glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            try:
                m = json.loads(line)
            except ValueError:
                continue
            goals = m.get("goals")
            if goals is None:
                continue
            a = acc.setdefault(m.get("league", "?"), [0, 0, 0])
            a[0] += 1
            a[1] += len(goals)
            a[2] += sum(1 for x in goals if x and x[0] is not None and x[0] >= LATE_FROM)
    return {lg: {"games": a[0], "late_share": round(a[2] / a[1], 4) if a[0] >= MIN_GAMES and a[1] else "PENDING"}
            for lg, a in acc.items()}


def build(history: list[dict], sporty: list[dict], now: datetime, late: dict | None = None) -> dict:
    by: dict[tuple, list] = {}
    for r in history:
        by.setdefault(("football-data.co.uk", r["league"], r["season"]), []).append(r)
    since = (now - timedelta(days=WINDOW_DAYS)).strftime("%Y-%m-%d")
    for r in sporty:
        if r["date"] >= since:
            by.setdefault(("sportybet", r["league"], f"last {WINDOW_DAYS} days"), []).append(r)
    leagues = []
    for (src, lg, season), rows in by.items():
        p = profile(rows)
        p.update(league=lg, season=season, source=src)
        leagues.append(p)
    late = late or {}
    for p in leagues:
        hit = late.get(p["league"])
        p["late_share"] = hit["late_share"] if hit else "PENDING"
        p["late_games"] = hit["games"] if hit else 0
    ranked = [p for p in leagues if isinstance(p["btts"], float)]
    ranked.sort(key=lambda p: -p["btts"])
    for i, p in enumerate(ranked, 1):
        p["btts_rank"] = i
    return {"generated_at": now.strftime("%Y-%m-%dT%H:%MZ"), "min_games": MIN_GAMES,
            "record_only": True, "ranked": len(ranked),
            "late_goal_note": ("goal minutes come from the world-facts detail archive (Flashscore, from "
                               "2026-11-12); a league reads PENDING until it has 20 such games"),
            "leagues": ranked + [p for p in leagues if not isinstance(p["btts"], float)]}


def write(doc: dict, now: datetime, out_dir: Path = OUT_DIR) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=1, ensure_ascii=False)
    (out_dir / f"league_profiles_{now:%Y-%m-%d}.json").write_text(text, encoding="utf-8")
    p = out_dir / "latest.json"
    p.write_text(text, encoding="utf-8")
    return p


def run(now: datetime | None = None, fetch: bool = True) -> str:
    from engine import stats_history as sh
    now = now or datetime.now(UTC)
    season_now = sh.CURRENT
    last = f"{int(season_now[:2]) - 1:02d}{int(season_now[2:]) - 1:02d}"
    hist, _cov = sh.load_history(seasons=(last, season_now), fetch=fetch)
    sporty = sh.load_sportybet()
    doc = build(hist, sporty, now, late_shares())
    p = write(doc, now)
    return f"league profiles: {doc['ranked']} leagues ranked ({len(doc['leagues'])} listed) -> {p.relative_to(ROOT)}"
