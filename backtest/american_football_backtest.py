"""
AMERICAN FOOTBALL walk-forward backtest (framework#352, multi-sport rollout; live from 2026-11-12).

The multi-sport board rates every sport with the same win-probability Elo (engine/multisport.py: K 24, start 1500,
a side needs MIN_GAMES rated games) and blends it with the exchange's fair price. This study replays every NFL game
since 2006 (nflverse games.csv: final scores + CLOSING moneylines, free) in date order:

  - every setting tried is counted (K x home advantage x blend weight x edge bar); the best is chosen on the
    FIRST test seasons and reported on the LATER seasons only (no peeking);
  - accuracy: Brier of the model vs the devigged closing price vs a coin-flip-with-home-edge baseline;
  - return: back the side whose blended chance beats the closing price by the edge bar, at the closing price,
    2% commission on winnings (Matchbook). Ties and pushes skipped.

College football (most of the live board's American-football games) has no free closing odds, so its edge comes
from the shadow board's own graded record; this study covers the NFL part.

  python backtest/american_football_backtest.py      writes backtest/AMERICAN_FOOTBALL_STUDY.md
"""
from __future__ import annotations

import csv
import io
import itertools
import math
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "backtest" / "AMERICAN_FOOTBALL_STUDY.md"
URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
COMMISSION = 0.02
FIRST_SEASON, TUNE_SEASONS, MIN_GAMES, ELO_START = 2006, (2010, 2015), 8, 1500.0
KS = (16.0, 24.0, 32.0)               # 24 = the live board's ELO_K
HOME = (0.0, 48.0)                    # the live board uses 0 (no home edge)
BLEND = (0.0, 0.25, 0.5)              # weight on the Elo chance; the rest is the closing fair price (0 = market only)
EDGES = (0.02, 0.04, 0.06)


def american_to_decimal(ml: float) -> float:
    return 1 + (ml / 100 if ml > 0 else 100 / -ml)


def load(text: str | None = None) -> list[dict]:
    if text is None:
        req = urllib.request.Request(URL, headers={"User-Agent": "olp-xdv-backtest"})
        with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310 (fixed https URL)
            text = r.read().decode("utf-8")
    games = []
    for row in csv.DictReader(io.StringIO(text)):
        try:
            season = int(row["season"])
            hs, as_ = int(row["home_score"]), int(row["away_score"])
            hml, aml = float(row["home_moneyline"]), float(row["away_moneyline"])
        except (KeyError, ValueError):
            continue
        if season < FIRST_SEASON or hs == as_:
            continue
        games.append({"season": season, "day": row["gameday"], "home": row["home_team"], "away": row["away_team"],
                      "y": 1.0 if hs > as_ else 0.0, "dh": american_to_decimal(hml), "da": american_to_decimal(aml)})
    games.sort(key=lambda g: (g["day"], g["home"]))
    return games


def fair_home(g: dict) -> float:
    ih, ia = 1 / g["dh"], 1 / g["da"]
    return ih / (ih + ia)


def replay(games: list[dict], k: float, home: float) -> list[float | None]:
    """The Elo chance of a home win BEFORE each game (None while a side has < MIN_GAMES games), then learn."""
    r, n, out = {}, {}, []
    for g in games:
        h, a = g["home"], g["away"]
        rh, ra = r.get(h, ELO_START), r.get(a, ELO_START)
        e = 1 / (1 + 10 ** ((ra - rh - home) / 400))
        out.append(e if n.get(h, 0) >= MIN_GAMES and n.get(a, 0) >= MIN_GAMES else None)
        r[h], r[a] = rh + k * (g["y"] - e), ra - k * (g["y"] - e)
        n[h], n[a] = n.get(h, 0) + 1, n.get(a, 0) + 1
    return out


def evaluate(games, probs, blend, edge, seasons) -> dict:
    bets = pnl = 0.0
    won = 0
    b_model = b_mkt = cnt = 0
    for g, p in zip(games, probs):
        if p is None or not (seasons[0] <= g["season"] <= seasons[1]):
            continue
        f = fair_home(g)
        q = blend * p + (1 - blend) * f
        b_model += (q - g["y"]) ** 2
        b_mkt += (f - g["y"]) ** 2
        cnt += 1
        for side_p, side_fair, dec, win in ((q, f, g["dh"], g["y"] == 1), (1 - q, 1 - f, g["da"], g["y"] == 0)):
            if side_p - side_fair >= edge and side_p * dec > 1:
                bets += 1
                if win:
                    won += 1
                    pnl += (dec - 1) * (1 - COMMISSION)
                else:
                    pnl -= 1
    return {"n": cnt, "brier": b_model / cnt if cnt else None, "brier_mkt": b_mkt / cnt if cnt else None,
            "bets": int(bets), "won": won, "roi": pnl / bets if bets else None, "pnl": pnl}


