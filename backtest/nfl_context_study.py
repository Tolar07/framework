"""
NFL context study: does anything beat the closing price? (framework#339, record-only SHADOW; refs #352, #373.)

The Elo blend loses to the NFL close (AMERICAN_FOOTBALL_STUDY.md). This asks a narrower question the practitioner
videos raise: does a SMALL correction ON TOP of the closing price, learned only from earlier games, carry information
the price lacks? Features (nflverse games.csv, free): rest-day difference, a starting-QB change for either side (the
QB id differs from that team's previous game), divisional game, and a margin-of-victory Elo difference (a margin
rating, unlike the live win/loss Elo). The candidate is an online logistic correction:

    p = sigmoid( logit(devigged closing fair price) + w . x )      w starts at 0, learned game by game, L2-shrunk

so with no signal it stays equal to the price. Replayed in date order; each game sees only earlier games (no
peeking). Every setting tried (learning rate) is counted; the best is chosen on 2008-2015 and reported on 2016+ only.
Score: log loss and Brier against the closing price, plus the return of backing a side the candidate rates >= 2 pts
above the price at the closing price, 2% commission. Missing columns/thin data read PENDING (HR35).
Record only: nothing here changes a pick rule, stake, bar, threshold or the live switch.

  python backtest/nfl_context_study.py      writes backtest/NFL_CONTEXT_STUDY.md
"""
from __future__ import annotations

import csv
import io
import math
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "backtest" / "NFL_CONTEXT_STUDY.md"
URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
COMMISSION, EDGE = 0.02, 0.02
TUNE = (2008, 2015)
WARMUP_SEASON = 2008          # 2006-07 only teach the ratings / QB history
LRS = (0.002, 0.005, 0.01)
L2 = 0.0005
MOV_K, MOV_HOME = 20.0, 48.0
FEATURES = ("rest_diff", "home_qb_new", "away_qb_new", "division", "mov_elo_diff")


def a2d(ml: float) -> float:
    return 1 + (ml / 100 if ml > 0 else 100 / -ml)


def _f(row: dict, key: str) -> float | None:
    try:
        return float(row[key])
    except (KeyError, ValueError, TypeError):
        return None


def load(text: str | None = None) -> list[dict]:
    if text is None:
        req = urllib.request.Request(URL, headers={"User-Agent": "olp-xdv-backtest"})
        with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310 (fixed https URL)
            text = r.read().decode("utf-8")
    out = []
    for row in csv.DictReader(io.StringIO(text)):
        try:
            season, hs, as_ = int(row["season"]), int(row["home_score"]), int(row["away_score"])
        except (KeyError, ValueError):
            continue
        out.append({"season": season, "day": row.get("gameday", ""), "home": row.get("home_team", ""),
                    "away": row.get("away_team", ""), "hs": hs, "as": as_,
                    "hml": _f(row, "home_moneyline"), "aml": _f(row, "away_moneyline"),
                    "hrest": _f(row, "home_rest"), "arest": _f(row, "away_rest"),
                    "hqb": row.get("home_qb_id") or None, "aqb": row.get("away_qb_id") or None,
                    "div": row.get("div_game") == "1"})
    out.sort(key=lambda g: (g["day"], g["home"]))
    return out


def sig(x: float) -> float:
    return 1 / (1 + math.exp(-max(-30.0, min(30.0, x))))


def replay(games: list[dict], lr: float) -> tuple[list[dict], list[float]]:
    """One record per priced game, in date order. Features use only earlier games; then the game is learned."""
    rating: dict[str, float] = {}
    last_qb: dict[str, str] = {}
    w = [0.0] * len(FEATURES)
    out = []
    for g in games:
        h, a = g["home"], g["away"]
        rh, ra = rating.get(h, 1500.0), rating.get(a, 1500.0)
        x = [((g["hrest"] - g["arest"]) / 4 if g["hrest"] is not None and g["arest"] is not None else 0.0),
             1.0 if g["hqb"] and last_qb.get(h) not in (None, g["hqb"]) else 0.0,
             1.0 if g["aqb"] and last_qb.get(a) not in (None, g["aqb"]) else 0.0,
             1.0 if g["div"] else 0.0,
             (rh - ra + MOV_HOME) / 400]
        margin = g["hs"] - g["as"]
        if margin != 0 and g["hml"] and g["aml"] and g["season"] >= WARMUP_SEASON:
            dh, da = a2d(g["hml"]), a2d(g["aml"])
            ih, ia = 1 / dh, 1 / da
            fair = ih / (ih + ia)
            q = sig(math.log(fair / (1 - fair)) + sum(wi * xi for wi, xi in zip(w, x, strict=True)))
            y = 1.0 if margin > 0 else 0.0
            out.append({"season": g["season"], "y": y, "fair": fair, "q": q, "dh": dh, "da": da})
            err = y - q                                   # gradient of log loss on the correction
            for i in range(len(w)):
                w[i] += lr * (err * x[i] - L2 * w[i])
        # learn the margin Elo (every game) and the QB history
        e = 1 / (1 + 10 ** ((ra - rh - MOV_HOME) / 400))
        res = 1.0 if margin > 0 else 0.0 if margin < 0 else 0.5
        mult = math.log(abs(margin) + 1) * 0.6 + 0.4
        rating[h], rating[a] = rh + MOV_K * mult * (res - e), ra - MOV_K * mult * (res - e)
        if g["hqb"]:
            last_qb[h] = g["hqb"]
        if g["aqb"]:
            last_qb[a] = g["aqb"]
    return out, w


