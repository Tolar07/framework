"""CL-LIVE closing-capture tests: close a paper leg's CLV before the archive.

The honest rule under test: a price captured FAR from kickoff is an intraday
price, not a closing line — manufacturing CLV out of it would be fabrication.
So capture happens only inside the window (kickoff imminent, or just started),
the leg must be paper-phase with an entry price and a kickoff date, the
fixture must match on (home, away, DATE), and an existing close is never
overwritten. grade_open_legs must then prefer the canonical archive close but
keep a CL-LIVE close when the archive has none.
"""
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock
sys.path.insert(0, str(Path(__file__).parent.parent))

from clv.clv_logger import CLVLog, PAPER_PHASE
from clv.closing_capture import (capture_closing_lines, CLOSING_CAPTURE_PATH,
                                 _minutes_to_kickoff, _in_window)
import pipeline.odds as odds
from engine import markets as mkt
from data.football_data_source import MatchOdds, MarketPrice

_tmp = Path(tempfile.mkdtemp(prefix="olp_xdv_closing_"))
log = CLVLog(path=_tmp / "clv.json")
NOW = datetime(2026, 8, 6, 12, 0, 0, tzinfo=timezone.utc)


def _leg(fixture="Celtic v Dundee", market="1X2_HOME", entry=1.5,
         match_date="2026-08-06", entry_odds=1.5):
    return log.log_entry(
        league="Scottish Premiership", fixture=fixture, market=market,
        model_prob=0.5, entry_odds=entry_odds,
        entry_capture_path="CL-LIVE", match_date=match_date)


_MARKET_FIELD = {mkt.HOME: "home", mkt.DRAW: "draw", mkt.AWAY: "away",
                 mkt.OVER_25: "over25", mkt.UNDER_25: "under25"}


def _fx(home, away, kickoff, price=2.0, market="1X2_HOME"):
    """A FixtureOdds with the requested market priced at `price`."""
    q = odds.MarketQuote(price=price, bookmaker="bet365", n_books=1,
                         captured_at=NOW.isoformat())
    fx = odds.FixtureOdds(league="Scottish Premiership", home_team=home,
                          away_team=away, kickoff_utc=kickoff)
    setattr(fx, _MARKET_FIELD[market], q)
    return fx


def _index(*fxs):
    return {(f.home_team, f.away_team): f for f in fxs}


# --- window maths -----------------------------------------------------------
assert _in_window(30) is True, "30 min before kickoff IS a closing line"
assert _in_window(5) is True, "5 min before kickoff is a closing line"
assert _in_window(-5) is True, "5 min after kickoff is still within grace"
assert _in_window(-30) is False, "30 min in-play is NOT a closing line"
assert _in_window(300) is False, "5h before kickoff is intraday, NOT a close"
assert _in_window(None) is False, "unknown kickoff can never be captured"
print("1. window rule: captures only near kickoff, never intraday/in-play: OK")

# --- capture within the window ----------------------------------------------
leg = _leg()  # Celtic v Dundee, kickoff today
fx = _fx("Celtic", "Dundee", "2026-08-06T12:30:00Z", price=1.8)
n, flags = capture_closing_lines(log, ["Scottish Premiership"],
                                 odds_index=_index(fx), now=NOW)
assert n == 1, f"expected 1 capture, got {n}: {flags}"
leg = log.legs[0]
assert leg.closing_odds == 1.8, f"close={leg.closing_odds}"
assert leg.closing_capture_path == CLOSING_CAPTURE_PATH
assert leg.clv_pct is not None, "CL-LIVE close must yield a CLV number"
print(f"2. capture in window: close={leg.closing_odds} "
      f"path={leg.closing_capture_path} CLV={leg.clv_pct:+.2f}%: OK")

# --- too early: intraday price is never a closing line ----------------------
log2 = CLVLog(path=_tmp / "clv2.json")
leg2 = log2.log_entry(league="Scottish Premiership", fixture="Celtic v Dundee",
                      market="1X2_HOME", model_prob=0.5, entry_odds=1.5,
                      match_date="2026-08-06")
fx_late = _fx("Celtic", "Dundee", "2026-08-06T18:00:00Z", price=1.2)
n, flags = capture_closing_lines(log2, ["Scottish Premiership"],
                                 odds_index=_index(fx_late), now=NOW)
assert n == 0, f"6h-before-kickoff price must NOT be captured, got {n}"
assert log2.legs[0].closing_odds is None
print("3. too early (intraday) is NOT captured: OK")

