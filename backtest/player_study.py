"""PLAYER MODEL STUDY (framework #557): does engine/player_model.py predict a player's cards, fouls, tackles, shots and
shots on target better than the player's own season per-90 rate times his minutes (the plain baseline)?

Walk-forward: for every game day after WARMUP_DAYS, both models are fitted on lines before (day - GAP_DAYS) only (one
matchday purge gap) and predict that day's players. The XI is the players who played MIN_STARTER_MINUTES or more (the
predicted line-up is not kept historically, so this isolates the player model from line-up errors). The team totals the
players must add up to come from engine/event_model.py fitted on the same past (never the game's own numbers).
Scores: Brier of "was carded" and mean absolute error of the counts; calibration of "to be carded" by bucket.
Tries so far: 1 configuration (SHRINK_MIN=900), no tuning on this data (deflated-Sharpe habit).

PENDING (HR35) until PLAYER_MIN_DAYS days and PLAYER_MIN_LINES lines of player data exist (collection began 2026-11-11,
framework #556). A stat is published (PLAYER_PUBLISH) only when it beats the baseline.

    python backtest/player_study.py [players_dir] [stats_dir]     -> backtest/PLAYER_MODEL_STUDY.md
"""
from __future__ import annotations

import math
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine import event_model as em  # noqa: E402
from engine import player_model as pm  # noqa: E402

WARMUP_DAYS = 14
GAP_DAYS = 1
PLAYER_MIN_DAYS = 28
PLAYER_MIN_LINES = 3000
OUT = Path(__file__).resolve().parent / "PLAYER_MODEL_STUDY.md"
BUCKETS = (0.0, 0.05, 0.1, 0.15, 0.2, 0.3, 1.01)


def run(players_dir: Path, stats_dir: Path) -> dict:
    rows = pm.load_players(sorted(players_dir.glob("*.jsonl")) if players_dir.exists() else [])
    days = sorted({r["date"] for r in rows})
    span = (date.fromisoformat(days[-1]) - date.fromisoformat(days[0])).days + 1 if days else 0
    res = {"lines": len(rows), "days": span, "pending": span < PLAYER_MIN_DAYS or len(rows) < PLAYER_MIN_LINES,
           "events": {}, "calib": []}
    if res["pending"]:
        return res
    matches = em.load_history(sorted(stats_dir.glob("*.jsonl"))) if stats_dir.exists() else []
    by_id = {m.get("fotmob_id"): m for m in matches}
    start = date.fromisoformat(days[0]) + timedelta(days=WARMUP_DAYS)
    score: dict = defaultdict(lambda: {"n": 0, "mae_model": 0.0, "mae_base": 0.0, "brier_model": 0.0, "brier_base": 0.0})
    cal = [[0, 0.0, 0.0] for _ in BUCKETS[:-1]]
    for day in days:
        if date.fromisoformat(day) < start:
            continue
        cut = (date.fromisoformat(day) - timedelta(days=GAP_DAYS)).isoformat()
        model = pm.PlayerModel.fit(rows, before=cut)
        team_model = em.EventModel.fit(matches, before=cut)
        games = defaultdict(list)
        for r in rows:
            if r["date"] == day and r["_min"] >= pm.MIN_STARTER_MINUTES and r.get("side") in ("home", "away"):
                games[(r.get("fotmob_id"), r["side"])].append(r)
        for (fid, side), xi in games.items():
            m = by_id.get(fid)
            if not m or len(xi) < 8:
                continue
            pred = team_model.predict(m.get("league"), m["home"], m["away"])["events"]
            tt = {ev: pred[ev]["home" if side == "home" else "away"] for ev in pm.TEAM_EVENT.values() if ev in pred}
            ref = pm.referee_factor(matches, (m.get("referee") or {}).get("name"), m.get("league"), cut)
            out = model.predict_side(xi, tt, None, ref)["players"]
            for o, r in zip(out, xi, strict=True):
                for ev in pm.EVENTS:
                    y = pm.stat_of(r, ev)
                    p = o["events"].get(ev)
                    if y is None or p is None:
                        continue
                    own = model.own_rate(r["id"], ev)
                    base = (own if own is not None else model.pooled_rate.get(ev, 0.0)) * model.expected_minutes(r["id"]) / 90
                    s = score[ev]
                    s["n"] += 1
                    s["mae_model"] += abs(p - y)
                    s["mae_base"] += abs(base - y)
                    if ev == "cards":
                        yy = int(y > 0)
                        pc, bc = o["events"]["card_chance"], 1 - math.exp(-base)
                        s["brier_model"] += (pc - yy) ** 2
                        s["brier_base"] += (bc - yy) ** 2
                        for i in range(len(BUCKETS) - 1):
                            if BUCKETS[i] <= pc < BUCKETS[i + 1]:
                                cal[i][0] += 1
                                cal[i][1] += pc
                                cal[i][2] += yy
    for ev, s in score.items():
        n = max(s["n"], 1)
        res["events"][ev] = {"n": s["n"], "mae_model": s["mae_model"] / n, "mae_base": s["mae_base"] / n,
                             "brier_model": s["brier_model"] / n if ev == "cards" else None,
                             "brier_base": s["brier_base"] / n if ev == "cards" else None}
    res["calib"] = [(BUCKETS[i], BUCKETS[i + 1], c[0], c[1] / c[0] if c[0] else None, c[2] / c[0] if c[0] else None)
                    for i, c in enumerate(cal)]
    return res


