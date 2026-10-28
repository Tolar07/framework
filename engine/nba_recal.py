"""
NBA NIGHTLY RECALIBRATION (Architect 2026-10-28, step 3 of 4): the normal widths (sigma)
and the 1st-half / 1st-quarter shares refitted on THIS season's graded games, adopted only
when the refit predicts the held-out games better — the way engine/retrain.py does football.

RECORDED ONLY: engine/nba_value.py keeps its fixed 2023-26 numbers for picks. The adopted
numbers are written to memory/nba_calibration_live.json and the NBA picks file records the
sharp line's chances under them beside the fixed ones (engine/nba_projection.py). Wiring
them into picks needs the Architect's OK.

Data: every finished regular-season game of the season with a sharp closing line and
quarter scores, kept in data/nba_lineups/graded_games.jsonl (incremental, tracked).

Families (mean from the sharp closing line, actual from the score):
  total    final total        mean = line                 sd TOTAL_SD
  margin   home margin        mean = -spread              sd MARGIN_SD
  h1       1st-half total     mean = H1_SHARE x line      sd H1_SD
  q1       1st-quarter total  mean = Q1_SHARE x line      sd Q1_SD

Method, per family: games sorted by tip-off; the newest ~20% (whole days) is the HOLDOUT,
the rest the FIT set. The refit (share = sum actual / sum line; sd = root-mean-square miss)
is pulled toward the live numbers by PRIOR_GAMES so a few nights can't swing it. GATE: the
refit goes live only with fit n >= MIN_FIT and holdout n >= MIN_HOLDOUT and if it beats the
live numbers on BOTH the holdout's normal log-likelihood and the Brier score of the yes/no
lines at the centre and 5 points either side (both sides of each line: a yes/no market).
Each night's comparison is appended to memory/nba_retrain_log.jsonl.
"""
from __future__ import annotations

import json
import math
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from data import nba_players as npl  # noqa: E402
from data import nba_source as ns  # noqa: E402
from engine import nba_value as nv  # noqa: E402

GAMES = npl.DIR / "graded_games.jsonl"
GAMES_META = npl.DIR / "graded_meta.json"
LIVE_PATH = ROOT / "memory" / "nba_calibration_live.json"
LOG_PATH = ROOT / "memory" / "nba_retrain_log.jsonl"
HOLDOUT_FRAC = 0.2
MIN_FIT, MIN_HOLDOUT = 60, 15
PRIOR_GAMES = 100
LINE_OFFSETS = (-5.0, 0.0, 5.0)

FIXED = {"total": {"share": 1.0, "sd": nv.TOTAL_SD}, "margin": {"share": 1.0, "sd": nv.MARGIN_SD},
         "h1": {"share": nv.H1_SHARE, "sd": nv.H1_SD}, "q1": {"share": nv.Q1_SHARE, "sd": nv.Q1_SD}}


# ---------------------------------------------------------------- data
def update_games(today: date, scoreboard=ns.scoreboard, attach=ns.attach_odds,
                 path: Path = GAMES, meta: Path = GAMES_META) -> int:
    """Append finished regular-season games (sharp close + quarters) up to yesterday."""
    m = json.loads(meta.read_text(encoding="utf-8")) if meta.exists() else {}
    start = npl.season_start(today)
    done = date.fromisoformat(m["through"]) if m.get("through") and m.get("season") == start.isoformat() else None
    if done is None and path.exists():
        path.unlink()
    have = {r["g"] for r in npl.load_log(path)}
    d, through, new = (done + timedelta(1)) if done else start, done, []
    while d < today:
        games = scoreboard(d)
        if d >= today - timedelta(1) and any(not g.completed for g in games if g.stype == 2):
            break
        for g in games:
            if g.stype != 2 or not g.completed or g.id in have:
                continue
            attach(g)
            if g.total is None or g.spread is None or not g.q_home or not g.q_away or len(g.q_home) < 4:
                continue                                  # no sharp line or no quarters: not gradable
            new.append({"g": g.id, "tip": g.tip, "line": g.total, "spread": g.spread,
                        "hs": g.hs, "as": g.as_, "h1": sum(g.q_home[:2]) + sum(g.q_away[:2]),
                        "q1": g.q_home[0] + g.q_away[0]})
        through = d
        d += timedelta(1)
    npl._append(path, new)
    if through:
        meta.parent.mkdir(parents=True, exist_ok=True)
        meta.write_text(json.dumps({"season": start.isoformat(), "through": through.isoformat()}) + "\n",
                        encoding="utf-8", newline="\n")
    return len(new)


def pairs(rows: list[dict], fam: str) -> list[tuple[float, float]]:
    """(base, actual): the sharp number the family's mean is a share of, and what happened."""
    if fam == "margin":
        return [(-r["spread"], r["hs"] - r["as"]) for r in rows]
    return [(r["line"], {"total": r["hs"] + r["as"], "h1": r["h1"], "q1": r["q1"]}[fam]) for r in rows]


