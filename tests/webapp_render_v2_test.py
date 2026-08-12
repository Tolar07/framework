"""Render tests for render_v2.py — the FEED page (Architect 2026-08-11;
Verge "Match Intelligence" skin, ratified 2026-08-12).

The web page IS the Telegram board: one render, two outlets. `render_dashboard`
is fed by schema.build_feed_payload (a widened trim) and renders:
  - the masthead (wordmark / centerline / dateline) + sticky tab nav,
  - the hero (honest-edge kicker, CTAs, phase / leagues / calibration chips),
  - the data-flag chips,
  - the gate callout — PASS / OVERRIDE / NOT MET, always visible (an Architect
    sign-off override is stated plainly, never silent),
  - Part 1 THE CALL — the parity anchor (Acca A headline -> split accas, each
    with its own SportyBet booking code; honest NO DATA — PENDING where a code
    is missing, HR35), at three densities (Lean tickets / Trimmed + Full call
    cards with the MODEL % dial, market bars and breakeven strip),
  - Part 2 THE SCAN — date pills + the league-grouped table with live-score
    badges and honest PENDING rows,
  - Part 3 SINGLES — standalone slips at three densities,
  - yesterday-graded, 7-day rolling, and the honest-edge/capital footer.

The data-leak boundary holds: no elo/xg/consensus/EV/verification internals
reach the page. Interaction is CSP-clean — no inline event handlers.
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
                    "best_bookmaker", "best_n_books", "lambda_home",
                    "modal_scoreline", "market_probs")


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
        rejection_reason="NO DATA — PENDING: no fitted history")


def _payload() -> dict:
    return schema.build_payload(
        date="2026-08-10", phase="Phase 2 — paper calibration, zero capital",
        leagues_scanned=["Champions League", "EFL Cup"],
        board=[_rated(), _unrated()],
        data_flags=["⚠ EFL Cup: no history"],
        gate={"legs_with_clv": 3, "gate_requirement": 30, "mean_clv_pct": -1.2},
        telemetry={}, calibration_count=3, mean_clv=-1.2,
        recommendation="",
        yesterday_graded=[{
            "fixture": "Fenerbahce v Sturm Graz",
            "league": "Champions League",
            "outcome": "HOME",
            "engines": {"dc": {"1X2_HOME": {"prob": 0.56, "hit": True}},
                        "elo": {"1X2_HOME": {"prob": 0.52, "hit": False}}},
        }],
        rolling_7d={
            "engines": {"dc": {"predictions": 20, "settled": 10,
                               "hit_rate": 0.5}},
            "legs_logged": 40, "legs_with_clv": 3, "avg_clv_pct": -1.2,
            "gate": {"legs_with_clv": 3, "gate_requirement": 30,
                     "gate_met": False},
        })


def _prod_leg(fixture, market_name, price, prob, league, ev):
    return {"fixture": fixture, "league": league, "market_key": "1X2_HOME",
            "market_name": market_name, "price": price, "prob": prob,
            "ev": ev}


def _prod_acca(label, legs, combined_odds, combined_prob):
    return {"label": label, "legs": legs, "combined_odds": combined_odds,
            "combined_prob": combined_prob, "n_legs": len(legs)}


def _payload_prod() -> dict:
    """A production payload: Acca A (Fenerbahce) + Acca B (Beta, Delta) +
    the two remainder fixtures as singles — exercises hero band, split list,
    true single codes and the honest NO DATA — PENDING when codes are absent."""
    accas = [
        _prod_acca("Acca A",
                   [_prod_leg("Fenerbahce v Sturm Graz (Champions League)",
                              "Fenerbahce to win", 1.91, 0.56,
                              "Champions League", 0.0696)],
                   1.91, 0.56),
        _prod_acca("Acca B",
                   [_prod_leg("Beta v Gamma (Eredivisie)", "Beta to win",
                              1.80, 0.61, "Eredivisie", 0.098),
                    _prod_leg("Delta v Epsilon (Eredivisie)", "Delta to win",
                              1.75, 0.55, "Eredivisie", 0.0625)],
                   1.80 * 1.75, 0.61 * 0.55),
        _prod_acca("SINGLE — Beta v Gamma (Eredivisie)",
                   [_prod_leg("Beta v Gamma (Eredivisie)", "Beta to win",
                              1.80, 0.61, "Eredivisie", 0.098)],
                   1.80, 0.61),
        _prod_acca("SINGLE — Delta v Epsilon (Eredivisie)",
                   [_prod_leg("Delta v Epsilon (Eredivisie)", "Delta to win",
                              1.75, 0.55, "Eredivisie", 0.0625)],
                   1.75, 0.55),
    ]
    return schema.build_payload(
        date="2026-08-10", phase="Phase 2 — paper calibration, zero capital",
        leagues_scanned=["Champions League", "Eredivisie", "EFL Cup"],
        board=[_rated()], data_flags=["⚠ EFL Cup: no history"],
        gate={"legs_with_clv": 3, "gate_requirement": 30, "mean_clv_pct": -1.2},
        telemetry={}, calibration_count=3, mean_clv=-1.2,
        recommendation="",
        rolling_7d={
            "engines": {"dc": {"predictions": 20, "settled": 10,
                               "hit_rate": 0.5}},
            "legs_logged": 40, "legs_with_clv": 3, "avg_clv_pct": -1.2,
            "gate": {"legs_with_clv": 3, "gate_requirement": 30,
                     "gate_met": False},
        },
        accas=accas)


CODES_PROD = {"results": [
    {"label": "Acca A", "code": "AA111",
     "per_leg": [{"fixture": "Fenerbahce v Sturm Graz (Champions League)"}]},
    {"label": "Acca B", "code": "AB222",
     "per_leg": [{"fixture": "Beta v Gamma (Eredivisie)"},
                 {"fixture": "Delta v Epsilon (Eredivisie)"}]},
    {"label": "SINGLE — Beta v Gamma (Eredivisie)", "code": "SB_BETA",
     "per_leg": [{"fixture": "Beta v Gamma (Eredivisie)"}]},
    {"label": "SINGLE — Delta v Epsilon (Eredivisie)", "code": "SB_DELTA",
     "per_leg": [{"fixture": "Delta v Epsilon (Eredivisie)"}]},
]}


def _render(payload, **kw):
    # Mirror the server path exactly: raw board -> build_feed_payload -> render.
    return render_v2.render_dashboard(schema.build_feed_payload(payload), **kw)


# Deterministic gate state: section 3 asserts the honest "NOT MET" callout, so
# pin the Architect sign-off OFF before the first render (3b flips it ON). This
# is robust whether or not the .env sets ARCHITECT_SIGNOFF=1.
os.environ["ARCHITECT_SIGNOFF"] = "0"

feed = _render(_payload())

# --- 1. masthead + tabnav + hero: wordmark / date / phase / leagues / cal ------
assert 'class="f-masthead"' in feed and 'class="f-hero"' in feed
assert "OLP XDV" in feed and "Mon, 10 Aug 2026" in feed
assert "Phase 2 — paper calibration, zero capital" in feed
assert "2 leagues" in feed and "3 legs logged" in feed
assert 'class="f-tabnav"' in feed
for pill in ("CALL", "SCAN", "SINGLES"):
    assert f'class="f-tabpill' in feed and pill in feed
assert 'class="f-btn f-btn-primary"' in feed and 'class="f-btn f-btn-ghost"' in feed
print("1. masthead + tab nav + hero (date/phase/leagues/calibration): OK")

# --- 2. data-flag chips -------------------------------------------------------
assert "1 data flag" in feed and "EFL Cup: no history" in feed
print("2. data-flag chips render: OK")

# --- 3. gate callout: NOT MET without sign-off --------------------------------
assert 'class="f-gate notmet"' in feed
assert "NOT MET" in feed and "3/30 legs with CLV" in feed
print("3. gate callout shows NOT MET: OK")

# --- 3b. gate callout: OVERRIDE when the Architect signs off (never silent) ---
os.environ["ARCHITECT_SIGNOFF"] = "1"
feed_ovr = _render(_payload())
assert 'class="f-gate override"' in feed_ovr and "OVERRIDE" in feed_ovr
assert "Architect sign-off active" in feed_ovr
assert "override never silent" in feed_ovr
os.environ.pop("ARCHITECT_SIGNOFF", None)
print("3b. gate callout shows OVERRIDE + honest statement: OK")

# --- 4. DATA-LEAK BOUNDARY: no model internals reach the page -----------------
for needle in _INTERNAL_FIELDS:
    assert needle not in feed, f"feed leaks {needle!r}"
print("4. feed carries no model internals: OK")

# --- 5. PRODUCTION BETS — the parity anchor (hero -> splits -> singles) -------
feed_prod = _render(_payload_prod(), booking_codes=CODES_PROD)
assert "PRODUCTION BETS" in feed_prod and "today's fixtures only" in feed_prod
# Lean tickets carry the byte-faithful block; Acca A is the amber hero ticket.
assert 'class="f-ticket f-ticket-hero"' in feed_prod
assert "★ Acca A — HEADLINE, 1 legs" in feed_prod
assert "Fenerbahce v Sturm Graz (Champions League)" in feed_prod
assert "Fenerbahce to win @ 1.91" in feed_prod
assert "Combined 1.91" in feed_prod and "AA111" in feed_prod
assert "★ Acca B  2 legs" in feed_prod and "AB222" in feed_prod
assert "SINGLES — one standalone slip each, own booking code" in feed_prod
assert "SB_BETA" in feed_prod and "SB_DELTA" in feed_prod
print("5. production block: hero -> splits -> singles, own codes: OK")

# --- 5a. density switcher + three density views per group ----------------------
assert feed_prod.count('class="f-densitybar"') == 2      # call + singles
assert 'data-group="call"' in feed_prod and 'data-group="singles"' in feed_prod
for grp in ("call", "singles"):
    for view in ("lean", "trimmed", "full"):
        assert f'data-view="{view}"' in feed_prod
assert feed_prod.count('class="f-density-view active" data-view="trimmed"') == 2
assert 'data-for="lean"' in feed_prod and 'data-for="trimmed"' in feed_prod \
    and 'data-for="full"' in feed_prod
# Trimmed call cards carry the MODEL % dial + market bars + breakeven strip.
assert 'class="f-call-card"' in feed_prod
assert 'class="f-dial"' in feed_prod and "MODEL 56%" in feed_prod
assert "DEPLOY @ 1.52" in feed_prod
assert 'class="f-mkt-line"' in feed_prod and "O2.5" in feed_prod
assert 'class="f-edge-block"' in feed_prod and "MODEL vs BREAKEVEN" in feed_prod
print("5a. density switcher + Trimmed call cards (dial/bars/edge): OK")

# --- 5b. HR35: missing codes render NO DATA — PENDING, never fabricated -------
feed_nocodes = _render(_payload_prod())
# 2 accas + 2 singles each need a code line -> at least 4 honest pendings
assert feed_nocodes.count("NO DATA — PENDING") >= 4
assert "AA111" not in feed_nocodes and "SB_BETA" not in feed_nocodes
print("5b. absent codes render NO DATA — PENDING (HR35): OK")

# --- 5c. honest empty day: no production picks -> the honest note --------------
p_empty = _payload()
p_empty["accas"] = []
feed_empty = _render(p_empty)
assert "NO production pick today" in feed_empty and "HR35" in feed_empty
print("5c. no eligible picks -> honest 'NO production pick today': OK")

# --- 6. scan: league-grouped table + live badge + honest pending ---------------
assert 'class="f-scan"' in feed and "<table" in feed
assert "Champions League (1)" in feed
assert "Fenerbahce to win" in feed and "56%" in feed
assert "NO DATA — PENDING (1)" in feed and "Plymouth Argyle v Exeter City" in feed
assert 'data-fixture="Fenerbahce|Sturm Graz"' in feed
assert "<th>Fixture</th>" in feed and "<th>1X2</th>" in feed and "<th>BTTS</th>" in feed
feed_scores = _render(_payload(),
                      scores={"Fenerbahce|Sturm Graz|2-1": "2-1"})
assert "2-1" in feed_scores
print("6. scan table (league rows, live badge, honest pending): OK")

# --- 7. yesterday / rolling / honest edge -------------------------------------
assert "YESTERDAY — GRADED" in feed
assert "Fenerbahce v Sturm Graz — HOME" in feed
assert 'class="f-mark hit"' in feed and 'class="f-mark miss"' in feed
assert "7-DAY ROLLING" in feed and "50%" in feed
assert "40 legs logged · 3 with CLV (avg CLV -1.20%)" in feed
assert "HONEST EDGE LINE" in feed
assert "Capital authority: THE ARCHITECT" in feed
print("7. yesterday / rolling / honest-edge sections render: OK")

# --- 8. CSP: no inline event handlers anywhere --------------------------------
for page in (feed, feed_prod, feed_nocodes, feed_empty, feed_ovr):
    assert not re.search(r"\son(?:click|change|submit|keyup|input|focus|blur)=",
                         page), "inline event handler found (CSP violation)"
    assert "javascript:" not in page
print("8. no inline handlers (CSP-clean): OK")

# --- 9. HTML tag balance + proto assets cache-busted --------------------------
for page, label in ((feed, "feed"), (feed_prod, "feed-prod")):
    for tag in ("div", "span", "section", "header", "main", "a", "button",
                "script", "nav", "footer", "p", "h2", "table", "tr", "td",
                "th", "svg", "circle"):
        opens = len(re.findall(rf"<{tag}\b", page))
        closes = len(re.findall(rf"</{tag}>", page))
        assert opens == closes, f"unbalanced <{tag}> in {label} ({opens} vs {closes})"
assert re.search(r"proto\.css\?v=\d+", feed)
assert re.search(r"proto\.js\?v=\d+", feed)
print("9. HTML tags balanced + proto assets cache-busted: OK")

print("\n[OK] ALL WEBAPP RENDER_V2 TESTS PASSED")
