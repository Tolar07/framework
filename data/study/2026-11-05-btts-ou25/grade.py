"""Grade the 2026-11-05 experiment slips (build.py) from Flashscore's 90-minute scores.

The Architect had the 34 accas (17 BTTS + 17 O/U 2.5 ACCA2) placed on SportyBet account 1 at
NGN 500 each, 2026-11-05 01:30 UTC (omniroute-test#54). The two long BTTS-ALL slips were not placed
and are graded as a record only. A leg with no unambiguous finished regular-time result reads
PENDING (HR35); a slip is won only when every leg is won.

usage: python data/study/2026-11-05-btts-ou25/grade.py [YYYY-MM-DD]   -> grades_<date>.json + summary
"""
import json, re, sys
from datetime import datetime, timezone
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from data import flashscore_results as fs

HERE = Path(__file__).resolve().parent
STAKE = 500
LEG = re.compile(r"^(?P<home>.+?) v (?P<away>.+?): (?P<mkt>BTTS (?P<btts>Yes|No)|O/U (?P<side>Over|Under) (?P<line>[\d.]+))")


def grade_leg(text: str, events: list[dict], date: str) -> dict:
    m = LEG.match(text)
    if not m:
        return {"leg": text, "result": "PENDING", "why": "leg not parsed"}
    ev = fs.find_result(events, m["home"], m["away"], date)
    if not ev or not ev.get("finished_regular") or ev.get("fthg") is None:
        return {"leg": text, "result": "PENDING", "why": "no finished regular-time result yet"}
    h, a = int(ev["fthg"]), int(ev["ftag"])
    if m["btts"]:
        won = (h > 0 and a > 0) == (m["btts"] == "Yes")
    else:
        won = (h + a > float(m["line"])) == (m["side"] == "Over")
    return {"leg": text, "result": "won" if won else "lost", "score": f"{h}-{a}"}


def grade_slip(s: dict, events: list[dict], date: str, placed: bool) -> dict:
    legs = [grade_leg(t, events, date) for t in s.get("legs") or []]
    rs = {x["result"] for x in legs}
    res = "lost" if "lost" in rs else "PENDING" if "PENDING" in rs else "won"
    out = {"name": s.get("name"), "code": s.get("code"), "odds": s.get("odds"), "chance": s.get("chance"),
           "placed": placed, "result": res, "legs": legs}
    if placed:
        out["stake_ngn"] = STAKE
        out["return_ngn"] = round(STAKE * float(s.get("odds") or 0), 2) if res == "won" else 0 if res == "lost" else None
    return out


def main(date: str = "2026-11-05", events: list[dict] | None = None) -> dict:
    src = json.loads((HERE / f"codes_{date}.json").read_text(encoding="utf-8"))
    events = events if events is not None else fs.results_since(3)
    groups = {"btts_accas": True, "ou25_acca2": True}
    doc = {"date": date, "graded_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), "groups": {}}
    for g, placed in groups.items():
        doc["groups"][g] = [grade_slip(s, events, date, placed) for s in src.get(g) or []]
    if src.get("btts_all"):
        alls = src["btts_all"] if isinstance(src["btts_all"], list) else [src["btts_all"]]
        doc["groups"]["btts_all (not placed)"] = [grade_slip(s, events, date, False) for s in alls if isinstance(s, dict)]
    summ = {}
    for g, slips in doc["groups"].items():
        n = {r: sum(s["result"] == r for s in slips) for r in ("won", "lost", "PENDING")}
        staked = sum(s.get("stake_ngn") or 0 for s in slips)
        ret = sum(s.get("return_ngn") or 0 for s in slips)
        summ[g] = {**n, "slips": len(slips), "staked_ngn": staked, "returned_ngn": ret,
                   "pnl_ngn": round(ret - staked, 2) if not n["PENDING"] else None}
    doc["summary"] = summ
    (HERE / f"grades_{date}.json").write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    return doc


def text(d: dict) -> str:
    L = [f"EXPERIMENT ACCAS {d['date']} (SportyBet account 1, NGN {STAKE} each) · graded {d['graded_at']}"]
    for g, s in d["summary"].items():
        L.append(f"{g}: {s['won']} won, {s['lost']} lost, {s['PENDING']} pending of {s['slips']}"
                 + (f" · staked NGN {s['staked_ngn']:,} returned NGN {s['returned_ngn']:,.0f} P&L "
                    + (f"NGN {s['pnl_ngn']:+,.0f}" if s['pnl_ngn'] is not None else "PENDING") if s['staked_ngn'] else ""))
    for g, slips in d["groups"].items():
        L.append("")
        L.append(g)
        for s in slips:
            L.append(f"  {s['name']} {s['code']} @{s['odds']}: {s['result'].upper()}  "
                     + "; ".join(f"{x['leg'].split(':')[0]} {x.get('score') or ''} {x['result']}" for x in s["legs"]))
    return "
".join(L)


if __name__ == "__main__":
    d = main(*(sys.argv[1:2] or []))
    t = text(d)
    (HERE / f"grades_{d['date']}.txt").write_text(t, encoding="utf-8")
    print(t)
