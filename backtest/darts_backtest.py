"""
DARTS walk-forward backtest (framework#352, multi-sport rollout; record-only).

One dated pool of every free PDC result the framework can fetch: the World Championship 2020-2026
(data/darts_results.py; the bracket has no match dates, so each Championship is placed at 1 January of its year, an
ORDERING key only: it runs mid-December to early January), Premier League Darts nights 2023-2026
(data/darts_pl_results.py, real night dates) and the PDC majors 2023-2026 at round-start dates
(data/darts_majors_results.py, PR #457). The board rates darts with the shared win-probability Elo
(engine/multisport.py, K=24, 8 games each). Every match is scored BEFORE it is learned; each setting tried
(K x min games) is counted; the best is chosen on matches before 2025 and reported on 2025 onward only, next to the
board's setting and the coin flip.

No free darts closing-odds history exists (none found), so this is accuracy, never an edge or a return. Sides are
ordered by name, never winner-first. A feed that will not load adds nothing (HR59). Record only: nothing here
changes a stake, a bar, a threshold or the live switch.

  python backtest/darts_backtest.py      writes backtest/DARTS_BACKTEST_STUDY.md
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import results_walkforward as wf  # noqa: E402
from engine import multisport as ms  # noqa: E402

OUT = ROOT / "backtest" / "DARTS_BACKTEST_STUDY.md"
DIR = ROOT / "data" / "darts"
SPLIT = "2025-01-01"
TRIES = [(k, mg) for k in (12.0, 24.0, 40.0) for mg in (1, 3, 8)]


def _feed(name: str, module: str) -> list[dict]:
    """Saved results (data/ is not in git); fetched and saved when missing."""
    f = DIR / name
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    mod = __import__(f"data.{module}", fromlist=["fetch_all"])
    rows = mod.fetch_all()
    if rows:
        DIR.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    return rows


def keyed(wc: list[dict], pl: list[dict], majors: list[dict]) -> list[dict]:
    """All three feeds in one order; a match listed twice (same date, same pair) is kept once."""
    rows = []
    for g in wc:
        year = g["kickoff_utc"][:4]
        rows.append((f"{year}-01-01-{g['kickoff_utc']}", g, "World Championship"))
    for g in pl:
        rows.append((f"{g['date']}-{g['kickoff_utc']}", g, "Premier League"))
    for g in majors:
        rows.append((f"{g['date']}-{g['kickoff_utc']}", g, "majors"))
    rows.sort(key=lambda r: r[0])
    seen: set[tuple] = set()
    out = []
    for key, g, src in rows:
        h, a = ms.norm(g["home"]), ms.norm(g["away"])
        pair = (key[:10], frozenset((h, a)))
        if not h or not a or h == a or pair in seen or g.get("winner") not in (1, 2):
            continue
        seen.add(pair)
        first = h < a
        out.append({"key": key, "src": src, "a": h if first else a, "b": a if first else h,
                    "y": 1.0 if (g["winner"] == 1) == first else 0.0})
    return out


def render(games: list[dict], now: datetime) -> str:
    L = ["# Darts walk-forward backtest", "",
         f"Made {now:%Y-%m-%d %H:%M} UTC by `backtest/darts_backtest.py` (framework#352). Record only.", ""]
    if not games:
        return "\n".join(L + ["NO DATA - PENDING (the darts feeds did not load).", ""])
    res = wf.results_only_study(games, TRIES, SPLIT, (ms.ELO_K, ms.MIN_GAMES))
    by = {s: sum(1 for g in games if g["src"] == s) for s in ("World Championship", "Premier League", "majors")}
    players = {g["a"] for g in games} | {g["b"] for g in games}
    L += [f"Data: {len(games)} PDC matches ({', '.join(f'{k} {v}' for k, v in by.items())}), {len(players)} players, "
          f"{games[0]['key'][:4]} to {games[-1]['key'][:4]} (Wikipedia, fetched by the three `data/darts_*` feeds). "
          f"Tuning: before {SPLIT}; held out: {SPLIT} onward. Tries counted: **{res['tries']}**.", ""]
    L += wf.results_only_lines(res)
    L += ["", "## Reading", "",
          "- No closing price: the darts board's edge is judged on its own graded shadow record, not here.",
          "- World Championship matches carry an ordering key (1 January of the Championship's year), not a date; "
          "majors share their round's start date.",
          "- Record only: nothing here changes a stake, a bar, a threshold or the live switch.", ""]
    return "\n".join(L)


def run(now: datetime | None = None) -> str:
    games = keyed(_feed("wc_results.json", "darts_results"), _feed("pl_results.json", "darts_pl_results"),
                  _feed("majors_results.json", "darts_majors_results"))
    text = render(games, now or datetime.now(UTC))
    OUT.write_text(text, encoding="utf-8")
    return text


if __name__ == "__main__":
    print(run())
