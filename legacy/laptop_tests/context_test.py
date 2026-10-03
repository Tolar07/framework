"""Match-context adjustment — bounded, honest about what it cannot see.

Architect directive 2026-09-19: always factor motivation into the engine
decision, as a BOUNDED and LOGGED adjustment. These tests pin the bound and
the reporting, which are the two properties that make the signal auditable
while it is still unvalidated.
"""
import pytest

from engine.context import (
    MAX_ADJUSTMENT,
    build_context,
    _matches_in_window,
    _rest_days,
)


class TestRestDays:
    def test_counts_days_since_most_recent_prior_match(self):
        assert _rest_days(["2026-09-13", "2026-09-06"], "2026-09-19") == 6

    def test_ignores_matches_at_or_after_kickoff(self):
        assert _rest_days(["2026-09-13", "2026-09-26"], "2026-09-19") == 6

    def test_unknown_history_is_none_not_well_rested(self):
        """HR35: absence must not be reported as a measured value."""
        assert _rest_days([], "2026-09-19") is None

    def test_unparseable_kickoff_is_none(self):
        assert _rest_days(["2026-09-13"], "not-a-date") is None


class TestCongestion:
    def test_counts_only_inside_the_window(self):
        dates = ["2026-09-17", "2026-09-13", "2026-09-09", "2026-08-01"]
        assert _matches_in_window(dates, "2026-09-19", window=14) == 3

    def test_empty_history_counts_zero(self):
        assert _matches_in_window([], "2026-09-19") == 0


class TestBuildContext:
    def test_normal_rest_is_neutral(self):
        adj = build_context("A", "B", "Premier League", "2026-09-19",
                            ["2026-09-13"], ["2026-09-13"])
        assert adj.is_neutral
        assert adj.home_rest_days == 6

    def test_short_turnaround_penalises_that_side_only(self):
        adj = build_context("A", "B", "Premier League", "2026-09-19",
                            ["2026-09-17"], ["2026-09-13"])
        assert adj.home_factor < 1.0
        assert adj.away_factor == 1.0
        assert any("short turnaround" in r for r in adj.reasons)

    def test_congestion_penalises_heavy_load(self):
        heavy = ["2026-09-17", "2026-09-14", "2026-09-11",
                 "2026-09-08", "2026-09-06"]
        adj = build_context("A", "B", "Premier League", "2026-09-19",
                            heavy, ["2026-09-13"])
        assert adj.home_matches_14d >= 5
        assert adj.home_factor < adj.away_factor

    def test_cup_applies_to_both_sides_symmetrically(self):
        """Without team news we cannot know who rotates; guessing the
        favourite rotates would be an unfounded inference."""
        adj = build_context("A", "B", "FA Cup", "2026-09-19",
                            ["2026-09-13"], ["2026-09-13"])
        assert adj.home_factor == adj.away_factor < 1.0
        assert any("rotation risk" in r for r in adj.reasons)

    @pytest.mark.parametrize("dates", [
        ["2026-09-18", "2026-09-16", "2026-09-14", "2026-09-12", "2026-09-10"],
    ])
    def test_total_swing_never_exceeds_the_cap(self, dates):
        """Every penalty stacked at once must still respect MAX_ADJUSTMENT."""
        adj = build_context("A", "B", "FA Cup", "2026-09-19", dates, dates)
        lo, hi = 1.0 - MAX_ADJUSTMENT, 1.0 + MAX_ADJUSTMENT
        assert lo <= adj.home_factor <= hi
        assert lo <= adj.away_factor <= hi

    def test_missing_history_is_reported_not_assumed(self):
        adj = build_context("A", "B", "Premier League", "2026-09-19", None, None)
        assert adj.is_neutral
        assert "home match history" in adj.missing
        assert "away match history" in adj.missing

    def test_injuries_always_reported_missing(self):
        """The plan does not expose /injuries for this season. The gap must be
        stated on every fixture, not silently treated as no injuries."""
        adj = build_context("A", "B", "Premier League", "2026-09-19",
                            ["2026-09-13"], ["2026-09-13"])
        assert adj.injury_factor == 1.0
        assert any("injur" in m for m in adj.missing)

    def test_reasons_are_populated_whenever_a_factor_moves(self):
        adj = build_context("A", "B", "Premier League", "2026-09-19",
                            ["2026-09-18"], ["2026-09-13"])
        assert not adj.is_neutral
        assert adj.reasons, "a non-neutral adjustment must say why"
