"""
PICKS LEDGER — what the board actually recommended, graded against results.

The CLV log records paper legs for calibration; it is NOT the list of slips the
Architect plays. This ledger is: every run writes output/picks/picks_<date>.json
with each single (pick, price, chance, tier, certainty, code) and every acca /
50%+ acca / mega slip with its legs and code. The latest run for a day
overwrites it, because the latest board is the one the Architect uses.

Every RATED fixture on the board (not just the picks) is also recorded under
"rated" with the model's main probabilities, and graded the same way. That
is the model's report card on far more matches than the picks alone; it is
read by the scorecard only and never changes how picks are chosen.

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
            "price": bf.best_price, "chance": bf.best_model_prob,
            # before any learned correction (engine/learning.py, 2026-10-05)
            "chance_raw": (None if bf.best_model_prob is None else
                           round(bf.best_model_prob - (getattr(bf, "learn_shift", 0.0) or 0.0), 4)),
            "tier": bf.tier,
            "certainty": bf.certainty, "code": bf.booking_code,
            "news_level": getattr(bf, "news_level", None),
            "news_note": getattr(bf, "news_note", None),
            "switched_from": getattr(bf, "switched_from", None),
            "orig_market": getattr(bf, "orig_market_key", None),
            "fotmob_id": getattr(bf, "fotmob_id", None),
            "kickoff_utc": getattr(bf, "kickoff_utc", None),
            "predicted_xi": getattr(bf, "predicted_xi", None),
            "lineup_check": None,
            # Closing-line value (improvement #5): SportyBet event + market
            # identity, so news_check.py can read the price just before kickoff.
            "sb_event_id": getattr(bf, "sb_event_id", None),
            "sb_tid": getattr(bf, "sb_tid", None),
            "sb_market": _sb_market(bf.best_market_key),
            "closing_price": None, "clv": None,
            "stake_pct": getattr(bf, "stake_pct", None),
            "ev": getattr(bf, "best_mes_ev", None),
            # the Betfair Exchange's fair chance and our price's value against
            # it (pipeline/sharp.py, 2026-10-05); None where not priced there
            "sharp_p": getattr(bf, "sharp_p", None),
            "sharp_ev": getattr(bf, "sharp_ev", None),
            # price at the FIRST board for this day + the move since (drift guard)
            "first_price": getattr(bf, "first_price", None) or bf.best_price,
            "drift_since_board": getattr(bf, "drift_pct", None),
            "result": None, "ft": None}


# Order of the probabilities stored per rated fixture.
RATED_KEYS = ("home", "draw", "away", "o15", "o25", "o35", "btts")
RATED_GRADE_DAYS = 14   # older ungraded fixtures are left as they are


def _rated(bf) -> dict:
    p = bf.probs
    return {"fixture": bf.fixture.split(" (")[0],
            "league": bf.fixture.rsplit("(", 1)[-1].rstrip(")").strip(),
            "home": p.home_team, "away": p.away_team, "kickoff": bf.kickoff_date,
            "src": getattr(bf, "prob_source", "model"),
            "p": [round(float(x), 3) for x in (p.p_home, p.p_draw, p.p_away, p.p_over_15,
                                                p.p_over_25, p.p_over_35, p.p_btts_yes)],
            "ft": None}


def _sb_market(key: str) -> Optional[dict]:
    """{id, desc, spec, outcome} identifying the pick's outcome on SportyBet."""
    if key and key.startswith("SB:"):
        from engine import full_markets as fm
        pk = fm.parse_key(key)
        return {"id": pk[0], "desc": None, "spec": pk[1], "outcome": pk[2]} if pk else None
    try:
        from pipeline.sportybet_booking import _SB_MARKET
    except Exception:  # noqa: BLE001
        return None
    spec = _SB_MARKET.get(key)
    return {"id": None, "desc": spec[0], "spec": spec[1], "outcome": spec[2]} if spec else None


def _slip(name, legs, combo, code) -> dict:
    odds = 1.0
    for bf, _pick, _prob in legs:
        odds *= bf.best_price or 1.0
    return {"name": name, "code": code, "odds": round(odds, 3), "chance": combo,
            "legs": [bf.fixture.split(" (")[0] for bf, _p, _q in legs], "result": None}


def _alt_slip(name, legs, combo, code) -> dict:
    """An alternative-market acca (order 31): its legs carry their OWN market,
    so they are graded here, not from the main singles."""
    odds = 1.0
    for leg in legs:
        odds *= leg[4] or 1.0
    return {"name": name, "code": code, "odds": round(odds, 3), "chance": combo,
            "legs": [bf.fixture.split(" (")[0] for bf, *_ in legs],
            "alt_legs": [{"fixture": bf.fixture.split(" (")[0],
                          "league": bf.fixture.rsplit("(", 1)[-1].rstrip(")").strip(),
                          "home": bf.probs.home_team, "away": bf.probs.away_team,
                          "kickoff": bf.kickoff_date, "market": key, "pick": pick,
                          "price": price, "chance": prob, "result": None, "ft": None}
                         for bf, pick, prob, key, price in legs],
            "result": None}


