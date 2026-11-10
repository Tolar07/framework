"""BASEBALL total-runs (over/under) walk-forward backtest vs the closing total line (framework#346; record-only).

The moneyline study (baseball_backtest.py) found the close is the better chance for the winner market. The same
cached ESPN data also holds the closing TOTAL (overUnder + over/under prices), the second market of the baseball
catalogue. Every game is replayed in date order: a team-offence / team-defence run rating (decayed running mean,
shrunk to the league) plus a ballpark term gives an expected total BEFORE the game; it is then blended with the
closing line (market weight). The setting is chosen on 2019-2022 and reported on 2023-2025 only; every try counted.

Judged by squared error against the actual total (the close's own error is the bar), then a flat-stake test: bet
Over when the model total beats the line by an edge bar, Under when it is that far under, (a) at the closing bookmaker
price and (b) at an even fair price less 2% commission on winnings. A game whose line is a push is not a bet. A game
without a closing total is skipped, never filled (HR35); a season that will not load reads PENDING (HR59).
Record only: nothing here changes a stake, a bar, a threshold or the live switch.

  python backtest/baseball_totals_backtest.py      writes backtest/BASEBALL_TOTALS_STUDY.md
"""
from __future__ import annotations

import itertools
import math
import statistics
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import baseball_backtest as bb  # noqa: E402
from backtest.tennis_backtest import num  # noqa: E402

OUT = ROOT / "backtest" / "BASEBALL_TOTALS_STUDY.md"
TUNE = bb.TUNE
SEASONS = bb.SEASONS
DECAYS = (0.97, 0.99)
SHRINKS = (10.0, 30.0)
PARK_W = (0.0, 1.0)
MKT_W = (0.0, 0.5, 0.75)
EDGES = (0.5, 1.0)
MIN_GAMES = 10
CARRY = 0.5                               # share of last season's evidence kept at a season turn
PARK_SHRINK = 60.0
COMMISSION = 0.02


def scores_of_day(board: dict) -> list[dict]:
    """Finished regular-season and play-off games with both scores (ties are not possible in baseball; skipped)."""
    out = []
    for e in (board or {}).get("events") or []:
        if (e.get("season") or {}).get("type") not in (2, 3):
            continue
        c = (e.get("competitions") or [{}])[0]
        if not ((c.get("status") or e.get("status") or {}).get("type") or {}).get("completed"):
            continue
        side = {t.get("homeAway"): t for t in c.get("competitors") or []}
        h, a = side.get("home"), side.get("away")
        if not h or not a:
            continue
        sh, sa = num(h.get("score")), num(a.get("score"))
        if sh is None or sa is None:
            continue
        out.append({"id": str(e["id"]), "key": e.get("date", "")[:16], "season": int((e.get("season") or {})["year"]),
                    "a": (a.get("team") or {}).get("abbreviation", ""), "b": (h.get("team") or {}).get("abbreviation", ""),
                    "ra": sa, "rb": sh, "total": sa + sh})
    return out


def close_total(odds: dict) -> dict | None:
    """Median closing total line and Over / Under decimal prices over the pre-game bookmakers (live, consensus and
    projection lines left out). None when no bookmaker gave a line."""
    lines, ov, un = [], [], []
    for it in (odds or {}).get("items") or []:
        name = str((it.get("provider") or {}).get("name", "")).lower()
        if any(x in name for x in bb.SKIP_PROVIDERS):
            continue
        line = num(it.get("overUnder"))
        if line is None or line <= 0:
            continue
        po, pu = bb.american(it.get("overOdds")), bb.american(it.get("underOdds"))
        if po and pu and 1 / po + 1 / pu < 1.15:
            lines.append(line)
            ov.append(po)
            un.append(pu)
    if not lines:
        return None
    return {"line": statistics.median(lines), "over": statistics.median(ov), "under": statistics.median(un)}