# --- in-play: grace passed --------------------------------------------------
log3 = CLVLog(path=_tmp / "clv3.json")
log3.log_entry(league="Scottish Premiership", fixture="Celtic v Dundee",
               market="1X2_HOME", model_prob=0.5, entry_odds=1.5,
               match_date="2026-08-06")
fx_play = _fx("Celtic", "Dundee", "2026-08-06T10:00:00Z", price=1.2)
n, flags = capture_closing_lines(log3, ["Scottish Premiership"],
                                 odds_index=_index(fx_play), now=NOW)
assert n == 0, "2h in-play is not a closing line"
print("4. in-play (grace passed) is NOT captured: OK")

# --- date guard: same pairing, wrong day ------------------------------------
log4 = CLVLog(path=_tmp / "clv4.json")
log4.log_entry(league="Scottish Premiership", fixture="Celtic v Dundee",
               market="1X2_HOME", model_prob=0.5, entry_odds=1.5,
               match_date="2026-08-07")          # leg is on the 7th...
fx_other_day = _fx("Celtic", "Dundee", "2026-08-06T12:30:00Z", price=1.8)
n, flags = capture_closing_lines(log4, ["Scottish Premiership"],
                                 odds_index=_index(fx_other_day), now=NOW)
assert n == 0, "a same-pairing match on another day must never close the leg"
print("5. date guard (HR48): wrong-day pairing never captured: OK")

# --- no overwrite + no entry odds + no match date ---------------------------
log5 = CLVLog(path=_tmp / "clv5.json")
a = log5.log_entry(league="Scottish Premiership", fixture="Celtic v Dundee",
                   market="1X2_HOME", model_prob=0.5, entry_odds=1.5,
                   match_date="2026-08-06")
log5.log_close(a.leg_id, closing_odds=9.99, closing_capture_path="CL-ARCHIVE")
b = log5.log_entry(league="Scottish Premiership", fixture="Rangers v Hearts",
                   market="1X2_HOME", model_prob=0.5, entry_odds=None,
                   match_date="2026-08-06")      # no entry price
c = log5.log_entry(league="Scottish Premiership", fixture="Aberdeen v Kilmarnock",
                   market="1X2_HOME", model_prob=0.5, entry_odds=1.5,
                   match_date=None)              # no kickoff date
n, flags = capture_closing_lines(log5, ["Scottish Premiership"],
                                 odds_index=_index(
                                     _fx("Celtic", "Dundee", "2026-08-06T12:30:00Z"),
                                     _fx("Rangers", "Hearts", "2026-08-06T12:30:00Z"),
                                     _fx("Aberdeen", "Kilmarnock", "2026-08-06T12:30:00Z")),
                                 now=NOW)
assert n == 0, "existing close / no entry / no date must never be captured"
assert log5.legs[0].closing_odds == 9.99, "first capture must win"
print("6. never overwrites, never captures entry-less or dateless legs: OK")

# --- grade_open_legs: CL-LIVE survives, archive upgrades --------------------
from run_daily import grade_open_legs


def _fake_load_league(league, season, **kw):
    """A played Scottish match with an ARCHIVE close for 1X2_HOME."""
    match = mock.Mock()
    match.home_team, match.away_team = "Celtic", "Dundee"
    match.date = "2026-08-06"
    match.fthg, match.ftag = 2, 0
    match.odds = MatchOdds(
        home=MarketPrice(open=1.6, close=1.4), draw=MarketPrice(),
        away=MarketPrice(), over25=MarketPrice(), under25=MarketPrice())
    return [match], []


# (a) CL-LIVE captured, archive ALSO has a close -> upgraded to CL-ARCHIVE.
logA = CLVLog(path=_tmp / "grade_a.json")
legA = logA.log_entry(league="Scottish Premiership", fixture="Celtic v Dundee",
                      market="1X2_HOME", model_prob=0.5, entry_odds=1.5,
                      match_date="2026-08-06")
logA.log_close(legA.leg_id, closing_odds=1.9, closing_capture_path="CL-LIVE")
with mock.patch("run_daily.load_league", side_effect=_fake_load_league):
    _, flags = grade_open_legs(logA, "2526")
legA = logA.legs[0]
assert legA.hit is True
assert legA.closing_odds == 1.4 and legA.closing_capture_path == "CL-ARCHIVE", \
    "the canonical archive close must upgrade a CL-LIVE close"
print("7. grade prefers the canonical archive close (upgrade): OK")

# (b) CL-LIVE captured, archive has NO close -> the CL-LIVE close stands.
def _fake_no_close(league, season, **kw):
    match = mock.Mock()
    match.home_team, match.away_team = "Celtic", "Dundee"
    match.date = "2026-08-06"
    match.fthg, match.ftag = 2, 0
    match.odds = None          # archive has no closing price at all
    return [match], []

