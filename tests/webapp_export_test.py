"""Static export tests — the export folder is the PUBLIC client surface.

Since a static host cannot authenticate, the export is trimmed: predictions
only, NO model internals (Architect order 2026-08-07). stats.json is gone —
it is the admin diagnostic layer and must not be hostable. The only external
fetches are the Architect-approved Google Fonts CDN, flagcdn.com (league
country flags) and r2.thesportsdb.com (club crests); every other asset is
inline.
"""
import json
import os
import re
import sys
import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

# Publish-gate sign-off so the fixture board passes the gate (the gate itself
# has its own dedicated tests in webapp_schema_test.py).
os.environ["ARCHITECT_SIGNOFF"] = "1"

from webapp import export
from webapp import schema
from engine.dixon_coles import FixtureProbabilities
from output.produce_bet import BoardFixture
from verification.id403 import verify, SourcedDatum

# Redirect ROOT to a temp tree so the export reads a synthetic payload instead
# of the real repo data.
tmp = Path(tempfile.mkdtemp(prefix="olp_webapp_export_"))
boards = tmp / "output" / "boards"
boards.mkdir(parents=True)
out = tmp / "site"

# Redirect the published store to the temp tree so the test never touches the
# real published boards / audit log.
pub = tmp / "output" / "boards" / "published"
pub.mkdir(parents=True, exist_ok=True)
patch.object(schema, "PUBLISHED_DIR", pub).start()
patch.object(schema, "AUDIT_LOG", pub / "publish_audit.jsonl").start()

bf = BoardFixture(
    fixture="Fenerbahce v Sturm Graz (Champions League)",
    probs=FixtureProbabilities("Fenerbahce", "Sturm Graz",
                               lambda_home=1.8, lambda_away=0.9,
                               p_home=0.56, p_draw=0.24, p_away=0.20,
                               p_over_15=0.71, p_over_25=0.45,
                               p_over_35=0.22, p_btts_yes=0.55,
                               modal_scoreline=(1, 0)),
    verification=verify([SourcedDatum(domain="thesportsdb.com",
                                      value="x", url="https://x",
                                      structured=True)]),
    softness_tier="D", on_deploy_shortlist=True,
    best_market="Fenerbahce to win", best_price=1.91, best_mes_ev=0.0696,
    best_model_prob=0.56, mes_trigger_price=1.52,
    kickoff_date=date.today().isoformat(),  # same-day call rule (2026-08-09)
    elo_probs=(0.52, 0.27, 0.21),
    engine_divergence="4pp on home — within tolerance")
payload = schema.build_payload(
    date="2026-08-11", phase="PHASE 2 — PAPER",
    leagues_scanned=["Champions League"], board=[bf],
    # Gate-PASSING fixture so this test exercises the export path, not the
    # publish gate (which has its own dedicated tests).
    data_flags=["⚠ x"], gate={"legs_with_clv": 35, "gate_requirement": 30, "mean_clv_pct": 1.2},
    telemetry={}, calibration_count=0, mean_clv=1.2,
    recommendation="⭐ TODAY'S PICKS\nNO DATA — no eligible pick today.")
# The export reads ONLY the published store (approve-gate boundary), so the
# board must be published first — exactly as /admin's "Approve → Publish" does.
schema.write_published(payload, approved_by="test")
schema.write_payload(payload, boards / "board_2026-08-11.json")

with patch.object(export, "ROOT", tmp):
    written = export.export("2026-08-11", out)

# --- 1. the three artifacts exist (stats.json is deliberately gone) ------------
assert (out / "index.html").exists(), written
assert (out / "board.json").exists()
assert (out / "README.md").exists()
assert not (out / "stats.json").exists(), "stats.json must NOT be exported"
print("1. index.html + board.json + README.md written; no stats.json: OK")

# --- 2. index is the CLIENT view: no internals, no honest footer ---------------
html_src = (out / "index.html").read_text(encoding="utf-8")
assert "<style>" in html_src and "Fenerbahce v Sturm Graz" in html_src
assert "The Call" in html_src and "The Scan" in html_src
assert "Full analysis — all markets" in html_src
for needle in ("elo_probs", "engine_divergence", "verification", "best_mes_ev",
               "Model Internals", "Data Flags", "Verified — Yesterday",
               "Honest edge", "zero capital", "PHASE 3 GATE", "CAP"):
    assert needle not in html_src, f"public export leaks {needle!r}"
print("2. index is the trimmed client view: OK")

# --- 3. external fetches are limited to the approved sources: the
# Architect-approved Google Fonts CDN, flagcdn.com (league country flags)
# and r2.thesportsdb.com (club crests). Every other asset is inline.
# The scan catches absolute (https:// and http://) AND protocol-relative
# (//host) references, so an unapproved host can't slip past either spelling.
_APPROVED_EXTERNAL_HOSTS = (
    "fonts.googleapis.com",
    "fonts.gstatic.com",
    "flagcdn.com",          # league country flags
    "r2.thesportsdb.com",   # club crests (Architect-approved hotlink)
)
_URL_RE = re.compile(r"(?:https?://|//)([a-zA-Z0-9][a-zA-Z0-9.-]*)")


def _assert_external_urls(html: str) -> None:
    """Every absolute or protocol-relative URL in `html` must be approved."""
    for line in html.splitlines():
        for host in _URL_RE.findall(line):
            assert host in _APPROVED_EXTERNAL_HOSTS, \
                f"unapproved external URL: {line.strip()} (host {host!r})"


_assert_external_urls(html_src)

# The crest hotlink is approved; a stranger is not — under every spelling.
_assert_external_urls('<img src="https://r2.thesportsdb.com/media/badge/x.png">')
for evil in ('<img src="https://evil.example/track.png">',
             '<img src="//evil.example/x.png">',
             '<script src="http://evil.example/x.js"></script>'):
    try:
        _assert_external_urls(evil)
        raise SystemExit(f"FAIL: unapproved host accepted: {evil}")
    except AssertionError:
        pass
print("3. only approved CDNs (fonts + flagcdn + thesportsdb crests) referenced: OK")

# --- 4. board.json is the TRIMMED payload --------------------------------------
d = schema.read_payload(out / "board.json")
b0 = d["board"][0]
assert d["date"] == "2026-08-11"
assert b0["probs"]["p_home"] == 0.56 and b0["best_market"] == "Fenerbahce to win"
assert "mes_trigger_price" in b0           # the public pick line keeps Deploy At
for k in ("elo_probs", "engine_divergence", "verification", "best_mes_ev",
          "best_price", "softness_tier", "consensus"):
    assert k not in b0, f"board.json leaks {k}"
for k in ("data_flags", "gate", "telemetry"):
    assert k not in d, f"board.json leaks top-level {k}"
print("4. board.json is the trimmed public payload: OK")

# --- 5. README explains the boundary -------------------------------------------
readme = (out / "README.md").read_text(encoding="utf-8")
assert "2026-08-11" in readme and "predictions only" in readme
assert "admin-only" in readme
print("5. README documents the public/admin boundary: OK")

print("\n[OK] ALL WEBAPP EXPORT TESTS PASSED")