# ---------------------------------------------------------------- fit and score
def fit(xy: list[tuple[float, float]], fam: str, live: dict) -> dict:
    n = len(xy)
    if fam in ("total", "margin"):
        share = 1.0                                      # the sharp line is the centre
    else:
        share = (sum(a for _b, a in xy) + PRIOR_GAMES * live["share"] * _mean_base(xy)) / (
            sum(b for b, _a in xy) + PRIOR_GAMES * _mean_base(xy))
    ms = sum((a - share * b) ** 2 for b, a in xy)
    sd = math.sqrt((ms + PRIOR_GAMES * live["sd"] ** 2) / (n + PRIOR_GAMES))
    return {"share": round(share, 4), "sd": round(sd, 3)}


def _mean_base(xy: list[tuple[float, float]]) -> float:
    return sum(b for b, _a in xy) / len(xy) if xy else 0.0


def nll(xy: list[tuple[float, float]], p: dict) -> float:
    """Mean normal negative log-likelihood of what happened."""
    sd = p["sd"]
    return sum(0.5 * ((a - p["share"] * b) / sd) ** 2 + math.log(sd * math.sqrt(2 * math.pi))
               for b, a in xy) / len(xy)


def brier(xy: list[tuple[float, float]], p: dict) -> float:
    """Brier of the yes/no lines (Over / home covers) at the centre and 5 points either side;
    the Under / away side is the same number (1 - p against 1 - y)."""
    tot, n = 0.0, 0
    for b, a in xy:
        centre = math.floor(p["share"] * b) + 0.5
        for off in LINE_OFFSETS:
            line = centre + off
            pr = 1 - nv._phi((line - p["share"] * b) / p["sd"])
            tot += (pr - (1.0 if a > line else 0.0)) ** 2
            n += 1
    return tot / n


def split(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    rows = sorted(rows, key=lambda r: r["tip"])
    days = sorted({r["tip"][:10] for r in rows})
    cut = days[-max(1, round(len(days) * HOLDOUT_FRAC))] if days else ""
    return [r for r in rows if r["tip"][:10] < cut], [r for r in rows if r["tip"][:10] >= cut]


def load_live(path: Path = LIVE_PATH) -> dict:
    doc = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return {fam: {k: doc.get(fam, {}).get(k, v) for k, v in base.items()} for fam, base in FIXED.items()}


def evaluate(rows: list[dict], live: dict) -> list[dict]:
    fit_rows, hold = split(rows)
    out = []
    for fam in FIXED:
        f, h = pairs(fit_rows, fam), pairs(hold, fam)
        rec: dict = {"family": fam, "n_fit": len(f), "n_holdout": len(h), "live": live[fam], "decision": "keep"}
        if len(f) < MIN_FIT or len(h) < MIN_HOLDOUT:
            rec["reason"] = f"too few games (fit {len(f)} < {MIN_FIT} or holdout {len(h)} < {MIN_HOLDOUT})"
            out.append(rec)
            continue
        new = fit(f, fam, live[fam])
        sc = {"live": (nll(h, live[fam]), brier(h, live[fam])), "refit": (nll(h, new), brier(h, new))}
        rec.update(refit=new, holdout={k: [round(x, 5) for x in v] for k, v in sc.items()})
        if sc["refit"][0] < sc["live"][0] and sc["refit"][1] < sc["live"][1]:
            rec.update(decision="adopt", adopt=new)
        else:
            rec["reason"] = "the refit does not beat the live numbers on both log-likelihood and Brier"
        out.append(rec)
    return out


def run(today: date, live_path: Path = LIVE_PATH, log_path: Path = LOG_PATH, **kw) -> list[dict]:
    added = update_games(today, **kw)
    rows = npl.load_log(kw.get("path", GAMES))
    live = load_live(live_path)
    res = evaluate(rows, live)
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    adopted = [r for r in res if r["decision"] == "adopt"]
    if adopted:
        doc = json.loads(live_path.read_text(encoding="utf-8")) if live_path.exists() else {}
        for r in adopted:
            doc[r["family"]] = {**r["adopt"], "adopted": stamp, "n_fit": r["n_fit"]}
        live_path.parent.mkdir(parents=True, exist_ok=True)
        live_path.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({"at": stamp, "games": len(rows), "added": added, "results": res}, sort_keys=True) + "\n")
    return res


if __name__ == "__main__":
    for r in run(datetime.now(UTC).date()):
        print(f"  {r['family']:6} {r['decision']:5} fit {r['n_fit']} / held out {r['n_holdout']}"
              f"  live {r['live']}  refit {r.get('refit')}  {r.get('reason', '')}")
