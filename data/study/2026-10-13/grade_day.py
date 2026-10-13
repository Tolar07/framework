"""
GRADE 13 OCT — every board and booking code made on 13 Oct 2026, settled
(Architect: "every ACC or every booking code that was created today, save
everything, because you grade everything"; "grade them now").

Results: FotMob (full time; half time from the goal minutes — a goal at 45'
or earlier, stoppage time included, is a first-half goal). Every leg settles
on SportyBet's own rule for its market (engine/full_markets.rule_for); the
1st-half double chance (market 63) is the double-chance rule on the half-time
score. A void leg leaves an acca at the other legs' odds. £1 flat on every
single and slip. A leg whose match has no FotMob result reads PENDING.

    python data/study/2026-10-13/grade_day.py   → GRADES.md, grades.json
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

from data import fotmob as fm  # noqa: E402
from data.flashscore_results import _sim  # noqa: E402
from engine import full_markets as fmk  # noqa: E402


def results() -> dict[str, dict]:
    """{'Home v Away' (study spelling): {ft, ht, fotmob}} from FotMob."""
    board = json.loads((HERE / "engine_board.json").read_text(encoding="utf-8"))
    fixtures = fm.matches_on("2026-10-13")
    out = {}
    for leg in board["legs"]:
        h, a = leg["match"].split(" v ", 1)
        m = max(fixtures, key=lambda m: min(_sim(h, m["home"]), _sim(a, m["away"])))
        if min(_sim(h, m["home"]), _sim(a, m["away"])) < 0.6:
            continue
        d = fm.match_details(m["id"])
        st = (d.get("header") or {}).get("status") or {}
        if not st.get("finished"):
            continue
        evs = ((d.get("content") or {}).get("matchFacts") or {}).get("events") or {}
        goals = [e for e in evs.get("events") or [] if e.get("type") == "Goal"]
        ht = [sum(1 for e in goals if e.get("isHome") and (e.get("time") or 99) <= 45),
              sum(1 for e in goals if not e.get("isHome") and (e.get("time") or 99) <= 45)]
        ft = [int(x) for x in st.get("scoreStr", "").replace(" ", "").split("-")]
        if len(goals) != sum(ft):
            ht = None                               # goal list incomplete: half time unknown
        out[leg["match"]] = {"ft": ft, "ht": ht, "fotmob": f"{m['home']} {ft[0]}-{ft[1]} {m['away']}"}
    return out


def settle(mid, spec: str, outcome: str, res: dict | None) -> str:
    """'won' / 'lost' / 'void' / 'PENDING'."""
    if not res:
        return "PENDING"
    if str(mid) == "63":                            # 1st-half double chance
        rule, score = fmk.rule_for(10, "", outcome), res["ht"]
    else:
        rule, score = fmk.rule_for(mid, spec or "", outcome), res["ft"]
    if rule is None or score is None:
        return "PENDING"
    r = rule(*score)
    return {"win": "won", "lose": "lost", "push": "void"}.get(r, r)


def slip(legs: list[tuple[str, float]]) -> dict:
    """{result, return (£1)} for a slip of (leg result, leg price)."""
    rs = [r for r, _p in legs]
    if "lost" in rs:
        return {"result": "lost", "return": 0.0}
    if "PENDING" in rs:
        return {"result": "PENDING", "return": None}
    odds = 1.0
    for r, p in legs:
        if r == "won":
            odds *= p
    return {"result": "won" if "won" in rs else "void", "return": round(odds, 2)}


def main() -> None:
    res = results()
    board = json.loads((HERE / "engine_board.json").read_text(encoding="utf-8"))
    codes = json.loads((HERE / "study_codes_v2.json").read_text(encoding="utf-8"))
    picks = json.loads((ROOT / "output/picks/picks_2026-10-13.json").read_text(encoding="utf-8"))

    def match_of(fixture: str) -> str | None:
        best = max(res, key=lambda k: min(_sim(fixture.split(" v ")[0], k.split(" v ")[0]),
                                          _sim(fixture.split(" v ", 1)[1], k.split(" v ", 1)[1])), default=None)
        return best

    out: dict = {"graded_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%MZ"), "results": res}
    # 1. live board
    singles = []
    for p in picks["singles"]:
        mid, spec, outcome = (p["market"].replace("SB:", "").split("|") + ["", ""])[:3]
        r = settle(mid, spec, outcome, res.get(match_of(p["fixture"])))
        singles.append({"fixture": p["fixture"], "pick": p["pick"], "price": p["price"], "code": p["code"], "result": r})
    by_fixture = {s["fixture"]: s for s in singles}
    board_slips = []
    for a in picks["accas"]:
        board_slips.append({"name": a["name"], "code": a["code"],
                            **slip([(by_fixture[f]["result"], by_fixture[f]["price"])
                                                                    for f in a["legs"]])})
    for a in picks["alts"]:
        legs = []
        for leg in a["alt_legs"]:
            mid, spec, outcome = (leg["market"].replace("SB:", "").split("|") + ["", ""])[:3]
            legs.append((settle(mid, spec, outcome, res.get(match_of(leg["fixture"]))), leg["price"]))
        board_slips.append({"name": a["name"], "code": a["code"], **slip(legs)})
    board_slips.append({"name": "Board MEGA (all 9 singles)", "code": "QGVBZ7",
                        **slip([(s["result"], s["price"]) for s in singles])})
    out["board"] = {"singles": singles, "slips": board_slips}
    # 2. study board
    legs = {}
    for leg in board["legs"]:
        pk, sel = leg["pick"], leg["pick"]["sel"]
        legs[leg["match"]] = {"match": leg["match"], "pick": f"{pk['mdesc']} {pk['pick']}".strip(), "price": pk["price"],
                              "result": settle(sel["marketId"], sel.get("specifier", ""), pk["pick"], res.get(leg["match"]))}

    def leg_of(text: str) -> dict:
        return legs[text.split(" — ")[0]]
    study_slips = []
    for a in codes["accas"] + [codes["mega"]]:
        study_slips.append({"name": a["name"], "code": a["code"],
                            **slip([(leg_of(t)["result"], leg_of(t)["price"])
                                                                    for t in a["legs"]])})
    btts = []
    for b in codes["btts"]:
        r = res.get(b["match"])
        won = None if not r else ((r["ft"][0] > 0 and r["ft"][1] > 0) == (b["call"] == "Yes"))
        btts.append({"match": b["match"], "call": b["call"], "price": b["price"], "code": b["code"],
                     "result": "PENDING" if won is None else "won" if won else "lost"})
    bmap = {b["match"]: b for b in btts}
    for s in codes["btts_slips"]:
        study_slips.append({"name": s["name"], "code": s["code"],
                            **slip([(bmap[t.split(" — ")[0]]["result"],
                                                                     bmap[t.split(" — ")[0]]["price"]) for t in s["legs"]])})
    out["study"] = {"legs": list(legs.values()), "btts": btts, "slips": study_slips}
    (HERE / "grades.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    (HERE / "GRADES.md").write_text(render(out), encoding="utf-8")
    print(render(out))


def _tally(rows: list[dict], price_key: str = "price") -> str:
    done = [r for r in rows if r["result"] in ("won", "lost", "void")]
    w = sum(r["result"] == "won" for r in done)
    lost = sum(r["result"] == "lost" for r in done)
    ret = sum(r[price_key] if r["result"] == "won" else 1.0 if r["result"] == "void" else 0.0 for r in done)
    return f"{w} won · {lost} lost · {len(done) - w - lost} void · £1 each: {ret - len(done):+.2f}u"


def render(o: dict) -> str:
    L = ["# 13 Oct 2026 — every board and code, graded", "",
         f"Graded {o['graded_at']} from FotMob results (`grade_day.py`). £1 flat on everything.", "",
         "## Results", ""]
    L += [f"- {v['fotmob']}" + (f" (HT {v['ht'][0]}-{v['ht'][1]})" if v["ht"] else " (HT PENDING)") for v in o["results"].values()]
    L += ["", "## Live board (sent to subscribers)", "", "| Fixture | Pick | Price | Code | Result |", "|---|---|---:|---|---|"]
    L += [f"| {s['fixture']} | {s['pick']} | {s['price']:.2f} | {s['code']} | {s['result']} |" for s in o["board"]["singles"]]
    L += ["", f"Singles: {_tally(o['board']['singles'])}", "", "| Slip | Code | Result | £1 returns |", "|---|---|---|---:|"]
    L += [f"| {s['name']} | {s['code']} | {s['result']} | {'PENDING' if s['return'] is None else format(s['return'], '.2f')} |"
          for s in o["board"]["slips"]]
    L += ["", "## Study board (not sent) — one market per fixture", "", "| Fixture | Pick | Price | Result |", "|---|---|---:|---|"]
    L += [f"| {g['match']} | {g['pick']} | {g['price']:.2f} | {g['result']} |" for g in o["study"]["legs"]]
    L += ["", f"Study singles: {_tally(o['study']['legs'])}", "", "### BTTS calls", "",
          "| Fixture | Call | Price | Code | Result |", "|---|---|---:|---|---|"]
    L += [f"| {b['match']} | {b['call']} | {b['price']:.2f} | {b['code']} | {b['result']} |" for b in o["study"]["btts"]]
    L += ["", f"BTTS calls: {_tally(o['study']['btts'])}", "", "### Study slips", "", "| Slip | Code | Result | £1 returns |",
          "|---|---|---|---:|"]
    L += [f"| {s['name']} | {s['code']} | {s['result']} | {'PENDING' if s['return'] is None else format(s['return'], '.2f')} |"
          for s in o["study"]["slips"]]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
