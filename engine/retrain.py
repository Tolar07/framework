"""
NIGHTLY RETRAIN — the model's chances refitted on every graded game
(Architect 2026-10-20: "auto" — refit on every graded game, including the
matches we never bet on, and go live by itself when it beats the current
model on games it was not fitted on; no /approve step).

Data: every rated fixture in the picks ledger (output/picks/picks_<day>.json,
"rated") whose source is the model ("src" == "model"; market-implied rows carry
the bookmaker's numbers, not the model's) and whose full-time score is graded.
That is every fixture the board rated, picked or not. Each row's "p" is the
model's RAW chance (the scoreline grid, before engine/calibration.py and before
any learned shift), so it is what the calibration maps from.

Universe games (data/universe/) carry prices and results but no model chance,
so they cannot calibrate the model and are not used here.

Families: the ones engine/calibration.py applies and the ledger stores a raw
chance for — BTTS and match-total Over 1.5 / 2.5 / 3.5. Over 4.5 (no stored raw
chance) and 1X2 / double chance / handicaps (never calibrated) are unchanged.

Method, per family:
  1. rows sorted by kickoff; the newest ~20% (whole days) is the HOLDOUT, the
     rest the FIT set. The fit never sees a holdout row.
  2. Platt fit (calibrated = sigmoid(A + B * logit(raw))) on the fit set, pulled
     gently toward the live A, B (PRIOR_WEIGHT) so a few days' noise can't swing it.
  3. GATE: three candidates on the holdout — the LIVE calibration, the REFIT
     and NO CALIBRATION (the raw model chance: A = 0, B = 1, the identity;
     Architect's "auto" rule: adopt whatever predicts best out of sample).
     A challenger goes live only if fit n >= MIN_FIT and holdout n >=
     MIN_HOLDOUT and it beats the live calibration on BOTH holdout Brier and
     log loss (the refit also needs B > 0: a higher raw chance never reads
     lower). If both challengers qualify, the one better on both wins; if they
     split, the lower Brier. Otherwise the live one stays.
Each night's comparison is appended to memory/retrain_log.jsonl; adopted
parameters are written to memory/calibration_live.json, which
engine/calibration.py reads. Chances only — stakes, gates and leagues untouched.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from engine import calibration as cal
from engine.picks_ledger import _outcomes

ROOT = Path(__file__).resolve().parent.parent
PICKS_DIR = ROOT / "output" / "picks"
LOG_PATH = ROOT / "memory" / "retrain_log.jsonl"

# family -> index into a rated row's "p" (and _outcomes): see picks_ledger.RATED_KEYS
FAMILIES = {"btts": 6, "over_1.5": 3, "over_2.5": 4, "over_3.5": 5}
LABEL = {"btts": "BTTS", "over_1.5": "Over 1.5", "over_2.5": "Over 2.5", "over_3.5": "Over 3.5"}
HOLDOUT_FRAC = 0.20
MIN_FIT = 200
MIN_HOLDOUT = 50
PRIOR_WEIGHT = 5.0     # L2 pull toward the live (A, B), in log-likelihood units
RAW = (0.0, 1.0)       # no calibration: sigmoid(0 + 1 * logit(p)) = p


def load_rows(picks_dir: Path = PICKS_DIR) -> list[dict]:
    """Every graded model-rated fixture, one row per match (kickoff, home, away).
    A match on two days' ledgers is kept once (the later file's copy)."""
    seen: dict[tuple, dict] = {}
    for f in sorted(picks_dir.glob("picks_*.json")):
        try:
            doc = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for r in doc.get("rated", []) or []:
            if r.get("src") != "model":
                continue
            y = _outcomes(r.get("ft"))
            p = r.get("p")
            if y is None or not isinstance(p, list) or len(p) < 7:
                continue
            day = str(r.get("kickoff") or doc.get("date") or "")
            if not day:
                continue
            seen[(day, r.get("home"), r.get("away"))] = {"day": day, "p": p, "y": y}
    return sorted(seen.values(), key=lambda r: r["day"])


def split(rows: list[dict], frac: float = HOLDOUT_FRAC) -> tuple[list[dict], list[dict], Optional[str]]:
    """(fit, holdout, first holdout day). Time-ordered, split on a day boundary:
    the holdout is the newest whole days holding at least `frac` of the rows."""
    if not rows:
        return [], [], None
    rows = sorted(rows, key=lambda r: r["day"])
    cut_day = rows[max(0, min(len(rows) - 1, math.floor(len(rows) * (1 - frac))))]["day"]
    fit = [r for r in rows if r["day"] < cut_day]
    hold = [r for r in rows if r["day"] >= cut_day]
    return fit, hold, cut_day


def _logit(p: float) -> float:
    p = min(max(float(p), 1e-4), 1 - 1e-4)
    return math.log(p / (1 - p))


def _sig(z: float) -> float:
    return 1 / (1 + math.exp(-z)) if z >= 0 else math.exp(z) / (1 + math.exp(z))


def fit_platt(xs: list[float], ys: list[int], prior: tuple[float, float],
              weight: float = PRIOR_WEIGHT) -> tuple[float, float]:
    """Penalised maximum likelihood for (A, B) by Newton's method."""
    a0, b0 = prior
    a, b = a0, b0
    zs = [_logit(x) for x in xs]
    for _ in range(50):
        ga, gb = weight * (a - a0), weight * (b - b0)
        haa, hab, hbb = weight, 0.0, weight
        for z, y in zip(zs, ys, strict=True):
            q = _sig(a + b * z)
            ga += q - y
            gb += (q - y) * z
            w = q * (1 - q)
            haa += w
            hab += w * z
            hbb += w * z * z
        det = haa * hbb - hab * hab
        if det <= 1e-12:
            break
        da = (hbb * ga - hab * gb) / det
        db = (haa * gb - hab * ga) / det
        a, b = a - da, b - db
        if abs(da) < 1e-9 and abs(db) < 1e-9:
            break
    return a, b


