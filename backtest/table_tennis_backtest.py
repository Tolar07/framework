"""
TABLE TENNIS walk-forward backtest (framework#352, multi-sport rollout; record-only).

The only free, dated, bulk table tennis results file found: the SCORE Sports Data Repository's Setka Cup dataset
(data.scorenetwork.org, from Kaggle; 7,851 matches, 10 June - 8 July 2022, both players, games won, date and time).
WTT/ITTF results sit behind a login (results.ittf.link) or an unpublished website API, so they are not used. Setka
Cup is a league the board LEAVES OUT for integrity (engine/multisport.py exclude, order 50), and the file covers one
month, not three seasons: this tests the board's Elo recipe on real table tennis results, not the board's
competitions. Every match is scored BEFORE it is learned; each setting tried (K x min games) is counted; the best is
chosen on the first half of the dates and reported on the second half only, next to the board's setting and the
coin flip.

No closing odds in this source, so this is accuracy, never an edge or a return. Sides are ordered by name, never
winner-first. A fetch that fails gives NO DATA - PENDING, never an invented match (HR59). Record only: nothing here
changes a stake, a bar, a threshold or the live switch.

  python backtest/table_tennis_backtest.py      writes backtest/TABLE_TENNIS_STUDY.md
"""
from __future__ import annotations

import csv
import io
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import results_walkforward as wf  # noqa: E402
from engine import multisport as ms  # noqa: E402

OUT = ROOT / "backtest" / "TABLE_TENNIS_STUDY.md"
URL = "https://data.scorenetwork.org/data/table_tennis-sept2022.csv"
UA = "OLP-XDV-research/1.0 (record-only backtest; github.com/Tolar07/framework)"
TRIES = [(k, mg) for k in (16.0, 24.0, 32.0, 48.0) for mg in (1, 3, 8)]


def fetch(url: str = URL) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})  # noqa: S310 (fixed https URL)
    with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310 (fixed https URL)
        return r.read().decode("utf-8", "replace")


def parse(text: str) -> list[dict]:
    """Matches with both names, a M/D/YYYY date, a time and a decided score; others skipped."""
    out: list[dict] = []
    for r in csv.DictReader(io.StringIO(text)):
        try:
            d = datetime.strptime(f"{r['Date']} {r['Time']}", "%m/%d/%Y %H:%M:%S")
            s1, s2 = int(r["Sets_P1"]), int(r["Sets_P2"])
        except (KeyError, ValueError):
            continue
        p1, p2 = ms.norm(r.get("Player1", "")), ms.norm(r.get("Player2", ""))
        if not p1 or not p2 or p1 == p2 or s1 == s2:
            continue
        first = p1 < p2
        out.append({"key": f"{d:%Y-%m-%dT%H:%M}-{r.get('X', '')}", "a": p1 if first else p2,
                    "b": p2 if first else p1, "y": 1.0 if (s1 > s2) == first else 0.0})
    out.sort(key=lambda g: g["key"])
    return out


def render(games: list[dict], now: datetime) -> str:
    L = ["# Table tennis walk-forward backtest", "",
         f"Made {now:%Y-%m-%d %H:%M} UTC by `backtest/table_tennis_backtest.py` (framework#352). Record only.", ""]
    if len(games) < 500:
        return "\n".join(L + [f"NO DATA - PENDING ({len(games)} matches read from {URL}).", ""])
    days = sorted({g["key"][:10] for g in games})
    split = days[len(days) // 2]
    res = wf.results_only_study(games, TRIES, split, (ms.ELO_K, ms.MIN_GAMES))
    players = {g["a"] for g in games} | {g["b"] for g in games}
    L += [f"Data: {len(games)} Setka Cup matches, {len(players)} players, {days[0]} to {days[-1]} ({len(days)} days; "
          f"SCORE Sports Data Repository, fetched in this run). Tuning: before {split}; held out: {split} onward. "
          f"Tries counted: **{res['tries']}**.", ""]
    L += wf.results_only_lines(res)
    L += ["", "## Reading", "",
          "- One month of one closed league (Setka Cup, left out of the board for integrity): a test of the Elo recipe "
          "on table tennis results, not three seasons and not the board's competitions. Treat it as a floor.",
          "- No closing price: the table tennis board's edge is judged on its own graded shadow record, not here.",
          "- Record only: nothing here changes a stake, a bar, a threshold or the live switch.", ""]
    return "\n".join(L)


def run(now: datetime | None = None) -> str:
    try:
        games = parse(fetch())
    except Exception as ex:  # noqa: BLE001 — PENDING, never invented
        print(f"not loaded ({type(ex).__name__})")
        games = []
    text = render(games, now or datetime.now(UTC))
    OUT.write_text(text, encoding="utf-8")
    return text


if __name__ == "__main__":
    print(run())
