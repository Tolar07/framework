"""
NCAA PROJECTION + ON/OFF STUDY (framework#396; twin of backtest/nba_projection_study.py and
backtest/nba_onoff_study.py) -> backtest/NCAA_PROJECTION_STUDY.md. RECORD-ONLY: reads
data/ncaa_graded/player_games.jsonl, changes no pick, stake or threshold. Wiring needs the Architect's OK.

1. PROJECTION  walk-forward player-built total (engine/ncaa_projection.py) vs the sharp line, as a forecast of
               the final total (mean miss) and on yes/no lines (Brier, log loss), with the gate's verdict.
2. ON/OFF      a player's points when a key teammate is out (backtest/nba_onoff_study.py, run on the NCAA log).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "backtest")]

import nba_onoff_study as onoff  # noqa: E402

from data import ncaa_players as npl  # noqa: E402
from engine import ncaa_projection as proj  # noqa: E402

OUT = ROOT / "backtest" / "NCAA_PROJECTION_STUDY.md"


def render(n_games: int, recs: list[dict], gate: dict, oo: dict) -> str:
    pr = gate["lines"]
    out = ["# NCAA projection + on/off study (record-only, framework#396)", "",
           f"{n_games} logged games with a pre-tip ESPN line; {len(recs)} projected walk-forward "
           f"(both teams >= {proj.MIN_PRIOR} prior games). Line-up = who played that night (HINDSIGHT, labelled). "
           "Nothing here feeds a pick.", ""]
    if not pr.get("n"):
        out += ["PENDING: no projected games yet (HR35).", ""]
    else:
        out += ["| forecast of the final total | mean miss (points) |", "|---|---|",
                f"| player-built projection | {pr['mae_projection']:.2f} |",
                f"| sharp line (+ fitted bias) | {pr['mae_sharp']:.2f} |", "",
                f"Yes/no total lines ({pr['n']}): projection Brier {pr['projection']['brier']:.4f} log loss "
                f"{pr['projection']['logloss']:.4f}; sharp Brier {pr['sharp']['brier']:.4f} log loss "
                f"{pr['sharp']['logloss']:.4f}.", ""]
    out += [f"Gate: {'OPEN' if gate['open'] else 'CLOSED'} - " + ("; ".join(gate["why"]) or "all tests pass"), "",
            "## Teammate on/off", ""]
    for k, lab in (("all", "all projected"), ("teammate_out", "a key teammate out"), ("adjusted", "adjustment applied")):
        g = oo[k]
        out.append(f"- {lab}: " + ("PENDING (0 player-games)" if not g["n"] else
                                    f"n {g['n']}, MAE plain {g['mae_plain']:.2f} vs adjusted {g['mae_adj']:.2f}"))
    return "\n".join(out) + "\n"


def main() -> int:
    rows = npl.load()
    recs = proj.walk(rows)
    gate = proj.status(recs)
    oo = onoff.summarise(onoff.evaluate(npl.flat(rows)))
    text = render(len(rows), recs, gate, oo)
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
