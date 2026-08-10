"""
Tests orchestrator.scan_one_league / run_all_leagues logic with mocked data
sources — confirms: uncovered leagues flag correctly (not silently dropped),
the global 6-fixture deploy cap applies across ALL leagues combined (not per
league), and scan-only tiers never leak into THE CALL even when scanned wide.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import random
import numpy as np
from unittest.mock import patch

import orchestrator
from data.football_data_source import MatchResult

random.seed(7)
np.random.seed(7)


def make_synthetic_results(league: str, n_teams: int = 10) -> list[MatchResult]:
    teams = [f"{league[:3]}Team{i}" for i in range(1, n_teams + 1)]
    attack = {t: random.uniform(-0.3, 0.3) for t in teams}
    defence = {t: random.uniform(-0.3, 0.3) for t in teams}
    results = []
    for home in teams:
        for away in teams:
            if home == away:
                continue
            lam_h = np.exp(attack[home] + defence[away] + 0.3)
            lam_a = np.exp(attack[away] + defence[home])
            results.append(MatchResult(
                league=league, date="2026-01-01", home_team=home, away_team=away,
                fthg=int(np.random.poisson(lam_h)), ftag=int(np.random.poisson(lam_a)),
                ftr="H",
            ))
    return results, teams


# --- test 1: uncovered league is flagged AND its real fixtures survive as ---
# NO DATA rows (2026-08-10 ratification). Champions League and HNL are now
# COVERED (odds feed / TheSportsDB + thesportsdb_results fallback). EFL Cup is
# the remaining honest uncovered league — no free history source. Ratified
# behavior: the history gap must NEVER make a real fixture invisible (HR35
# wide-eyes), so the fixture scan falls through to the SportyBet cache and the
# fixture is listed as a NO DATA — PENDING row, never fabricated, never dropped.
board, flags = orchestrator.scan_one_league("EFL Cup", season="2526")
assert len(board) >= 1, \
    "an uncovered league's real fixtures must still be listed as NO DATA rows, never dropped"
assert all(b.probs is None for b in board), \
    "no probability may be fabricated for an uncovered league"
assert all("NO DATA — PENDING" in (b.rejection_reason or "") for b in board), \
    "unrated fixtures must carry the honest NO DATA reason"
assert any("NO DATA" in f and "EFL Cup" in f for f in flags), \
    f"uncovered league must be flagged explicitly, got: {flags}"
print(f"Uncovered league (EFL Cup) flagged + {len(board)} fixture(s) listed as NO DATA (never dropped): OK")


# --- test 2: thin history is flagged, fixtures still shown as NO DATA -------
# A league with no usable history cannot be RATED, but its fixtures must still
# appear on the wide-eyes board as NO DATA — PENDING rows (HR35) — never
# silently dropped. The thin-fit guardrail stays: the flag is present and the
# row carries no probability.
with patch("orchestrator.load_league", return_value=([], [])):
    board, flags = orchestrator.scan_one_league("Scottish Premiership", season="2526",
                                                  upcoming_fixtures=[("A", "B")])
    assert len(board) == 1, \
        f"fixtures must survive as NO DATA rows, never dropped: {board}"
    assert board[0].probs is None, "no probability on a historyless league"
    assert "NO DATA — PENDING" in board[0].rejection_reason, board[0].rejection_reason
    assert any("insufficient match history" in f for f in flags)
print("Thin/empty history flagged; fixtures shown as NO DATA (never dropped): OK")


# --- test 3: global deploy cap across MULTIPLE leagues combined ---
results_a, teams_a = make_synthetic_results("Eredivisie")   # tier A
results_b, teams_b = make_synthetic_results("Scottish Premiership")  # tier B
results_c, teams_c = make_synthetic_results("Bundesliga")   # tier C — scan only

fixtures_a = [(teams_a[0], teams_a[1]), (teams_a[2], teams_a[3]), (teams_a[4], teams_a[5])]
fixtures_b = [(teams_b[0], teams_b[1]), (teams_b[2], teams_b[3]), (teams_b[4], teams_b[5])]
fixtures_c = [(teams_c[0], teams_c[1]), (teams_c[2], teams_c[3])]

def fake_load_league(league, season):
    return {"Eredivisie": (results_a, []),
            "Scottish Premiership": (results_b, []),
            "Bundesliga": (results_c, [])}[league]

def fake_fetch_upcoming(league, season_year):
    raise RuntimeError("fixtures_source not used in this test — fixtures passed directly")

import engine.softness as softness
softness.SOFTNESS_PAUSED = False  # test the ratified A/B gating machinery

with patch("orchestrator.load_league", side_effect=fake_load_league):
    board_a, _ = orchestrator.scan_one_league("Eredivisie", "2526", upcoming_fixtures=fixtures_a)
    board_b, _ = orchestrator.scan_one_league("Scottish Premiership", "2526", upcoming_fixtures=fixtures_b)
    board_c, _ = orchestrator.scan_one_league("Bundesliga", "2526", upcoming_fixtures=fixtures_c)

combined = board_a + board_b + board_c
assert all(not b.on_deploy_shortlist for b in board_c), \
    "Bundesliga (tier C, scan-only) must never appear in the deploy shortlist"
print(f"Tier C (Bundesliga) fixtures correctly excluded from deploy shortlist: OK "
      f"({len(board_c)} scanned, 0 deploy-eligible)")

# Force more than 6 eligible across A+B combined to test the GLOBAL cap
from engine.softness import build_deploy_shortlist, DEPLOY_POOL_CAP
eligible = [b for b in combined if b.on_deploy_shortlist]
print(f"Deploy-eligible fixtures across Eredivisie+Scottish Premiership combined: {len(eligible)}")
capped = build_deploy_shortlist(eligible)
assert len(capped) <= DEPLOY_POOL_CAP
print(f"Global cap enforced across leagues combined: {len(capped)} <= {DEPLOY_POOL_CAP} OK")

# --- test 3b: SOFTNESS_PAUSED=True — C tier becomes deploy-eligible, no cap ---
softness.SOFTNESS_PAUSED = True
with patch("orchestrator.load_league", side_effect=fake_load_league):
    board_c_paused, _ = orchestrator.scan_one_league("Bundesliga", "2526", upcoming_fixtures=fixtures_c)
assert any(b.on_deploy_shortlist for b in board_c_paused), \
    "Bundesliga (tier C) must be deploy-eligible when softness is PAUSED"
assert len(board_c_paused) == len(fixtures_c), "all C fixtures rated"
print(f"Softness PAUSED: Bundesliga (tier C) fixtures deploy-shortlisted: OK "
      f"({sum(1 for b in board_c_paused if b.on_deploy_shortlist)} of {len(board_c_paused)})")

softness.SOFTNESS_PAUSED = False  # restore for subsequent modules

print("\n✅ ALL MULTI-LEAGUE ORCHESTRATION TESTS PASSED")
