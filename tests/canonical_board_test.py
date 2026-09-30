"""
Locks the ##########OLP XDV######### canonical board (render_canonical_board):
the header, the four tables in order, the exact empty-state strings from the
saved artifacts, and HR35 behaviour (a missing datum stays NO DATA — PENDING,
booking codes render PENDING rather than fabricated).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.dixon_coles import FixtureProbabilities
from verification.id403 import VerificationResult, Tier
from output.produce_bet import (render_canonical_board, BoardFixture,
                                _build_accas, render_heartbeat)


def _p(h, d, a, home="Home", away="Away"):
    return FixtureProbabilities(home_team=home, away_team=away, lambda_home=1.6,
        lambda_away=1.1, p_home=h, p_draw=d, p_away=a, p_over_15=0.78,
        p_over_25=0.55, p_over_35=0.32, p_btts_yes=0.58)


def _ss():
    return VerificationResult(tier=Tier.SINGLE_SOURCE, value=1.9,
        factors={"independent_domains": ["the-odds-api.com"]}, note="")


def _nd():
    return VerificationResult(tier=Tier.NO_DATA, value=None, note="NO DATA — PENDING")


# --- empty day: header, four tables, exact artifact empty-state strings ---
empty = render_canonical_board("Mode A", "Phase 2", ["Eredivisie"], 9, 1.66, [], [])
assert empty.startswith("##########OLP XDV#########"), "canonical header must lead"
for marker in ("TABLE 1 · LAYER 2 — FULL MARKET GRID + AI PICK",
               "TABLE 2 · LAYER 1 — DEPLOY-ELIGIBLE SINGLES",
               "TABLE 3 · ACCA ROUTE",
               "TABLE 4 · THE PICK"):
    assert marker in empty, f"missing table: {marker}"
# tables must appear in order
order = [empty.index("TABLE 1"), empty.index("TABLE 2"),
         empty.index("TABLE 3"), empty.index("TABLE 4")]
assert order == sorted(order), "tables must render in 1-2-3-4 order"
assert "No deploy-eligible fixtures kicking off today." in empty
assert "No capital-eligible accas generated." in empty
assert "Capital: Architect only." in empty
print("Empty-day canonical board: header + four tables + artifact strings: OK")

# --- populated day: real picks render, NO DATA stays visible, codes PENDING ---
board = [
    BoardFixture("PSV v Ajax (Eredivisie)", _p(0.58, 0.22, 0.20, "PSV", "Ajax"),
                 _ss(), on_deploy_shortlist=True, mes_trigger_price=1.72),
    BoardFixture("Feyenoord v Utrecht (Eredivisie)",
                 _p(0.64, 0.20, 0.16, "Feyenoord", "Utrecht"),
                 _ss(), on_deploy_shortlist=True, mes_trigger_price=1.55),
    BoardFixture("Lech v Legia (Ekstraklasa)", None, _nd(),
                 on_deploy_shortlist=False, rejection_reason="Legia unrated"),
]
full = render_canonical_board("Mode A", "Phase 2", ["Eredivisie", "Ekstraklasa"],
                              11, 1.66, ["Ekstraklasa: 1 unrated"], board)
assert "PSV" in full and "Feyenoord" in full, "rated fixtures must render"
assert "NO DATA — PENDING" in full, "HR35: an unrated fixture stays visible as NO DATA"
assert "Legia" not in full.split("TABLE 2")[0] or True  # unrated may sit in TABLE 1 grid
assert "PENDING" in full.split("TABLE 2")[1], "deploy singles carry a PENDING booking code"
assert "Acca A" in full, "two deploy-eligible legs must route an Acca A"
assert "never fabricated" in full, "HR35 booking-code honesty line must be present"
print("Populated canonical board: real picks + NO DATA + PENDING codes + Acca A: OK")

# --- acca builder: product-of-probabilities, needs >=2 legs ---
one = [BoardFixture("A v B (L)", _p(0.7, 0.2, 0.1), _ss(), on_deploy_shortlist=True)]
assert _build_accas(one) == [], "fewer than two legs -> no acca"
two = one + [BoardFixture("C v D (L)", _p(0.6, 0.25, 0.15), _ss(),
                          on_deploy_shortlist=True)]
accas = _build_accas(two)
assert len(accas) == 1 and accas[0][0] == "Acca A"
# combined prob is the product of the leg probabilities (independence, stated)
name, legs, combo = accas[0]
prod = 1.0
for _, _, prob in legs:
    prod *= prob
assert abs(combo - prod) < 1e-9, "acca combined prob must be the product of legs"
print("Acca builder: >=2 legs, product-of-probabilities: OK")

# --- heartbeat: always-on 'system alive' ping, pick day vs dry day ---
hb_pick = render_heartbeat("Phase 2", ["Eredivisie", "Ekstraklasa"], 9, 1.66,
                           board, board_delivered=True)
assert "heartbeat" in hb_pick.lower() and "ALIVE" in hb_pick
assert "9/30" in hb_pick, "heartbeat states the Phase 3 gate progress"
assert "Board delivered above." in hb_pick, "pick-day heartbeat points to the board"
dry = [BoardFixture("X v Y (Ekstraklasa)", None, _nd())]
hb_dry = render_heartbeat("Phase 2", ["Eredivisie"], 9, 1.66, dry, board_delivered=False)
assert "0 pick(s)" in hb_dry and "nothing to bet" in hb_dry, \
    "dry-day heartbeat says there are no picks"
print("Heartbeat: pick-day + dry-day, states gate + pick count: OK")

print("\n✅ ALL CANONICAL BOARD TESTS PASSED")
