"""Phase 4.2 — Automated CLV grading tests.

The logger's grade_all_pending() method is the canonical automated path
shared with the CLI; run_daily.grade_open_legs is the run-specific richer
renderer. Both must grade honestly against the settled record.
"""
import sys
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent))

from clv.clv_logger import CLVLog, PAPER_PHASE
from data.football_data_source import MatchOdds, MarketPrice, MatchResult
import data.football_data_source as fds


def _leg(log: CLVLog, league: str, fixture: str, market: str,
         entry_odds: float, match_date: str) -> str:
    leg = log.log_entry(
        league=league, fixture=fixture, market=market,
        model_prob=0.55, entry_odds=entry_odds,
        phase=PAPER_PHASE, match_date=match_date
    )
    return leg.leg_id


def _fake_results(league: str, season: str):
    """Mock football-data results for a played match."""
    match = mock.Mock()
    match.home_team, match.away_team = "Ajax", "Feyenoord"
    match.date = "2026-08-09"
    match.fthg, match.ftag = 2, 1  # Over 2.5 = HIT
    match.odds = MatchOdds(
        home=MarketPrice(open=1.6, close=1.5), draw=MarketPrice(open=4.0, close=4.2),
        away=MarketPrice(open=5.0, close=5.5), over25=MarketPrice(open=1.9, close=1.85),
        under25=MarketPrice(open=2.0, close=2.1))
    return [match], []


def test_grade_all_pending_basic():
    """A pending leg with an entry price gets graded and a closing price."""
    with tempfile.TemporaryDirectory() as td:
        log = CLVLog(Path(td) / "clv_grade.json")
        leg_id = _leg(log, "Eredivisie", "Ajax v Feyenoord", "OVER_2_5", 1.90, "2026-08-09")

        with mock.patch("data.football_data_source.load_league", side_effect=_fake_results):
            summary, flags = log.grade_all_pending("2526")

        assert summary["graded"] == 1, f"expected 1 graded, got {summary}"
        leg = next(l for l in log.legs if l.leg_id == leg_id)
        assert leg.hit is True
        assert leg.ft_result == "2-1"
        assert leg.closing_odds == 1.85  # archive close
        assert leg.closing_capture_path == "CL-ARCHIVE"
        assert leg.clv_pct is not None
        print("1. grade_all_pending grades a pending leg with archive close: OK")


def test_grade_all_pending_preserves_cl_live():
    """If a leg already has a CL-LIVE close, the archive UPGRADES it."""
    with tempfile.TemporaryDirectory() as td:
        log = CLVLog(Path(td) / "clv_grade2.json")
        leg_id = _leg(log, "Eredivisie", "Ajax v Feyenoord", "OVER_2_5", 1.90, "2026-08-09")
        # Pre-set a CL-LIVE close (captured near kickoff)
        log.log_close(leg_id, closing_odds=1.95, closing_capture_path="CL-LIVE")

        with mock.patch("data.football_data_source.load_league", side_effect=_fake_results):
            summary, flags = log.grade_all_pending("2526")

        leg = next(l for l in log.legs if l.leg_id == leg_id)
        assert leg.closing_odds == 1.85  # upgraded to archive
        assert leg.closing_capture_path == "CL-ARCHIVE"
        print("2. grade_all_pending upgrades CL-LIVE to CL-ARCHIVE: OK")


def test_grade_all_pending_keeps_cl_live_when_archive_missing():
    """If the archive has NO price, the CL-LIVE close stands."""
    def _fake_no_archive(league: str, season: str):
        match = mock.Mock()
        match.home_team, match.away_team = "Ajax", "Feyenoord"
        match.date = "2026-08-09"
        match.fthg, match.ftag = 2, 1
        match.odds = None  # archive has NO close
        return [match], []

    with tempfile.TemporaryDirectory() as td:
        log = CLVLog(Path(td) / "clv_grade3.json")
        leg_id = _leg(log, "Eredivisie", "Ajax v Feyenoord", "OVER_2_5", 1.90, "2026-08-09")
        log.log_close(leg_id, closing_odds=1.95, closing_capture_path="CL-LIVE")

        with mock.patch("data.football_data_source.load_league", side_effect=_fake_no_archive):
            summary, flags = log.grade_all_pending("2526")

        leg = next(l for l in log.legs if l.leg_id == leg_id)
        assert leg.closing_odds == 1.95
        assert leg.closing_capture_path == "CL-LIVE"
        assert leg.clv_pct is not None
        # A CL-LIVE close is a real closing line — it must NOT be flagged
        # NO DATA, exactly like closing_capture_test.py test 8. Only a leg
        # with no closing line from ANY path is NO DATA — PENDING (HR35).
        assert not any("no closing price" in f for f in flags), \
            f"a CL-LIVE close must not be flagged NO DATA: {flags}"
        print("3. grade_all_pending keeps CL-LIVE when archive missing: OK")