def passes(e: dict) -> bool:
    ok = e["n"] >= 500 and e["mae_model"] < e["mae_base"]
    if e["brier_model"] is not None:
        ok = ok and e["brier_model"] < e["brier_base"]
    return ok


def report(res: dict) -> tuple[str, list[str]]:
    lines = ["# Player model study (framework #557)", "",
             f"Player lines saved: {res['lines']} over {res['days']} days. Needs {PLAYER_MIN_DAYS} days and "
             f"{PLAYER_MIN_LINES} lines.", ""]
    publish: list[str] = []
    if res["pending"]:
        lines += ["**PENDING** - not enough player data yet (HR35). Nothing is published; the player file is "
                  "labelled shadow and carries no number until this study lets it through.", ""]
    else:
        lines += ["| event | player-games | MAE model | MAE own-rate baseline | Brier model | Brier baseline |",
                  "|---|---|---|---|---|---|"]
        for ev, e in res["events"].items():
            ok = passes(e)
            if ok:
                publish.append(ev)
            b = (f"{e['brier_model']:.4f} | {e['brier_base']:.4f}" if e["brier_model"] is not None else "- | -")
            lines.append(f"| {ev}{' (published)' if ok else ''} | {e['n']} | {e['mae_model']:.3f} | "
                         f"{e['mae_base']:.3f} | {b} |")
        lines += ["", "Calibration of the chance of a card, by bucket:", "", "| bucket | n | predicted | observed |",
                  "|---|---|---|---|"]
        for lo, hi, n, p, o in res["calib"]:
            lines.append(f"| {lo:.2f}-{min(hi, 1):.2f} | {n} | " + (f"{p:.3f} | {o:.3f} |" if n else "- | - |"))
        lines.append("")
    lines += ["Tries so far: 1 configuration, no tuning on this data.", "",
              f"PLAYER_PUBLISH = {publish!r}"]
    return "\n".join(lines) + "\n", publish


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    pdir = Path(sys.argv[1]) if len(sys.argv) > 1 else root / "data" / "match_players"
    sdir = Path(sys.argv[2]) if len(sys.argv) > 2 else root / "data" / "match_stats"
    res = run(pdir, sdir)
    text, publish = report(res)
    OUT.write_text(text, encoding="utf-8")
    print(f"player study: {res['lines']} lines, {res['days']} days, "
          f"{'PENDING' if res['pending'] else 'published ' + str(publish)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
