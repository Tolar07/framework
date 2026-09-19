"""Bookability gate — a leg must be placeable before it can be a bet.

Architect directive 2026-09-19: build the accas from the pool we can actually
book. These tests pin the rule that was derived from measured data, not from a
guess about which competitions are obscure — on the 2026-09-19 board, totals
went 13/13 including Latvia and Croatia while Draw No Bet went 0/4 including
Serie A, so the gate keys on market family and registry coverage, never on
competition prestige.
"""
import pytest

from booking.bookability import (
    competition_is_bookable,
    leg_is_bookable,
    market_is_drivable,
)


class TestMarketIsDrivable:
    @pytest.mark.parametrize("key", [
        "UNDER_3_5", "OVER_1_5", "UNDER_2_5", "OVER_0_5",
        "1X2_HOME", "1X2_DRAW", "1X2_AWAY",
        "DNB_HOME", "DNB_AWAY",
        "DC_1X", "DC_12", "DC_X2",
    ])
    def test_proven_families_are_drivable(self, key):
        assert market_is_drivable(key)

    @pytest.mark.parametrize("key", ["BTTS_YES", "BTTS_NO"])
    def test_unproven_families_are_withheld(self, key):
        """Held out until observed landing on a real slip, not assumed broken."""
        assert not market_is_drivable(key)

    @pytest.mark.parametrize("key", ["CS_1_0", "HT_FT_HOME_HOME", "", None])
    def test_unknown_markets_are_refused(self, key):
        assert not market_is_drivable(key)


class TestCompetitionIsBookable:
    @pytest.mark.parametrize("league", [
        "Serie A", "Premier League", "Championship",
        # Not top-20, and they booked without complaint on 2026-09-19 — the
        # gate must not exclude them.
        "Latvian Virsliga", "HNL", "Serbian Super Liga", "Israeli Premier League",
        # Resolved 2026-09-19 after the id map wrongly recorded them as absent.
        "Taça de Portugal", "Austrian Bundesliga", "Czech First League",
    ])
    def test_registered_competitions_pass(self, league):
        assert competition_is_bookable(league)

    @pytest.mark.parametrize("league", [
        "Gibraltarian National League",   # genuinely not in SportyBet's menu
        "Luxembourg National Division",
        "Not A Real League",
        "",
        None,
    ])
    def test_unregistered_competitions_fail(self, league):
        assert not competition_is_bookable(league)


class TestLegIsBookable:
    def test_bookable_leg_has_no_reason(self):
        ok, reason = leg_is_bookable("Serie A", "UNDER_3_5")
        assert ok and reason == ""

    def test_serie_a_dnb_is_bookable_after_match_page_fix(self):
        """The exact leg that failed on 2026-09-19 (Lazio Draw No Bet)."""
        ok, _ = leg_is_bookable("Serie A", "DNB_AWAY")
        assert ok

    def test_unbookable_competition_names_itself(self):
        ok, reason = leg_is_bookable("Gibraltarian National League", "UNDER_3_5")
        assert not ok
        assert "Gibraltarian National League" in reason

    def test_undrivable_market_names_itself(self):
        ok, reason = leg_is_bookable("Serie A", "CS_1_0")
        assert not ok
        assert "CS_1_0" in reason

    def test_unproven_market_is_distinguished_from_undrivable(self):
        """BTTS is unproven, not known-broken — the reason must say so, since
        the two warrant different follow-up (observe one land vs build a path)."""
        _, unproven = leg_is_bookable("Serie A", "BTTS_YES")
        _, unknown = leg_is_bookable("Serie A", "CS_1_0")
        assert "unproven" in unproven
        assert "unproven" not in unknown

    def test_competition_checked_before_market(self):
        """Both wrong -> report the competition, the more fundamental gap."""
        ok, reason = leg_is_bookable("Not A Real League", "CS_1_0")
        assert not ok
        assert "competition" in reason
