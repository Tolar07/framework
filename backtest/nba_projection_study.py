"""
NBA PROJECTION STUDY (Architect 2026-10-28, step 4 of 4: "measure every day") ->
backtest/NBA_PROJECTION_STUDY.md. Runs after every daily board; reads only, changes nothing.

For every graded game the board recorded a projection for (output/picks/nba_<date>.json
"players"; results and the sharp CLOSING line from data/nba_lineups/graded_games.jsonl):

  1. ERROR   projection vs actual points — total, spread (home margin), 1st half, 1st
             quarter — beside the sharp line at board time, the sharp close and SportyBet's
             main line, each read as a forecast of the same number (mean miss, bias).
  2. RESULTS both sides of every recorded yes/no line (Over/Under, home/away covers):
             Brier and log loss of the projection's chance vs the sharp line's (and the
             sharp line with this season's refit, "sharp_recal", once step 3 adopts one).
  3. CLV     the side the projection prefers at SportyBet's board-time total, against the
             sharp CLOSING total: points gained (close moved toward the side) and % positive.
  4. SHOCK   games flagged line-up shock (a top-3 scorer out, line unmoved) on their own.

Plus a HINDSIGHT section from the season log: every logged game projected from the games
before it with the players who actually played (known only afterwards — labelled, not a
forecast), so there are numbers from the first day.

Nothing here feeds a pick. Wiring the projection into picks needs the Architect's OK after
it beats the sharp line on games it was not fitted to.
"""
from __future__ import annotations

import json
import math
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from data import nba_players as npl  # noqa: E402
from engine import nba_gate as gate  # noqa: E402
from engine import nba_projection as proj  # noqa: E402
from engine import nba_recal as recal  # noqa: E402

PICKS = ROOT / "output" / "picks"
OUT = ROOT / "backtest" / "NBA_PROJECTION_STUDY.md"
SPLIT = 4.0          # "projection disagrees" = 4+ points off the sharp total
FAMS = (("total", "total"), ("h1_total", "h1"), ("q1_total", "q1"))


def actual(r: dict, key: str) -> float:
    return {"total": r["hs"] + r["as"], "h1_total": r["h1"], "q1_total": r["q1"],
            "spread": r["as"] - r["hs"]}[key]


def load(picks_dir: Path = PICKS, graded: Path = recal.GAMES) -> list[dict]:
    """One record per graded game with a recorded projection (the latest board's record)."""
    res = {r["g"]: r for r in npl.load_log(graded)}
    out: dict[str, dict] = {}
    for f in sorted(picks_dir.glob("nba_2*.json")):
        try:
            doc = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        study = {s.get("espn_id"): s for s in doc.get("study") or [] if s.get("espn_id")}
        for p in (doc.get("players") or {}).get("projections") or []:
            gid = p.get("espn_id")
            if gid in res and p.get("projection"):
                s = study.get(gid, {})
                out[gid] = {**p, "result": res[gid], "board_sharp": s.get("sharp") or {},
                            "sb_main": s.get("sb_main") or {}, "board": f.stem[4:]}
    return sorted(out.values(), key=lambda x: x["result"]["tip"])


def _mean(xs: list[float]) -> float | None:
    return sum(xs) / len(xs) if xs else None


def errors(recs: list[dict]) -> dict:
    """Mean absolute miss and bias per number, per forecaster."""
    out: dict = {}
    for key in ("total", "spread", "h1_total", "q1_total"):
        src: dict[str, list[tuple[float, float]]] = {"projection": [], "sharp board": [], "sharp close": [],
                                                     "SportyBet": []}
        for r in recs:
            a, res, bs = actual(r["result"], key), r["result"], r["board_sharp"]
            src["projection"].append((r["projection"][key], a))
            if key == "spread":
                if bs.get("spread") is not None:
                    src["sharp board"].append((bs["spread"], a))
                src["sharp close"].append((res["spread"], a))
                continue
            share = {"total": 1.0, "h1_total": proj.nv.H1_SHARE, "q1_total": proj.nv.Q1_SHARE}[key]
            if bs.get("total") is not None:
                src["sharp board"].append((bs["total"] * share, a))
            src["sharp close"].append((res["line"] * share, a))
            sb = r["sb_main"].get({"total": "225", "h1_total": "68", "q1_total": "236"}[key])
            if sb is not None:
                src["SportyBet"].append((sb, a))
        out[key] = {k: {"n": len(v), "mae": _mean([abs(f - a) for f, a in v]), "bias": _mean([f - a for f, a in v])}
                    for k, v in src.items() if v}
    return out


