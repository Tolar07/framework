"""
GOALS EXPERIMENT BLOCK (Architect 2026-11-05: "today's results for the BTTS ... yes or no, and under 2.5 /
over 2.5. How to see the results for the experiment.", issue #349).

Reads the graded `rated` rows of football picks_<date>.json (the model's chance on every game it rated, with the
full-time score once played), calibrates BTTS-yes and Over 2.5 with engine.calibration, and reports for today and
all graded days: BTTS yes at 50%+ / 55%+, BTTS no at 55%+, Over 2.5 at 55%+, Under 2.5 at 55%+ (won/total, %), the
model's lean on every game, and the staked `btts` / `under25` slips (won/lost).

RECORD-ONLY. No pick, stake, threshold or rule is read from or changed by this. A game with no full-time score is
left out (PENDING, HR35), never guessed. Written to data/bots/goals_experiment.json by the nightly bot-grader run
(monitor/bot_grader.py), shown as one block in the 23:02 report.

    python monitor/goals_experiment.py              print the block (no file written)
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import calibration  # noqa: E402

PICKS_DIR = ROOT / "output" / "picks"
OUT = ROOT / "data" / "bots" / "goals_experiment.json"
SLIP_SECTIONS = ("btts", "under25")
# (label, bar, which side) — the Architect's reference list
BARS = (("BTTS yes 50%+", 0.50, "btts_yes"), ("BTTS yes 55%+", 0.55, "btts_yes"),
        ("BTTS no 55%+", 0.55, "btts_no"), ("Over 2.5 55%+", 0.55, "over"),
        ("Under 2.5 55%+", 0.55, "under"))


def _score(ft) -> tuple[int, int] | None:
    m = re.fullmatch(r"(\d+)-(\d+)", str(ft or "").strip())
    return (int(m.group(1)), int(m.group(2))) if m else None


def game_rows(doc: dict) -> list[dict]:
    """One row per graded rated game: calibrated chances and what happened."""
    out = []
    for r in doc.get("rated") or []:
        sc, p = _score(r.get("ft")), r.get("p") or []
        if sc is None or len(p) < 7 or p[4] is None or p[6] is None:
            continue
        btts = calibration.btts_yes(float(p[6]))
        over = calibration.over(2.5, float(p[4]))
        out.append({"p_btts": btts, "p_over": over,
                    "btts": sc[0] > 0 and sc[1] > 0, "over": sc[0] + sc[1] >= 3})
    return out


def _hit(rows: list[dict], side: str, bar: float) -> tuple[int, int]:
    """(won, total) for the calls on that side whose calibrated chance is at the bar or above."""
    won = tot = 0
    for g in rows:
        if side == "btts_yes":
            p, ok = g["p_btts"], g["btts"]
        elif side == "btts_no":
            p, ok = 1 - g["p_btts"], not g["btts"]
        elif side == "over":
            p, ok = g["p_over"], g["over"]
        else:
            p, ok = 1 - g["p_over"], not g["over"]
        if p >= bar:
            tot += 1
            won += ok
    return won, tot


def _lean(rows: list[dict]) -> dict:
    """The model's lean on every game: the side it rates above 50%, and how often that lean landed."""
    n = len(rows)
    b = sum((g["p_btts"] >= 0.5) == g["btts"] for g in rows)
    o = sum((g["p_over"] >= 0.5) == g["over"] for g in rows)
    return {"games": n, "btts_lean_right": b, "ou25_lean_right": o,
            "btts_lean_yes": sum(g["p_btts"] >= 0.5 for g in rows),
            "ou25_lean_over": sum(g["p_over"] >= 0.5 for g in rows)}


def slips(doc: dict) -> dict:
    """Won / lost / still open on the staked btts and under25 sections (singles and accas)."""
    out = {}
    for sec in SLIP_SECTIONS:
        t = {"won": 0, "lost": 0, "open": 0}
        for s in doc.get(sec) or []:
            r = s.get("result")
            t[r if r in ("won", "lost") else "open"] += 1
        if sum(t.values()):
            out[sec] = t
    return out


def collect(picks_dir: Path = PICKS_DIR) -> list[dict]:
    days = []
    if not picks_dir.exists():
        return days
    for f in sorted(picks_dir.glob("picks_20*.json")):
        try:
            doc = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        days.append({"date": str(doc.get("date") or f.stem.split("_")[-1]),
                     "rows": game_rows(doc), "slips": slips(doc)})
    return days


def _cells(rows: list[dict]) -> dict:
    cells = {}
    for label, bar, side in BARS:
        w, t = _hit(rows, side, bar)
        cells[label] = {"won": w, "total": t, "pct": round(w / t, 3) if t else None}
    return {"bars": cells, "lean": _lean(rows)}


def _slip_sum(days: list[dict]) -> dict:
    out: dict = {}
    for d in days:
        for sec, t in d["slips"].items():
            o = out.setdefault(sec, {"won": 0, "lost": 0, "open": 0})
            for k, v in t.items():
                o[k] += v
    return out


def build(days: list[dict], today: str) -> dict:
    allrows = [g for d in days for g in d["rows"]]
    todays = [d for d in days if d["date"] == today]
    card = {"as_of": today, "graded_days": sum(1 for d in days if d["rows"]),
            "today": {**_cells([g for d in todays for g in d["rows"]]), "slips": _slip_sum(todays)},
            "all": {**_cells(allrows), "slips": _slip_sum(days)}}
    card["report_line"] = report_block(card)
    return card


def _fmt(c: dict) -> str:
    return "PENDING" if not c["total"] else f"{c['won']}/{c['total']} {c['pct']:.0%}"


def _block(name: str, part: dict) -> list[str]:
    ln = part["lean"]
    if not ln["games"]:
        return [f"  {name}: PENDING (no graded games)"]
    out = [f"  {name} ({ln['games']} games): " + " · ".join(f"{k} {_fmt(c)}" for k, c in part["bars"].items()),
           f"    lean: BTTS yes on {ln['btts_lean_yes']}, right {ln['btts_lean_right']}/{ln['games']}; "
           f"Over 2.5 on {ln['ou25_lean_over']}, right {ln['ou25_lean_right']}/{ln['games']}"]
    for sec, t in part["slips"].items():
        out.append(f"    staked {sec}: won {t['won']}, lost {t['lost']}, open {t['open']}")
    return out


def report_block(card: dict) -> str:
    if not card["graded_days"]:
        return "GOALS EXPERIMENT (BTTS yes/no, Over/Under 2.5, recorded only): no graded games yet"
    return "\n".join(["GOALS EXPERIMENT (BTTS yes/no, Over/Under 2.5, calibrated, recorded only)"]
                     + _block("today", card["today"]) + _block(f"all {card['graded_days']} graded days", card["all"]))


def save(card: dict, path: Path = OUT) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(card, indent=1), encoding="utf-8")


def run(today: str, picks_dir: Path = PICKS_DIR, write: bool = True) -> dict:
    card = build(collect(picks_dir), today)
    if write:
        save(card)
    return card


if __name__ == "__main__":
    print(run(date.today().isoformat(), write=False)["report_line"])
