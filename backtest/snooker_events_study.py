"""
Snooker events study (framework #590, Event models #11; RECORD ONLY). Writes backtest/SNOOKER_EVENTS_STUDY.md.

Question: does the frame ladder in engine/snooker_events.py (board Elo win chance -> per-frame chance -> exact score
distribution) beat the plain climatology of earlier matches of the same format at (a) the exact frame score (correct
score, from the Elo favourite's side) and (b) every total-frames half-line the format can settle?

Data: data/snooker/results.json (World Snooker Tour draws, 2019-26). Centuries: PENDING, no per-frame break record is stored.
No free historical correct-score / total prices exist, so this measures accuracy, not return.

Walk-forward, one-matchday purge: a match on day D is predicted from matches dated BEFORE D-1 only (Elo ratings and the
climatology both). Matches share their event's start date, so within-event results are excluded too (stricter than live).
Settings tried (shrink of the Elo chance toward 0.5: 1.0 / 0.9 / 0.8 / 0.7) are counted and picked on matches before the
split; only matches from the split on are reported. Baseline = the favourite-side score frequencies of earlier matches of
the same format (+0.5 smoothing) and the earlier share over each line (+1/+2). Nothing here changes a pick, stake or threshold.

  python backtest/snooker_events_study.py
"""
from __future__ import annotations

import math
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import results_walkforward as wf  # noqa: E402
from backtest import snooker_backtest as sb  # noqa: E402
from engine import multisport as ms  # noqa: E402
from engine import snooker_events as se  # noqa: E402

OUT = ROOT / "backtest" / "SNOOKER_EVENTS_STUDY.md"
SPLIT = sb.SPLIT
SHRINK = (1.0, 0.9, 0.8, 0.7)
MIN_FORMAT = 100
EPS = 1e-4


def ll(p: float, y: int) -> float:
    p = min(1 - EPS, max(EPS, p))
    return -math.log(p if y else 1 - p)


def matches(rows: list[dict]) -> list[dict]:
    out = []
    for r in sorted(rows, key=lambda x: x["kickoff_utc"]):
        h, a = ms.norm(r["home"]), ms.norm(r["away"])
        hf, af = r.get("home_frames"), r.get("away_frames")
        if not h or not a or h == a or hf is None or af is None or hf == af:
            continue
        first = h < a
        fa, fb = (hf, af) if first else (af, hf)
        out.append({"day": date.fromisoformat(r["date"]), "a": min(h, a), "b": max(h, a), "t": max(hf, af),
                    "fa": fa, "fb": fb, "y": 1.0 if fa > fb else 0.0})
    return out


def run(rows: list[dict], shrinks: tuple[float, ...] = SHRINK, min_format: int = MIN_FORMAT) -> dict:
    """Walk-forward. Per shrink: per-match score / totals log losses (ladder vs climatology) and the over-chance pairs."""
    g = matches(rows)
    elo: dict[str, float] = {}
    cnt: dict[str, int] = {}
    hist: dict[int, list[tuple[int, int]]] = {}     # format -> favourite-side frames of purged-in matches
    ptr = 0
    pend: list[tuple[date, dict, tuple[int, int] | None]] = []   # processed matches waiting to become visible
    res = {s: {"rows": [], "cal": []} for s in shrinks}
    k, mg = ms.ELO_K, ms.MIN_GAMES
    for x in g:
        cutoff = x["day"] - timedelta(days=1)        # only matches dated before D-1 are visible
        while ptr < len(pend) and pend[ptr][0] < cutoff:
            _, m, orient = pend[ptr]
            ra, rb = elo.get(m["a"], wf.ELO_START), elo.get(m["b"], wf.ELO_START)
            e = 1 / (1 + 10 ** ((rb - ra) / 400))
            d = k * (m["y"] - e)
            elo[m["a"]], elo[m["b"]] = ra + d, rb - d
            cnt[m["a"]], cnt[m["b"]] = cnt.get(m["a"], 0) + 1, cnt.get(m["b"], 0) + 1
            if orient:
                hist.setdefault(m["t"], []).append(orient)
            ptr += 1
        ra, rb = elo.get(x["a"], wf.ELO_START), elo.get(x["b"], wf.ELO_START)
        p = 1 / (1 + 10 ** ((rb - ra) / 400)) if cnt.get(x["a"], 0) >= mg and cnt.get(x["b"], 0) >= mg else None
        orient = None
        if p is not None:
            orient = (x["fa"], x["fb"]) if p >= 0.5 else (x["fb"], x["fa"])
        h = hist.get(x["t"], [])
        if p is not None and x["t"] >= 4 and len(h) >= min_format:
            n = len(h)
            base_sc = (sum(1 for o in h if o == orient) + 0.5) / (n + 0.5 * 2 * x["t"])
            lines = se.total_lines(x["t"])
            base_over = {ln: (sum(1 for o in h if sum(o) > ln) + 1) / (n + 2) for ln in lines}
            for s in shrinks:
                pr = se.predict(0.5 + s * (max(p, 1 - p) - 0.5), x["t"])
                lm = -math.log(max(pr["score"].get(f"{orient[0]}-{orient[1]}", 0.0), EPS))
                om = ob = 0.0
                for ln in lines:
                    y = 1 if sum(orient) > ln else 0
                    om += ll(pr["total_over"][str(ln)], y)
                    ob += ll(base_over[ln], y)
                    res[s]["cal"].append((pr["total_over"][str(ln)], y))
                res[s]["rows"].append({"day": x["day"].isoformat(), "t": x["t"], "sc_m": lm, "sc_b": -math.log(base_sc),
                                       "tot_m": om / len(lines), "tot_b": ob / len(lines)})
        pend.append((x["day"], x, orient))
    return res


