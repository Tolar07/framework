"""HTML render tests for the two-tier dashboard (Architect order 2026-08-07).

The critical guarantee tested here is the DATA-LEAK BOUNDARY: the public
client view (render_dashboard on a trim_payload) contains NO model internals —
no Elo/xG second opinion, no engine divergence, no consensus votes, no
verification, no EV verdicts, no gate/flags — while the authed admin view
renders them. NO DATA rows are shown, never dropped (HR35). The honest-edge
statement + capital authority live on /admin (the client view omits them by
Architect's explicit choice)."""
import sys
import tempfile
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
        kickoff_date="2026-08-11",
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
        softness_tier="D",
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
a = render.render_admin_dashboard(p)

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

# --- 4. admin view renders the internals the client was denied ---------------
for needle in ["Model Internals", "Elo second opinion", "Engine divergence",
               "HR30 MES", "Verification", "Data Flags", "Verified — Yesterday",
               "✓ HIT", "Honest edge", "zero capital", "PHASE 3 GATE",
               "TIER D", "SINGLE-SOURCE"]:
    assert needle in a, f"admin dashboard missing {needle!r}"
print("4. admin has internals + verification + flags + yesterday + footer: OK")

# --- 5. the full market grid renders (10 rows) -------------------------------
assert "Over 1.5 goals" in h and "Double Chance 1X" in h and "BTTS No" in h
assert "56%" in h and "Deploy At" in h
print("5. full market grid + pick line render: OK")

# --- 6. scan row click wiring present (toggleScanRow + detail rows) ----------
assert "toggleScanRow('scan-" in h and "class=\"detail-row\"" in h
assert "toggleScanRow('a-scan-" in a
print("6. scan rows are click-to-expand in both views: OK")

# --- 7. why / stats / history / 404 all render --------------------------------
assert "Fenerbahce" in render.render_why_html(p, "Fenerbahce")
assert "Pick" in render.render_why_html(p, "Fenerbahce")
assert "NO DATA — PENDING" in render.render_why_html(p, "Nonexistent FC")
assert "Gate &amp; calibration" in render.render_stats_html("x", "2026-08-11")
assert "Board history" in render.render_history_html(["2026-08-11"], "2026-08-11")
assert "No board for that date" in render.render_404_html("1999-01-01", "2026-08-11")
print("7. why/stats/history/404 pages render: OK")

# --- 8. tag balance sanity (no broken markup) ---------------------------------
import re
for html_text, label in ((h, "client"), (a, "admin")):
    # Word-boundary match so "<th>" counts but "<thead" doesn't, and "<li>" is
    # distinguishable from the "<link ...>" font tags.
    for tag in ("div", "table", "thead", "tbody", "tr", "td", "th", "section",
                "header", "main", "footer", "span", "script", "a", "li"):
        opens = len(re.findall(rf"<{tag}\b", html_text))
        closes = len(re.findall(rf"</{tag}>", html_text))
        assert opens == closes, f"unbalanced <{tag}> in {label} ({opens} vs {closes})"
print("8. HTML tags balanced in both views: OK")

print("\n[OK] ALL WEBAPP RENDER TESTS PASSED")