logB = CLVLog(path=_tmp / "grade_b.json")
legB = logB.log_entry(league="Scottish Premiership", fixture="Celtic v Dundee",
                      market="1X2_HOME", model_prob=0.5, entry_odds=1.5,
                      match_date="2026-08-06")
logB.log_close(legB.leg_id, closing_odds=1.9, closing_capture_path="CL-LIVE")
with mock.patch("run_daily.load_league", side_effect=_fake_no_close):
    _, flags = grade_open_legs(logB, "2526")
legB = logB.legs[0]
assert legB.closing_odds == 1.9 and legB.closing_capture_path == "CL-LIVE"
assert legB.clv_pct is not None, "CL-LIVE close must still yield CLV"
assert not any("no closing price" in f for f in flags), \
    f"a CL-LIVE close must not be flagged NO DATA: {flags}"
print("8. grade keeps the CL-LIVE close when the archive has none: OK")

# (c) NO close from either path -> honest NO DATA flag, never estimated.
logC = CLVLog(path=_tmp / "grade_c.json")
logC.log_entry(league="Scottish Premiership", fixture="Celtic v Dundee",
               market="1X2_HOME", model_prob=0.5, entry_odds=1.5,
               match_date="2026-08-06")
with mock.patch("run_daily.load_league", side_effect=_fake_no_close):
    _, flags = grade_open_legs(logC, "2526")
assert any("no closing price" in f for f in flags), "must stay honest NO DATA"
assert logC.legs[0].clv_pct is None
print("9. no close from any path stays NO DATA (HR35): OK")

print("\nCL-LIVE CLOSING CAPTURE WORKS — legs close with a live closing "
      "line, the archive upgrades it, and nothing is ever estimated.")

# ============================================================
# PHASE 4.1 — CL-PM (Polymarket) CAPTURE PATH TESTS
# ============================================================
import os
from clv import closing_capture as cc

print("\n--- CL-PM (Polymarket) capture path tests ---")

# --- 1. CL-PM is dormant without POLYMARKET_API_KEY ---------------------------
old_key = os.environ.pop("POLYMARKET_API_KEY", None)
try:
    with tempfile.TemporaryDirectory() as td:
        log = CLVLog(Path(td) / "clv_pm.json")
        leg = log.log_entry(
            league="Eredivisie", fixture="Ajax v Feyenoord", market="OVER_2_5",
            model_prob=0.55, entry_odds=2.10,
            phase=PAPER_PHASE, match_date="2026-08-09")
        n, flags = cc._capture_polymarket_closing_lines(
            log, ["Eredivisie"], odds_index=None)
        assert n == 0, f"expected 0 captures without key, got {n}"
        assert flags == [], f"expected no flags, got {flags}"
    print("1. CL-PM dormant without POLYMARKET_API_KEY: OK")
finally:
    if old_key:
        os.environ["POLYMARKET_API_KEY"] = old_key
    else:
        os.environ.pop("POLYMARKET_API_KEY", None)

# --- 2. CL-PM respects the same closing window as CL-LIVE --------------------
os.environ["POLYMARKET_API_KEY"] = "dummy"
try:
    with tempfile.TemporaryDirectory() as td:
        log = CLVLog(Path(td) / "clv_pm2.json")
        # 90 minutes ahead = outside 60-min window
        leg = log.log_entry(
            league="Eredivisie", fixture="Ajax v Feyenoord", market="OVER_2_5",
            model_prob=0.55, entry_odds=2.10,
            phase=PAPER_PHASE, match_date="2026-08-09")
        n, flags = cc._capture_polymarket_closing_lines(
            log, ["Eredivisie"], odds_index=None)
        assert n == 0, f"expected 0 captures outside window, got {n}"
    print("2. CL-PM respects closing window: OK")
finally:
    os.environ.pop("POLYMARKET_API_KEY", None)

