"""Brain store tests — schema, migrations, content_hash, payload round-trip,
predictions, runs, legs mirror, corrections, read-only guard.

Uses a throwaway SQLite file (tempdir); never touches brain/olp.db.
"""
import sys
import tempfile
import json
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).parent.parent))

from brain.store import (Brain, content_hash, elo_to_payload, elo_from_payload,
                         dc_to_payload, dc_from_payload, SCHEMA_VERSION)
from engine.elo import EloModel
from clv.clv_logger import CLVLog

_tmp = Path(tempfile.mkdtemp(prefix="olp_xdv_brain_test_"))

R = lambda d, h, a, fh, fa: SimpleNamespace(date=d, home_team=h, away_team=a,
                                            fthg=fh, ftag=fa)

# --- 1. schema + version refusal ------------------------------------------
db = _tmp / "t1.db"
b = Brain(db)
assert b.schema_version == SCHEMA_VERSION, "fresh DB must be at SCHEMA_VERSION"
names = {r["name"] for r in b.query(
    "SELECT name FROM sqlite_master WHERE type='table'")}
assert {"meta", "model_state", "predictions", "legs", "corrections", "runs"} \
    <= names, f"missing tables: {names}"
b.close()
b2 = Brain(db)
b2._conn.execute("UPDATE meta SET value='99' WHERE key='schema_version'")
b2._conn.commit(); b2.close()
try:
    Brain(db)
    raise AssertionError("newer-schema DB must be refused")
except RuntimeError:
    pass
print("1. schema + newer-schema refusal: OK")

# --- 2. content_hash -------------------------------------------------------
rs = [R("2026-08-01", "A", "B", 1, 2), R("2026-08-02", "B", "A", 0, 0)]
assert content_hash(rs) == content_hash(list(reversed(rs))), "order-insensitive"
assert content_hash(rs) != content_hash(rs, salt="x"), "salt-sensitive"
assert content_hash(rs) != content_hash([R("2026-08-01", "A", "B", 1, 3)]), \
    "row-sensitive"
print("2. content_hash: OK")

# --- 3. model_state round-trip + version refusal ---------------------------
db3 = _tmp / "t3.db"
b3 = Brain(db3)
m = EloModel(ratings={"A": 1500.0, "B": 1421.5}, n_matches=12,
             last_date="2026-08-02")
m._draw_a, m._draw_b = 0.1, 0.2
b3.save_model_state("elo:test", "elo", 1, "h", m.n_matches, m.last_date,
                    None, elo_to_payload(m))
st = b3.load_model_state("elo:test")
assert st is not None and st["content_hash"] == "h"
m2 = elo_from_payload(st["payload"])
assert m2.ratings == m.ratings and m2.n_matches == m.n_matches
assert abs(m2._draw_a - 0.1) < 1e-12
# upsert overwrites
m3 = EloModel(ratings={"A": 1600.0}, n_matches=13, last_date="2026-08-03")
b3.save_model_state("elo:test", "elo", 1, "h2", m3.n_matches, m3.last_date,
                    None, elo_to_payload(m3))
assert b3.load_model_state("elo:test")["n_matches"] == 13, "upsert must overwrite"
# newer engine version refused by from_payload (HR35)
bad = dict(elo_to_payload(m)); bad["version"] = 99
try:
    elo_from_payload(bad)
    raise AssertionError("newer payload version must be refused")
except ValueError:
    pass
# dc payload delegates to the engine (round-trip through the engine's shape)
from engine.dixon_coles import DixonColesModel, TeamStrength
dc = DixonColesModel(league="X", home_advantage=0.3, rho=-0.05,
                     n_matches_fit=200)
dc.teams = {"A": TeamStrength(1.2, -0.4), "B": TeamStrength(0.7, -0.1)}
assert dc_to_payload(dc)["teams"]["A"] == [1.2, -0.4]
assert dc_from_payload(dc_to_payload(dc)).teams["B"].attack == 0.7
print("3. model_state round-trip + version refusal + dc payload: OK")

# --- 4. predictions --------------------------------------------------------
db4 = _tmp / "t4.db"
b4 = Brain(db4)
rows = []
for i, mkt in enumerate(["1X2_HOME", "OVER_2_5"]):
    rows.append(dict(run_id="r1", predicted_at="2026-08-05T07:00:00+00:00",
                     league="Eredivisie", fixture="Nijmegen v Telstar",
                     match_date="2026-08-05", market=mkt, model_engine="dc",
                     model_prob=0.5 + 0.1 * i, entry_odds=None, bookmaker=None,
                     ev=None, on_deploy_shortlist=1))
