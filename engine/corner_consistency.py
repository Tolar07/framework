"""
CORNER CONSISTENCY (framework #583) - the teams whose total match corners vary least. RECORD ONLY.

The Architect's video of 2026-11-12 ranked "the most consistent teams in corners in the world" (lowest variation of
total corners per game, 20+ games in 2026; a side averaging about 9 with variation 1.92, 30 of 36 games between 7
and 11). A steady team would make the corner total line easier to price, IF the steadiness lasts: over 20-36 games
low variation is partly luck. backtest/CORNER_CONSISTENCY_STUDY.md tests whether a team's spread in the first half of
a season predicts its spread in the second half before anything uses it.

Per team, from rows with corners (engine/stats_history.py: football-data.co.uk HC/AC; the world-facts detail archive
adds every league Flashscore has stats for once teams there reach MIN_GAMES):
  games, mean and standard deviation of TOTAL match corners (for + against), home and away means, the share of
  games inside mean +/- 2, and the team's own corners for / against per game.
Fewer than MIN_GAMES games in the calendar year: not listed (PENDING).
Output: output/corners/consistency.json, the steadiest TOP first.
"""
from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "corners" / "consistency.json"
DETAIL = ROOT / "data" / "world_facts_detail"
MIN_GAMES = 20
TOP = 30


def detail_rows(detail_dir: Path = DETAIL) -> list[dict]:
    """World-facts detail matches with match corners, as stats_history-style rows."""
    out = []
    for f in sorted(Path(detail_dir).glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            try:
                m = json.loads(line)
            except ValueError:
                continue
            c = (((m.get("stats") or {}).get("match") or {}).get("corners"))
            if not c or len(c) != 2 or c[0] is None or c[1] is None or not m.get("ft"):
                continue
            out.append({"league": m.get("league", "?"), "date": (m.get("ko") or "")[:10], "home": m.get("home"),
                        "away": m.get("away"), "hg": m["ft"][0], "ag": m["ft"][1], "hc": int(c[0]), "ac": int(c[1]),
                        "source": "flashscore"})
    return out


def _sd(xs: list[float]) -> float:
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1)) if len(xs) > 1 else 0.0


def per_team(rows: list[dict]) -> dict[tuple, list[tuple]]:
    """(team, league) -> [(date, total corners, venue, corners for, corners against)] in date order."""
    acc: dict[tuple, list] = {}
    for r in rows:
        if r.get("hc") is None or r.get("ac") is None:
            continue
        tot = r["hc"] + r["ac"]
        acc.setdefault((r["home"], r["league"]), []).append((r["date"], tot, "h", r["hc"], r["ac"]))
        acc.setdefault((r["away"], r["league"]), []).append((r["date"], tot, "a", r["ac"], r["hc"]))
    for v in acc.values():
        v.sort()
    return acc


def summary(games: list[tuple]) -> dict:
    tots = [g[1] for g in games]
    m, sd = sum(tots) / len(tots), _sd(tots)
    home = [g[1] for g in games if g[2] == "h"]
    away = [g[1] for g in games if g[2] == "a"]
    return {"games": len(tots), "mean": round(m, 2), "sd": round(sd, 2),
            "within_2": round(sum(1 for t in tots if abs(t - m) <= 2) / len(tots), 3),
            "home_mean": round(sum(home) / len(home), 2) if home else "PENDING",
            "away_mean": round(sum(away) / len(away), 2) if away else "PENDING",
            "for_pg": round(sum(g[3] for g in games) / len(games), 2),
            "against_pg": round(sum(g[4] for g in games) / len(games), 2),
            "last": [g[1] for g in games[-10:]]}


def build(rows: list[dict], year: str, now: datetime) -> dict:
    teams = []
    for (team, lg), games in per_team([r for r in rows if r["date"][:4] == year]).items():
        if len(games) >= MIN_GAMES:
            teams.append({"team": team, "league": lg, **summary(games)})
    teams.sort(key=lambda t: (t["sd"], -t["games"]))
    return {"generated_at": now.strftime("%Y-%m-%dT%H:%MZ"), "year": year, "min_games": MIN_GAMES,
            "population": len(teams), "record_only": True,
            "study": "backtest/CORNER_CONSISTENCY_STUDY.md", "teams": teams[:TOP]}


def run(now: datetime | None = None, fetch: bool = True) -> str:
    from engine import stats_history as sh
    now = now or datetime.now(UTC)
    prev = f"{int(sh.CURRENT[:2]) - 1:02d}{int(sh.CURRENT[2:]) - 1:02d}"
    hist, _ = sh.load_history(seasons=(prev, sh.CURRENT), fetch=fetch)
    doc = build(hist + detail_rows(), f"{now:%Y}", now)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    return f"corner consistency: {doc['population']} teams with {MIN_GAMES}+ games in {doc['year']}"
