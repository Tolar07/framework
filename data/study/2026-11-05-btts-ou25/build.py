"""EXPERIMENT (Architect 2026-11-05 00:00): two record-only slips from the board.

1. BTTS for EVERY fixture on the board: the side (Yes or No) the board rates
   likelier, grouped into accas in the board's 2.00-3.00 odds band, plus one
   slip with every fixture.
2. Over/Under 2.5 for EVERY fixture: the likelier side, as 2-leg accas
   ("ACCA2"), strongest pairs first.

Chances are the board's own rated p (output/picks rated[].p: p_over_25, p_btts_yes).
Prices and outcome ids are pulled live from SportyBet now (HR59); a closed or
missing market reads PENDING (HR35). Codes are booked for viewing only: this
is NOT on the board, the placer never reads this folder, no stake anywhere.

usage: python data/study/2026-11-05-btts-ou25/build.py [YYYY-MM-DD]
"""
import json, sys, time, uuid
from datetime import datetime, timezone
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from pipeline.odds_sportybet import _get, is_open
from pipeline.sportybet_booking import create_booking_code

EVENT = "https://www.sportybet.com/api/ng/factsCenter/event?eventId={eid}&productId=3"
date = sys.argv[1] if len(sys.argv) > 1 else "2026-11-05"
picks = json.loads((ROOT / f"output/picks/picks_{date}.json").read_text(encoding="utf-8"))
run_id = f"exp-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:6]}"
now = datetime.now(timezone.utc)
ev_id = {s["fixture"]: (s.get("sb_event_id"), s.get("kickoff_utc")) for s in picks["singles"]}


def side(m, outs, chances):
    """[(pick, price, chance, selection)] for the open market's outcomes."""
    res = []
    for o in m.get("outcomes", []):
        if o.get("desc") in chances and o.get("odds") and o.get("id") is not None:
            res.append({"pick": o["desc"], "price": float(o["odds"]), "chance": chances[o["desc"]],
                        "sel": {"eventId": m["_eid"], "marketId": m.get("id"),
                                "specifier": m.get("specifier") or "", "outcomeId": o["id"]}})
    return sorted(res, key=lambda r: -r["chance"])


rows, pending = [], []
for r in picks["rated"]:
    fx = r["fixture"]
    eid, ko = ev_id.get(fx, (None, None))
    if not eid:
        pending.append(f"{fx}: no SportyBet event id"); continue
    if ko and datetime.fromisoformat(ko.replace("Z", "+00:00")) <= now:
        pending.append(f"{fx}: already kicked off"); continue
    try:
        ev = _get(EVENT.format(eid=eid)).get("data") or {}
    except Exception as e:  # noqa: BLE001
        pending.append(f"{fx}: fetch failed ({e})"); continue
    p_o25, p_btts = r["p"][4], r["p"][6]
    row = {"fixture": fx, "league": r["league"], "kickoff_utc": ko, "btts": None, "ou25": None}
    for m in ev.get("markets", []):
        if not is_open(m):
            continue
        m["_eid"] = eid
        if m.get("desc") == "GG/NG" and not m.get("specifier"):
            row["btts"] = side(m, None, {"Yes": p_btts, "No": 1 - p_btts})
        if m.get("desc") == "Over/Under" and m.get("specifier") == "total=2.5":
            row["ou25"] = side(m, None, {"Over 2.5": p_o25, "Under 2.5": 1 - p_o25})
    for k in ("btts", "ou25"):
        if not row[k] or len(row[k]) < 2:
            pending.append(f"{fx}: {k} NO DATA - PENDING (market closed or missing)"); row[k] = None
    rows.append(row)
    time.sleep(0.3)


def slip(name, legs):
    odds = chance = 1.0
    for l in legs:
        odds *= l["price"]; chance *= l["chance"]
    code, _u, note = create_booking_code([l["sel"] for l in legs])
    return {"name": name, "code": code or f"PENDING ({note})", "odds": round(odds, 2),
            "chance": round(chance, 3), "legs": [f"{l['fixture']}: {l['label']} @{l['price']:.2f} ({l['chance']:.0%})" for l in legs]}


def legs_for(k, label):
    out = []
    for row in rows:
        if row[k]:
            best, other = row[k][0], row[k][1]
            out.append({**best, "fixture": row["fixture"], "label": f"{label} {best['pick']}",
                        "other": f"{other['pick']} @{other['price']:.2f}"})
    return sorted(out, key=lambda l: -l["chance"])


def band_groups(legs, lo=2.0, hi=3.0, max_legs=6):
    groups, cur, odds = [], [], 1.0
    for l in legs:
        if cur and (odds * l["price"] > hi or len(cur) >= max_legs):
            groups.append(cur); cur, odds = [], 1.0
        cur.append(l); odds *= l["price"]
        if odds >= lo:
            groups.append(cur); cur, odds = [], 1.0
    if cur:
        groups.append(cur)
    # an acca is 2+ legs: pair the leftover singles, an odd last one joins the slip before
    singles = [g[0] for g in groups if len(g) == 1]
    groups = [g for g in groups if len(g) > 1] + pairs(singles)
    return groups


def pairs(legs):
    gs = [legs[i:i + 2] for i in range(0, len(legs), 2)]
    if len(gs) > 1 and len(gs[-1]) == 1:
        last = gs.pop()
        gs[-1] = gs[-1] + last
    return gs


btts = legs_for("btts", "BTTS")
ou = legs_for("ou25", "O/U")
out = {"run_id": run_id, "fetched_at": now.isoformat(timespec="seconds"), "date": date,
       "status": "EXPERIMENT - record only, not on the board, not placed",
       "btts_accas": [slip(f"BTTS {chr(65 + i)}", g) for i, g in enumerate(band_groups(btts))],
       "btts_all": [slip(f"BTTS ALL part {i // 26 + 1}", btts[i:i + 26]) for i in range(0, len(btts), 26)],
       "ou25_acca2": [slip(f"O/U2.5 ACCA2 {chr(65 + i)}", g) for i, g in enumerate(pairs(ou))],
       "btts_yes_no_split": {"yes": sum(l["pick"] == "Yes" for l in btts), "no": sum(l["pick"] == "No" for l in btts)},
       "ou_split": {"over": sum(l["pick"].startswith("Over") for l in ou), "under": sum(l["pick"].startswith("Under") for l in ou)},
       "pending": pending}
(Path(__file__).parent / f"codes_{date}.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
print(json.dumps(out, indent=1))
