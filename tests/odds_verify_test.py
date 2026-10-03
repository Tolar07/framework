"""
Tests for pipeline.odds_verify — the ID403 F2 quorum stamp for live odds.

Offline, plain-script style. Guards:
  1. prices_agree: within/outside tolerance, and None when a price is missing.
  2. cross_verify: VERIFIED when an independent source agrees, CONFLICT when it
     disagrees, SINGLE-SOURCE when there's no counterpart or no co-quoted market.
  3. Two quotes from the same source never corroborate (independence required).
  4. It never drops or rewrites a price — only labels provenance.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.odds import FixtureOdds, MarketQuote
import pipeline.odds_verify as v


def _fx(home_p, draw_p, away_p, source, ht="Ajax", at="Feyenoord") -> FixtureOdds:
    return FixtureOdds(
        league="Eredivisie", home_team=ht, away_team=at, kickoff_utc="2026-10-04",
        home=MarketQuote(price=home_p, bookmaker="bet365"),
        draw=MarketQuote(price=draw_p, bookmaker="bet365"),
        away=MarketQuote(price=away_p, bookmaker="bet365"),
        source=source)


def test_prices_agree() -> None:
    assert v.prices_agree(2.00, 2.02, 5.0) is True
    assert v.prices_agree(2.00, 2.50, 5.0) is False       # 22% apart
    assert v.prices_agree(2.00, None, 5.0) is None
    assert v.prices_agree(None, 2.00, 5.0) is None


def test_verified_when_independent_source_agrees() -> None:
    primary = [_fx(1.80, 3.80, 4.20, "the-odds-api.com")]
    secondary = [_fx(1.82, 3.75, 4.10, "football-data.co.uk (fixtures)")]
    out, flags = v.cross_verify(primary, secondary, tol_pct=5.0)
    assert out[0].verification == v.VERIFIED, flags
    assert out[0].home.price == 1.80, "must not rewrite the primary price"


def test_conflict_when_prices_diverge() -> None:
    primary = [_fx(1.80, 3.80, 4.20, "the-odds-api.com")]
    secondary = [_fx(2.60, 3.20, 2.70, "football-data.co.uk (fixtures)")]
    out, _ = v.cross_verify(primary, secondary, tol_pct=5.0)
    assert out[0].verification == v.CONFLICT
    assert any("CONFLICT" in n for n in out[0].notes)


def test_single_source_when_no_counterpart() -> None:
    primary = [_fx(1.80, 3.80, 4.20, "the-odds-api.com")]
    out, _ = v.cross_verify(primary, [], tol_pct=5.0)
    assert out[0].verification == v.SINGLE_SOURCE


def test_same_source_does_not_corroborate() -> None:
    primary = [_fx(1.80, 3.80, 4.20, "the-odds-api.com")]
    secondary = [_fx(1.80, 3.80, 4.20, "the-odds-api.com")]  # same source
    out, _ = v.cross_verify(primary, secondary, tol_pct=5.0)
    assert out[0].verification == v.SINGLE_SOURCE, "same source is not independent"


def main() -> None:
    test_prices_agree()
    test_verified_when_independent_source_agrees()
    test_conflict_when_prices_diverge()
    test_single_source_when_no_counterpart()
    test_same_source_does_not_corroborate()
    print("odds_verify_test: OK")


if __name__ == "__main__":
    main()