def score(rows: list[dict], seasons: tuple[int, int]) -> dict:
    ll_q = ll_f = br_q = br_f = 0.0
    n = bets = won = 0
    pnl = 0.0
    for r in rows:
        if not seasons[0] <= r["season"] <= seasons[1]:
            continue
        n += 1
        y, q, f = r["y"], min(max(r["q"], 1e-6), 1 - 1e-6), r["fair"]
        ll_q += -(y * math.log(q) + (1 - y) * math.log(1 - q))
        ll_f += -(y * math.log(f) + (1 - y) * math.log(1 - f))
        br_q += (q - y) ** 2
        br_f += (f - y) ** 2
        for p, fair, dec, win in ((q, f, r["dh"], y == 1), (1 - q, 1 - f, r["da"], y == 0)):
            if p - fair >= EDGE and p * dec > 1:
                bets += 1
                if win:
                    won += 1
                    pnl += (dec - 1) * (1 - COMMISSION)
                else:
                    pnl -= 1
    if not n:
        return {"n": 0}
    return {"n": n, "ll": ll_q / n, "ll_mkt": ll_f / n, "br": br_q / n, "br_mkt": br_f / n,
            "bets": bets, "won": won, "roi": pnl / bets if bets else None}


def run(games: list[dict]) -> str:
    made = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    usable = [g for g in games if g["hml"] and g["aml"] and g["season"] >= WARMUP_SEASON]
    head = ["# NFL context study: a learned correction on the closing price", "",
            f"Made {made} by `backtest/nfl_context_study.py` (framework#339, record-only shadow)."]
    if len(usable) < 1500:
        return "\n".join(head + ["", f"PENDING: only {len(usable)} games with closing prices (need 1500)."]) + "\n"
    last = max(g["season"] for g in games)
    test = (TUNE[1] + 1, last)
    tuned = []
    for lr in LRS:
        rows, w = replay(games, lr)
        tuned.append((lr, rows, w, score(rows, TUNE)))
    lr, rows, w, tune = min(tuned, key=lambda t: t[3]["ll"] - t[3]["ll_mkt"])
    held = score(rows, test)
    if not held["n"]:
        return "\n".join(head + ["", "PENDING: no held-out games."]) + "\n"

    def pct(x):
        return "-" if x is None else f"{x * 100:+.1f}%"

    d_ll = held["ll"] - held["ll_mkt"]
    L = head + [
        f"{len(usable)} NFL games {WARMUP_SEASON}-{last}. Settings tried: **{len(LRS)}** (learning rate); chosen on "
        f"{TUNE[0]}-{TUNE[1]} (rate {lr}), reported on **{test[0]}-{test[1]} only**. Bets at the closing price, "
        f"{COMMISSION:.0%} commission, edge >= {EDGE * 100:.0f} pts.", "",
        "| Held-out seasons | Games | Log loss | Log loss closing price | Brier | Brier closing price | Bets | Won "
        "| Return/bet |",
        "|---|---|---|---|---|---|---|---|---|",
        f"| Price + learned correction | {held['n']} | {held['ll']:.4f} | {held['ll_mkt']:.4f} | {held['br']:.4f} | "
        f"{held['br_mkt']:.4f} | {held['bets']} | {held['won']} | {pct(held['roi'])} |", "",
        "Learned weights at the end (logit points per unit): "
        + ", ".join(f"{n} {v:+.3f}" for n, v in zip(FEATURES, w, strict=True)), "", "## Reading", "",
        f"- Accuracy: log loss {'BELOW' if d_ll < 0 else 'ABOVE'} the closing price by {abs(d_ll):.4f} "
        + ("(the correction adds a little information; confirm on the shadow record before trusting it)."
           if d_ll < 0 else "(the closing price already holds what rest, QB changes, division and a margin rating "
           "say; leave the price alone)."),
        "- Return at the closing price is a hard test; CLV against the exchange close on the shadow record decides.",
        f"- {len(LRS)} settings tried; the held-out line is the honest one. Record only: nothing here changes a "
        "stake, bar, threshold or the live switch."]
    return "\n".join(L) + "\n"


def main() -> int:
    text = run(load())
    OUT.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
