import json, sys
from types import SimpleNamespace as NS
from pathlib import Path
sys.path.insert(0, "/home/user/framework")
from output import produce_bet as pb
from pipeline import sportybet_booking as bk
SCR = Path("/tmp/claude-0/-home-user/57b767b7-a00f-5352-ac61-3afe90d7689d/scratchpad")
d = json.load(open(SCR / "engine_board.json"))
def leg(l, p):
    key = f"SB:{p['mid']}|{p['spec']}|{p['pick']}"
    bf = NS(fixture=f"{l['match']} ({l['comp']})", best_price=p["price"], best_market_key=key,
            best_market=f"{p['mdesc']} {p['spec']}: {p['pick']}".replace("  ", " "))
    return (bf, bf.best_market, p["win"]), p, l
def book(items):
    c, _u, note = bk.create_booking_code([p["sel"] for _, p, _ in items])
    return c or f"PENDING ({note})"
def slip(name, items):
    odds = ch = 1.0
    for t, p, _ in items: odds *= p["price"]; ch *= p["win"]
    return {"name": name, "code": book(items), "odds": round(odds, 2), "chance": round(ch, 3),
            "legs": [f"{l['match']} — {p['fam']}: {t[1]}" for t, p, l in items]}
legs = [leg(l, l["pick"]) for l in d["legs"] if l["pick"]]
val = lambda x: -(x[0][2] * x[0][0].best_price)
out = {"run_id": d["run_id"], "fetched_at": d["fetched_at"]}
# 1) main accas: 75%+ legs by the board's rules, then the rest (study) by the same odds band + mix
strong = sorted([x for x in legs if x[0][2] >= pb.ACCA_LEG_MIN], key=val)
rest = sorted([x for x in legs if x[0][2] < pb.ACCA_LEG_MIN], key=val)
by = {id(x[0][0]): x for x in legs}
accas, n = [], 0
for pool, tag in ((strong, "75%+ legs"), (rest, "study legs, under 75%")):
    for g in pb._table3_groups([x[0] for x in pool]):
        accas.append({**slip(pb._acca_name(n), [by[id(t[0])] for t in g]), "kind": tag}); n += 1
placed = {l for a in accas for l in a["legs"]}
left = [x for x in legs if f"{x[2]['match']} — {x[1]['fam']}: {x[0][1]}" not in placed]
if left:                                     # anything the 2.00-3.00 band couldn't fit: one last slip
    accas.append({**slip(pb._acca_name(n), left), "kind": "remaining legs"})
out["accas"] = accas
out["mega"] = slip("Main MEGA", legs)
# 2) BTTS: every fixture, the side the engine rates likelier
bt = []
for l in d["legs"]:
    y, nn = l["btts"].get("Yes"), l["btts"].get("No")
    if not (y and nn): continue
    side = y if y["win"] >= nn["win"] else nn
    other = nn if side is y else y
    bt.append((l, side, other))
out["btts"] = [{"match": l["match"], "call": s["pick"], "price": s["price"], "win": round(s["win"], 3),
                "model": s["model_win"], "ev": round(s["ev"], 3), "other": f"{o['pick']} @{o['price']:.2f} {o['win']:.0%}",
                "code": book([leg(l, s)])} for l, s, o in bt]
btl = sorted([leg(l, s) for l, s, _ in bt], key=lambda x: -x[0][2])
strong_b = [x for x in btl if x[0][2] >= 0.60]
bby = {id(x[0][0]): x for x in btl}
groups = pb._table3_groups(sorted([x[0] for x in strong_b], key=lambda t: -(t[2] * t[0].best_price)))
out["btts_slips"] = [slip(f"BTTS {chr(65+i)}", [bby[id(t[0])] for t in g]) for i, g in enumerate(groups)]
out["btts_slips"].append(slip("BTTS MEGA (all 17)", btl))
json.dump(out, open(SCR / "study_codes_v2.json", "w"), indent=1, default=str)
print(json.dumps(out, indent=1, default=str))
