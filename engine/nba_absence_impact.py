"""
NBA ABSENCE IMPACT - does an NBA absence really hurt? Twin of engine/squad_depth.py (framework #330).

engine/nba_team_news.py counts every Out / Questionable player's recent minutes as lost. That over-flags
exactly like football's raw missing share did: a player out for weeks is already in the team's recent
results and in the price. Here each absent player is weighed by what his absence still changes:

  ALREADY OUT  he played none of the team's last RECENT games: results and price carry it -> weight 0;
  ROTATION     he played k of the last RECENT games: weight k / RECENT (a regular = 1);
  PRICED IN    if the sharp line moved after the news, the market has taken it: weight 0. No before/after
               line recorded -> that step reads PENDING (HR35), never guessed;
  ON/OFF       backtest/NBA_ONOFF_STUDY.md measures the teammate swap; while it applies to 0 games its
               impact reads PENDING and is not used.

    effective minutes = minutes x chance he sits x play share x (0 if priced in)
    adjusted share    = sum(effective) / minutes of everyone on the sheet

RECORDED ONLY: nothing here drops, restakes or re-prices a pick, and engine/nba_team_news.py is untouched.
It writes output/nba_absence_impact/<date>.jsonl (raw share beside adjusted) so a RISK flag can be graded
against results before it is ever allowed to matter.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from data import nba_players as npl
from engine import nba_team_news as ntn

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "output" / "nba_absence_impact"
RECENT = 5
LINE_MOVE = 1.0     # points: a sharp line that moved this far (either way) after the news has priced it in


def _pending(team: str, why: str) -> dict:
    return {"team": team, "raw_share": None, "adj_share": None, "level": "PENDING", "players": [],
            "pending": why}


def _played_recent(rows: list[dict], team: str, pid: str, last: list[str]) -> int:
    return len({r["g"] for r in rows if r["t"] == team and r["p"] == pid and r["g"] in last and r["m"] > 0})


def team_impact(rows: list[dict], team: str, injured: Optional[list[dict]],
                line_move: Optional[float] = None) -> dict:
    """{team, raw_share, adj_share, level, players:[{name,status,min,weight,why}], pending}.
    `line_move` = points the sharp line moved on this team after the news (None = not recorded)."""
    if injured is None:
        return _pending(team, "injury report unreadable")
    players, n_games, _ = npl.player_lines(rows, team)
    if n_games < npl.MIN_GAMES:
        return _pending(team, f"{n_games} games logged")
    last = [g for _d, g in sorted({(r["d"], r["g"]) for r in rows if r["t"] == team})[-RECENT:]]
    mins = {p["id"]: (p["min10"] if p["min10"] is not None else p["min"]) or 0.0 for p in players}
    total = sum(mins.values())
    if total <= 0:
        return _pending(team, "no minutes logged")
    priced = line_move is not None and abs(line_move) >= LINE_MOVE
    raw = eff = 0.0
    out = []
    for i in injured:
        chance, m = ntn.sits_chance(i.get("status", "")), mins.get(i.get("id"), 0.0)
        if chance <= 0 or m <= 0:
            continue
        k = _played_recent(rows, team, i["id"], last)
        if k == 0:
            w, why = 0.0, f"played none of the last {len(last)}: already out, price carries it"
        elif priced:
            w, why = 0.0, f"sharp line moved {line_move:+.1f} after the news: priced in"
        else:
            w = k / max(len(last), 1)
            why = f"played {k} of the last {len(last)}" + ("" if line_move is not None else "; line move PENDING")
        raw += chance * m
        eff += chance * m * w
        out.append({"name": i.get("name", ""), "status": i["status"], "min": round(m, 1),
                    "weight": round(w, 2), "why": why})
    out.sort(key=lambda x: -x["min"])
    adj = round(eff / total, 3)
    return {"team": team, "raw_share": round(raw / total, 3), "adj_share": adj, "level": ntn.level(adj),
            "players": out, "pending": None}


def assess_game(rows: list[dict], home: str, away: str, inj: Optional[dict],
                moves: Optional[dict] = None) -> dict:
    """One record per game: both teams' raw v adjusted share. `moves` = {team: line move} when known."""
    moves = moves or {}
    h = team_impact(rows, home, None if inj is None else inj.get(home, []), moves.get(home))
    a = team_impact(rows, away, None if inj is None else inj.get(away, []), moves.get(away))
    flips = [t["team"] for t in (h, a)
             if t["raw_share"] is not None and ntn.level(t["raw_share"]) != t["level"]]
    return {"home": h, "away": a, "false_flag_teams": flips,
            "onoff": "PENDING (backtest/NBA_ONOFF_STUDY.md applies to 0 games)"}


def record(day: str, now_iso: str, game: str, rec: dict, out_dir: Path = OUT_DIR) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / f"{day}.jsonl").open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"at": now_iso, "game": game, **rec}) + "\n")


def study(rows: list[dict]) -> dict:
    """Numbers from the box-score log: for every logged team-game, each regular (>=15 min average over
    his prior games, 3+ played) who logged 0 minutes is an absence. Split by whether he had also missed
    all of the prior RECENT team games ('already out') or was a fresh absence. Past games only."""
    teams: dict[str, dict] = {}
    for r in rows:
        teams.setdefault(r["t"], {}).setdefault((r["d"], r["g"]), {})[r["p"]] = r["m"]
    absences = already = 0
    for games in teams.values():
        order = sorted(games)
        hist: dict[str, list[float]] = {}
        for idx, key in enumerate(order):
            for pid, m in games[key].items():
                played = [x for x in hist.get(pid, []) if x > 0]
                if m == 0 and len(played) >= 3 and sum(played) / len(played) >= 15:
                    absences += 1
                    last = order[max(0, idx - RECENT):idx]
                    if last and all(games[g].get(pid, 0) == 0 for g in last):
                        already += 1
                hist.setdefault(pid, []).append(m)
    return {"absences": absences, "already_out": already,
            "share_already_out": None if not absences else round(already / absences, 3)}