def scores(xs: list[float], ys: list[int], ab: Optional[tuple[float, float]]) -> tuple[float, float]:
    """(Brier, log loss) of the calibration `ab` (None = raw chance) on (xs, ys)."""
    br = ll = 0.0
    for x, y in zip(xs, ys, strict=True):
        q = min(max(float(x), 1e-4), 1 - 1e-4) if ab is None else _sig(ab[0] + ab[1] * _logit(x))
        q = min(max(q, 1e-6), 1 - 1e-6)
        br += (q - y) ** 2
        ll -= y * math.log(q) + (1 - y) * math.log(1 - q)
    n = max(len(xs), 1)
    return br / n, ll / n


def evaluate(rows: list[dict], live: dict[str, tuple[float, float]]) -> list[dict]:
    """One decision per family. Fitting reads the fit rows only."""
    fit, hold, cut_day = split(rows)
    out = []
    for fam, i in FAMILIES.items():
        old = live[fam]
        rec: dict = {"family": fam, "n_fit": len(fit), "n_holdout": len(hold),
                     "holdout_from": cut_day, "live": [round(old[0], 4), round(old[1], 4)]}
        if len(fit) < MIN_FIT or len(hold) < MIN_HOLDOUT:
            rec.update(decision="keep", reason=f"sample too small (fit {len(fit)} < {MIN_FIT} "
                       f"or holdout {len(hold)} < {MIN_HOLDOUT})")
            out.append(rec)
            continue
        new = fit_platt([r["p"][i] for r in fit], [r["y"][i] for r in fit], old)
        hx, hy = [r["p"][i] for r in hold], [r["y"][i] for r in hold]
        b_old, l_old = scores(hx, hy, old)
        b_new, l_new = scores(hx, hy, new)
        b_raw, l_raw = scores(hx, hy, None)
        rec.update(new=[round(new[0], 4), round(new[1], 4)],
                   brier_live=round(b_old, 5), brier_new=round(b_new, 5), brier_raw=round(b_raw, 5),
                   logloss_live=round(l_old, 5), logloss_new=round(l_new, 5), logloss_raw=round(l_raw, 5))
        refit_ok = math.isfinite(new[0]) and math.isfinite(new[1]) and new[1] > 0
        # challengers that beat the live calibration on BOTH holdout scores
        wins = [(b, ll, name, ab) for b, ll, name, ab in
                ((b_new, l_new, "refit", new), (b_raw, l_raw, "raw", RAW))
                if (name != "refit" or refit_ok) and tuple(ab) != tuple(old) and b < b_old and ll < l_old]
        if wins:
            dom = [w for w in wins if all(w[0] <= o[0] and w[1] <= o[1] for o in wins)]
            b, ll, name, ab = (dom or sorted(wins))[0]
            rec.update(decision="adopt", choice=name, adopt=[round(ab[0], 4), round(ab[1], 4)],
                       brier_after=round(b, 5),
                       reason=("no calibration (raw chance)" if name == "raw" else "refit")
                       + " beats live on holdout Brier and log loss")
        elif not refit_ok:
            rec.update(decision="keep", reason="fit not usable (slope <= 0 or not finite); raw not better")
        else:
            rec.update(decision="keep", reason="neither the refit nor raw chance is better on the holdout")
        out.append(rec)
    return out


