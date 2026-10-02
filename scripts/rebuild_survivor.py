"""
One-off rebuild of the AI Survivor lineage from the last saved laptop state
(19 Sep 2026, framework branch elo-persistence: data/heartbeat/lineage.json +
history.jsonl, copied to data/survivor/legacy/) onto the cloud framework's
engine/survivor.py. Run once, 2026-10-02:  python scripts/rebuild_survivor.py

Rules applied strictly (Architect rulings 2026-08-29 / 09-17 / 09-19):
  1. ONE LOSS IS EXTINCTION. ln_d6ef3f7604 lost "Celtic Draw No Bet" on 17 Sep
     (1-3, graded in the legacy history) but the loss was never applied to the
     lineage, which kept playing. It goes extinct on 17 Sep; its 18 Sep pick
     (Reims v Montpellier Under 3.5, won) stays in the record but is not
     credited to a dead lineage.
  2. The 18 Sep pick FC Gandzasar v FC Urartu (Urartu Draw No Bet @1.40) was
     never graded: FT 0-3 (FotMob) -> WIN for ln_4abf6adda1.
  3. Breeding on 19 Sep with the FIXED slot allocation (every survivor keeps a
     slot, spare slots go to the richest winners). The legacy run used the
     buggy breed that deleted two winning lineages and 26.11 of bankroll.
  4. The 8 picks issued that day (dated 19 Sep, played 20 Sep) are assigned
     by the model's own rule — strongest lineage takes the strongest pick
     (legacy edge order) — and graded from FotMob full-time scores.
No heartbeat was issued 21 Sep - 2 Oct (the laptop pipeline was down), so the
lineages simply waited. They breed on the next daily run.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from engine import survivor as sv  # noqa: E402

LEG = ROOT / "data" / "survivor" / "legacy"
legacy_pop = json.loads((LEG / "lineage_2026-09-19.json").read_text(encoding="utf-8"))
legacy_hist = [json.loads(x) for x in
               (LEG / "history_2026-09-19.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]

# Full-time scores read from FotMob on 2026-10-02 (regular time, all "FT").
SCORES = {
    "FC Gandzasar v FC Urartu": (0, 3),
    "FK Crvena Zvezda v FK Radnicki Nis": (3, 0),
    "Getafe v Malaga CF": (1, 0),
    "Mjallby AIF v GAIS": (0, 3),
    "FC Porto v Benfica": (3, 1),
    "HNK Rijeka v HNK Hajduk Split": (3, 0),
    "Egnatia v Partizani": (2, 1),
    "Siroki Brijeg v Borac Banja Luka": (2, 3),
    "Zaglebie Lubin v Wisla Plock": (0, 2),
}
DEAD_D6EF = "ln_d6ef3f7604"

# --- population at 19 Sep, before breeding -----------------------------------
pop = {"lineages": [], "last_bred_date": "2026-09-18"}
for l in legacy_pop["lineages"]:
    pop["lineages"].append({
        "lineage_id": l["lineage_id"], "parent_id": l["parent_id"],
        "generation": l["generation"], "bankroll": l["bankroll"], "stake": sv.STAKE,
        "wins": l["wins"], "losses": l["losses"], "alive": l["alive"],
        "born_date": l["born_date"], "last_result": l["last_result"],
        "to_breed": l["alive"] and l["last_result"] == "WIN", "holding": None})

# --- history in the new schema --------------------------------------------------
hist = []
for r in legacy_hist:
    home, _, away = (r["fixture"] or "").partition(" v ")
    rec = {"date": r["date"], "lineage_id": r.get("lineage_id"), "generation": r.get("generation"),
           "fixture": r["fixture"], "home": home, "away": away, "league": r.get("league"),
           "market_key": r.get("market_key"), "pick": r.get("pick") or r.get("market_type"),
           "price": r.get("price"), "chance": r.get("probability"), "stake": sv.STAKE,
           "result": r["result"], "score": r.get("settled_score"), "applied": True,
           "source": "legacy (laptop) " + (r.get("graded_by") or r.get("source") or "")}
    hist.append(rec)

# 1. d6ef: one loss is extinction (17 Sep Celtic DNB 1-3).
d6 = next(l for l in pop["lineages"] if l["lineage_id"] == DEAD_D6EF)
reims = next(h for h in hist if h["lineage_id"] == DEAD_D6EF and h["date"] == "2026-09-18")
d6.update(bankroll=round(d6["bankroll"] - sv.STAKE * (reims["price"] - 1), 2), wins=d6["wins"] - 1,
          losses=d6["losses"] + 1, alive=False, last_result="LOSS", to_breed=False)
reims["note"] = "holder extinct 17 Sep (Celtic DNB lost 1-3) — win not credited (rebuild 2026-10-02)"

# 2. Urartu (18 Sep) for ln_4abf6adda1.
urartu = next(h for h in hist if h["fixture"] == "FC Gandzasar v FC Urartu")
urartu.update(market_key="SB:11||Away", applied=False, score="0-3",
              source="graded from FotMob (rebuild 2026-10-02)")
sv.apply_result(pop, urartu, "WIN")

# 3. Fixed breeding on 19 Sep.
sv.breed(pop, "2026-09-19")

# 4. The 8 picks of 19 Sep (played 20 Sep): strongest lineage -> strongest pick.
day = [h for h in hist if h["date"] == "2026-09-19"]
hist = [h for h in hist if h["date"] != "2026-09-19"]
day.sort(key=lambda h: -float(next(r["edge"] for r in legacy_hist if r["fixture"] == h["fixture"])))
alive = sorted(sv.living(pop), key=lambda x: -x["bankroll"])
assert len(alive) == len(day) == 8, (len(alive), len(day))
for ln, h in zip(alive, day):
    hg, ag = SCORES[h["fixture"]]
    h.update(date="2026-09-20", legacy_date="2026-09-19", legacy_lineage_id=h["lineage_id"],
             lineage_id=ln["lineage_id"], generation=ln["generation"], applied=False,
             result="PENDING", score=f"{hg}-{ag}",
             source="graded from FotMob (rebuild 2026-10-02)")
    from engine.picks_ledger import _settle
    res = {"won": "WIN", "lost": "LOSS", "void": "VOID"}[_settle(h["market_key"], hg, ag)]
    sv.apply_result(pop, h, res)
    hist.append(h)
pop["rebuilt"] = "2026-10-02 from laptop state of 2026-09-19 (scripts/rebuild_survivor.py)"

sv.save(pop, hist)
print(sv.report(pop, hist, "2026-10-03"))