def _score(p: float, y: int) -> tuple[float, float]:
    p = min(max(p, 1e-4), 1 - 1e-4)
    return (p - y) ** 2, -(y * math.log(p) + (1 - y) * math.log(1 - p))


def results(recs: list[dict]) -> dict:
    """Brier / log loss per forecaster over every recorded line, both sides (one binary each)."""
    acc: dict[str, list[tuple[float, float]]] = {}
    for r in recs:
        for key, _fam in FAMS + (("spread", "margin"),):
            a = actual(r["result"], key)
            for _src, row in ((r.get("sides") or {}).get(key) or {}).items():
                for who, c in row.items():
                    if not c:
                        continue
                    if key == "spread":
                        line, p = c["line"], c["home"]
                        y = int(-a > -line)                     # home margin beats the handicap
                    else:
                        line, p = c["line"], c["over"]
                        y = int(a > line)
                    acc.setdefault(who, []).append(_score(p, y))
    return {k: {"n": len(v), "brier": _mean([b for b, _ in v]), "logloss": _mean([ll for _, ll in v])}
            for k, v in acc.items()}


def clv(recs: list[dict]) -> dict:
    """The projection's side at SportyBet's board-time total vs the sharp closing total."""
    pts, pos, n, div = [], 0, 0, []
    for r in recs:
        sb = r["sb_main"].get("225")
        if sb is None:
            continue
        side = 1 if r["projection"]["total"] > sb else -1
        gain = side * (r["result"]["line"] - sb)
        pts.append(gain)
        pos += gain > 0
        n += 1
        if abs(r["projection"]["total"] - sb) >= SPLIT:
            div.append(gain)
    return {"n": n, "mean_pts": _mean(pts), "positive": pos / n if n else None,
            "n_split": len(div), "mean_pts_split": _mean(div)}


def side_record(recs: list[dict]) -> dict:
    """When the projection is 4+ points off the board-time sharp total: whose side won."""
    won = lost = 0
    for r in recs:
        line = r["board_sharp"].get("total")
        if line is None or abs(r["projection"]["total"] - line) < SPLIT:
            continue
        a = actual(r["result"], "total")
        if a == line:
            continue
        won += (a > line) == (r["projection"]["total"] > line)
        lost += (a > line) != (r["projection"]["total"] > line)
    return {"won": won, "lost": lost}


def hindsight(rows: list[dict], trows: list[dict], graded: list[dict]) -> dict:
    """Each graded game projected from the games before it with the players who played."""
    close = {g["g"]: g for g in graded}
    by_g: dict[str, list[dict]] = {}
    for r in trows:
        by_g.setdefault(r["g"], []).append(r)
    pr, sh, act, won, lost = [], [], [], 0, 0
    for gid, gr in sorted(by_g.items(), key=lambda x: x[1][0]["tip"]):
        if gid not in close or len(gr) != 2:
            continue
        h = next(r for r in gr if r["h"])
        a = next(r for r in gr if not r["h"])
        prior = [r for r in rows if r["d"] < h["d"]]
        teams, lg = proj.team_table([r for r in trows if r["tip"] < h["tip"]])
        played = {r["p"] for r in rows if r["g"] == gid and r["m"] > 0}
        sheets = []
        for t in (h["t"], a["t"]):
            s = npl.team_sheet(prior, t, [], date.fromisoformat(h["d"]))
            s["players"] = [p for p in s["players"] if p["id"] in played]
            s["stale"] = [x for x in s["stale"] if "games logged" in x]
            sheets.append(s)
        out = proj.project({"espn_id": gid, "tip": h["tip"], "home_sheet": sheets[0], "away_sheet": sheets[1]},
                           teams, lg)
        if not out["projection"]:
            continue
        p, line, y = out["projection"]["total"], close[gid]["line"], h["pts"] + a["pts"]
        pr.append(abs(p - y))
        sh.append(abs(line - y))
        act.append(y)
        if abs(p - line) >= SPLIT and y != line:
            won += (y > line) == (p > line)
            lost += (y > line) != (p > line)
    return {"n": len(pr), "mae_projection": _mean(pr), "mae_sharp_close": _mean(sh), "won": won, "lost": lost}


