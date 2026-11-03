"""
LEARNED WEIGHTS — step 3 of the bot-training plan (the Architect, 2026-11-01). RECORDED ONLY.

The verdict panel weights each member by its own Brier (1/Brier), member by member; the AI fact
sheet's facts (engine/fact_sheet.py) are not used at all. Here ONE small model is fitted on the
graded picks and the results decide every weight:

    logit(p) = logit(anchor) + b0 + sum_m b_m * (logit(member_m) - logit(anchor)) + sum_f c_f * x_f

    anchor     the market's de-margined chance the panel starts from
    member_m   each panel member's probability (missing -> its term is 0: no shift)
    x_f        each fact sheet fact, direction * size (+ helps the pick, - hurts it)

Ridge-penalised (L2) so a thin record keeps every weight near 0, i.e. near the market. A weight
that the results don't support stays ~0 by itself — nobody has to switch a member off.

Judged WALK-FORWARD: each date is predicted by a model fitted only on the dates before it, so the
Brier it reports is out of sample. "beats_market" needs MIN_N such predictions and a Brier at least
MARGIN under the anchor's on the same picks. Until then (and even then — promotion is a separate
decision) the weights change nothing.

    python -m engine.learned_weights          # fit + print
"""
from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from engine import fact_sheet as FS
from engine import verdict_panel as VP

ROOT = Path(__file__).parent.parent
RECORD = ROOT / "memory" / "learned_weights.json"
MEMBERS = list(VP.MEMBERS)
RIDGE = 4.0                # L2 strength: weights need evidence to move off 0
MIN_TRAIN = 40             # graded rows before a walk-forward fit is attempted
MIN_N = 60                 # out-of-sample predictions before "beats_market" can be true
MARGIN = 0.002             # Brier points under the anchor
RECHECK_N = 300            # out-of-sample rows at which the bias-only v full-model read is re-checked


def _logit(p: float) -> float:
    p = min(max(p, 0.01), 0.99)
    return math.log(p / (1 - p))


def _sig(z: np.ndarray) -> np.ndarray:
    return 1 / (1 + np.exp(-z))


def _split_id(rid: str) -> tuple[str, str, str, str]:
    """(domain, date, fixture, market) from a panel row id 'domain|date|fixture|market...|stage'."""
    parts = rid.split("|")
    return parts[0], parts[1], parts[2], "|".join(parts[3:-1])


def fact_index(out_dir: Path = FS.OUT_DIR) -> dict:
    """{(date, fixture, market): {fact (sign): direction*size}} from every fact sheet."""
    idx: dict = {}
    for f in sorted(out_dir.glob("facts_*.json")):
        try:
            doc = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for p in doc.get("picks") or []:
            row: dict = {}
            for x in p.get("facts") or []:
                if x.get("direction"):
                    row[x["fact"]] = row.get(x["fact"], 0.0) + x["direction"] * float(x.get("size") or 0)
            idx[(doc.get("date"), p.get("fixture"), p.get("market"))] = row
    return idx


def rows(history: list[dict], facts: dict) -> list[dict]:
    out = []
    for r in history:
        a = r.get("anchor")
        if a is None or r.get("won") is None or (r.get("stage") or "board") != "board":
            continue
        _, date, fixture, market = _split_id(str(r.get("id") or ""))
        out.append({"date": r.get("date") or date, "anchor": float(a), "won": bool(r["won"]),
                    "members": r.get("members") or {}, "facts": facts.get((date, fixture, market)) or {},
                    "panel_prob": r.get("panel_prob")})
    return sorted(out, key=lambda x: x["date"])


