"""Render tests for render_v2.py — the ACTIVE /dashboard and /admin renderer
(Architect order 2026-08-10).

The old webapp_render_test.py covers the legacy webapp.render module (still used
for /why). This suite covers the new design that the server actually serves:
  - the FULL 13-row market grid on every client card (1X2, O/U 1.5, O/U 2.5,
    BTTS and Double Chance — derived only from client-safe probs),
  - the CALL recommended singles OPEN BY DEFAULT (UX 2026-08-10: "every single
    detail for every thing" on the actionable list), the SCAN board CLOSED by
    default with per-tile expand — one tap opens THAT fixture's breakdown only,
  - the breakeven trigger price honestly labelled as a trigger, NOT a live quote,
  - a cache-buster (?v=) on the proto.js/css tags so browsers can never serve a
    stale asset (the user's "clicking one tile opens every tile" was a cached JS),
  - the recommended pick row visually distinct (.c-mkt-row.pick),
  - the data-leak boundary still holds (no model internals reach the client),
  - the Phase 3 gate status on /admin: PASS / OVERRIDE / NOT MET, and the
    Architect override is honoured by render (as it is by schema).
"""
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.dixon_coles import FixtureProbabilities
from output.produce_bet import BoardFixture
from verification.id403 import verify, SourcedDatum
from webapp import render_v2, schema

_INTERNAL_FIELDS = ("elo_probs", "xg_probs", "engine_divergence", "consensus",
                    "engine_picks", "consensus_pick", "verification",
                    "cal_adjustment", "best_mes_ev", "best_price",
                    "best_bookmaker", "best_n_books", "softness_tier")


def _rated() -> BoardFixture:
    return BoardFixture(
        fixture="Fenerbahce v Sturm Graz (Champions League)",
        probs=FixtureProbabilities("Fenerbahce", "Sturm Graz",
                                   lambda_home=1.8, lambda_away=0.9,
                                   p_home=0.56, p_draw=0.24, p_away=0.20,
                                   p_over_15=0.71, p_over_25=0.45,
                                   p_over_35=0.22, p_btts_yes=0.55,
                                   modal_scoreline=(1, 0)),
        verification=verify([SourcedDatum(domain="thesportsdb.com",
                                          value="Fenerbahce v Sturm Graz",
                                          url="https://x", structured=True)]),
        softness_tier="D", on_deploy_shortlist=True,
        best_market="Fenerbahce to win", best_price=1.91,
        best_bookmaker="bet365", best_n_books=3, best_mes_ev=0.0696,
        best_model_prob=0.56, mes_trigger_price=1.52,
        kickoff_date="2026-08-10",
        elo_probs=(0.52, 0.27, 0.21),
        market_probs=(0.54, 0.26, 0.20),
        engine_divergence="4pp on home — within tolerance",
        rejection_reason=None)


def _unrated() -> BoardFixture:
    return BoardFixture(
        fixture="Plymouth Argyle v Exeter City (EFL Cup)", probs=None,
        verification=verify([SourcedDatum(domain="thesportsdb.com",
                                          value="x", url="https://x",
                                          structured=True)]),
        softness_tier="D",
        rejection_reason="NO DATA — PENDING: no fitted history")


def _payload() -> dict:
    return schema.build_payload(
        date="2026-08-10", phase="Phase 2 — paper calibration, zero capital",
        leagues_scanned=["Champions League", "EFL Cup"],
        board=[_rated(), _unrated()],
        data_flags=["⚠ EFL Cup: no history"],
        gate={"legs_with_clv": 3, "gate_requirement": 30},
        telemetry={"clv_capture_rate": 0.5, "days_to_gate": 42,
                   "legs_per_day": 5.5},
        calibration_count=3, mean_clv=1.2,
        recommendation="⭐ TODAY'S PICKS — 1 pick",
        rolling_7d={"engines": {"dc": {"settled": 1, "hits": 1}},
                    "legs_logged": 3, "legs_with_clv": 0, "avg_clv_pct": None})


p = _payload()
client = render_v2.render_dashboard(schema.trim_payload(p))

# --- 1. FULL market grid: all 13 rows on the rated card -----------------------
_MARKET_LABELS = ("Home win", "Draw", "Away win",
                  "Over 1.5 goals", "Under 1.5 goals",
                  "Over 2.5 goals", "Under 2.5 goals",
                  "BTTS Yes", "BTTS No",
                  "Double Chance 1X", "Double Chance X2", "Double Chance 12",
                  "Trigger price")
for label in _MARKET_LABELS:
    assert label in client, f"client card missing market {label!r}"
print(f"1. full 13-row market grid renders (all {len(_MARKET_LABELS)} labels): OK")

# --- 2. derived markets are correct (Under = 1 - Over, DC = sum) --------------
# p_over_15=0.71 -> Under 1.5 = 29%; p_over_25=0.45 -> Under 2.5 = 55%
# p_btts_yes=0.55 -> BTTS No = 45%; DC 1X = 0.56+0.24 = 80%; X2 = 44%; 12 = 76%
for needle in ("29%", "55%", "45%", "80%", "44%", "76%"):
    assert needle in client, f"derived market {needle!r} missing/wrong"