def load(get=None, seasons=SEASONS) -> tuple[list[dict], list[str]]:
    """All finished games with a closing total, in date order (+ notes on what did not load)."""
    notes: list[str] = []
    games: list[dict] = []
    for s in seasons:
        day, end = date(s, 3, 15), date(s, 11, 10)
        todo: list[dict] = []
        while day <= end:
            d = day.strftime("%Y%m%d")
            b = bb.cached(f"sb_{d}.json", bb.BOARD.format(d=d), get)
            todo += [g for g in scores_of_day(b) if g["season"] == s] if b else []
            day += timedelta(days=1)
        with ThreadPoolExecutor(max_workers=4) as pool:
            got = list(pool.map(lambda g: bb.cached(f"odds_{g['id']}.json", bb.ODDS.format(e=g["id"]), get), todo))
        priced = 0
        for g, o in zip(todo, got, strict=True):
            t = close_total(o) if o else None
            if t:
                g.update(t)
                games.append(g)
                priced += 1
        if not todo:
            notes.append(f"{s}: no games loaded - PENDING")
        elif priced < len(todo):
            notes.append(f"{s}: {len(todo) - priced} of {len(todo)} games without a closing total (skipped)")
    games.sort(key=lambda g: (g["key"], g["a"], g["b"]))
    return games, notes


class _Rating:
    """Decayed running sum of a team's runs for / against, and the ballpark's runs over the league, all shrunk."""

    def __init__(self):
        self.w = self.rf = self.ra = 0.0
        self.pw = self.pe = 0.0


def _shrunk(runs: float, w: float, lg: float, shrink: float) -> float:
    """A team's runs-per-game rating less the league mean, shrunk toward the league."""
    return (runs + shrink * lg) / (w + shrink) - lg


def expected_totals(games: list[dict], decay: float, shrink: float, park_w: float) -> list[float | None]:
    """Model expected total runs for each game, using only games played before it (no peeking). None until both teams
    and the league have MIN_GAMES of evidence."""
    teams: dict[str, _Rating] = {}
    lg_n, lg_runs = 0.0, 0.0
    out: list[float | None] = []
    season = None
    for g in games:
        if season is not None and g["season"] != season:
            for r in teams.values():
                for f in ("w", "rf", "ra", "pw", "pe"):
                    setattr(r, f, getattr(r, f) * CARRY)
        season = g["season"]
        ra_, rb_ = teams.setdefault(g["a"], _Rating()), teams.setdefault(g["b"], _Rating())
        base = None
        if lg_n < 200 or ra_.w < MIN_GAMES or rb_.w < MIN_GAMES:
            out.append(None)
        else:
            lg = lg_runs / lg_n                                   # runs per team per game
            ea = lg + _shrunk(ra_.rf, ra_.w, lg, shrink) + _shrunk(rb_.ra, rb_.w, lg, shrink)
            eb = lg + _shrunk(rb_.rf, rb_.w, lg, shrink) + _shrunk(ra_.ra, ra_.w, lg, shrink)
            park = rb_.pe / (rb_.pw + PARK_SHRINK)                # home park: total runs over what the teams' own ratings gave
            base = ea + eb
            out.append(max(3.0, base + park_w * park))
        # learn from this game after predicting it
        lg_n += 2
        lg_runs += g["total"]
        for t, rf, ra_runs in ((ra_, g["ra"], g["rb"]), (rb_, g["rb"], g["ra"])):
            t.w = t.w * decay + 1
            t.rf = t.rf * decay + rf
            t.ra = t.ra * decay + ra_runs
        if base is not None:
            rb_.pw += 1
            rb_.pe += g["total"] - base
    return out


def blend(model: float, line: float, mw: float) -> float:
    """Market weight mw = share of the closing line in the final expected total."""
    return mw * line + (1 - mw) * model


def evaluate(games, exp, seasons, mw) -> dict:
    se = se_line = 0.0
    n = 0
    for g, e in zip(games, exp, strict=True):
        if e is None or not (seasons[0] <= g["season"] <= seasons[1]):
            continue
        se += (blend(e, g["line"], mw) - g["total"]) ** 2
        se_line += (g["line"] - g["total"]) ** 2
        n += 1
    return {"n": n, "rmse": math.sqrt(se / n) if n else None, "rmse_line": math.sqrt(se_line / n) if n else None}