def se_roi(res: dict) -> float | None:
    if not res["bets"]:
        return None
    return math.sqrt(max(res["bets"], 1)) / res["bets"] * 1.0   # ~1 unit sd per bet at these prices


def run(games: list[dict]) -> str:
    last = max(g["season"] for g in games)
    test = (TUNE_SEASONS[1] + 1, last)
    rows, tries = [], 0
    cache = {(k, h): replay(games, k, h) for k, h in itertools.product(KS, HOME)}
    for (k, h), probs in cache.items():
        for blend, edge in itertools.product(BLEND, EDGES):
            tries += 1
            tune = evaluate(games, probs, blend, edge, TUNE_SEASONS)
            rows.append({"k": k, "home": h, "blend": blend, "edge": edge, "tune": tune})
    elo_only = [r for r in rows if r["blend"] > 0 and r["tune"]["bets"] >= 50 and r["tune"]["roi"] is not None]
    best = max(elo_only, key=lambda r: r["tune"]["roi"]) if elo_only else None
    live = evaluate(games, cache[(24.0, 0.0)], 0.25, 0.04, test)
    pure = evaluate(games, cache[(24.0, 0.0)], 1.0, 0.04, test)
    held = evaluate(games, cache[(best["k"], best["home"])], best["blend"], best["edge"], test) if best else None
    base_b = sum((0.57 - g["y"]) ** 2 for g in games if test[0] <= g["season"] <= test[1]) / max(1, sum(
        1 for g in games if test[0] <= g["season"] <= test[1]))

    def pct(x):
        return "-" if x is None else f"{x * 100:+.1f}%"

    def line(name, r):
        return (f"| {name} | {r['n']} | {r['brier']:.4f} | {r['brier_mkt']:.4f} | {r['bets']} | "
                f"{r['won']} | {pct(r['roi'])} |")

    made = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    L = ["# American football (NFL) walk-forward backtest", "",
         f"Made {made} by `backtest/american_football_backtest.py` (framework#352). {len(games)} NFL games "
         f"{FIRST_SEASON}-{last} with closing moneylines (nflverse). Settings tried: **{tries}** (K x home edge x "
         f"blend x edge bar); chosen on {TUNE_SEASONS[0]}-{TUNE_SEASONS[1]}, reported on **{test[0]}-{test[1]} only**. "
         f"Bets at the closing price, {COMMISSION:.0%} commission on winnings.", "",
         "| Rule (held-out seasons) | Games rated | Brier | Brier closing price | Bets | Won | Return/bet |",
         "|---|---|---|---|---|---|---|",
         line("Live board: Elo K24 no home edge, 25% Elo + 75% price, edge >= 4 pts", live),
         line("Elo alone (K24), edge >= 4 pts", pure)]
    if held:
        L.append(line(f"Best on the tuning seasons: K{best['k']:.0f} home+{best['home']:.0f}, "
                      f"{best['blend']:.0%} Elo, edge >= {best['edge'] * 100:.0f} pts", held))
    L += [f"| Baseline: home team 57% every game | - | {base_b:.4f} | - | - | - | - |", "",
          "## Reading", ""]
    beat = live["brier"] is not None and live["brier"] < live["brier_mkt"]
    L.append(f"- Accuracy: the live blend's Brier is {'BELOW' if beat else 'ABOVE'} the closing price's "
             f"({live['brier']:.4f} vs {live['brier_mkt']:.4f}); "
             + ("the Elo adds information to the price." if beat else
                "the closing price already knows more than this Elo; the blend should lean on the price."))
    if live["roi"] is not None:
        se = se_roi(live)
        L.append(f"- Return: {live['bets']} bets, {pct(live['roi'])} per bet (about ±{se * 100:.0f} pts at 1 se). "
                 + ("Inside the noise: NOT proof of an edge." if abs(live["roi"]) < 2 * se else
                    ("Clearly negative at the closing price: do not stake this rule on NFL." if live["roi"] < 0 else
                     "Clearly positive, but a closing-price test flatters timing; confirm on the shadow record.")))
    L += [f"- {tries} settings were tried; the more tries, the more a good tuning result can be luck (deflated "
          "result rule). The held-out line is the honest one.",
          "- Return at the CLOSING price is a hard test: the live board bets earlier prices, so its CLV split "
          "(decision vs close) decides; this says whether the model itself can beat the close.",
          "- Record only: nothing here changes a stake, a bar or the live switch. College football: shadow record."]
    return "\n".join(L) + "\n"


def main() -> int:
    games = load()
    if len(games) < 1000:
        print(f"only {len(games)} games read: NO DATA - PENDING")
        return 1
    text = run(games)
    OUT.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
