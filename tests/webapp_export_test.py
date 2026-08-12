"""Static export tests — the export folder is the PUBLIC feed surface.

The export IS the Telegram board (one render, two outlets): it is built from
the raw board_<date>.json via schema.build_feed_payload — NO publish step, NO
model internals (Architect 2026-08-12). stats.json is gone — it was the admin
diagnostic layer and must not be hostable. Fonts are self-hosted (Sprint 4, no
Google CDN); the only external fetches left are the Architect-approved
flagcdn.com (league country flags) and r2.thesportsdb.com (club crests).
CSS/JS/fonts are copied as a relative ./static tree beside index.html, so the
exported folder stays self-contained.
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

# The export now reads the day's RAW board through the feed builder
# (schema.read_feed → build_feed_payload) — redirect BOARD_DIR to the temp tree
# so the test never touches the real boards. Auto-feed = auto-publish: there is
# no publish step at all.
patch.object(schema, "BOARD_DIR", boards).start()

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
    on_deploy_shortlist=True,
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
# The export reads the day's RAW board via the feed builder (auto-feed =
# auto-publish) — a plain board_<date>.json is all it needs, no publish step.
schema.write_payload(payload, boards / "board_2026-08-11.json")

with patch.object(export, "ROOT", tmp):
    written = export.export("2026-08-11", out)

# --- 1. the three artifacts exist (stats.json is deliberately gone) ------------
assert (out / "index.html").exists(), written
assert (out / "board.json").exists()
assert (out / "README.md").exists()
assert not (out / "stats.json").exists(), "stats.json must NOT be exported"
print("1. index.html + board.json + README.md written; no stats.json: OK")

# --- 2. index IS the feed (Telegram board): no internals ----------------------
html_src = (out / "index.html").read_text(encoding="utf-8")
assert "./static/css/proto.css" in html_src and "Fenerbahce v Sturm Graz" in html_src
# The export IS the Telegram board: hero, gate callout, PRODUCTION BETS, scan
# cards, rolling + honest edge (one render, two outlets).
assert 'class="f-hero"' in html_src and "PRODUCTION BETS" in html_src
assert 'class="f-scan-card"' in html_src and "7-DAY ROLLING" in html_src
assert "HONEST EDGE LINE" in html_src and "Capital authority: THE ARCHITECT" in html_src
for needle in ("elo_probs", "engine_divergence", "verification", "best_mes_ev",
               "consensus", "Model Internals", "Data Flags", "Verified — Yesterday",
               "Honest edge", "zero capital", "PHASE 3 GATE", "CAP"):
    assert needle not in html_src, f"public export leaks {needle!r}"
print("2. index is the feed (Telegram board) view: OK")

# --- Sprint 4: self-hosted static tree copied; index references it relatively -
assert (out / "static" / "css" / "proto.css").is_file()
assert (out / "static" / "js" / "proto.js").is_file()
assert (out / "static" / "fonts" / "Inter-normal-400.woff2").is_file()
assert 'data-asset-base="./static"' in html_src
# The static export uses the same _shell as the server, so it inherits the
# ?v= cache-buster — a locally opened index.html can never serve a stale
# proto.js (the user's all-tiles-open bug was exactly a cached JS).
assert re.search(r'src="\./static/js/proto\.js\?v=\d+"', html_src), \
    "exported script tag must carry the ?v= cache-buster"
# Fonts are self-hosted — the Google CDN is gone, and section 3 would now
# reject it too (it is no longer on the approved-host list).
assert "fonts.googleapis.com" not in html_src and "fonts.gstatic.com" not in html_src
print("Sprint 4. static tree copied + self-hosted fonts, no Google CDN: OK")

# --- 3. external fetches are limited to the approved sources: flagcdn.com
# (league country flags) and r2.thesportsdb.com (club crests). Fonts are
# self-hosted — the Google CDN is NOT approved, so a reintroduced
# fonts.googleapis.com link fails here. CSS/JS/fonts are relative (./static/...)
# so they never match the absolute/protocol-relative scan. The scan catches
# absolute (https:// and http://) AND protocol-relative (//host) references, so
# an unapproved host can't slip past either spelling.
_APPROVED_EXTERNAL_HOSTS = (
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

# --- 4. board.json is the FEED payload: lean + honest gate numbers -------------
d = schema.read_payload(out / "board.json")
b0 = d["board"][0]
assert d["date"] == "2026-08-11"
assert b0["probs"]["p_home"] == 0.56 and b0["best_market"] == "Fenerbahce to win"
assert "mes_trigger_price" in b0           # the public pick line keeps Deploy At
# The honest gate/edge numbers the Telegram board carries ARE present...
assert d["data_flags"] == ["⚠ x"]
assert d["gate_state"]["legs_with_clv"] == 35
assert d["mean_clv"] == 1.2
# ...and the model internals are not.
for k in ("elo_probs", "engine_divergence", "verification", "best_mes_ev",
          "best_price", "consensus"):
    assert k not in b0, f"board.json leaks {k}"
for k in ("gate", "telemetry"):
    assert k not in d, f"board.json leaks top-level {k}"
print("4. board.json is the feed payload (lean + gate numbers): OK")

# --- 5. README explains the feed boundary --------------------------------------
readme = (out / "README.md").read_text(encoding="utf-8")
assert "2026-08-11" in readme and "Telegram board" in readme
assert "never leave the server" in readme
print("5. README documents the feed/public boundary: OK")

print("\n[OK] ALL WEBAPP EXPORT TESTS PASSED")
