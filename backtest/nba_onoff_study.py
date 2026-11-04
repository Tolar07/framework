"""
NBA TEAMMATE ON/OFF STUDY (self-improvement #296) -> backtest/NBA_ONOFF_STUDY.md.
RECORD-ONLY SHADOW: reads data/nba_lineups/player_games.jsonl, changes no pick, stake or threshold.

Idea (Billy Collins, https://www.youtube.com/watch?v=hTbMIwItUhI @ 05:45-08:53): a player's
scoring moves when a key teammate is out. For every player-game, walk-forward (only games
BEFORE it), two projections of the player's points are made and graded against the actual:
  plain     = his season points-per-minute x his season average minutes
  adjusted  = if a key teammate (top-3 minutes on the team) is out tonight and the player has
              MIN_SAMPLE games both with and without him: his points-per-minute in the games
              without him x his minutes in those games. Otherwise identical to plain.
Graded on the games where a key teammate was actually out. Low confidence: a player with
fewer than MIN_GAMES games for the team, or a first-game player. The log holds points and
minutes only (no usage or assists), and no prop lines are recorded, so the over/under Brier
and log-loss from the issue read PENDING (HR35); the grade here is points error (MAE, bias).
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from data import nba_players as npl  # noqa: E402

OUT = ROOT / "backtest" / "NBA_ONOFF_STUDY.md"
KEY_N = 3         # a "key" teammate = top-3 by season average minutes (games before)
MIN_GAMES = 5     # fewer prior games with the team = low confidence, no projection
MIN_SAMPLE = 2    # prior games needed both with and without the teammate


def _rate(rows: list[dict]) -> tuple[float, float] | None:
    mins = sum(r["m"] for r in rows)
    if not rows or mins <= 0:
        return None
    return sum(r["pts"] for r in rows) / mins, mins / len(rows)


def evaluate(log: list[dict]) -> list[dict]:
    """One record per (player, game) with a plain and an adjusted projection, walk-forward."""
    by_game: dict[tuple, list[dict]] = defaultdict(list)
    for r in log:
        by_game[(r["d"], r["g"], r["t"])].append(r)
    team_games = defaultdict(list)           # team -> [(date, game, rows)] in order
    for (d, g, t), rows in sorted(by_game.items()):
        team_games[t].append((d, g, rows))
    recs = []
    for t, games in team_games.items():
        for i, (d, g, rows) in enumerate(games):
            prior = games[:i]
            if len(prior) < MIN_GAMES:
                continue
            tot, played = defaultdict(float), defaultdict(int)
            for _, _, prows in prior:
                for r in prows:
                    tot[r["p"]] += r["m"]
                    played[r["p"]] += 1
            key = sorted(tot, key=lambda p: -tot[p] / max(len(prior), 1))[:KEY_N]
            here = {r["p"]: r for r in rows}
            out = [k for k in key if k not in here or here[k]["m"] == 0]
            for r in rows:
                p = r["p"]
                if r["m"] <= 0 or played[p] < MIN_GAMES:
                    continue
                mine = [x for _, _, rs in prior for x in rs if x["p"] == p and x["m"] > 0]
                plain = _rate(mine)
                if not plain:
                    continue
                pm = plain[0] * plain[1]
                adj, why = pm, None
                for k in out:
                    if k == p:
                        continue
                    gone = {gg for _, gg, rs in prior if not any(x["p"] == k and x["m"] > 0 for x in rs)}
                    wo = [x for x in mine if x["g"] in gone]
                    wi = [x for x in mine if x["g"] not in gone]
                    if len(wo) >= MIN_SAMPLE and len(wi) >= MIN_SAMPLE and _rate(wo):
                        a = _rate(wo)
                        adj, why = a[0] * a[1], k
                        break
                recs.append({"g": g, "d": d, "p": p, "n": r["n"], "actual": r["pts"], "plain": pm,
                             "adj": adj, "teammate_out": bool(out), "adjusted": why is not None})
    return recs


def _grade(rs: list[dict]) -> dict:
    if not rs:
        return {"n": 0}
    n = len(rs)
    return {"n": n,
            "mae_plain": sum(abs(r["plain"] - r["actual"]) for r in rs) / n,
            "mae_adj": sum(abs(r["adj"] - r["actual"]) for r in rs) / n,
            "bias_plain": sum(r["plain"] - r["actual"] for r in rs) / n,
            "bias_adj": sum(r["adj"] - r["actual"] for r in rs) / n}


def summarise(recs: list[dict]) -> dict:
    return {"all": _grade(recs),
            "teammate_out": _grade([r for r in recs if r["teammate_out"]]),
            "adjusted": _grade([r for r in recs if r["adjusted"]])}


def render(s: dict, n_log: int) -> str:
    def row(label, g):
        if not g["n"]:
            return f"| {label} | 0 | PENDING | PENDING | PENDING | PENDING |"
        return (f"| {label} | {g['n']} | {g['mae_plain']:.2f} | {g['mae_adj']:.2f} | "
                f"{g['bias_plain']:+.2f} | {g['bias_adj']:+.2f} |")
    return "\n".join([
        "# NBA teammate on/off study (shadow, record-only, #296)", "",
        f"Walk-forward over {n_log} logged player-games. Points error of the plain projection vs the "
        "projection that swaps in the player's with-key-teammate-out rate. Nothing here feeds a pick.", "",
        "| games | n | MAE plain | MAE adjusted | bias plain | bias adjusted |", "|---|---|---|---|---|---|",
        row("all projected", s["all"]), row("a key teammate out", s["teammate_out"]),
        row("adjustment applied", s["adjusted"]), "",
        "Over/under Brier and log-loss: PENDING (no prop lines recorded yet; 2024-25 not in the log).",
        "Source: https://www.youtube.com/watch?v=hTbMIwItUhI @ 05:45-08:53. Promotion is the Architect's decision.", ""])


def main() -> int:
    log = npl.load_log()
    s = summarise(evaluate(log))
    OUT.write_text(render(s, len(log)), encoding="utf-8")
    print(render(s, len(log)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
