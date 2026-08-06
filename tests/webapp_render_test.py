"""HTML render tests — the dashboard must show the board honestly and never
trim the honest-edge statement or capital authority."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.dixon_coles import FixtureProbabilities
from output.produce_bet import BoardFixture
from verification.id403 import verify, SourcedDatum
from webapp import render, schema

tmp = Path(tempfile.mkdtemp(prefix="olp_webapp_render_"))


def _payload():
    rated = BoardFixture(
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
        best_market="Fenerbahce to win", best_price=1.91,
        best_bookmaker="bet365", best_n_books=3, best_mes_ev=0.0696,
        best_model_prob=0.56, kickoff_date="2026-08-11",
        elo_probs=(0.52, 0.27, 0.21),
        market_probs=(0.54, 0.26, 0.20))
    unrated = BoardFixture(
        fixture="Bristol City v Walsall (EFL Cup)", probs=None,
        verification=verify([SourcedDatum(domain="thesportsdb.com",
                                          value="x", url="https://x",
                                          structured=True)]),
        softness_tier="D",
        rejection_reason="NO DATA — PENDING: no fitted history for this league")
    return schema.build_payload(
        date="2026-08-11", phase="PHASE 2 — PAPER",
        leagues_scanned=["Champions League", "EFL Cup"],
        board=[rated, unrated], data_flags=["⚠ EFL Cup: no history"],
        gate={"legs_with_clv": 3, "gate_requirement": 30,
              "gate_met_pending_architect_signoff": False},
        telemetry={"clv_capture_rate": 0.5, "days_to_gate": 42,
                   "clv_legs_per_day": 0.3},
        calibration_count=3, mean_clv=1.2,
        recommendation="⭐ TODAY'S PICKS — 1 pick (not enough for a 2-leg parlay)\n1. Fenerbahce v Sturm Graz → Fenerbahce 56%")


p = _payload()
h = render.render_dashboard(p)

# --- 1. today's picks, the call, honest-edge, capital authority, gate ---------
for needle in ["TODAY'S PICKS", "THE CALL", "Honest edge",
               "zero capital", "Road to the Phase", "Fenerbahce v Sturm Graz"]:
    assert needle in h, f"dashboard missing {needle!r}"
print("1. dashboard has picks/call/gate/honest-edge/capital: OK")

# --- 2. NO DATA rows are shown, not dropped (HR35) ---------------------------
assert "Bristol City" in h and "Walsall" in h
assert "NO DATA — PENDING" in h
assert "no fitted history" in h
print("2. NO DATA fixture rendered honestly: OK")

# --- 3. gate strip carries a number + label (colour is never alone) ----------
assert "3 of 30" in h and "legs with CLV" in h
assert "~42 days" in h
print("3. gate strip labelled, not colour-alone: OK")

# --- 4. league section header present -----------------------------------------
assert "Champions League" in h and "EFL Cup" in h
print("4. league sections render: OK")

# --- 5. flags block collapses with a count ------------------------------------
assert "1 data flag" in h or "⚠ 1" in h
print("5. data flags rendered: OK")

# --- 6. the rated card carries the design language ----------------------------
assert "AI pick" in h                      # the pick line
assert "3 of 3 models agree" in h          # DC + Elo + Bookmaker agree (xG no data)
assert "2–1" in h                          # predicted score from lambda 1.8/0.9
assert 'class="winbar"' in h               # win-probability bar
assert "✓ Dixon-Coles" in h and "✓ Elo" in h and "✓ Bookmaker" in h and "xG —" in h
print("6. rated card: pick / agreement / score / win bar / chips: OK")

# --- 7. why / stats / history / 404 all render --------------------------------
assert "Fenerbahce" in render.render_why_html(p, "Fenerbahce")
assert "Win chance" in render.render_why_html(p, "Fenerbahce")
assert "models agree" in render.render_why_html(p, "Fenerbahce")
assert "NO DATA — PENDING" in render.render_why_html(p, "Nonexistent FC")
assert "Gate &amp; calibration" in render.render_stats_html("x", "2026-08-11")
assert "Board history" in render.render_history_html(["2026-08-11"], "2026-08-11")
assert "No board for that date" in render.render_404_html("1999-01-01", "2026-08-11")
print("7. why/stats/history/404 pages render: OK")

# --- 8. tag balance sanity (no broken markup) ----------------------------------
for tag in ("div", "nav", "details", "ul", "span"):
    assert h.count(f"<{tag}") == h.count(f"</{tag}>"), f"unbalanced <{tag}>"
print("8. HTML tags balanced: OK")

print("\n✅ ALL WEBAPP RENDER TESTS PASSED")