def write_ledger(target: str, board: list, accas: list, safe3: list, megas: list,
                 acca_codes: dict, safe3_codes: dict, mega_codes: Optional[dict],
                 alts: Optional[list] = None, alt_codes: Optional[dict] = None,
                 values: Optional[list] = None, value_codes: Optional[dict] = None) -> Path:
    singles = [_single(bf) for bf in board
               if bf.on_deploy_shortlist and bf.probs is not None and bf.best_market_key]
    doc = {
        "date": target,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "singles": singles,
        "accas": [_slip(n, l, c, acca_codes.get(n)) for n, l, c in accas],
        "safe3": [_slip(n, l, c, safe3_codes.get(n)) for n, l, c in safe3],
        "megas": [_slip(n, l, c, (mega_codes or {}).get(n)) for n, l, c in megas],
        "alts": [_alt_slip(n, l, c, (alt_codes or {}).get(n)) for n, l, c in (alts or [])],
        # positive-value bets (order 37): own markets, graded like the alt legs
        "value": [_alt_slip(n, l, c, (value_codes or {}).get(n)) for n, l, c in (values or [])],
        "rated": [_rated(bf) for bf in board if bf.probs is not None],
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
    by_day = _index_by_day(events)
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
                    if s.get("orig_market"):      # order 32: did switching pay?
                        s["orig_result"] = _settle(s["orig_market"], ev["fthg"], ev["ftag"])
                    changed += 1
                elif ev and ev["finished_other"]:
                    s["result"] = "no-90min-result"
                    changed += 1
            graded += s["result"] is not None
            pending += s["result"] is None
            by_fixture[s["fixture"]] = s
        for slip in (doc.get("alts", []) + doc.get("replaced", [])
                     + doc.get("value", [])):                         # own-market legs
            for leg in slip.get("alt_legs", []):
                if leg["result"] is None:
                    ev = find_result(events, leg["home"], leg["away"],
                                     leg["kickoff"] or doc["date"])
                    if ev and ev["finished_regular"]:
                        leg["ft"] = f'{ev["fthg"]}-{ev["ftag"]}'
                        leg["result"] = _settle(leg["market"], ev["fthg"], ev["ftag"])
                        changed += 1
                    elif ev and ev["finished_other"]:
                        leg["result"] = "no-90min-result"
                        changed += 1
        for kind in ("accas", "safe3", "megas", "alts", "replaced", "value"):
            for slip in doc.get(kind, []):
                if kind in ("alts", "replaced", "value"):
                    legs = slip.get("alt_legs", [])
                else:
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
        rated = doc.get("rated", [])
        rated_done = 0
        recent = doc["date"] >= (date.fromisoformat(today)
                                 - timedelta(days=RATED_GRADE_DAYS)).isoformat()
        for r in rated:
            if r["ft"] is None and recent:
                day = r["kickoff"] or doc["date"]
                ev = find_result(_events_near(by_day, day), r["home"], r["away"], day)
                if ev and ev["finished_regular"]:
                    r["ft"] = f'{ev["fthg"]}-{ev["ftag"]}'
                    changed += 1
                elif ev and ev["finished_other"]:
                    r["ft"] = "no-90min-result"
                    changed += 1
            rated_done += r["ft"] is not None
        if changed:
            path.write_text(json.dumps(doc, indent=1), encoding="utf-8")
        if doc["date"] < today:
            flags.append(f"picks {doc['date']}: {graded} graded, {pending} pending"
                         + (f"; {rated_done}/{len(rated)} rated fixtures graded" if rated else "")
                         + " (Flashscore)")
    return flags


def _index_by_day(events: list[dict]) -> dict:
    out: dict = defaultdict(list)
    for ev in events:
        out[(ev.get("kickoff_utc") or "")[:10]].append(ev)
    return out


def _events_near(by_day: dict, day: str) -> list[dict]:
    """Events within a day either side (the window find_result accepts)."""
    try:
        d0 = date.fromisoformat(day[:10])
    except ValueError:
        return []
    return [ev for k in (-1, 0, 1)
            for ev in by_day.get((d0 + timedelta(days=k)).isoformat(), [])]


def _pl(s: dict) -> float:
    if s["result"] == "won":
        return (s["price"] or 1.0) - 1.0
    if s["result"] == "lost":
        return -1.0
    return 0.0


def calibration(singles: list) -> list[str]:
    """Is the chance we state the chance that happens? Brier score, log loss
    and a bucket table on won/lost singles (voids excluded)."""
    import math
    done = [s for s in singles if s.get("result") in ("won", "lost") and s.get("chance")]
    if len(done) < 5:
        return []
    ys = [(min(max(float(s["chance"]), 0.01), 0.99), 1 if s["result"] == "won" else 0)
          for s in done]
    brier = sum((p - y) ** 2 for p, y in ys) / len(ys)
    logloss = -sum(math.log(p if y else 1 - p) for p, y in ys) / len(ys)
    out = [f"Calibration ({len(ys)} picks): Brier {brier:.3f} · log loss {logloss:.3f} "
           f"(lower = better; Brier 0.25 = coin-flip)"]
    rows = []
    for lo, hi in ((0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.0)):
        b = [(p, y) for p, y in ys if lo <= p < hi]
        if b:
            rows.append(f"said {lo*100:.0f}-{hi*100:.0f}% → won {100*sum(y for _, y in b)/len(b):.0f}% "
                        f"(n={len(b)})")
    if rows:
        out.append("  " + " · ".join(rows))
    return out


def _outcomes(ft: str) -> Optional[list[int]]:
    """0/1 for each RATED_KEYS outcome from a 'h-a' score, None if not a score."""
    try:
        hg, ag = (int(x) for x in ft.split("-"))
    except (AttributeError, ValueError):
        return None
    t = hg + ag
    return [int(hg > ag), int(hg == ag), int(hg < ag), int(t > 1.5), int(t > 2.5),
            int(t > 3.5), int(hg > 0 and ag > 0)]


def model_check(rated: list) -> list[str]:
    """How well the model's own numbers matched reality on every rated fixture
    (src 'model'): Brier scores for 1X2, Over 2.5 and BTTS, and how often the
    model's favourite won by stated chance."""
    rows = [(r["p"], y) for r in rated
            if r.get("src") == "model" and (y := _outcomes(r.get("ft"))) is not None]
    if len(rows) < 10:
        return []
    n = len(rows)
    b1x2 = sum(sum((p[i] - y[i]) ** 2 for i in range(3)) for p, y in rows) / n
    bo25 = sum((p[4] - y[4]) ** 2 for p, y in rows) / n
    bbtts = sum((p[6] - y[6]) ** 2 for p, y in rows) / n
    out = [f"Model check ({n} rated fixtures, not just picks): Brier 1X2 {b1x2:.3f} · "
           f"Over 2.5 {bo25:.3f} · BTTS {bbtts:.3f} (no skill = 0.667 / 0.250 / 0.250)"]
    fav = []
    for p, y in rows:
        i = max(range(3), key=lambda k: p[k])
        fav.append((p[i], y[i]))
    cells = []
    for lo, hi in ((0.4, 0.5), (0.5, 0.6), (0.6, 0.7), (0.7, 1.0)):
        b = [won for q, won in fav if lo <= q < hi]
        if b:
            cells.append(f"{lo*100:.0f}-{hi*100:.0f}% → {100*sum(b)/len(b):.0f}% (n={len(b)})")
    if cells:
        out.append("  Model favourite said → won: " + " · ".join(cells))
    return out


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
    for kind, label in (("safe3", "50%+ accas"), ("accas", "Accas"), ("alts", "Alt-market accas"),
                        ("megas", "Megas")):
        slips = [x for d in docs for x in d.get(kind, []) if x["result"] in ("won", "lost")]
        if slips:
            won = sum(x["result"] == "won" for x in slips)
            L.append(f"{label}: {won}/{len(slips)} landed")
    L.extend(calibration(allsing))
    L.extend(model_check([r for d in docs for r in d.get("rated", [])]))
    pos = [s for s in allsing if (s.get("ev") or 0) > 0]
    neg = [s for s in allsing if s.get("ev") is not None and s["ev"] <= 0]
    if pos or neg:
        L.append("By value — " + line("+EV", pos).replace("+EV: ", "+EV ") + " · "
                 + line("-EV", neg).replace("-EV: ", "-EV "))
    clvs = [s["clv"] for s in allsing if s.get("clv") is not None]
    if clvs:
        beat = sum(c > 0 for c in clvs)
        L.append(f"Closing-line value: avg {sum(clvs)/len(clvs):+.2f}% over {len(clvs)} picks · "
                 f"beat the close {beat}/{len(clvs)} (positive = price shortened after we picked)")
    pend = sum(1 for s in allsing if s["result"] is None)
    if pend:
        L.append(f"{pend} single(s) still awaiting a result.")
    return "\n".join(L)