print("2. derived Under / BTTS No / Double Chance values correct: OK")

# --- 3. recommended pick row is visually distinct + correct -------------------
assert 'class="c-mkt-row pick"' in client, "pick row must carry the .pick class"
assert "Fenerbahce to win" in client and "56%" in client
print("3. recommended pick row distinct + shows the pick: OK")

# --- 4. UX split (2026-08-10): CALL open by default, SCAN closed per-tile ----
# CALL = the actionable shortlist (a handful of cards) — "every single detail
# for every thing" visible immediately. SCAN = the whole board (10+ fixtures) —
# collapsed, per-tile: one tap opens THAT fixture's breakdown only.
assert 'class="c-detail open"' in client, "CALL cards must render OPEN by default"
assert 'aria-expanded="true"' in client, "CALL cards must start expanded"
assert 'data-detail="call-' in client and 'id="call-' in client
# SCAN cards stay closed (no 'open' on their detail block).
assert 'data-detail="scan-' in client and 'id="scan-' in client
assert 'class="c-detail" id="scan-' in client, "scan detail must be closed (no 'open')"
assert 'aria-expanded="false"' in client, "scan cards must start collapsed"
print("4. CALL open by default + SCAN per-tile closed: OK")

# --- 4b. breakeven trigger price honestly labelled — NOT a live quote ---------
assert "breakeven, not a live quote" in client, \
    "trigger price must be labelled a trigger, not a live price"
assert "1.52+" in client, "trigger price must render the mes_trigger_price (1.52)"
assert "Deploy at" not in client, "old 'Deploy at' label must be gone"
print("4b. trigger price labelled breakeven-trigger, not a live quote: OK")

# --- 4c. cache-buster on the asset tags. The user's "clicking one tile opens
#        EVERY tile" was a stale cached proto.js (the on-disk code was already
#        per-card correct); a ?v= on the script/css tags forces a refresh. -----
assert re.search(r'proto\.css\?v=\d+', client), "stylesheet must carry ?v= cache-buster"
assert re.search(r'proto\.js\?v=\d+', client), "script must carry ?v= cache-buster"
print("4c. proto.css/js carry a ?v= cache-buster: OK")

# --- 5. DATA-LEAK BOUNDARY: client still carries no model internals -----------
for needle in _INTERNAL_FIELDS:
    assert needle not in client, f"client leaks {needle!r}"
for needle in ("Model Internals", "Data Flags", "PHASE 3 GATE", "CAP",
               "zero capital"):
    assert needle not in client, f"client leaks admin section {needle!r}"
print("5. client view has NO model internals / admin sections: OK")

# --- 6. NO DATA fixture stays honest on the client (HR35) ---------------------
assert "Plymouth Argyle v Exeter City" in client
assert "NO DATA — PENDING" in client
print("6. NO DATA fixture rendered honestly: OK")

# --- 7. admin gate status: NOT MET (no sign-off) then OVERRIDE (sign-off) -----
os.environ.pop("ARCHITECT_SIGNOFF", None)
admin = render_v2.render_admin_dashboard(p)
assert "NOT MET — publish blocked" in admin, "gate detail must say NOT MET"
assert "Legs with CLV:</b> 3 / 30 required" in admin

os.environ["ARCHITECT_SIGNOFF"] = "1"
admin_override = render_v2.render_admin_dashboard(p)
assert "OVERRIDE — publish allowed by Architect sign-off" in admin_override, \
    "gate detail must show the Architect override"
assert "Architect sign-off:</b> YES" in admin_override
os.environ.pop("ARCHITECT_SIGNOFF", None)

# gate PASS path
p_pass = _payload()
p_pass["gate"] = {"legs_with_clv": 30, "gate_requirement": 30, "mean_clv_pct": 1.1}
admin_pass = render_v2.render_admin_dashboard(p_pass)
assert "PASS — publish allowed" in admin_pass, "met gate must say PASS"
print("7. admin gate status shows PASS / OVERRIDE / NOT MET correctly: OK")

# --- 8. admin still renders the internals the client was denied ---------------
# render_v2 inlines _internals per-row (no "Model Internals" heading), so assert
# the actual emitted labels: the engine second opinions, MES, the log, the flag.
for needle in ("Elo second opinion:", "Engine divergence:", "HR30 MES:",
               "Error / Rejection Log", "FLAG", "no fitted history",
               "Gate status:", "Architect sign-off:"):
    assert needle in admin, f"admin missing internal {needle!r}"
print("8. admin has engine internals + rejection log + flags + gate: OK")

# --- 9. tag balance sanity -----------------------------------------------------
import re
for html_text, label in ((client, "client-v2"), (admin, "admin-v2")):
    for tag in ("div", "table", "thead", "tbody", "tr", "td", "th", "section",
                "header", "main", "footer", "span", "script", "a", "li", "button"):
        opens = len(re.findall(rf"<{tag}\b", html_text))
        closes = len(re.findall(rf"</{tag}>", html_text))
        assert opens == closes, f"unbalanced <{tag}> in {label} ({opens} vs {closes})"
print("9. HTML tags balanced in both views: OK")

print("\n[OK] ALL WEBAPP RENDER_V2 TESTS PASSED")