def run(picks_dir: Path = PICKS_DIR, live_path: Path = cal.LIVE_PATH,
        log_path: Path = LOG_PATH, now: Optional[datetime] = None) -> dict:
    """Refit, gate, save. Returns {"date", "results", "changed"}."""
    now = now or datetime.now(timezone.utc)
    stamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    live = cal.load_params(live_path)
    results = evaluate(load_rows(picks_dir), live)
    changed = [r for r in results if r["decision"] == "adopt"]
    if changed:
        try:
            doc = json.loads(live_path.read_text(encoding="utf-8"))
            if not isinstance(doc.get("families"), dict):
                doc = {"families": {}}
        except (OSError, ValueError):
            doc = {"families": {}}
        for r in changed:
            doc["families"][r["family"]] = {
                "a": r["adopt"][0], "b": r["adopt"][1], "adopted": stamp, "choice": r["choice"],
                "n_fit": r["n_fit"], "n_holdout": r["n_holdout"],
                "holdout_from": r["holdout_from"],
                "brier_before": r["brier_live"], "brier_after": r["brier_after"]}
        doc["updated"] = stamp
        doc["source"] = "engine/retrain.py (nightly, retrain.yml)"
        live_path.parent.mkdir(parents=True, exist_ok=True)
        live_path.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as fh:
        for r in results:
            fh.write(json.dumps({"at": stamp, **r}, sort_keys=True) + "\n")
    return {"date": stamp[:10], "results": results, "changed": [r["family"] for r in changed]}


def message(summary: dict) -> str:
    """The one Telegram line to the Architect."""
    res = summary["results"]
    if not res:
        return f"Retrain {summary['date']}: NO DATA — PENDING"
    n = f"n {res[0]['n_fit']} fit / {res[0]['n_holdout']} held out"
    parts = []
    for r in res:
        lab = LABEL[r["family"]]
        if "brier_new" not in r:
            parts.append(f"{lab} kept (sample too small)")
        elif r["decision"] == "adopt":
            to = " (no calibration)" if r.get("choice") == "raw" else ""
            parts.append(f"{lab} CHANGED{to} {r['brier_live']:.4f}→{r['brier_after']:.4f}")
        else:
            parts.append(f"{lab} kept ({r['brier_live']:.4f} live vs {r['brier_new']:.4f} new)")
    return f"Retrain {summary['date']} (holdout Brier, {n}): " + " · ".join(parts)
