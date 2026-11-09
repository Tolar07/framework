"""
NBA FULL-GAME ACCA REPLAY - record only, flat 1 unit (framework: NBA full-game legs for fullgame_accas).

Replays the NBA full-game legs (engine/nba_value.fullgame_leg: the board's own chance, BAND and MIN_CHANCE, no value
bar) over the saved every-market record (output/nba_markets/), taking each game's FIRST look (the morning board's),
builds the full-game accas with engine/basketball_board.build_fullgame, settles every leg from ESPN's final score
and prints: legs per night, accas per night, the leg record and the flat 1-unit result of the accas.
The legs sit at the sharp fair price minus the bookmaker's margin, so no edge is expected: this measures it.
World basketball / NCAA legs are not in this record, so the real board has them in addition.

    python backtest/nba_fullgame_replay.py [markets_folder] [first_night YYYY-MM-DD]
"""
from __future__ import annotations

import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backtest import nba_market_study as study  # noqa: E402
from engine import basketball_board as bb  # noqa: E402
from engine import nba_markets as nm  # noqa: E402
from engine import nba_value as nv  # noqa: E402


def _t(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def _event(row: dict) -> dict:
    """The saved compact look in the shape of SportyBet's event (outcome ids are placeholders)."""
    return {"markets": [{"id": m["id"], "specifier": m.get("spec"), "status": 0 if m.get("open", True) else 2,
                         "outcomes": [{"desc": d, "odds": p, "id": f"{m['id']}:{i}"}
                                      for i, (d, p) in enumerate(m["outcomes"])]} for m in row["markets"]]}


def night_of(tip: datetime) -> str:
    return (tip - timedelta(hours=10)).date().isoformat()


def first_looks(rows: list[dict]) -> list[dict]:
    best: dict[str, dict] = {}
    for r in rows:
        if r.get("tip") and (r["event_id"] not in best or _t(r["at"]) < _t(best[r["event_id"]]["at"])):
            best[r["event_id"]] = r
    return list(best.values())


def main() -> int:
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else nm.OUT_DIR
    first = sys.argv[2] if len(sys.argv) > 2 else "0000"
    rows = [r for r in first_looks(nm.load(folder)) if night_of(_t(r["tip"])) >= first]
    nights: dict[str, list[dict]] = defaultdict(list)
    won: dict[tuple, int | None] = {}
    for r in rows:
        sh = r.get("sharp") or {}
        sharp = SimpleNamespace(ml_home=sh.get("ml_home"), ml_away=sh.get("ml_away"),
                                spread=sh.get("spread"), total=sh.get("total"))
        if not (sharp.ml_home and sharp.ml_away):
            continue
        leg = nv.fullgame_leg(_event(r), sharp)
        if leg is None:
            continue
        g = study.espn_game(r) if _t(r["tip"]) < datetime.now().astimezone() - timedelta(hours=3) else None
        w = None if g is None else nm.settle_any(leg["market_id"], leg["specifier"], leg["outcome"], g.hs, g.as_,
                                                  g.q_home, g.q_away)
        won[(r["event_id"], leg["market_id"], leg["specifier"], leg["outcome_id"])] = w
        nights[night_of(_t(r["tip"]))].append(
            {**leg, "event_id": r["event_id"], "home": r["home"], "away": r["away"], "tip": r["tip"],
             "code": "X", "pick": nv.display(leg, r["home"], r["away"]), "_tip": _t(r["tip"])})
    claimed = []
    legs_t = legs_w = n_acca = acc_w = acc_n = 0
    ret = 0.0
    lines = ["night       games  legs-won/graded  accas  acca-won/graded  flat-1 return"]
    for night in sorted(nights):
        legs = sorted(nights[night], key=lambda x: x["_tip"])
        accas = bb.build_fullgame(legs, {})
        lw = [won[(x["event_id"], x["market_id"], x["specifier"], x["outcome_id"])] for x in legs]
        claimed += [x["chance"] for x, w in zip(legs, lw) if w is not None]
        lw = [w for w in lw if w is not None]
        aw = ar = 0
        graded = 0
        for s in accas:
            res = [won[(d["event_id"], d["market_id"], d["specifier"], d["outcome_id"])] for d in s["leg_detail"]]
            if None in res:
                continue
            graded += 1
            if all(res):
                aw += 1
                ar += s["odds"] - 1
            else:
                ar -= 1
        legs_t += len(lw)
        legs_w += sum(lw)
        n_acca += len(accas)
        acc_n += graded
        acc_w += aw
        ret += ar
        lines.append(f"{night}  {len(legs):5d}  {sum(lw):3d}/{len(lw):<3d}          {len(accas):5d}  "
                     f"{aw:3d}/{graded:<3d}          {ar:+.2f}")
    lines.append(f"TOTAL  nights {len(nights)}  legs won {legs_w}/{legs_t}  accas {n_acca} (graded {acc_n}, won {acc_w})"
                 f"  flat-1 return {ret:+.2f} units on {acc_n} accas")
    if claimed:
        lines.append(f"legs: framework chance {sum(claimed) / len(claimed):.1%} on average, landed {legs_w / legs_t:.1%}")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
