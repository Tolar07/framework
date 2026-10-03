"""
Tests for pipeline.odds_verify — the ID403 F2 price check.

Offline, plain-script style. Guards:
  1. prices_agree: within/outside tolerance, and None when a price is missing.
  2. cross_verify: VERIFIED when an independent source agrees, CONFLICT when it
     disagrees, SINGLE-SOURCE when there's no counterpart or no co-quoted market.
  3. Two quotes from the same source never corroborate (independence required).
  4. It never drops or rewrites a price — only labels provenance.
  5. Books with different margins but the same view AGREE (chances compared
     with the margin removed, not raw prices).
  6. check_prices (the live wiring): labels each SportyBet quote on the board's
     day against bet365 (football-data) and DraftKings (ESPN), spelling
     differences included; leaves other days unchecked; a source that is down
     is flagged, never fatal.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pipeline.odds_verify as v
from data.espn_fixtures import EspnEvent
from pipeline.odds import FixtureOdds, MarketQuote


def _fx(home_p, draw_p, away_p, source, ht="Ajax", at="Feyenoord",
        day="2026-10-04", book="bet365") -> FixtureOdds:
    return FixtureOdds(
        league="Eredivisie", home_team=ht, away_team=at, kickoff_utc=day,
        home=MarketQuote(price=home_p, bookmaker=book),
        draw=MarketQuote(price=draw_p, bookmaker=book),
        away=MarketQuote(price=away_p, bookmaker=book),
        source=source)


def test_prices_agree() -> None:
    assert v.prices_agree(2.00, 2.02, 5.0) is True
    assert v.prices_agree(2.00, 2.50, 5.0) is False       # 22% apart
    assert v.prices_agree(2.00, None, 5.0) is None
    assert v.prices_agree(None, 2.00, 5.0) is None


def test_verified_when_independent_source_agrees() -> None:
    primary = [_fx(1.80, 3.80, 4.20, "the-odds-api.com")]
    secondary = [_fx(1.82, 3.75, 4.10, "football-data.co.uk (fixtures)")]
    out, flags = v.cross_verify(primary, secondary, tol_pp=5.0)
    assert out[0].verification == v.VERIFIED, flags
    assert out[0].home.price == 1.80, "must not rewrite the primary price"


def test_conflict_when_prices_diverge() -> None:
    primary = [_fx(1.80, 3.80, 4.20, "the-odds-api.com")]
    secondary = [_fx(2.60, 3.20, 2.70, "football-data.co.uk (fixtures)")]
    out, _ = v.cross_verify(primary, secondary, tol_pp=5.0)
    assert out[0].verification == v.CONFLICT
    assert "differs" in out[0].price_note and "home" in out[0].price_note


def test_single_source_when_no_counterpart() -> None:
    primary = [_fx(1.80, 3.80, 4.20, "the-odds-api.com")]
    out, _ = v.cross_verify(primary, [], tol_pp=5.0)
    assert out[0].verification == v.SINGLE_SOURCE


def test_same_source_does_not_corroborate() -> None:
    primary = [_fx(1.80, 3.80, 4.20, "the-odds-api.com")]
    secondary = [_fx(1.80, 3.80, 4.20, "the-odds-api.com")]  # same source
    out, _ = v.cross_verify(primary, secondary, tol_pp=5.0)
    assert out[0].verification == v.SINGLE_SOURCE, "same source is not independent"


def test_margin_difference_is_not_a_conflict() -> None:
    # A soft book (7% margin) and a sharp one (2.5%) with the same view: raw
    # prices 5-8% apart, chances within a point once margins are removed.
    soft = _fx(1.85, 3.40, 4.30, "sportybet.com")
    sharp = _fx(1.97, 3.62, 4.62, "football-data.co.uk (fixtures)", book="pinnacle")
    assert v.prices_agree(1.85, 1.97, 5.0) is False   # the raw test would cry wolf
    out, _ = v.cross_verify([soft], [sharp], tol_pp=5.0)
    assert out[0].verification == v.VERIFIED, out[0].price_note


def _espn(home, away, prices, day="2026-10-04T14:00Z"):
    return EspnEvent(league="Eredivisie", home=home, away=away, kickoff_utc=day,
                     status="STATUS_SCHEDULED", url="https://www.espn.com/x",
                     prices=prices, provider="DraftKings")


def test_check_prices_live_wiring() -> None:
    sporty = [
        _fx(1.85, 3.40, 4.30, "sportybet.com", "Twente", "Utrecht"),            # FD agrees
        _fx(1.40, 4.60, 7.50, "sportybet.com", "Nijmegen", "For Sittard"),      # ESPN agrees
        _fx(1.60, 4.00, 5.50, "sportybet.com", "Heerenveen", "Zwolle"),         # ESPN differs
        _fx(2.10, 3.30, 3.40, "sportybet.com", "Groningen", "Telstar"),         # nobody quotes it
        _fx(2.10, 3.30, 3.40, "sportybet.com", "Ajax", "PSV", day="2026-10-11"),  # not the board's day
    ]
    fd = [_fx(1.90, 3.50, 4.40, "football-data.co.uk (fixtures)", "Twente", "Utrecht")]
    espn = {"2026-10-04": [
        _espn("NEC Nijmegen", "Fortuna Sittard", {"home": 1.42, "draw": 4.75, "away": 7.0}),
        _espn("SC Heerenveen", "PEC Zwolle", {"home": 2.50, "draw": 3.50, "away": 2.70}),
    ]}
    flags = v.check_prices("Eredivisie", sporty, {"2026-10-04"},
                           fetch_espn=lambda lg, d: espn.get(d, []),
                           fetch_fd=lambda lg: (fd, []), fetch_fd_extra=lambda lg: ([], []))
    got = [f.verification for f in sporty]
    assert got == [v.VERIFIED, v.VERIFIED, v.CONFLICT, v.SINGLE_SOURCE, ""], (got, flags)
    assert "bet365 via football-data" in sporty[0].price_note
    assert "DraftKings via ESPN" in sporty[1].price_note
    assert "home" in sporty[2].price_note and "differs" in sporty[2].price_note
    assert sporty[0].home.price == 1.85, "never rewrites a price"
    assert any("2 agree" in f and "1 differ" in f for f in flags), flags


def test_check_prices_sources_down_is_not_fatal() -> None:
    sporty = [_fx(1.85, 3.40, 4.30, "sportybet.com", "Twente", "Utrecht")]

    def boom(*_a):
        raise OSError("timed out")
    flags = v.check_prices("Eredivisie", sporty, {"2026-10-04"},
                           fetch_espn=boom, fetch_fd=boom, fetch_fd_extra=boom)
    assert sporty[0].verification == v.SINGLE_SOURCE
    assert any("football-data unavailable" in f for f in flags), flags
    assert any("ESPN unavailable" in f for f in flags), flags


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"{name}: OK")
    print("odds_verify_test: OK")
