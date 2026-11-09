"""
ACCA + SINGLES PAPER CHALLENGER (Architect 2026-11-09: "add it to the paper challenger and let's see
what it produces").

The Architect's old Bet365 staking: a 5-game acca at 5 units, and each of its legs as a 2-unit single
on top, so if the acca fails the singles that won hand some money back. This grades that format on
EVERY acca the boards already make and grade (football picks_<date>.json and basketball
basketball_<date>.json), at the same 5:2 ratio:

    acca part     2.5 units on the slip at the slip's odds
    singles part  1 unit on each leg at the leg's own price (void leg = stake back)

and compares it with the slip on its own (the acca part alone), per board section and sport.

PAPER ONLY. Nothing here places, changes or sizes a bet. Units only, never money (this repo is
public). A slip is counted only when the slip and every one of its legs is graded; the rest are
PENDING (HR35), never guessed. Written to data/bots/acca_singles_paper.json from the nightly
bot-grader run (monitor/bot_grader.py) and shown as one block in the 23:02 report.

    python monitor/acca_singles_paper.py            print the block (no file written)
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PICKS_DIR = ROOT / "output" / "picks"
OUT = ROOT / "data" / "bots" / "acca_singles_paper.json"

ACCA_UNITS = 2.5          # £5 acca : £2 singles, as the Architect staked it
SINGLE_UNITS = 1.0
# multi-leg sections of the football board; legs are fixtures graded in doc["singles"]
FB_FIXTURE_SECTIONS = ("accas", "safe3", "megas", "clv_accas")
# football sections whose legs carry their own price and result
FB_OWN_LEG_SECTIONS = ("alts", "value", "btts", "under25", "short3")
BB_SECTIONS = ("accas", "safe3", "megas", "clv_accas", "alts", "value", "fullgame_accas")
DONE = ("won", "lost", "void")


def _price(x: dict) -> float | None:
    try:
        p = float(x.get("price") or x.get("odds") or 0)
    except (TypeError, ValueError):
        return None
    return p if p > 1.0 else None


def football_slips(doc: dict) -> list[dict]:
    """Every graded multi-leg slip on a football board, each leg as (price, result)."""
    singles = {s.get("fixture"): s for s in doc.get("singles") or []}
    out = []
    for sec in FB_FIXTURE_SECTIONS + FB_OWN_LEG_SECTIONS:
        for slip in doc.get(sec) or []:
            if sec in FB_OWN_LEG_SECTIONS:
                raw = slip.get("alt_legs") or []
                legs = [(_price(x), x.get("result")) for x in raw]
            else:
                detail = {d.get("fixture"): d for d in slip.get("leg_detail") or []}
                legs = []
                for f in slip.get("legs") or []:
                    s = singles.get(f) or {}
                    legs.append((_price(detail.get(f) or s), s.get("result")))
            out.append(_slip("football", sec, slip, legs))
    return [s for s in out if s]


def basketball_slips(doc: dict) -> list[dict]:
    """Every graded multi-leg basketball slip. A leg's result comes from a one-leg slip on the same
    board with the same game and pick; a won slip means every leg won (or was void)."""
    one_leg = {}
    for sec in ("singles", "value", "alts"):
        for s in doc.get(sec) or []:
            for d in (s.get("leg_detail") or [])[:1]:
                if len(s.get("legs") or []) == 1 and s.get("result") in DONE:
                    one_leg[(d.get("event_id"), d.get("pick"))] = s["result"]
    out = []
    for sec in BB_SECTIONS:
        for slip in doc.get(sec) or []:
            legs = []
            for d in slip.get("leg_detail") or []:
                res = one_leg.get((d.get("event_id"), d.get("pick")))
                if res is None and slip.get("result") == "won":
                    res = "won"
                legs.append((_price(d), res))
            out.append(_slip("basketball", sec, slip, legs))
    return [s for s in out if s]


def _slip(sport: str, section: str, slip: dict, legs: list) -> dict | None:
    if len(legs) < 2:
        return None
    graded = slip.get("result") in ("won", "lost") and all(p and r in DONE for p, r in legs)
    return {"sport": sport, "section": section, "name": slip.get("name"),
            "odds": _price(slip), "result": slip.get("result"), "legs": legs, "graded": graded}


def returns(s: dict) -> dict:
    """Units staked and returned for the acca part and the singles part of one graded slip."""
    acca_back = ACCA_UNITS * s["odds"] if s["result"] == "won" else 0.0
    singles_back = 0.0
    for p, r in s["legs"]:
        singles_back += SINGLE_UNITS * p if r == "won" else SINGLE_UNITS if r == "void" else 0.0
    n = len(s["legs"])
    return {"acca_staked": ACCA_UNITS, "acca_back": acca_back,
            "singles_staked": SINGLE_UNITS * n, "singles_back": singles_back}


def _cell(slips: list[dict]) -> dict:
    t: defaultdict[str, float] = defaultdict(float)
    won = profit_slips = 0
    for s in slips:
        r = returns(s)
        for k, v in r.items():
            t[k] += v
        won += s["result"] == "won"
        profit_slips += (r["acca_back"] + r["singles_back"]) > (r["acca_staked"] + r["singles_staked"])
    n = len(slips)
    staked = t["acca_staked"] + t["singles_staked"]
    back = t["acca_back"] + t["singles_back"]
    return {
        "slips": n,
        "acca_won": won,
        "slips_in_profit": profit_slips,
        "combo_roi": round(back / staked - 1, 4) if staked else None,
        "acca_only_roi": round(t["acca_back"] / t["acca_staked"] - 1, 4) if n else None,
        "singles_only_roi": round(t["singles_back"] / t["singles_staked"] - 1, 4) if n else None,
        "combo_units": round(back - staked, 2),
    }


def collect(picks_dir: Path = PICKS_DIR) -> list[dict]:
    rows: list[dict] = []
    if not picks_dir.exists():
        return rows
    for f in sorted(picks_dir.glob("picks_20*.json")) + sorted(picks_dir.glob("basketball_20*.json")):
        try:
            doc = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        day = str(doc.get("date") or f.stem.split("_")[-1])
        found = basketball_slips(doc) if f.name.startswith("basketball_") else football_slips(doc)
        for s in found:
            s["date"] = day
            rows.append(s)
    return rows


def build(rows: list[dict], today: str) -> dict:
    graded = [s for s in rows if s["graded"]]
    since30 = (date.fromisoformat(today) - timedelta(days=30)).isoformat()
    since7 = (date.fromisoformat(today) - timedelta(days=7)).isoformat()
    by = defaultdict(list)
    for s in graded:
        by[f"{s['sport']} / {s['section']}"].append(s)
        by[f"{s['sport']} / all"].append(s)
    card = {
        "as_of": today,
        "units": {"acca": ACCA_UNITS, "single": SINGLE_UNITS},
        "pending": len(rows) - len(graded),
        "all": _cell(graded),
        "last_30d": _cell([s for s in graded if s["date"] >= since30]),
        "last_7d": _cell([s for s in graded if s["date"] >= since7]),
        "by_section": {k: _cell(v) for k, v in sorted(by.items())},
    }
    card["report_line"] = report_block(card)
    return card


def _pct(x) -> str:
    return "PENDING" if x is None else f"{x:+.1%}"


def report_block(card: dict) -> str:
    a = card["all"]
    if not a["slips"]:
        return "ACCA + SINGLES (paper, 2.5u acca + 1u per leg): no graded slips yet"
    lines = [f"ACCA + SINGLES (paper, 2.5u acca + 1u per leg) · {a['slips']} graded slips, "
             f"{card['pending']} pending",
             f"  all: combo {_pct(a['combo_roi'])} v acca alone {_pct(a['acca_only_roi'])} "
             f"v singles alone {_pct(a['singles_only_roi'])} · acca won {a['acca_won']}, "
             f"slips in profit {a['slips_in_profit']}"]
    w = card["last_7d"]
    if w["slips"]:
        lines.append(f"  last 7 days: {w['slips']} slips, combo {_pct(w['combo_roi'])} "
                     f"v acca alone {_pct(w['acca_only_roi'])}")
    for k, c in card["by_section"].items():
        if not k.endswith("/ all") and c["slips"] >= 10:
            lines.append(f"  {k}: {c['slips']} slips, combo {_pct(c['combo_roi'])}")
    return "\n".join(lines)


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
    sys.exit(0)