def _f(x, d=1) -> str:
    return "—" if x is None else f"{x:.{d}f}"


def render(recs: list[dict], hs: dict, today: str) -> str:
    shock = [r for r in recs if (r.get("lineup_shock") or {}).get("flag")]
    lines = [f"# NBA projection study — {today}", "",
             "RECORDED ONLY (Architect 2026-10-28). The player-built projection (engine/nba_projection.py) "
             "against the sharp line and SportyBet, on games it was not fitted to. Nothing here feeds a pick.", "",
             f"Graded games with a board-time projection: **{len(recs)}** (line-up shock: {len(shock)}).", ""]
    for title, sub in (("All games", recs), ("Line-up shock games", shock)):
        lines += [f"## {title}", ""]
        if not sub:
            lines += ["No graded games yet.", ""]
            continue
        lines += ["### 1. Error against actual points (mean miss / bias, points)", "",
                  "| number | forecaster | n | mean miss | bias |", "|---|---|---|---|---|"]
        for key, d in errors(sub).items():
            for who, e in d.items():
                lines.append(f"| {key} | {who} | {e['n']} | {_f(e['mae'])} | {_f(e['bias'], 1)} |")
        lines += ["", "### 2. Results — both sides of every recorded line (lower is better)", "",
                  "| forecaster | lines | Brier | log loss |", "|---|---|---|---|"]
        for who, e in sorted(results(sub).items()):
            lines.append(f"| {who} | {e['n']} | {_f(e['brier'], 4)} | {_f(e['logloss'], 4)} |")
        c, s = clv(sub), side_record(sub)
        lines += ["", "### 3. CLV — the projection's side at SportyBet's board total vs the sharp close", "",
                  f"- games {c['n']}: mean {_f(c['mean_pts'], 2)} points toward the projection's side, "
                  f"positive {_f(None if c['positive'] is None else 100 * c['positive'], 0)}%",
                  f"- projection {SPLIT:.0f}+ points off SportyBet: {c['n_split']} games, "
                  f"mean {_f(c['mean_pts_split'], 2)} points",
                  f"- projection {SPLIT:.0f}+ points off the board-time sharp total: its side won "
                  f"{s['won']}, lost {s['lost']}", ""]
    lines += ["## Hindsight check (season log, line-ups known only afterwards — NOT a forecast)", "",
              f"- games {hs['n']}: total mean miss projection {_f(hs['mae_projection'])} vs sharp close "
              f"{_f(hs['mae_sharp_close'])}",
              f"- projection {SPLIT:.0f}+ points off the sharp close: its side won {hs['won']}, lost {hs['lost']}", ""]
    return "\n".join(lines)


def main() -> int:
    recs = load()
    graded = npl.load_log(recal.GAMES)
    hs = hindsight(npl.load_log(npl.LOG), npl.load_log(npl.TEAM_LOG), graded)
    text = render(recs, hs, date.today().isoformat())
    st = gate.status(recs, clv(recs))
    gate.save(st)
    text += (f"\n## Projection gate (engine/nba_gate.py)\n\n**{'OPEN' if st['open'] else 'closed'}** — "
             + ("the projection drops picks it prices on the other side." if st["open"]
                else "; ".join(st["why"]) + ". Recorded only until all hold.") + "\n")
    OUT.write_text(text + "\n", encoding="utf-8", newline="\n")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
