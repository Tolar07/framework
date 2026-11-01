"""
MODEL SIDES STUDY — every side of every market, on paper, at the framework's own chance.

Architect 2026-11-01 07:55 ("Yes, do the same for all the betting markets"), after BTTS:
every market is yes/no and both sides are bets (Football-Markets-Catalogue.md), so the
BTTS-yes 50% test is run for EVERY side of EVERY market SportyBet prices: BTTS yes AND no,
Over AND Under on every line, each 1X2 and Double Chance option, handicaps, team goals,
clean sheets, win to nil, combos, multigoals.

PAPER ONLY: nothing here books a code or stakes money. It grades what would have happened.

For each day's board (output/picks/picks_<date>.json), every model-rated fixture
(rated[].src == "model") is joined to its graded SportyBet game (data/universe): first by
the board's sb_event_id, else by both team names on the same day. Each priced ladder side
(the game's last SportyBet price before kick-off) gets the model's chance from the board's
score-line grid (rated[].scores, engine/full_markets.evaluate), the same calibration the
board uses for BTTS and the goals lines, and becomes a paper single at 1 unit when its
chance is 50%+. Results: hit rate vs chance and profit at SportyBet's price, by market and
side, at bars 50 / 55 / 60 / 65%.

    python backtest/model_sides_study.py          # rewrites backtest/MODEL_SIDES_STUDY.md
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import calibration as cal  # noqa: E402
from engine import full_markets as fm  # noqa: E402
from engine import universe as uv  # noqa: E402

PICKS_DIR = ROOT / "output" / "picks"
OUT = ROOT / "backtest" / "MODEL_SIDES_STUDY.md"
BARS = (0.50, 0.55, 0.60, 0.65)
DAYS = 45                       # boards read, newest first
MIN_PRICE = 1.01
NGN_STAKE = 1000                # SportyBet: NGN 1,000 a single (the board singles stake, 2026-10-24)


def _n(s: str) -> str:
    return re.sub(r"[^a-z ]", "", (s or "").lower()).replace(" fc", "").replace("fc ", "").strip()


def _alike(a: str, b: str) -> float:
    return SequenceMatcher(None, _n(a), _n(b)).ratio()


def grid(scores) -> np.ndarray | None:
    """The board's score-line grid (goals 0..n-1), normalised, padded to full_markets' size."""
    m = np.asarray(scores or [], dtype=float)
    if m.ndim != 2 or m.size == 0 or m.sum() <= 0:
        return None
    out = np.zeros((fm.MAX_G + 1, fm.MAX_G + 1))
    k = min(m.shape[0], fm.MAX_G + 1)
    out[:k, :k] = m[:k, :k]
    return out / out.sum()


def chance(k: str, g: np.ndarray) -> float | None:
    """The model's chance that side k wins (pushes count as not-won), calibrated as the board is."""
    pk = fm.parse_key(k)
    rule = fm.rule_for(*pk) if pk else None
    if rule is None:
        return None
    win, _push = fm.evaluate(g, rule)
    mid, spec, out = pk
    if mid == 29:                                   # BTTS: engine/calibration.btts_yes
        yes = cal.btts_yes(fm.evaluate(g, fm.rule_for(29, "", "Yes"))[0])
        return yes if out == "Yes" else 1 - yes
    if mid == 18:                                   # goals lines: engine/calibration.over
        line = float(spec.split("=")[1])
        over = cal.over(line, fm.evaluate(g, fm.rule_for(18, spec, f"Over {spec.split('=')[1]}"))[0])
        return over if out.startswith("Over") else 1 - over
    return win


NAMES = {**fm._NAMES, 19: "Home Team Goals", 20: "Away Team Goals"}


def market_of(k: str) -> str:
    pk = fm.parse_key(k)
    return NAMES.get(pk[0], f"market {pk[0]}") if pk else "?"


def side_of(k: str) -> str:
    """A side's generic name: 'Yes' / 'No', 'Over 2.5', 'Home (-1.5)', 'Home or Draw' ..."""
    return fm.parse_key(k)[2]


def join(picks: dict, games: list[dict]) -> list[tuple[dict, dict]]:
    """(rated row, graded game) pairs for one board day."""
    by_id = {g["id"]: g for g in games}
    ids = {}
    for sec in ("singles", "singles_dropped"):
        for s in picks.get(sec) or []:
            if s.get("sb_event_id"):
                ids.setdefault(s.get("fixture"), s["sb_event_id"])
    out = []
    for r in picks.get("rated") or []:
        if r.get("src") != "model" or not r.get("scores"):
            continue
        g = by_id.get(ids.get(r.get("fixture")))
        if g is None:
            best = max(games, key=lambda x: _alike(r["home"], x["home"]) + _alike(r["away"], x["away"]),
                       default=None)
            if best and _alike(r["home"], best["home"]) + _alike(r["away"], best["away"]) >= 1.3:
                g = best
        if g is not None:
            out.append((r, g))
    return out