def bets(games, exp, seasons, mw, edge) -> dict:
    """Flat 1-unit Over/Under bets where the blended total is `edge` runs away from the line (pushes dropped)."""
    n = 0
    book = fair = 0.0
    for g, e in zip(games, exp, strict=True):
        if e is None or not (seasons[0] <= g["season"] <= seasons[1]) or g["total"] == g["line"]:
            continue
        d = blend(e, g["line"], mw) - g["line"]
        if abs(d) < edge:
            continue
        over = d > 0
        won = (g["total"] > g["line"]) == over
        n += 1
        book += ((g["over"] if over else g["under"]) - 1) if won else -1.0
        fair += (1 - COMMISSION) if won else -1.0
    return {"n": n, "book": book / n if n else None, "fair": fair / n if n else None}


def _pct(x):
    return "PENDING" if x is None else f"{x * 100:+.1f}%"


def run(games: list[dict], notes: list[str] | None = None) -> str:
    last = max(g["season"] for g in games)
    test = (TUNE[1] + 1, last)
    grid = list(itertools.product(DECAYS, SHRINKS, PARK_W))
    exps = {c: expected_totals(games, *c) for c in grid}
    tries = len(grid) * len(MKT_W) + len(MKT_W) * len(EDGES)
    best = min(itertools.product(grid, MKT_W), key=lambda cm: evaluate(games, exps[cm[0]], TUNE, cm[1])["rmse"] or 1e9)
    (c, mw) = best
    held = evaluate(games, exps[c], test, mw)
    alone = evaluate(games, exps[c], test, 0.0)
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    L = ["# Baseball (MLB) total-runs walk-forward backtest", "",
         f"Made {now} by `backtest/baseball_totals_backtest.py` (framework#346). {len(games)} MLB games {SEASONS[0]}-{last} "
         f"with a closing total line and Over/Under prices (cached ESPN scoreboard + odds record, median pre-game "
         f"bookmaker). Tries counted: **{tries}** (decay x shrink x park x market weight, then the edge bars). Chosen on "
         f"{TUNE[0]}-{TUNE[1]}, reported on **{test[0]}-{test[1]} only** ({held['n']} games).", ""]
    if notes:
        L += ["Not loaded: " + "; ".join(notes), ""]
    L += ["| Rule (held-out seasons) | Games | RMSE of the total (runs) |", "|---|---|---|",
          f"| The closing total line | {held['n']} | {held['rmse_line']:.3f} |",
          f"| Model alone (decay {c[0]}, shrink {c[1]:.0f}, park {c[2]:.0f}) | {alone['n']} | {alone['rmse']:.3f} |",
          f"| Best blend on tuning seasons (same model, market weight {mw:.0%}) | {held['n']} | {held['rmse']:.3f} |", "",
          "## Flat-stake test (Over/Under vs the closing line, pushes dropped)", "",
          "| Setting | Edge bar (runs) | Bets | ROI at the bookmaker close | ROI at an even price less 2% commission |",
          "|---|---|---|---|---|"]
    for e in EDGES:
        for name, m in (("Model alone", 0.0), ("Best blend", mw)):
            b = bets(games, exps[c], test, m, e)
            L.append(f"| {name} | {e} | {b['n']} | {_pct(b['book'])} | {_pct(b['fair'])} |")
    gap = (held["rmse"] or 0) - (held["rmse_line"] or 0)
    L += ["", "## Reading", "",
          f"- Model alone RMSE {alone['rmse']:.3f} vs the close {held['rmse_line']:.3f}: "
          + ("the closing total is the better forecast of runs." if alone["rmse"] >= held["rmse_line"]
             else "level with the closing total (a gap this small is noise, not an edge)."),
          f"- Best blend RMSE {held['rmse']:.3f} vs the close {held['rmse_line']:.3f} ({gap:+.3f}): "
          + ("no information beyond the line: price baseball totals off the exchange." if gap >= 0
             else "a small gain beyond the line held-out" + (", worth a shadow." if gap <= -0.05
                                                              else ", under 0.05 runs: noise until a shadow confirms it.")),
          f"- {tries} tries made; the held-out lines are the honest ones, any ROI above is one of them, not a result to bank.",
          "- No starting-pitcher, weather or bullpen input here (the biggest total movers): PENDING; weather and "
          "wind are not in the free cache.",
          "- Record only: nothing here changes a stake, a bar, a threshold or the live switch."]
    return "\n".join(L) + "\n"


def main() -> int:
    games, notes = load()
    if len(games) < 5000:
        print(f"only {len(games)} games read: NO DATA - PENDING ({'; '.join(notes)})")
        return 1
    text = run(games, notes)
    OUT.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