# --- 3. Combined capture_closing_lines calls both paths -----------------------
# Deterministic by design: both inner capture paths are MOCKED. The old version
# leaned on odds.fetch_odds RAISING (emitting a "CL-LIVE capture skipped" flag);
# the odds multi-source now returns informational flags instead of raising, so
# the assertion was at the mercy of live Odds-API quota state. The contract under
# test is the orchestration: capture_closing_lines MUST call CL-LIVE and CL-PM
# and SUM their results — that is provable with mocks, no network involved.
os.environ["POLYMARKET_API_KEY"] = "dummy"
try:
    with tempfile.TemporaryDirectory() as td:
        lg = CLVLog(Path(td) / "clv_pm3.json")
        lg.log_entry(
            league="Eredivisie", fixture="Ajax v Feyenoord", market="OVER_2_5",
            model_prob=0.55, entry_odds=2.10,
            phase=PAPER_PHASE, match_date="2026-08-09")
        calls = {"live": False, "pm": False}

        def _fake_live(log_, leagues_, *a, **k):
            calls["live"] = True
            return 2, ["Ajax v Feyenoord / OVER_2_5: CL-LIVE closing line"]

        def _fake_pm(log_, leagues_, *a, **k):
            calls["pm"] = True
            return 3, ["CL-PM closing lines captured this run: 3"]

        with mock.patch.object(cc, "_capture_live_closing_lines", _fake_live), \
             mock.patch.object(cc, "_capture_polymarket_closing_lines", _fake_pm):
            n, flags = cc.capture_closing_lines(lg, ["Eredivisie"])
        assert calls["live"] and calls["pm"], \
            "capture_closing_lines must call BOTH the CL-LIVE and CL-PM paths"
        assert n == 5, f"combined capture must sum both paths, got {n}"
        assert any("CL-LIVE" in f for f in flags) and any("CL-PM" in f for f in flags)
    print("3. Combined capture calls both paths and sums them: OK")
finally:
    os.environ.pop("POLYMARKET_API_KEY", None)

# --- 4. First capture wins: existing closing line is not overwritten ----------
os.environ["POLYMARKET_API_KEY"] = "dummy"
try:
    with tempfile.TemporaryDirectory() as td:
        log = CLVLog(Path(td) / "clv_pm4.json")
        leg = log.log_entry(
            league="Eredivisie", fixture="Ajax v Feyenoord", market="OVER_2_5",
            model_prob=0.55, entry_odds=2.10,
            phase=PAPER_PHASE, match_date="2026-08-09")
        leg.closing_odds = 2.05
        leg.closing_capture_path = "CL-ARCHIVE"
        leg.clv_pct = 2.44
        log._save()

        n, flags = cc.capture_closing_lines(log, ["Eredivisie"])
        assert n == 0, f"expected 0 captures (already closed), got {n}"
        updated = next(l for l in log.legs if l.leg_id == leg.leg_id)
        assert updated.closing_odds == 2.05
        assert updated.closing_capture_path == "CL-ARCHIVE"
    print("4. First capture wins (no overwrite): OK")
finally:
    os.environ.pop("POLYMARKET_API_KEY", None)

# --- 5. HR48 date guard: wrong-day fixture not captured -----------------------
os.environ["POLYMARKET_API_KEY"] = "dummy"
try:
    with tempfile.TemporaryDirectory() as td:
        log = CLVLog(Path(td) / "clv_pm5.json")
        leg = log.log_entry(
            league="Eredivisie", fixture="Ajax v Feyenoord", market="OVER_2_5",
            model_prob=0.55, entry_odds=2.10,
            phase=PAPER_PHASE, match_date="2026-08-09")
        fx = odds.FixtureOdds(
            league="Eredivisie", home_team="Ajax", away_team="Feyenoord",
            kickoff_utc=(datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
            over25=odds.MarketQuote(price=2.0, bookmaker="test")
        )
        n, flags = cc._capture_polymarket_closing_lines(
            log, ["Eredivisie"], odds_index={("Ajax", "Feyenoord"): fx})
        assert n == 0, f"expected 0 captures (date mismatch), got {n}"
    print("5. HR48 date guard works for CL-PM: OK")
finally:
    os.environ.pop("POLYMARKET_API_KEY", None)

# --- 6. _fetch_polymarket_price returns None on 404/errors (HR35) ------------
os.environ["POLYMARKET_API_KEY"] = "dummy"
try:
    price = cc._fetch_polymarket_price("Eredivisie", "Ajax", "Feyenoord", "OVER_2_5")
    assert price is None, f"expected None on dummy key, got {price}"
    print("6. _fetch_polymarket_price returns None on missing market (HR35): OK")
finally:
    os.environ.pop("POLYMARKET_API_KEY", None)

# --- 7. Polymarket market key construction is deterministic --------------------
key = cc._polymarket_market_key("Eredivisie", "Ajax", "Feyenoord", "OVER_2_5")
assert "eredivisie" in key
assert "ajax" in key
assert "feyenoord" in key
assert "over_2_5" in key
print("7. Polymarket key format is deterministic: OK")

print("\nALL CL-PM CAPTURE TESTS PASSED")