def records(date: str, picks: dict, games: list[dict]) -> list[dict]:
    recs = []
    for r, g in join(picks, games):
        m = grid(r["scores"])
        res = g.get("result") or {}
        ladder = ((g.get("last") or {}).get("p") or {}).get("ladder") or {}
        if m is None or "h" not in res:
            continue
        for k, price in ladder.items():
            if not price or price < MIN_PRICE:
                continue
            won = fm.settle_key(k, res["h"], res["a"])
            if won is None:                         # a push or a market the rules can't settle
                continue
            ch = chance(k, m)
            if ch is None or ch < BARS[0]:
                continue
            recs.append({"date": date, "fixture": r["fixture"], "key": k, "market": market_of(k),
                         "side": side_of(k), "chance": round(ch, 4), "price": price, "won": int(won)})
    return recs


def _row(rs: list[dict]) -> str:
    n = len(rs)
    w = sum(x["won"] for x in rs)
    pl = sum((x["price"] - 1) if x["won"] else -1 for x in rs)
    ch = sum(x["chance"] for x in rs) / n
    return f"{n} | {w} | {w / n:.0%} | {ch:.0%} | {pl:+.2f} | ₦{pl * NGN_STAKE:+,.0f} | {pl / n:+.1%}"


def report(recs: list[dict], days: list[str]) -> list[str]:
    L = ["# Model sides study — every side of every market, paper only", "",
         "Architect 2026-11-01: the BTTS 50% test run for every side of every market. A paper single "
         "is a side the model gives 50%+ (board's score grid, BTTS/goals calibrated), priced at "
         "SportyBet's last price before kick-off, 1 unit. Nothing here is staked.", "",
         f"Boards read: {len(days)} ({days[0] if days else '-'} to {days[-1] if days else '-'}) · "
         f"{len(recs)} paper singles at 50%+.", "",
         "## By bar (all markets)", "", "| Bar | Singles | Won | Hit | Avg chance | Profit (1 unit) | Profit (₦1,000 a single) | ROI |",
         "|---|---|---|---|---|---|---|---|"]
    for b in BARS:
        rs = [x for x in recs if x["chance"] >= b]
        if rs:
            L.append(f"| {b:.0%} | {_row(rs)} |")
    for b in BARS:
        groups = defaultdict(list)
        for x in recs:
            if x["chance"] >= b:
                groups[(x["market"], re.sub(r"[\d.:+-]+", "N", x["side"]).replace("(N)", "").strip())].append(x)
        L += ["", f"## Bar {b:.0%}: by market and side (10+ singles)", "",
              "| Market | Side | Singles | Won | Hit | Avg chance | Profit (1 unit) | Profit (₦1,000 a single) | ROI |",
              "|---|---|---|---|---|---|---|---|---|"]
        for (mk, sd), rs in sorted(groups.items(), key=lambda t: -len(t[1])):
            if len(rs) >= 10:
                L.append(f"| {mk} | {sd} | {_row(rs)} |")
    L += ["", "## By day (bar 50%)", "", "| Day | Singles | Won | Hit | Avg chance | Profit (1 unit) | Profit (₦1,000 a single) | ROI |",
          "|---|---|---|---|---|---|---|---|"]
    for d in days:
        rs = [x for x in recs if x["date"] == d]
        if rs:
            L.append(f"| {d} | {_row(rs)} |")
    return L


def main() -> int:
    graded = {}
    for g in uv.load_graded():
        if g.get("sport") == "football" and g.get("result") and "srl" not in (g["home"] + g["away"]).lower():
            graded[g["id"]] = g
    by_day = defaultdict(list)
    for g in graded.values():
        by_day[(g.get("ko") or "")[:10]].append(g)
    files = sorted(PICKS_DIR.glob("picks_????-??-??.json"))[-DAYS:]
    recs, days = [], []
    for f in files:
        date = f.stem.split("_")[1]
        if not by_day.get(date):
            continue
        rs = records(date, json.loads(f.read_text(encoding="utf-8")), by_day[date])
        if rs:
            days.append(date)
            recs += rs
    OUT.write_text("\n".join(report(recs, days)) + "\n", encoding="utf-8")
    print(f"model sides study: {len(days)} board day(s), {len(recs)} paper singles at 50%+")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