def design(rs: list[dict], fact_names: list[str]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """X (bias, member shifts, facts), offset = logit(anchor), y."""
    X = np.zeros((len(rs), 1 + len(MEMBERS) + len(fact_names)))
    off = np.zeros(len(rs))
    y = np.zeros(len(rs))
    for i, r in enumerate(rs):
        la = _logit(r["anchor"])
        off[i], y[i] = la, float(r["won"])
        X[i, 0] = 1.0
        for j, m in enumerate(MEMBERS):
            v = r["members"].get(m)
            if v is not None:
                X[i, 1 + j] = _logit(float(v)) - la
        for k, f in enumerate(fact_names):
            X[i, 1 + len(MEMBERS) + k] = r["facts"].get(f, 0.0)
    return X, off, y


def fit(X: np.ndarray, off: np.ndarray, y: np.ndarray, ridge: float = RIDGE, iters: int = 50) -> np.ndarray:
    """Ridge logistic regression with an offset (Newton). All weights start, and are pulled, to 0."""
    w = np.zeros(X.shape[1])
    lam = np.full(X.shape[1], ridge)
    for _ in range(iters):
        p = _sig(off + X @ w)
        g = X.T @ (p - y) + lam * w
        H = (X * (p * (1 - p))[:, None]).T @ X + np.diag(lam)
        step = np.linalg.solve(H, g)
        w -= step
        if np.max(np.abs(step)) < 1e-6:
            break
    return w


def predict(X: np.ndarray, off: np.ndarray, w: np.ndarray) -> np.ndarray:
    return _sig(off + X @ w)


def walk_forward(rs: list[dict], fact_names: list[str], bias_only: bool = False) -> dict:
    """Each date predicted from a fit on the dates before it -> out-of-sample Brier v the anchor.

    bias_only: only the global shift b0 is fitted (member and fact columns zeroed, so their weights
    stay 0): the shadow that shows how much of the gain is calibration and how much is the panel."""
    dates = sorted({r["date"] for r in rs})
    pl, al, pp, n = 0.0, 0.0, 0.0, 0
    pn = 0
    for d in dates:
        train = [r for r in rs if r["date"] < d]
        test = [r for r in rs if r["date"] == d]
        if len(train) < MIN_TRAIN:
            continue
        Xtr, otr, ytr = design(train, fact_names)
        Xt, ot, yt = design(test, fact_names)
        if bias_only:
            Xtr, Xt = Xtr.copy(), Xt.copy()
            Xtr[:, 1:] = 0.0
            Xt[:, 1:] = 0.0
        w = fit(Xtr, otr, ytr)
        p = predict(Xt, ot, w)
        pl += float(np.sum((p - yt) ** 2))
        al += float(np.sum((_sig(ot) - yt) ** 2))
        for r in test:
            if r.get("panel_prob") is not None:
                pp += (float(r["panel_prob"]) - float(r["won"])) ** 2
                pn += 1
        n += len(test)
    if not n:
        return {"n": 0}
    out = {"n": n, "learned_brier": round(pl / n, 4), "market_brier": round(al / n, 4)}
    if pn == n:
        out["panel_brier"] = round(pp / n, 4)
    out["beats_market"] = bool(n >= MIN_N and out["learned_brier"] + MARGIN <= out["market_brier"])
    return out


def build(history: list[dict] | None = None, facts: dict | None = None) -> dict:
    history = history if history is not None else (VP.load_record().get("history") or [])
    facts = facts if facts is not None else fact_index()
    rs = rows(history, facts)
    fact_names = sorted({f for r in rs for f in r["facts"]})
    out: dict = {"built_at": datetime.now(UTC).isoformat(timespec="seconds"), "recorded_only": True,
                 "rows": len(rs), "ridge": RIDGE}
    if len(rs) < MIN_TRAIN:
        out["note"] = f"{len(rs)} graded rows, a fit needs {MIN_TRAIN}: every weight stays 0 (the market)"
        out["weights"] = {}
        out["walk_forward"] = {"n": 0}
        return out
    w = fit(*design(rs, fact_names))
    names = ["bias"] + [f"member:{m}" for m in MEMBERS] + [f"fact:{f}" for f in fact_names]
    cover = {f"member:{m}": sum(1 for r in rs if r["members"].get(m) is not None) for m in MEMBERS}
    cover.update({f"fact:{f}": sum(1 for r in rs if f in r["facts"]) for f in fact_names})
    out["weights"] = {k: {"w": round(float(v), 4), "rows": cover.get(k, len(rs))} for k, v in zip(names, w, strict=True)}
    out["walk_forward"] = walk_forward(rs, fact_names)
    out["bias_only_walk_forward"] = bias_only = walk_forward(rs, fact_names, bias_only=True)
    out["attribution"] = attribution(out["walk_forward"], bias_only)
    return out


def attribution(full: dict, bias_only: dict) -> dict:
    """Split the out-of-sample gain over the market into the bias part and the member/fact part.

    PENDING (HR35) while either walk-forward has no rows. Recorded only: promotion is the Architect's."""
    if not full.get("n") or not bias_only.get("n"):
        return {"status": "PENDING"}
    gain = full["market_brier"] - full["learned_brier"]
    bias_gain = bias_only["market_brier"] - bias_only["learned_brier"]
    return {"status": "OK", "n": full["n"], "total_gain": round(gain, 4), "bias_gain": round(bias_gain, 4),
            "panel_gain": round(gain - bias_gain, 4), "mostly_bias": bool(bias_gain >= 0.5 * gain > 0),
            "recheck_at": RECHECK_N, "recheck_ready": bool(full["n"] >= RECHECK_N)}


def _attr_text(a: dict) -> str:
    if a.get("status") != "OK":
        return ""
    return (f" · gain {a['total_gain']:+.4f} = bias {a['bias_gain']:+.4f} + panel {a['panel_gain']:+.4f}"
            + (" (re-check due)" if a["recheck_ready"] else f" (re-check at {a['recheck_at']})"))


def summary_line(rec: dict) -> str:
    wf = rec.get("walk_forward") or {}
    if not wf.get("n"):
        return f"learned weights: {rec.get('note') or 'no out-of-sample days yet'}"
    top = sorted(((k, v) for k, v in (rec.get("weights") or {}).items() if k != "bias"),
                 key=lambda kv: -abs(kv[1]["w"]))[:3]
    return (f"learned weights: out of sample n{wf['n']} Brier {wf['learned_brier']} v market {wf['market_brier']}"
            + (f" v panel {wf['panel_brier']}" if "panel_brier" in wf else "")
            + (" · BEATS the market" if wf.get("beats_market") else " · not better than the market yet")
            + _attr_text(rec.get("attribution") or {})
            + f" · bias {(rec.get('weights') or {}).get('bias', {}).get('w', 0):+.2f}"
            + (" · " + ", ".join(f"{k} {v['w']:+.2f}" for k, v in top) if top else ""))


if __name__ == "__main__":
    r = build()
    print(summary_line(r))
    print(json.dumps(r["weights"], indent=1))