def test_grade_all_pending_honest_no_data_when_no_close():
    """If neither archive nor live close exists, leg stays NO DATA — PENDING."""
    def _fake_no_archive(league: str, season: str):
        match = mock.Mock()
        match.home_team, match.away_team = "Ajax", "Feyenoord"
        match.date = "2026-08-09"
        match.fthg, match.ftag = 2, 1
        match.odds = None
        return [match], []

    with tempfile.TemporaryDirectory() as td:
        log = CLVLog(Path(td) / "clv_grade4.json")
        leg_id = _leg(log, "Eredivisie", "Ajax v Feyenoord", "OVER_2_5", 1.90, "2026-08-09")
        # No CL-LIVE close, no archive close

        with mock.patch("data.football_data_source.load_league", side_effect=_fake_no_archive):
            summary, flags = log.grade_all_pending("2526")

        leg = next(l for l in log.legs if l.leg_id == leg_id)
        assert leg.hit is True
        assert leg.closing_odds is None
        assert leg.clv_pct is None
        assert any("no closing price" in f for f in flags)
        print("4. grade_all_pending stays honest NO DATA when no close: OK")


def test_grade_all_pending_skips_unplayed():
    """Legs whose match hasn't been played yet stay pending."""
    def _fake_future(league: str, season: str):
        # A match that hasn't been played yet is ABSENT from the results
        # source (football-data.co.uk only publishes played matches) — so
        # load_league returns nothing, not a 0-0 result. Returning a "played"
        # future fixture would let grade_all_pending settle it, which is
        # exactly the defect this test guards against (ID48).
        return [], []

    with tempfile.TemporaryDirectory() as td:
        log = CLVLog(Path(td) / "clv_grade5.json")
        leg_id = _leg(log, "Eredivisie", "Ajax v Feyenoord", "OVER_2_5", 1.90, "2026-08-20")

        with mock.patch("data.football_data_source.load_league", side_effect=_fake_future):
            summary, flags = log.grade_all_pending("2526")

        leg = next(l for l in log.legs if l.leg_id == leg_id)
        assert leg.hit is None
        assert leg.closing_odds is None
        assert summary["graded"] == 0
        print("5. grade_all_pending skips unplayed matches: OK")


def test_grade_all_pending_refuses_no_match_date():
    """A leg logged without a kickoff date cannot be graded (HR35/HR48)."""
    with tempfile.TemporaryDirectory() as td:
        log = CLVLog(Path(td) / "clv_grade6.json")
        leg = log.log_entry(
            league="Eredivisie", fixture="Ajax v Feyenoord", market="OVER_2_5",
            model_prob=0.55, entry_odds=1.90,
            phase=PAPER_PHASE, match_date=None  # no kickoff date
        )

        with mock.patch("data.football_data_source.load_league", side_effect=_fake_results):
            summary, flags = log.grade_all_pending("2526")

        assert summary["graded"] == 0
        assert any("no kickoff date" in f for f in flags)
        print("6. grade_all_pending refuses legs without kickoff date: OK")


def test_cli_grade_invocation():
    """The CLI entry point (--grade) calls grade_all_pending."""
    import clv.clv_logger as cl
    with tempfile.TemporaryDirectory() as td:
        # Explicit temp path — DEFAULT_LOG_PATH is a default-arg bound at class
        # definition, so reassigning the module constant would not redirect
        # CLVLog() and the test would touch the real clv_log.json.
        log = cl.CLVLog(Path(td) / "cli_test.json")
        _leg(log, "Eredivisie", "Ajax v Feyenoord", "OVER_2_5", 1.90, "2026-08-09")

        with mock.patch("data.football_data_source.load_league", side_effect=_fake_results):
            # Simulate CLI call
            summary, flags = log.grade_all_pending("2526")
        assert summary["graded"] == 1
    print("7. CLI grade invocation works: OK")


if __name__ == "__main__":
    test_grade_all_pending_basic()
    test_grade_all_pending_preserves_cl_live()
    test_grade_all_pending_keeps_cl_live_when_archive_missing()
    test_grade_all_pending_honest_no_data_when_no_close()
    test_grade_all_pending_skips_unplayed()
    test_grade_all_pending_refuses_no_match_date()
    test_cli_grade_invocation()
    print("\n✅ ALL AUTOMATED CLV GRADING TESTS PASSED")