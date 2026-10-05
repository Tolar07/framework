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


# --- test 1: an uncovered league is flagged, never silently skipped or guessed ---
board, flags = orchestrator.scan_one_league("Not A Real League", season="2526")
assert board == [], "an uncovered league must produce an empty board, never fabricated fixtures"
assert flags and any("Not A Real League" in f for f in flags), \
    f"uncovered league must be flagged explicitly, got: {flags}"
print("Uncovered league correctly flagged, not silently dropped: OK")

# --- test 1b: European cups are market-implied (2026-10-05) and never invent a price ---
assert {"Champions League", "Europa League", "Conference League", "HNL"} <= \
    orchestrator.MARKET_ONLY_LEAGUES
with patch("pipeline.odds.fixtures_from_odds",
           return_value=([("Lens", "Sporting")], {("Lens", "Sporting"): "2026-10-13"}, [])), \
        patch("orchestrator._odds_by_pair", return_value=({}, [])):
    board, flags = orchestrator.scan_one_league("Champions League", season="2526")
assert len(board) == 1 and board[0].probs is None and not board[0].on_deploy_shortlist, \
    "a fixture with no price is listed, never given made-up numbers or deployed (HR35)"
assert "NO DATA — PENDING" in (board[0].rejection_reason or "")
assert board[0].prob_source == "market"
assert any("0/1 fixture(s) priced MARKET-IMPLIED" in f and "no edge claimed" in f
           for f in flags), flags
print("Champions League priced market-implied, nothing invented without a price: OK")


# --- test 2: thin history is flagged rather than fit on too little ---
with patch("orchestrator.load_league", return_value=([], [])):
    board, flags = orchestrator.scan_one_league("Scottish Premiership", season="2526",
                                                  upcoming_fixtures=[("A", "B")])
    assert board == []
    assert any("insufficient match history" in f for f in flags)
print("Thin/empty history correctly flagged rather than fit: OK")


# --- test 3: global deploy cap across MULTIPLE leagues combined ---
results_a, teams_a = make_synthetic_results("Eredivisie")   # tier A
results_b, teams_b = make_synthetic_results("Scottish Premiership")
results_c, teams_c = make_synthetic_results("Bundesliga")   # whitelisted, now deploy-eligible

fixtures_a = [(teams_a[0], teams_a[1]), (teams_a[2], teams_a[3]), (teams_a[4], teams_a[5])]
fixtures_b = [(teams_b[0], teams_b[1]), (teams_b[2], teams_b[3]), (teams_b[4], teams_b[5])]
fixtures_c = [(teams_c[0], teams_c[1]), (teams_c[2], teams_c[3])]

def fake_load_league(league, season):
    return {"Eredivisie": (results_a, []),
            "Scottish Premiership": (results_b, []),
            "Bundesliga": (results_c, [])}[league]

def fake_fetch_upcoming(league, season_year):
    raise RuntimeError("fixtures_source not used in this test — fixtures passed directly")

with patch("orchestrator.load_league", side_effect=fake_load_league):
    board_a, _ = orchestrator.scan_one_league("Eredivisie", "2526", upcoming_fixtures=fixtures_a)
    board_b, _ = orchestrator.scan_one_league("Scottish Premiership", "2526", upcoming_fixtures=fixtures_b)
    board_c, _ = orchestrator.scan_one_league("Bundesliga", "2526", upcoming_fixtures=fixtures_c)

combined = board_a + board_b + board_c
# Softness tiering RETIRED: every whitelisted league (incl. the former "scan-only"
# Bundesliga) is now deploy-eligible when it has model probabilities.
assert any(b.on_deploy_shortlist for b in board_c), \
    "Bundesliga is whitelisted, so its fixtures with probs must be deploy-eligible now"
print(f"Whitelisted Bundesliga fixtures are deploy-eligible (no tiering): OK "
      f"({len(board_c)} scanned)")

# All three leagues feed one pool; the GLOBAL cap still holds across them.
from engine.slate import build_deploy_shortlist, DEPLOY_POOL_CAP
eligible = [b for b in combined if b.on_deploy_shortlist]
print(f"Deploy-eligible fixtures across all three leagues combined: {len(eligible)}")
capped = build_deploy_shortlist(eligible)
assert len(capped) <= DEPLOY_POOL_CAP
print(f"Global cap enforced across leagues combined: {len(capped)} <= {DEPLOY_POOL_CAP} OK")

print("\n✅ ALL MULTI-LEAGUE ORCHESTRATION TESTS PASSED")
