"""HTML render tests for the legacy client dashboard (Architect 2026-08-12).

The admin tier is paused: render_admin_dashboard / render_stats_html /
render_why_html were removed (server + export both use render_v2's feed page).
This suite now guards the legacy client renderer that the old two-tier tests
still exercise, plus the public pages that remain: /history and the honest 404.

The DATA-LEAK BOUNDARY still holds: the client view (render_dashboard on a
trim_payload) contains NO model internals — no Elo/xG second opinion, no engine
divergence, no consensus votes, no verification, no EV verdicts, no gate/flags.
NO DATA rows are shown, never dropped (HR35)."""
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.dixon_coles import FixtureProbabilities
from output.produce_bet import BoardFixture
from verification.id403 import verify, SourcedDatum
from webapp import render, schema

tmp = Path(tempfile.mkdtemp(prefix="olp_webapp_render_"))

# Internals that must NEVER reach the client HTML (defence in depth — the trim
# already drops them from the payload).
_INTERNAL_FIELDS = ("elo_probs", "xg_probs", "engine_divergence", "consensus",
                    "engine_picks", "consensus_pick", "verification",
                    "cal_adjustment", "best_mes_ev", "best_price",
                    "best_bookmaker", "best_n_books")


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
        on_deploy_shortlist=True,
        best_market="Fenerbahce to win", best_price=1.91,
        best_bookmaker="bet365", best_n_books=3, best_mes_ev=0.0696,
        best_model_prob=0.56, mes_trigger_price=1.52,
        kickoff_date=date.today().isoformat(),  # same-day rule (2026-08-09)
        elo_probs=(0.52, 0.27, 0.21),
        market_probs=(0.54, 0.26, 0.20),
        engine_divergence="4pp on home — within tolerance",
        rejection_reason=None)


def _unrated() -> BoardFixture:
    return BoardFixture(
        fixture="Bristol City v Walsall (EFL Cup)", probs=None,
        verification=verify([SourcedDatum(domain="thesportsdb.com",
                                          value="x", url="https://x",
                                          structured=True)]),
        rejection_reason="NO DATA — PENDING: no fitted history")


def _payload() -> dict:
    return schema.build_payload(
        date="2026-08-11", phase="Phase 2 — paper calibration, zero capital",
        leagues_scanned=["Champions League", "EFL Cup"],
        board=[_rated(), _unrated()],
        data_flags=["⚠ EFL Cup: no history"],
        gate={"legs_with_clv": 3, "gate_requirement": 30},
        telemetry={"clv_capture_rate": 0.5, "days_to_gate": 42,
                   "legs_per_day": 5.5},
        calibration_count=3, mean_clv=1.2,
        recommendation="⭐ TODAY'S PICKS — 1 pick",
        yesterday_graded=[{
            "fixture": "Aarhus v Sabah FA", "league": "Champions League",
            "match_date": "2026-08-10", "outcome": "2-1",
            "engines": {"dc": {"1X2_HOME": {"prob": 0.56, "hit": True}}},
        }],
        rolling_7d={"engines": {"dc": {"settled": 1, "hits": 1}},
                    "legs_logged": 3, "legs_with_clv": 0, "avg_clv_pct": None})


p = _payload()
client_payload = schema.trim_payload(p)
h = render.render_dashboard(client_payload)

# --- 1. client view: the two sections + click-to-expand -----------------------
for needle in ["The Call", "The Scan", "Full analysis — all markets",
               "Deploy At", "Fenerbahce v Sturm Graz", "Champions League",
               "Bristol City v Walsall"]:
    assert needle in h, f"client dashboard missing {needle!r}"
print("1. client has The Call / The Scan / expand / fixtures: OK")

# --- 2. NO DATA rows are shown, not dropped (HR35) ---------------------------
assert "NO DATA — PENDING" in h
assert "no fitted history" in h
print("2. NO DATA fixture rendered honestly: OK")

# --- 3. DATA-LEAK BOUNDARY: client never carries an internal -----------------
for needle in _INTERNAL_FIELDS:
    assert needle not in h, f"client dashboard leaks {needle!r}"
for needle in ["Model Internals", "Data Flags", "Verified — Yesterday",
               "Honest edge", "zero capital", "PHASE 3 GATE", "CAP"]:
    assert needle not in h, f"client dashboard leaks admin section {needle!r}"
print("3. client view has NO model internals / admin sections: OK")

# --- 4. the full market grid renders (10 rows) -------------------------------
assert "Over 1.5 goals" in h and "Double Chance 1X" in h and "BTTS No" in h
assert "56%" in h and "Deploy At" in h
print("4. full market grid + pick line render: OK")

# --- 5. scan row click wiring present (data-target + detail rows) ------------
# Sprint 4: no inline onclick — scan.js reads data-target under the strict CSP.
assert "data-target=\"scan-" in h and "class=\"detail-row\"" in h
print("5. scan rows are click-to-expand: OK")

# --- 6. history / 404 — the public pages that remain ---------------------------
assert "Board history" in render.render_history_html(["2026-08-11"], "2026-08-11")
assert "No board for that date" in render.render_404_html("1999-01-01", "2026-08-11")
# The admin pages were removed with the paused tier — calling them is an
# AttributeError (they no longer exist), which the routes prove by 404ing.
for dead in ("render_admin_dashboard", "render_stats_html", "render_why_html"):
    assert not hasattr(render, dead), f"{dead} should be removed with the admin tier"
print("6. history/404 render; admin renderers removed: OK")

# --- 7. tag balance sanity (no broken markup) ---------------------------------
import re
for tag in ("div", "table", "thead", "tbody", "tr", "td", "th", "section",
            "header", "main", "footer", "span", "script", "a", "li"):
    # Word-boundary match so "<th>" counts but "<thead" doesn't, and "<li>" is
    # distinguishable from the "<link ...>" font tags.
    opens = len(re.findall(rf"<{tag}\b", h))
    closes = len(re.findall(rf"</{tag}>", h))
    assert opens == closes, f"unbalanced <{tag}> ({opens} vs {closes})"
print("7. HTML tags balanced: OK")

# --- 8. Sprint 4: strict-CSP discipline (no inline handlers, external assets) -
import re as _re
assert not _re.search(r"\son(click|keydown|keyup|change|submit|load|focus|blur)=",
                      h), "inline event handler — violates script-src 'self'"
assert 'data-asset-base="/static"' in h
assert 'src="/static/js/assets.js"' in h
assert 'src="/static/js/scan.js"' in h
print("8. no inline handlers; external css/js/font assets referenced: OK")

print("\n[OK] ALL WEBAPP RENDER TESTS PASSED")
