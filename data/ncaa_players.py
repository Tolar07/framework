"""
NCAA PLAYER BOX SCORES (framework#396; the twin of data/nba_players.py, Architect 2026-11-06: basketball
inherits the NBA). RECORD-ONLY: nothing here feeds a pick, stake or threshold.

For each finished NCAA men's game that had a pre-tip ESPN sharp line (total + spread), one row per game in
data/ncaa_graded/player_games.jsonl with both teams' final points, the line, and every player's minutes and
points (ESPN summary box score; DNP kept with minutes 0). Incremental (data/ncaa_graded/players_meta.json),
bounded per run. A missing number stays missing (HR35): a game whose box score cannot be read is skipped,
never filled in.
"""
from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "backtest")]

DIR = ROOT / "data" / "ncaa_graded"
LOG = DIR / "player_games.jsonl"
META = DIR / "players_meta.json"
_SUM = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/summary?event={e}"
MAX_DAYS_PER_RUN = 4                                    # ~300 box scores a day: catch up a few days a night


def season_start(today: date) -> date:
    return date(today.year if today.month >= 11 else today.year - 1, 11, 1)


def load(path: Path = LOG) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def _num(x) -> float | None:
    try:
        return float(str(x).strip())
    except ValueError:
        return None


def players(blob: dict) -> dict[str, list[dict]]:
    """team id -> [{p, n, s, m, pts}] from a summary blob (DNP = minutes 0)."""
    out: dict[str, list[dict]] = {}
    for side in (blob.get("boxscore") or {}).get("players") or []:
        tid = str((side.get("team") or {}).get("id"))
        for st in side.get("statistics") or []:
            keys = st.get("keys") or []
            if "minutes" not in keys or "points" not in keys:
                continue
            im, ip = keys.index("minutes"), keys.index("points")
            for a in st.get("athletes") or []:
                ath, stats = a.get("athlete") or {}, a.get("stats") or []
                dnp = bool(a.get("didNotPlay")) or not stats
                m = 0.0 if dnp else _num(stats[im])
                pts = 0.0 if dnp else _num(stats[ip])
                if m is None or pts is None:
                    continue
                out.setdefault(tid, []).append({"p": str(ath.get("id")), "n": ath.get("displayName", ""),
                                                "s": int(bool(a.get("starter"))), "m": m, "pts": int(pts)})
    return out


def game_row(g: dict, blob: dict) -> dict | None:
    """One record for a finished game, or None when the line, the score or either box score is missing."""
    if g.get("total") is None or g.get("spread") is None or g.get("hs") is None:
        return None
    teams = {}
    comp = ((blob.get("header") or {}).get("competitions") or [{}])[0]
    for c in comp.get("competitors") or []:
        teams[c.get("homeAway")] = str((c.get("team") or {}).get("id"))
    pl = players(blob)
    if not teams.get("home") or not teams.get("away") or not all(teams[k] in pl for k in ("home", "away")):
        return None
    return {"g": g["id"], "day": g["date"], "ot": bool(g.get("ot")), "hs": g["hs"], "as": g["as"],
            "line": float(g["total"]), "spread": float(g["spread"]),
            "home": teams["home"], "away": teams["away"],
            "pl": {"home": pl[teams["home"]], "away": pl[teams["away"]]}}


def _default_boards(d: date) -> list[dict]:
    import ncaa_study as st
    return [st.attach_line(g) for g in st.games_on(d)]


def _default_summary(eid: str) -> dict | None:
    import ncaa_study as st
    return st._get(_SUM.format(e=eid))


def update(today: date, boards=_default_boards, summary=_default_summary,
           path: Path = LOG, meta: Path = META) -> int:
    """Append finished games (with a pre-tip line) up to yesterday; returns rows added."""
    m = json.loads(meta.read_text(encoding="utf-8")) if meta.exists() else {}
    start = season_start(today)
    done = date.fromisoformat(m["through"]) if m.get("through") and m.get("season") == start.isoformat() else None
    if done is None and path.exists():
        path.unlink()                                     # a new season starts a new file
    have = {r["g"] for r in load(path)}
    d, through, new = (done + timedelta(1)) if done else start, done, []
    for _ in range(MAX_DAYS_PER_RUN):
        if d >= today:
            break
        for g in boards(d):
            if g["id"] in have or g.get("total") is None or g.get("spread") is None:
                continue
            blob = summary(g["id"])
            row = game_row(g, blob) if blob else None
            if row:
                new.append(row)
        through = d
        d += timedelta(1)
    if new:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as fh:
            for r in new:
                fh.write(json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n")
    if through:
        meta.parent.mkdir(parents=True, exist_ok=True)
        meta.write_text(json.dumps({"season": start.isoformat(), "through": through.isoformat()}) + "\n",
                        encoding="utf-8", newline="\n")
    return len(new)


def flat(rows: list[dict]) -> list[dict]:
    """Player-game rows in the data/nba_players.py shape (g, d, t, p, n, m, pts) for the shared on/off study."""
    out = []
    for r in rows:
        for side in ("home", "away"):
            for p in r["pl"][side]:
                out.append({"g": r["g"], "d": r["day"], "t": r[side], "p": p["p"], "n": p["n"], "m": p["m"],
                            "pts": p["pts"], "s": p["s"]})
    return out


if __name__ == "__main__":
    from datetime import UTC, datetime
    print("added", update(datetime.now(UTC).date()))
