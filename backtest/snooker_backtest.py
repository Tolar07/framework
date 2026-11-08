"""
SNOOKER walk-forward backtest (framework#352, multi-sport rollout; record-only).

Source: World Snooker Tour draws on Wikipedia (data/snooker_results.py: every bracket match of every WST event of the
2019-20 .. 2025-26 seasons, dated by the event's start, rounds in order). The board rates snooker with the shared
win-probability Elo (engine/multisport.py, K=24, 8 games each). Every match is scored BEFORE it is learned; each
setting tried (K x min games) is counted, the best is chosen on the seasons before 2024-25 and reported on 2024-25
onward only, next to the board's own setting and the coin flip.

No free snooker closing-odds history exists (none found; the odds sites that keep one refuse scripts or sell it), so
this is a results-only test: accuracy, never an edge or a return. Return and CLV come from the shadow board's own
graded record. Sides are ordered by name, never winner-first. Record only: nothing here changes a stake, a bar, a
threshold or the live switch.

  python backtest/snooker_backtest.py      writes backtest/SNOOKER_STUDY.md
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

OUT = ROOT / "backtest" / "SNOOKER_STUDY.md"
DATA = ROOT / "data" / "snooker" / "results.json"
SPLIT = "2024-07-01"                     # seasons before 2024-25 tune; 2024-25 onward is held out
TRIES = [(k, mg) for k in (16.0, 24.0, 32.0, 48.0) for mg in (1, 3, 8)]


def to_games(rows: list[dict]) -> list[dict]:
    out = []
    for r in sorted(rows, key=lambda x: x["kickoff_utc"]):
        h, a = ms.norm(r["home"]), ms.norm(r["away"])
        if not h or not a or h == a:
            continue
        first = h < a
        won_h = r["winner"] == 1
        out.append({"key": r["kickoff_utc"], "a": h if first else a, "b": a if first else h,
                    "y": 1.0 if won_h == first else 0.0})
    return out


def load() -> list[dict]:
    if DATA.exists():
        return json.loads(DATA.read_text(encoding="utf-8"))
    from data import snooker_results
    rows = snooker_results.fetch_all()
    if rows:
        DATA.parent.mkdir(parents=True, exist_ok=True)
        DATA.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    return rows


def render(rows: list[dict], now: datetime) -> str:
    L = ["# Snooker walk-forward backtest", "",
         f"Made {now:%Y-%m-%d %H:%M} UTC by `backtest/snooker_backtest.py` (framework#352). Record only.", ""]
    if not rows:
        return "\n".join(L + ["NO DATA - PENDING (run `python data/snooker_results.py`).", ""])
    games = to_games(rows)
    res = wf.results_only_study(games, TRIES, SPLIT, (ms.ELO_K, ms.MIN_GAMES))
    events = {r["tournament"] for r in rows}
    players = {g["a"] for g in games} | {g["b"] for g in games}
    L += [f"Data: {len(games)} World Snooker Tour matches from {len(events)} events, {len(players)} players, "
          f"{rows[0]['date']} to {rows[-1]['date']} (Wikipedia draws, fetched by `data/snooker_results.py`; each match "
          f"dated by its event's start). Tuning: events before {SPLIT}; held out: {SPLIT} onward. "
          f"Tries counted: **{res['tries']}**.", ""]
    L += wf.results_only_lines(res)
    L += ["", "## Reading", "",
          "- No closing price: the snooker board's edge has to be judged on its own graded shadow record against the "
          "exchange, not here.",
          "- Matches inside one event share its start date; only the round order inside an event is known. A match "
          "that is only in a results table (not a bracket) is not read.",
          "- Record only: nothing here changes a stake, a bar, a threshold or the live switch.", ""]
    return "\n".join(L)


def run(now: datetime | None = None) -> str:
    text = render(load(), now or datetime.now(UTC))
    OUT.write_text(text, encoding="utf-8")
    return text


if __name__ == "__main__":
    print(run())
