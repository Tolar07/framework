"""
Second-source fixture check (verification/fixture_check.py), the cross-feed
matcher (engine/fixture_match.py) and the ESPN reader (data/espn_fixtures.py).

Guards:
  1. TheSportsDB + ESPN (or football-data) agreeing on a match -> ✓ VERIFIED,
     whatever each feed calls the clubs.
  2. ESPN listing the match POSTPONED (strong name match) -> ⚠ CONFLICT, off
     the deploy list with the reason; a WEAK match never raises a conflict.
  3. A source that can't find the match, doesn't cover the league, or is down
     adds nothing: the fixture keeps its stamp and the run carries on.
  4. An odds-feed fixture (sportybet.com, not T1/T2) + one T2 source stays
     SINGLE-SOURCE — two T1/T2 sources are needed (ID404).
  5. The matcher never pairs different clubs (Man City / Man United, a derby
     listed the other way round, an ambiguous candidate set).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data import espn_fixtures as espn
from data.espn_fixtures import EspnEvent
from engine.fixture_match import STRONG, WEAK, find_match, team_score
from output.produce_bet import BoardFixture
from pipeline.odds import FixtureOdds
from verification import fixture_check as fc
from verification.id403 import SourcedDatum, Tier, verify


def _bf(home, away, league="La Liga 2", day="2026-10-04", base="thesportsdb.com"):
    v = verify([SourcedDatum(domain=base, value=f"{home} v {away}",
                             url=f"https://www.{base}")])
    return BoardFixture(fixture=f"{home} v {away} ({league})", probs=None,
                        verification=v, on_deploy_shortlist=True, kickoff_date=day)


def _ev(home, away, status="STATUS_SCHEDULED", when="2026-10-04T12:00Z", league="La Liga 2"):
    return EspnEvent(league=league, home=home, away=away, kickoff_utc=when,
                     status=status, url="https://www.espn.com/soccer/match/_/gameId/1")


def _fd(home, away, day="2026-10-04", league="La Liga 2"):
    return FixtureOdds(league=league, home_team=home, away_team=away, kickoff_utc=day,
                       source="football-data.co.uk (fixtures)")


def _run(board, espn_events=(), fd_rows=(), espn_error=None):
    def fetch_espn(league, day):
        if espn_error:
            raise espn_error
        return [e for e in espn_events if e.kickoff_utc[:10] == day]
    return fc.check_board(board, fetch_espn=fetch_espn,
                          fetch_fd=lambda lg: (list(fd_rows), []),
                          fetch_fd_extra=lambda lg: ([], []))


def test_espn_agreement_verifies_despite_spelling() -> None:
    board = [_bf("Sociedad B", "Granada"), _bf("Castellon", "Ceuta")]
    flags = _run(board, [_ev("Real Sociedad II", "Granada"), _ev("Castellón", "Ceuta")])
    assert [b.verification.tier for b in board] == [Tier.VERIFIED, Tier.VERIFIED], flags
    assert "espn.com" in board[0].verification.factors["verifying_domains"]
    assert all(b.on_deploy_shortlist for b in board)
    assert any("2/2 confirmed" in f for f in flags), flags


def test_football_data_alone_verifies() -> None:
    board = [_bf("Las Palmas", "Valladolid")]
    _run(board, fd_rows=[_fd("Las Palmas", "Valladolid")])
    assert board[0].verification.tier == Tier.VERIFIED


def test_postponed_is_conflict_and_not_deployed() -> None:
    board = [_bf("Girona", "Mallorca")]
    flags = _run(board, [_ev("Girona", "Mallorca", status="STATUS_POSTPONED")])
    b = board[0]
    assert b.verification.tier == Tier.CONFLICT
    assert not b.on_deploy_shortlist
    assert "POSTPONED" in b.rejection_reason and "Not deployed" in b.rejection_reason
    assert any("1 conflict" in f and "POSTPONED" in f for f in flags), flags


def test_weak_match_never_conflicts() -> None:
    board = [_bf("Karlsruhe", "Elversberg", league="2. Bundesliga")]
    _run(board, [_ev("Karlsruher SC", "SV Elversberg", status="STATUS_POSTPONED",
                     league="2. Bundesliga")])
    assert board[0].verification.tier == Tier.SINGLE_SOURCE
    assert board[0].on_deploy_shortlist


def test_no_match_or_source_down_adds_nothing() -> None:
    board = [_bf("Albacete", "Cadiz")]
    flags = _run(board, [_ev("Huesca", "Eibar")])
    assert board[0].verification.tier == Tier.SINGLE_SOURCE and board[0].on_deploy_shortlist
    board = [_bf("Albacete", "Cadiz")]
    flags = _run(board, espn_error=OSError("timed out"))
    assert board[0].verification.tier == Tier.SINGLE_SOURCE
    assert any("ESPN unavailable" in f for f in flags), flags


def test_league_espn_does_not_cover_is_quiet() -> None:
    board = [_bf("Legia", "Lech", league="Ekstraklasa")]
    flags = _run(board, espn_error=ValueError("ESPN has no slug"))
    assert board[0].verification.tier == Tier.SINGLE_SOURCE
    assert not any("ESPN unavailable" in f for f in flags)


def test_odds_feed_base_needs_two_trusted_sources() -> None:
    board = [_bf("Wigan", "Bolton", league="League One", base="sportybet.com")]
    _run(board, [_ev("Wigan Athletic", "Bolton Wanderers", league="League One")])
    assert board[0].verification.tier == Tier.SINGLE_SOURCE
    board = [_bf("Wigan", "Bolton", league="League One", base="sportybet.com")]
    _run(board, [_ev("Wigan Athletic", "Bolton Wanderers", league="League One")],
         fd_rows=[_fd("Wigan", "Bolton", league="League One")])
    assert board[0].verification.tier == Tier.VERIFIED


def test_no_data_and_undated_fixtures_untouched() -> None:
    nd = BoardFixture(fixture="A v B (La Liga 2)", probs=None,
                      verification=verify([]), kickoff_date="2026-10-04")
    undated = _bf("Castellon", "Ceuta", day=None)
    _run([nd, undated], [_ev("Castellón", "Ceuta")])
    assert nd.verification.tier == Tier.NO_DATA
    assert undated.verification.tier == Tier.SINGLE_SOURCE


def test_split_fixture() -> None:
    assert fc.split_fixture("Sp Gijon v Celta B (La Liga 2)") == ("Sp Gijon", "Celta B", "La Liga 2")
    assert fc.split_fixture("Dundee v Hearts (Scottish Premiership)")[2] == "Scottish Premiership"
    assert fc.split_fixture("no league here") is None


def test_team_score_and_find_match() -> None:
    assert team_score("Nott'm Forest", "Nottingham Forest") == 1.0
    assert team_score("Sociedad B", "Real Sociedad II") == STRONG
    assert team_score("Karlsruhe", "Karlsruher SC") == WEAK
    assert team_score("Man City", "Manchester United") == 0.0
    assert team_score("Bristol City", "Bristol Rovers") == 0.0
    pairs = [("Dundee United", "Dundee"), ("Celtic", "Rangers")]
    assert find_match("Dundee", "Dundee United", pairs, lambda p: p) is None   # derby reversed
    assert find_match("Celtic", "Rangers", pairs, lambda p: p).strong
    twins = [("Celtic", "Rangers"), ("Celtic", "Rangers")]
    assert find_match("Celtic", "Rangers", twins, lambda p: p) is None        # ambiguous


def test_espn_reader() -> None:
    assert espn.american_to_decimal("+160") == 2.6
    assert espn.american_to_decimal("-120") == 1.8333
    assert espn.american_to_decimal(230) == 3.3
    assert espn.american_to_decimal("EVEN") == 2.0
    assert espn.american_to_decimal("") is None and espn.american_to_decimal("+50") is None
    payload = {"events": [
        {"date": "2026-10-04T12:00Z", "status": {"type": {"name": "STATUS_SCHEDULED"}},
         "links": [{"href": "https://www.espn.com/soccer/match/_/gameId/9"}],
         "competitions": [{"competitors": [
             {"homeAway": "home", "team": {"displayName": "Real Sociedad II"}},
             {"homeAway": "away", "team": {"displayName": "Granada"}}],
             "odds": [{"provider": {"name": "DraftKings"}, "overUnder": 2.5,
                       "moneyline": {"home": {"close": {"odds": "+160"}},
                                     "away": {"close": {"odds": "+175"}}},
                       "drawOdds": {"moneyLine": 230},
                       "total": {"over": {"close": {"odds": "-110"}},
                                 "under": {"close": {"odds": "-120"}}}}]}]},
        {"date": "", "competitions": [{"competitors": []}]},   # HR35: dropped
    ]}
    evs = espn.parse_events("La Liga 2", payload)
    assert len(evs) == 1
    e = evs[0]
    assert (e.home, e.away, e.day, e.off) == ("Real Sociedad II", "Granada", "2026-10-04", None)
    assert e.prices == {"home": 2.6, "draw": 3.3, "away": 2.75, "over25": 1.9091,
                        "under25": 1.8333}, e.prices
    assert _ev("A", "B", status="STATUS_POSTPONED").off == "POSTPONED"
    try:
        espn.fetch_day("Ekstraklasa", "2026-10-04")
        raise AssertionError("an unmapped league must raise, not return []")
    except ValueError:
        pass


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"{name}: OK")
    print("fixture_check_test: OK")
