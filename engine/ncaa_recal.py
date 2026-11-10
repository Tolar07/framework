"""
NCAA NIGHTLY RECALIBRATION (framework#395; the twin of engine/nba_recal.py, Architect 2026-11-06: basketball
inherits the NBA). RECORDED ONLY.

engine/ncaa_lines.py prices SportyBet's NCAA men's sides from ESPN's sharp line with shapes fitted last season
(backtest/NCAA_STUDY.md): total = Normal(line + TOTAL_BIAS, TOTAL_SD), handicap = Normal(-spread + MARGIN_BIAS,
MARGIN_SD), 1st half = Normal(H1_SHARE x line, H1_SD). Every night this refits those widths / biases / share on
THIS season's graded games (ESPN final + half-time score beside the pre-tip line, kept in
data/ncaa_graded/games.jsonl, incremental) and adopts the refit only if it predicts the held-out newest ~20% of
days better on BOTH the normal log-likelihood and the Brier score of yes/no lines at the centre and 5 points
either side (the engine/nba_recal.py gate). The adopted numbers go to memory/ncaa_calibration_live.json and each
night's comparison to memory/ncaa_retrain_log.jsonl.

It changes NOTHING in picks: engine/ncaa_lines.py keeps its fixed constants. Wiring the adopted numbers in needs
the Architect's OK. Too few games = "too few games" (PENDING, HR35), never a guess.
"""
from __future__ import annotations

import json
import math
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "backtest")]

from engine import ncaa_lines as nl  # noqa: E402

DIR = ROOT / "data" / "ncaa_graded"
GAMES = DIR / "games.jsonl"
META = DIR / "meta.json"
LIVE_PATH = ROOT / "memory" / "ncaa_calibration_live.json"
LOG_PATH = ROOT / "memory" / "ncaa_retrain_log.jsonl"
HOLDOUT_FRAC = 0.2
MIN_FIT, MIN_HOLDOUT = 300, 75
PRIOR_GAMES = 200
LINE_OFFSETS = (-5.0, 0.0, 5.0)
MAX_DAYS_PER_RUN = 14                                   # bounds the first catch-up; the rest follows nightly

FIXED = {"total": {"share": 1.0, "bias": nl.TOTAL_BIAS, "sd": nl.TOTAL_SD},
         "margin": {"share": 1.0, "bias": nl.MARGIN_BIAS, "sd": nl.MARGIN_SD},
         "h1": {"share": nl.H1_SHARE, "bias": 0.0, "sd": nl.H1_SD}}


def season_start(today: date) -> date:
    return date(today.year if today.month >= 11 else today.year - 1, 11, 1)


def load(path: Path = GAMES) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def _default_scoreboard(d: date) -> list[dict]:
    import ncaa_study as st
    return st.games_on(d)


def _default_line(g: dict) -> dict | None:
    return nl.line(g)


def update_games(today: date, scoreboard=_default_scoreboard, line=_default_line,
                 path: Path = GAMES, meta: Path = META) -> int:
    """Append finished games that had a pre-tip sharp line (total + spread), up to yesterday."""
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
        for g in scoreboard(d):
            if g["id"] in have:
                continue
            ln = line(g)
            if not ln or ln.get("total") is None or ln.get("spread") is None:
                continue                                  # no sharp line: not gradable
            new.append({"g": g["id"], "day": d.isoformat(), "hs": g["hs"], "as": g["as"],
                        "h1": g.get("h1"), "ot": bool(g.get("ot")), "line": ln["total"], "spread": ln["spread"],
                        "ml_home": ln.get("ml_home"), "ml_away": ln.get("ml_away")})
        through = d
        d += timedelta(1)
    if new:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as fh:
            for r in new:
                fh.write(json.dumps(r, sort_keys=True) + "\n")
    if through:
        meta.parent.mkdir(parents=True, exist_ok=True)
        meta.write_text(json.dumps({"season": start.isoformat(), "through": through.isoformat()}) + "\n",
                        encoding="utf-8", newline="\n")
    return len(new)


def pairs(rows: list[dict], fam: str) -> list[tuple[float, float]]:
    """(base, actual): the sharp number the family's mean is built on, and what happened."""
    if fam == "margin":
        return [(-r["spread"], r["hs"] - r["as"]) for r in rows]
    if fam == "h1":
        return [(r["line"], r["h1"]) for r in rows if r.get("h1") and not r.get("ot")]
    return [(r["line"], r["hs"] + r["as"]) for r in rows]


def fit(xy: list[tuple[float, float]], fam: str, live: dict) -> dict:
    n = len(xy)
    mb = sum(b for b, _a in xy) / n
    if fam == "h1":
        share = (sum(a for _b, a in xy) + PRIOR_GAMES * live["share"] * mb) / (sum(b for b, _a in xy) + PRIOR_GAMES * mb)
        bias = 0.0
    else:
        share = 1.0
        bias = (sum(a - b for b, a in xy) + PRIOR_GAMES * live["bias"]) / (n + PRIOR_GAMES)
    ms = sum((a - share * b - bias) ** 2 for b, a in xy)
    sd = math.sqrt((ms + PRIOR_GAMES * live["sd"] ** 2) / (n + PRIOR_GAMES))
    return {"share": round(share, 4), "bias": round(bias, 3), "sd": round(sd, 3)}


def _mean(b: float, p: dict) -> float:
    return p["share"] * b + p["bias"]


def nll(xy: list[tuple[float, float]], p: dict) -> float:
    return sum(0.5 * ((a - _mean(b, p)) / p["sd"]) ** 2 + math.log(p["sd"] * math.sqrt(2 * math.pi))
               for b, a in xy) / len(xy)


def brier(xy: list[tuple[float, float]], p: dict) -> float:
    tot, n = 0.0, 0
    for b, a in xy:
        mu = _mean(b, p)
        for off in LINE_OFFSETS:
            ln = math.floor(mu) + 0.5 + off
            pr = 1 - nl._phi((ln - mu) / p["sd"])
            tot += (pr - (1.0 if a > ln else 0.0)) ** 2
            n += 1
    return tot / n


def split(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """The newest ~20% of whole days is the holdout; nothing is fitted on it."""
    days = sorted({r["day"] for r in rows})
    cut = days[-max(1, round(len(days) * HOLDOUT_FRAC))] if days else ""
    return [r for r in rows if r["day"] < cut], [r for r in rows if r["day"] >= cut]


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
    rows = load(kw.get("path", GAMES))
    res = evaluate(rows, load_live(live_path))
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
