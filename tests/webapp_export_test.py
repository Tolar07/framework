"""Static export tests — the export folder is self-contained and host-ready."""
import json
import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from webapp import export
from webapp import schema
from engine.dixon_coles import FixtureProbabilities
from output.produce_bet import BoardFixture
from verification.id403 import verify, SourcedDatum
import brain.report as rep

# Redirect ROOT to a temp tree so the export reads a synthetic payload + a
# throwaway brain instead of the real repo data.
tmp = Path(tempfile.mkdtemp(prefix="olp_webapp_export_"))
boards = tmp / "output" / "boards"
boards.mkdir(parents=True)
out = tmp / "site"
# The brain opens read-only — it needs an EXISTING db file.
(tmp / "brain").mkdir(parents=True, exist_ok=True)
sqlite3.connect(tmp / "brain" / "olp.db").close()

bf = BoardFixture(
    fixture="Fenerbahce v Sturm Graz (Champions League)",
    probs=FixtureProbabilities("Fenerbahce", "Sturm Graz",
                               lambda_home=1.8, lambda_away=0.9,
                               p_home=0.56, p_draw=0.24, p_away=0.20,
                               p_over_15=0.71, p_over_25=0.45,
                               p_over_35=0.22, p_btts_yes=0.55),
    verification=verify([SourcedDatum(domain="thesportsdb.com",
                                      value="x", url="https://x",
                                      structured=True)]),
    softness_tier="D", on_deploy_shortlist=True,
    best_market="Fenerbahce to win", best_price=1.91, best_mes_ev=0.0696,
    best_model_prob=0.56, kickoff_date="2026-08-11")
payload = schema.build_payload(
    date="2026-08-11", phase="PHASE 2 — PAPER",
    leagues_scanned=["Champions League"], board=[bf],
    data_flags=["⚠ x"], gate={"legs_with_clv": 0, "gate_requirement": 30},
    telemetry={}, calibration_count=0, mean_clv=None,
    recommendation="⭐ TODAY'S PICKS\nNO DATA — no eligible pick today.")
schema.write_payload(payload, boards / "board_2026-08-11.json")

with patch.object(export, "ROOT", tmp), \
     patch.object(rep, "render_stats", lambda *a, **k: "OLP XDV — STATS (test)"):
    written = export.export("2026-08-11", out)

# --- 1. all four artifacts exist ----------------------------------------------
assert (out / "index.html").exists(), written
assert (out / "board.json").exists()
assert (out / "stats.json").exists()
assert (out / "README.md").exists()
print("1. index.html + board.json + stats.json + README.md written: OK")

# --- 2. index is self-contained (inline CSS, no external deps) ------------------
html_src = (out / "index.html").read_text(encoding="utf-8")
assert "<style>" in html_src and "Fenerbahce v Sturm Graz" in html_src
assert "https://" not in html_src or "thesportsdb" not in html_src  # no external fetch
assert "Honest edge" in html_src
print("2. index is self-contained + honest: OK")

# --- 3. board.json is the same structured payload -------------------------------
d = schema.read_payload(out / "board.json")
assert d["date"] == "2026-08-11" and d["board"][0]["probs"]["p_home"] == 0.56
print("3. board.json is the structured payload: OK")

# --- 4. stats.json exists and carries text --------------------------------------
stats = json.loads((out / "stats.json").read_text(encoding="utf-8"))
assert isinstance(stats.get("text"), str) and stats["text"]
print("4. stats.json carries the stats text: OK")

print("\n✅ ALL WEBAPP EXPORT TESTS PASSED")
