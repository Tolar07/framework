"""
PICKS LEDGER — what the board actually recommended, graded against results.

The CLV log records paper legs for calibration; it is NOT the list of slips the
Architect plays. This ledger is: every run writes output/picks/picks_<date>.json
with each single (pick, price, chance, tier, certainty, code) and every acca /
50%+ acca / mega slip with its legs and code. The latest run for a day
overwrites it, because the latest board is the one the Architect uses.

Each run then grades every past day from Flashscore results
(data.flashscore_results) and the heartbeat carries a SCORECARD: how many
singles won, hit rate and profit at 1 unit per single, split by tier and
certainty, plus how many accas landed. Results never guessed: a match not
found, or finished after extra time/penalties, stays PENDING (ID48).
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from engine import markets as mkt

LEDGER_DIR = Path(__file__).parent.parent / "output" / "picks"


def _single(bf) -> dict:
    league = bf.fixture.rsplit("(", 1)[-1].rstrip(")").strip()
    pick = mkt.display(bf.best_market_key, bf.probs.home_team, bf.probs.away_team)
    return {"fixture": bf.fixture.split(" (")[0], "league": league,
            "home": bf.probs.home_team, "away": bf.probs.away_team,
            "kickoff": bf.kickoff_date, "market": bf.best_market_key, "pick": pick,
            "price": bf.best_price, "chance": bf.best_model_prob, "tier": bf.tier,
            "certainty": bf.certainty, "code": bf.booking_code,
            "news_level": getattr(bf, "news_level", None),
            "news_note": getattr(bf, "news_note", None),
            "fotmob_id": getattr(bf, "fotmob_id", None),
            "kickoff_utc": getattr(bf, "kickoff_utc", None),
            "predicted_xi": getattr(bf, "predicted_xi", None),
            "lineup_check": None,
            "result": None, "ft": None}


def _slip(name, legs, combo, code) -> dict:
    odds = 1.0
    for bf, _pick, _prob in legs:
        odds *= bf.best_price or 1.0
    return {"name": name, "code": code, "odds": round(odds, 3), "chance": combo,
            "legs": [bf.fixture.split(" (")[0] for bf, _p, _q in legs], "result": None}


def write_ledger(target: str, board: list, accas: list, safe3: list, megas: list,
                 acca_codes: dict, safe3_codes: dict, mega_codes: Optional[dict]) -> Path:
    singles = [_single(bf) for bf in board
               if bf.on_deploy_shortlist and bf.probs is not None and bf.best_market_key]
    doc = {
        "date": target,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "singles": singles,
        "accas": [_slip(n, l, c, acca_codes.get(n)) for n, l, c in accas],
        "safe3": [_slip(n, l, c, safe3_codes.get(n)) for n, l, c in safe3],
        "megas": [_slip(n, l, c, (mega_codes or {}).get(n)) for n, l, c in megas],
    }
    LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    path = LEDGER_DIR / f"picks_{target}.json"
    path.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    return path


def _settle(market: str, hg: int, ag: int) -> str:
    """'won' / 'lost' / 'void' (stake back: DNB draw, Asian whole-line push)."""
    if market and market.startswith("SB:"):
        from engine import full_markets as fm
        pk = fm.parse_key(market)
        rule = fm.rule_for(*pk) if pk else None
        if rule is None:
            return "unknown"
        return {"win": "won", "lose": "lost", "push": "void"}[rule(hg, ag)]
    hit = mkt.settle(market, hg, ag)
    return "unknown" if hit is None else ("won" if hit else "lost")


def grade_all(events: list[dict], today: Optional[str] = None) -> list[str]:
    """Grade every ungraded single + slip in past ledgers. Returns flags."""
    from data.flashscore_results import find_result
    today = today or date.today().isoformat()
    flags = []
    for path in sorted(LEDGER_DIR.glob("picks_*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        if doc["date"] > today:
            continue
        changed = graded = pending = 0
        by_fixture = {}
        for s in doc["singles"]:
            if s["result"] is None:
                ev = find_result(events, s["home"], s["away"], s["kickoff"] or doc["date"])
                if ev and ev["finished_regular"]:
                    s["ft"] = f'{ev["fthg"]}-{ev["ftag"]}'
                    s["result"] = _settle(s["market"], ev["fthg"], ev["ftag"])
                    changed += 1
                elif ev and ev["finished_other"]:
                    s["result"] = "no-90min-result"
                    changed += 1
            graded += s["result"] is not None
            pending += s["result"] is None
            by_fixture[s["fixture"]] = s
        for kind in ("accas", "safe3", "megas"):
            for slip in doc.get(kind, []):
                legs = [by_fixture.get(f) for f in slip["legs"]]
                res = [l["result"] if l else None for l in legs]
                if "lost" in res:
                    new = "lost"
                elif res and all(r in ("won", "void") for r in res):
                    new = "won"
                else:
                    new = None
                if new != slip["result"]:
                    slip["result"] = new
                    changed += 1
        if changed:
            path.write_text(json.dumps(doc, indent=1), encoding="utf-8")
        if doc["date"] < today:
            flags.append(f"picks {doc['date']}: {graded} graded, {pending} pending "
                         f"(Flashscore)")
    return flags


def _pl(s: dict) -> float:
    if s["result"] == "won":
        return (s["price"] or 1.0) - 1.0
    if s["result"] == "lost":
        return -1.0
    return 0.0


def scorecard(days: int = 7, today: Optional[str] = None) -> str:
    """Short text: latest graded day + rolling `days`, singles by tier and
    certainty at 1 unit each, and slips landed."""
    today = today or date.today().isoformat()
    since = (date.fromisoformat(today) - timedelta(days=days)).isoformat()
    docs = []
    for path in sorted(LEDGER_DIR.glob("picks_*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        if since <= doc["date"] < today:
            docs.append(doc)
    if not docs:
        return "Scorecard: no graded days yet — results start after the first board's matches."

    def line(label, singles):
        done = [s for s in singles if s["result"] in ("won", "lost", "void")]
        if not done:
            return f"{label}: no results yet"
        w = sum(s["result"] == "won" for s in done)
        l = sum(s["result"] == "lost" for s in done)
        v = sum(s["result"] == "void" for s in done)
        pl = sum(_pl(s) for s in done)
        hit = 100 * w / max(w + l, 1)
        return (f"{label}: {w}W-{l}L" + (f"-{v}V" if v else "") +
                f" · {hit:.0f}% · {pl:+.2f}u")

    last = docs[-1]
    L = [f"📊 SCORECARD (singles at 1 unit each)",
         line(f"{last['date']}", last["singles"])]
    allsing = [s for d in docs for s in d["singles"]]
    L.append(line(f"Last {days} days", allsing))
    by_tier = defaultdict(list)
    by_cert = defaultdict(list)
    for s in allsing:
        by_tier[s.get("tier") or "?"].append(s)
        by_cert[s.get("certainty") or "?"].append(s)
    L.append("By tier — " + " · ".join(line(t, v).replace(f"{t}: ", f"{t} ")
                                        for t, v in sorted(by_tier.items())))
    L.append("By certainty — " + " · ".join(line(c, v).replace(f"{c}: ", f"{c} ")
                                            for c, v in sorted(by_cert.items())))
    for kind, label in (("safe3", "50%+ accas"), ("accas", "Accas"), ("megas", "Megas")):
        slips = [x for d in docs for x in d.get(kind, []) if x["result"] in ("won", "lost")]
        if slips:
            won = sum(x["result"] == "won" for x in slips)
            L.append(f"{label}: {won}/{len(slips)} landed")
    pend = sum(1 for s in allsing if s["result"] is None)
    if pend:
        L.append(f"{pend} single(s) still awaiting a result.")
    return "\n".join(L)