rows.append(dict(run_id="r1", predicted_at="2026-08-05T07:00:00+00:00",
                 league="Champions League", fixture="Fenerbahçe v Sturm Graz",
                 match_date="2026-08-05", market="1X2_HOME", model_engine="dc",
                 model_prob=0.56, entry_odds=1.9, bookmaker="Bet365", ev=0.05,
                 on_deploy_shortlist=0))
assert b4.append_predictions(rows) == 3
assert len(b4.predictions_for(market="1X2_HOME")) == 2
assert len(b4.predictions_for(run_id="r1", fixture="Nijmegen")) == 2
# accent-insensitive team lookup
hit = b4.predictions_for(team="Fenerbahce", limit=10)
assert any("Fenerbahçe" in h["fixture"] for h in hit), \
    "accent folding must match Fenerbahce -> Fenerbahçe"
p = b4.predictions_summary()
assert p["n_rows"] == 3 and p["n_runs"] == 1 and p["last_run_predictions"] == 3
print("4. predictions append/query + accent folding: OK")

# --- 5. runs ---------------------------------------------------------------
db5 = _tmp / "t5.db"
b5 = Brain(db5)
b5.append_run("R1", "2026-08-05T07:00:00+00:00")
b5.update_run("R1", status="ok", leagues_scanned=15, dc_reused=15, dc_refit=0,
              fit_seconds=12.5, predictions_logged=9, legs_logged=11,
              warnings="[]")
last = b5.last_run()
assert last["status"] == "ok" and last["dc_reused"] == 15
assert last["predictions_logged"] == 9
print("5. runs: OK")

# --- 6. legs mirror: JSON wins --------------------------------------------
db6 = _tmp / "t6.db"
b6 = Brain(db6)
ledger = _tmp / "clv_log.json"
log = CLVLog(path=ledger)
leg = log.log_entry(league="Eredivisie", fixture="Nijmegen v Telstar",
                    market="1X2 Home", model_prob=0.66, entry_odds=1.9)
log.log_close(leg.leg_id, closing_odds=1.85)
mirrored = leg.clv_pct
assert mirrored is not None, "log_close must compute a CLV"
assert b6.sync_legs([ledger])[str(ledger)] == 1
g = b6.gate_status()
assert g["legs_with_clv"] == 1, "mirror must reflect the ledger's paper leg"
mk = b6.clv_by_market("phase2_paper")
assert mk and abs(mk[0]["mean_clv_pct"] - mirrored) < 1e-9
# edit the JSON, re-sync -> the JSON wins
data = json.loads(ledger.read_text(encoding="utf-8"))
data[0]["clv_pct"] = mirrored + 0.01
ledger.write_text(json.dumps(data, indent=2), encoding="utf-8")
assert b6.sync_legs([ledger])[str(ledger)] == 1
mk2 = b6.clv_by_market("phase2_paper")
assert abs(mk2[0]["mean_clv_pct"] - (mirrored + 0.01)) < 1e-9, \
    "JSON must win on re-sync"
print("6. legs mirror (JSON is boss): OK")

# --- 7. corrections idempotent seed ---------------------------------------
db7 = _tmp / "t7.db"
b7 = Brain(db7)
csvf = _tmp / "corrections.csv"
csvf.write_text("logged_at,source,note,actioned\n"
                "2026-08-03,telegram,model looks wrong on Motherwell,no\n",
                encoding="utf-8")
assert b7.sync_corrections(csvf) == 1
assert b7.sync_corrections(csvf) == 0, "re-seed must be idempotent"
pend = b7.corrections_pending()
assert len(pend) == 1 and pend[0]["note"].startswith("model looks wrong")
b7.mark_corrections_consumed([pend[0]["id"]])
assert len(b7.corrections_pending()) == 0
print("7. corrections idempotent seed + consumed flag: OK")

# --- 8. read-only query guard ---------------------------------------------
try:
    b.query("DELETE FROM predictions")
    raise AssertionError("write SQL must be refused")
except ValueError:
    pass
print("8. read-only query guard: OK")

print("\n✅ ALL BRAIN STORE TESTS PASSED")