def summarise(rows: list[dict], a: str, b: str) -> tuple[float, float, float, int]:
    """(mean a, mean b, standard error of the mean of b - a, n)."""
    n = len(rows)
    if not n:
        return 0.0, 0.0, 0.0, 0
    d = [r[b] - r[a] for r in rows]
    m = sum(d) / n
    sd = math.sqrt(sum((v - m) ** 2 for v in d) / max(n - 1, 1))
    return sum(r[a] for r in rows) / n, sum(r[b] for r in rows) / n, sd / math.sqrt(n), n


def render(rows: list[dict], now: datetime) -> str:
    L = ["# Snooker events study (correct score, total frames; centuries PENDING)", "",
         f"Made {now:%Y-%m-%d %H:%M} UTC by `backtest/snooker_events_study.py` (framework #590). Record only, a shadow; "
         "no price in the source, so accuracy not edge.", ""]
    if not rows:
        return "\n".join(L + ["NO DATA - PENDING (run `python data/snooker_results.py`).", ""])
    res = run(rows)
    tune = {s: [r for r in v["rows"] if r["day"] < SPLIT] for s, v in res.items()}
    if not any(tune.values()):
        return "\n".join(L + ["No tuning-period match with enough history - PENDING.", ""])
    best = min(SHRINK, key=lambda s: summarise(tune[s], "sc_m", "sc_b")[0] if tune[s] else 9e9)
    held = [r for r in res[best]["rows"] if r["day"] >= SPLIT]
    L += [f"Settings tried: **{len(SHRINK)}** (Elo shrink {', '.join(str(s) for s in SHRINK)}); chosen on matches before {SPLIT}: "
          f"**{best}**. Held-out matches from {SPLIT}: **{len(held)}** (" +
          ", ".join(f"first-to-{t}: {sum(1 for r in held if r['t'] == t)}" for t in sorted({r['t'] for r in held})) + ").", "",
          "| Event | Ladder log loss | Climatology log loss | Gain (base - ladder) | s.e. |", "|---|---|---|---|---|"]
    for name, a, b in (("Exact frame score (favourite side)", "sc_m", "sc_b"), ("Total frames over, every line", "tot_m", "tot_b")):
        m, bs, sem, _ = summarise(held, a, b)
        L.append(f"| {name} | {m:.4f} | {bs:.4f} | {bs - m:+.4f} | {sem:.4f} |")
    L += ["", "Calibration of the total-frames over chance (all lines, tuning and held-out pooled, chosen shrink):", "",
          "| Predicted | Cases | Happened |", "|---|---|---|"]
    cal = res[best]["cal"]
    for lo in (0.0, 0.2, 0.4, 0.6, 0.8):
        c = [y for pm, y in cal if lo <= pm < lo + 0.2 or (lo == 0.8 and pm >= 1.0)]
        if c:
            L.append(f"| {lo:.1f}-{lo + 0.2:.1f} | {len(c)} | {sum(c) / len(c):.3f} |")
    L += ["", "Centuries: **PENDING** (HR35). No per-frame break record is stored in the framework; cuetracker.net / snooker.org "
          "would need a scraper and a graded century count before a model can be tested.", "",
          "## Reading", "",
          "- A positive gain means the ladder (Elo win chance spread over frames) beats repeating how earlier matches of "
          "that length finished; a gain within about 2 s.e. of zero is no proof either way.",
          "- Formats are read from the winner's frame count, so a retirement or walkover is filed under a shorter format (a known blur).",
          "- Record only: nothing here changes a stake, a bar, a threshold or the live switch.", ""]
    return "\n".join(L)


def main(now: datetime | None = None) -> str:
    text = render(sb.load(), now or datetime.now(UTC))
    OUT.write_text(text, encoding="utf-8")
    return text


if __name__ == "__main__":
    print(main())
