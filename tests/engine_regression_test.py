"""
Regression tests for defects found in the 2026-08-03 audit.

Every bug below was live, silent, and passed the existing suites. Each test
here fails loudly if the defect returns.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import math
import random
import numpy as np

from engine.dixon_coles import (fit, predict, score_matrix, _dc_tau,
                                 RHO_CLAMP, LAMBDA_CLAMP)
from data.football_data_source import MatchResult
from verification.id403 import verify, SourcedDatum, Tier, _domain_root
from clv.clv_logger import compute_clv
from config import assert_paper_only, CapitalGateError


def synth(n_teams=14, rounds=3, seed=5):
    rng = random.Random(seed)
    np.random.seed(seed)
    teams = [f"T{i}" for i in range(n_teams)]
    atk = {t: rng.uniform(-0.35, 0.35) for t in teams}
    dfc = {t: rng.uniform(-0.35, 0.35) for t in teams}
    out = []
    for r in range(rounds):
        for i, h in enumerate(teams):
            for a in teams:
                if h == a:
                    continue
                lh = math.exp(atk[h] + dfc[a] + 0.28)
                la = math.exp(atk[a] + dfc[h])
                out.append(MatchResult(
                    league="Synth", date=f"2025-{(r%12)+1:02d}-{(i%28)+1:02d}",
                    home_team=h, away_team=a,
                    fthg=int(np.random.poisson(lh)), ftag=int(np.random.poisson(la)),
                    ftr="H"))
    return out


# --- BUG8: tau must be 1.0 outside {0,1}x{0,1} -----------------------------
for h, a in [(2, 0), (0, 2), (3, 2), (5, 4), (2, 2), (9, 1)]:
    assert _dc_tau(h, a, 1.5, 1.2, -0.11) == 1.0, (
        f"BUG8: Dixon-Coles tau must equal 1.0 for {h}-{a}; applying the "
        f"low-score correction to high scores biases rho and every parameter "
        f"fitted with it")
for h, a in [(0, 0), (0, 1), (1, 0), (1, 1)]:
    assert _dc_tau(h, a, 1.5, 1.2, -0.11) != 1.0, f"tau must ADJUST {h}-{a}"
print("1. BUG8 — tau applies only to {0,1}x{0,1}: OK")


# --- BUG6: the fit must be reproducible regardless of starting point -------
data = synth()
cold = fit(data, return_raw_x=True)
seeded = fit(data, x0_teams=cold.warm_seed[0], x0_globals=cold.warm_seed[1],
             return_raw_x=True)
assert abs(cold.rho - seeded.rho) < 1e-3, (
    f"BUG6: rho depends on the starting point ({cold.rho} vs {seeded.rho}) — "
    f"a clamp inside the objective has flattened the gradient again")
assert abs(cold.home_advantage - seeded.home_advantage) < 1e-3
print(f"2. BUG6 — fit reproducible from any start (rho={cold.rho:+.4f}): OK")


# --- BUG6b: rho must not be silently pinned to the clamp ------------------
assert abs(cold.rho - RHO_CLAMP[0]) > 1e-6, (
    "rho sits exactly on the lower clamp — that is the signature of the "
    "flat-gradient bug, not a fitted value")
print("3. rho is a genuine interior optimum, not the clamp boundary: OK")


# --- BUG7: identifiability centering must be scoring-neutral --------------
assert abs(sum(t.attack for t in cold.teams.values())) < 1e-8, "attack must centre to 0"
total_goals = sum(r.fthg + r.ftag for r in data) / len(data)
preds = [p for p in (predict(cold, r.home_team, r.away_team) for r in data) if p]
model_goals = sum(p.lambda_home + p.lambda_away for p in preds) / len(preds)
assert abs(model_goals - total_goals) < 0.15, (
    f"BUG7: model predicts {model_goals:.3f} goals/game on data averaging "
    f"{total_goals:.3f} — centering has shifted the scoring level again")
print(f"4. BUG7 — centering scoring-neutral "
      f"(model {model_goals:.3f} vs actual {total_goals:.3f}): OK")


# --- BUG2: probabilities must sum to 1 at full precision ------------------
p = preds[0]
assert abs(p.p_home + p.p_draw + p.p_away - 1.0) < 1e-9, (
    "BUG2: 1X2 does not sum to 1 — probabilities are being rounded before "
    "they leave the engine")
assert p.p_over_15 >= p.p_over_25 >= p.p_over_35, "overs must be monotonic"
m = score_matrix(1.4, 1.1, cold.rho)
assert abs(m.sum() - 1.0) < 1e-12
print("5. BUG2 — probabilities sum to 1 at full precision: OK")


# --- Lambdas stay sane at prediction time (BUG1 guard still in place) -----
for pr in preds:
    assert LAMBDA_CLAMP[0] <= pr.lambda_home <= LAMBDA_CLAMP[1]
    assert LAMBDA_CLAMP[0] <= pr.lambda_away <= LAMBDA_CLAMP[1]
print("6. BUG1 — predicted lambdas remain inside the sane range: OK")


# --- Domain spoofing must not inherit a trusted tier ----------------------
assert _domain_root("bbc.co.uk") == "bbc.co.uk"
assert _domain_root("sport.bbc.co.uk") == "bbc.co.uk", "true subdomains resolve"
assert _domain_root("bbc.co.uk.evil.example") != "bbc.co.uk", (
    "a lookalike domain inherited a trusted tier via substring matching")
assert _domain_root("notbbc.co.uk") != "bbc.co.uk"
print("7. Domain resolution rejects lookalikes: OK")


# --- ID404: T3 aggregators are lead-only and never verify -----------------
t3 = verify([SourcedDatum(domain="predictz.com", value="X", url="http://a"),
             SourcedDatum(domain="fctables.com", value="X", url="http://b")])
assert t3.tier == Tier.SINGLE_SOURCE, (
    "ID404 violated: two T3 aggregators agreeing produced a VERIFIED stamp")
real = verify([SourcedDatum(domain="football-data.co.uk", value="X", url="http://a"),
               SourcedDatum(domain="bbc.co.uk", value="X", url="http://b")])
assert real.tier == Tier.VERIFIED, "T1 + T2 agreeing must VERIFY"
print("8. ID404 — T3 never verifies; T1+T2 does: OK")


# --- CLV sign and the capital gate ---------------------------------------
assert compute_clv(2.10, 2.00) > 0, "beating the close must be POSITIVE CLV"
assert compute_clv(2.00, 2.10) < 0
assert_paper_only(None, "phase2_paper")          # a paper leg is fine
for bad in (250.0, 0.0, -1.0):
    try:
        assert_paper_only(bad, "phase2_paper")
        raise AssertionError(f"capital gate let stake={bad} through")
    except CapitalGateError:
        pass
print("9. CLV sign correct; capital gate blocks every stake: OK")


print("\n✅ ALL ENGINE REGRESSION TESTS PASSED")


# --- Elo (ID82): a genuinely independent second engine ---------------------
from engine.elo import (EloModel, rate_through, divergence,
                        goal_difference_modifier, HOME_ADVANTAGE_ELO, BASE_RATING)

e = EloModel()
before = e.rating("A") + e.rating("B")
e.update("A", "B", 3, 0)
assert abs((e.rating("A") + e.rating("B")) - before) < 1e-9, (
    "Elo must be zero-sum: what one club gains the other loses")
assert e.rating("A") > BASE_RATING > e.rating("B")
print("10. Elo updates are zero-sum: OK")

mods = [goal_difference_modifier(g) for g in (0, 1, 2, 3, 4, 7)]
assert mods == sorted(mods), "margin weighting must be non-decreasing in goal difference"
assert mods[0] == mods[1] == 1.0, "a 1-goal win carries no extra weight"
assert mods[-1] < 3.0, "a 7-goal win must not move ratings absurdly"
print(f"11. Goal-difference weighting tapers correctly {mods}: OK")

# Leakage: a rating cut at date D must be identical whether or not later
# matches exist in the input. This is Elo's structural guarantee.
early = [r for r in data if r.date < "2025-06-01"]
m_cut = rate_through(data, cut_date="2025-06-01", burn_in=1)
m_only = rate_through(early, burn_in=1)
assert m_cut.n_matches == m_only.n_matches, "cut must exclude later matches"
for t in list(m_only.ratings)[:20]:
    assert abs(m_cut.rating(t) - m_only.rating(t)) < 1e-9, (
        f"LEAK: rating for {t} changed because future matches were present")
print(f"12. Elo cut-date is leak-proof ({m_cut.n_matches} matches): OK")

m_full = rate_through(data, burn_in=3)
probs = None
for r in data:
    p = m_full.probabilities(r.home_team, r.away_team)
    if p:
        probs = p
        break
assert probs is not None, "Elo produced no probabilities at all"
assert abs(sum(probs) - 1.0) < 1e-9, "Elo 1X2 must sum to 1"
assert all(0 < x < 1 for x in probs), "no probability may be 0 or 1"
print(f"13. Elo 1X2 sums to 1 and stays in range {tuple(round(x,3) for x in probs)}: OK")


class _FakeDC:
    p_home, p_draw, p_away = 0.70, 0.20, 0.10


assert divergence((0.70, 0.20, 0.10), _FakeDC()) is None, "agreement must not flag"
d = divergence((0.35, 0.30, 0.35), _FakeDC())
assert d and "ENGINE DIVERGENCE" in d, "a 35pp gap between engines must flag"
print("14. Engine-divergence flag fires on disagreement, silent on agreement: OK")


# --- ID405: a blocked market must be unreachable on EVERY path ------------
from engine import markets as mkt
from output.produce_bet import _best_market_desc


class _P:
    home_team, away_team = "Hearts", "Celtic"
    p_home, p_draw, p_away = 0.20, 0.15, 0.65      # away is the strongest side
    p_over_15, p_over_25, p_over_35 = 0.99, 0.95, 0.50   # overs also strong
    p_btts_yes = 0.90


assert mkt.blocked(mkt.AWAY) and mkt.blocked(mkt.OVER_25), "ID405 markets must be blocked"
assert mkt.AWAY not in mkt.DEPLOYABLE and mkt.OVER_25 not in mkt.DEPLOYABLE
name, prob = _best_market_desc(_P())
assert "Celtic to win" not in name, (
    f"ID405 LEAK: the board headlined a blocked away win ({name}). The gate "
    f"must hold on the RENDER path too, not only when logging — otherwise the "
    f"board recommends exactly what the framework refuses to record.")
assert "Over 2.5" not in name, f"ID405 LEAK: board headlined a blocked Over 2.5 ({name})"
print(f"15. ID405 - blocked markets cannot headline THE CALL (chose '{name}'): OK")

assert mkt.settle(mkt.HOME, 2, 1) is True and mkt.settle(mkt.AWAY, 2, 1) is False
assert mkt.settle(mkt.UNDER_25, 1, 1) is True and mkt.settle(mkt.OVER_25, 1, 1) is False
assert mkt.settle("NOT_A_MARKET", 1, 1) is None, "an unknown market must not be guessed"
assert mkt.display(mkt.AWAY, "Hearts", "Celtic") == "Celtic to win"
print("16. Canonical registry: display, settle and gate all agree on one key: OK")

print("\n✅ ALL ENGINE REGRESSION TESTS PASSED (incl. Elo + ID405)")


# --- Telegram board: fences balanced, no blocked market as a Pick ----------
from output.notify import _chunk, FENCE
from output.produce_bet import render_telegram_board, BoardFixture
from verification.id403 import verify as _verify, SourcedDatum as _SD


class _Probs:
    home_team, away_team = "Heart of Midlothian", "Dundee United"
    p_home, p_draw, p_away = 0.20, 0.15, 0.65        # away strongest
    p_over_15, p_over_25, p_over_35 = 0.99, 0.95, 0.60
    p_btts_yes, lambda_home, lambda_away = 0.90, 2.4, 1.1


_v = _verify([_SD(domain="thesportsdb.com", value="x", url="http://x")])
# Enough fixtures to exceed Telegram's per-message limit and force a split
# INSIDE a code fence — the case that used to emit an unclosed ``` and render
# the table as broken plain text.
_fixtures = [
    BoardFixture(fixture=f"Long Club Name {i} v Another Long Club {i} (Eredivisie)",
                 probs=_Probs(), verification=_v, softness_tier="A",
                 on_deploy_shortlist=(i < 3), mes_trigger_price=1.5)
    for i in range(120)
]
_board_txt = render_telegram_board("Mode A", "Phase 2", ["Eredivisie"], 0, None,
                                    ["a flag"], _fixtures)

_parts = _chunk(_board_txt)
for _i, _p in enumerate(_parts, 1):
    assert _p.count(FENCE) % 2 == 0, (
        f"chunk {_i} of {len(_parts)} has an unbalanced code fence — Telegram "
        f"would render it as broken plain text and the columns would collapse")
assert len(_parts) >= 2, "test board should be long enough to force a split"
print(f"17. Telegram chunking: {len(_parts)} parts, every fence balanced: OK")

# The board now shows market probabilities in plain language (e.g. an "Over
# 2.5 goals: 74%" line is a probability, not a pick), so the leak check must
# target the PICK lines only — the ⭐ rows. A blocked market as a ⭐ Pick is
# the failure; mentioning it as a probability is not.
_pick_lines = [ln for ln in _board_txt.splitlines()
               if ln.lstrip().startswith("⭐")]
assert not any("Dundee United to win" in ln for ln in _pick_lines), (
    "ID405 LEAK in the board: a blocked away win appeared as a Pick")
assert not any("Over 2.5" in ln for ln in _pick_lines), (
    "ID405 LEAK: blocked Over 2.5 appeared as a Pick")
assert "Heart of Midlothian" in _board_txt, "HR53: club names must not be truncated"
print("18. Table board honours ID405 and keeps full club names: OK")


# --- Elo persistence ------------------------------------------------------
# What must hold: round-trip is EXACT, snapshot + zero new matches is EXACT,
# a wrong-version snapshot is REFUSED. What must NOT be claimed: that an
# incremental run equals a fresh full run \u2014 burn-in makes that mathematically
# impossible, and asserting it hid a real behaviour the caller needs to know.
import json as _json
import tempfile as _tempfile
from pathlib import Path as _Path

_data = synth(seed=19)
_full = rate_through(_data)
_snap = _Path(_tempfile.mkdtemp()) / "elo.json"
_full.save(_snap)
_back = EloModel.load(_snap)
for _t in _full.ratings:
    assert abs(_full.rating(_t) - _back.rating(_t)) < 1e-12, "round trip must be exact"
assert (_full.n_matches == _back.n_matches and _full.last_date == _back.last_date
        and abs(_full._draw_a - _back._draw_a) < 1e-12
        and abs(_full._draw_b - _back._draw_b) < 1e-12), "metadata must round-trip"
print(f"19. Elo save/load is byte-exact ({len(_full.ratings)} clubs): OK")

# Snapshot + no new matches must be a no-op. This is the guarantee the daily
# job depends on: "load yesterday's ratings, apply today's matches" must not
# quietly rewrite yesterday.
_noop = rate_through(_data, seed_from=_snap,
                     cut_date=_full.last_date)  # cut BEFORE last_date -> 0 new
assert _noop.n_matches == _full.n_matches, "noop must not change match count"
for _t in _full.ratings:
    assert abs(_noop.rating(_t) - _full.rating(_t)) < 1e-9, (
        f"noop rerun changed {_t}: {_full.rating(_t)} -> {_noop.rating(_t)}")
print("20. Elo incremental with no new matches is a no-op: OK")

# Wrong-version snapshot must be REFUSED, not adapted. Adapting would mean
# guessing what missing fields used to mean \u2014 the HR35 fabrication trap.
_bad = _Path(_tempfile.mkdtemp()) / "wrong.json"
_blob = _json.loads(_snap.read_text(encoding="utf-8"))
_blob["version"] = 99
_bad.write_text(_json.dumps(_blob), encoding="utf-8")
try:
    EloModel.load(_bad)
    raise AssertionError("wrong-version snapshot was loaded silently")
except ValueError:
    pass
print("21. Elo refuses a wrong-version snapshot (HR35): OK")

# CSV export is human-inspection only, but must produce a header + at least
# one row and must be sorted strongest first.
_csv = _Path(_tempfile.mkdtemp()) / "elo.csv"
_full.export_csv(_csv)
_lines = _csv.read_text(encoding="utf-8").splitlines()
assert _lines[0].startswith("rank,team,elo"), "CSV must have header row"
_first_rating = float(_lines[1].split(",")[2])
_last_rating = float(_lines[-1].split(",")[2])
assert _first_rating >= _last_rating, "CSV must be sorted strongest first"
print(f"22. Elo CSV export: {len(_lines)-1} rows, strongest first: OK")


print("\n\u2705 ALL ENGINE REGRESSION TESTS PASSED (incl. Elo + ID405 + board + persistence)")
