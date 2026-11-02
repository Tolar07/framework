"""Publish-time edge freeze: entry_fair_odds / entry_edge_pct captured at
log_entry and never rewritten, closing_edge_pct graded against the frozen
model_prob, and the decay surfaced in phase2_status."""
from clv.clv_logger import (
    PHASE3_GATE_MIN_LEGS,
    CLVLog,
    fair_odds,
    value_edge_pct,
)


def test_fair_odds_and_edge_helpers():
    assert fair_odds(0.5) == 2.0
    assert fair_odds(0) is None          # non-positive prob -> nothing to freeze
    assert fair_odds(-0.1) is None
    # model 0.5 (fair 2.0), price 2.2 -> +10% value
    assert value_edge_pct(0.5, 2.2) == 10.0
    assert value_edge_pct(0.5, 1.8) == -10.0   # price shorter than fair
    assert value_edge_pct(0, 2.0) is None
    assert value_edge_pct(0.5, None) is None


def test_entry_freezes_fair_odds_and_edge(tmp_path):
    log = CLVLog(tmp_path / "clv.json")
    leg = log.log_entry("EPL", "A v B", "O2.5", model_prob=0.5, entry_odds=2.2)
    assert leg.entry_fair_odds == 2.0
    assert leg.entry_edge_pct == 10.0


def test_entry_without_price_keeps_fair_odds_but_no_edge(tmp_path):
    # HR46: no backfilled price guess, so edge stays None; fair price still frozen.
    log = CLVLog(tmp_path / "clv.json")
    leg = log.log_entry("EPL", "A v B", "O2.5", model_prob=0.4, entry_odds=None)
    assert leg.entry_fair_odds == 2.5
    assert leg.entry_edge_pct is None


def test_close_grades_edge_against_frozen_prob(tmp_path):
    log = CLVLog(tmp_path / "clv.json")
    leg = log.log_entry("EPL", "A v B", "O2.5", model_prob=0.5, entry_odds=2.2)
    log.log_close(leg.leg_id, closing_odds=2.0)
    reloaded = CLVLog(tmp_path / "clv.json").legs[0]
    # frozen claim untouched by the close
    assert reloaded.entry_edge_pct == 10.0
    assert reloaded.entry_fair_odds == 2.0
    # edge measured at the close: 0.5*2.0-1 = 0 -> the market erased the 10%
    assert reloaded.closing_edge_pct == 0.0
    assert reloaded.clv_pct == 10.0   # price CLV: 2.2 into a 2.0 close


def test_status_reports_entry_edge_and_decay(tmp_path):
    log = CLVLog(tmp_path / "clv.json")
    for _ in range(PHASE3_GATE_MIN_LEGS):
        leg = log.log_entry("EPL", "A v B", "O2.5", model_prob=0.5, entry_odds=2.2)
        log.log_close(leg.leg_id, closing_odds=2.0)
    s = log.phase2_status()
    assert s["mean_entry_edge_pct"] == 10.0
    assert s["mean_edge_decay_pct"] == 10.0   # 10% claimed -> 0% at close
    assert s["mean_clv_pct"] == 10.0


def test_old_legs_without_fields_load(tmp_path):
    # A ledger written before these fields must still load (defaults -> None).
    p = tmp_path / "clv.json"
    p.write_text('[{"leg_id":"x","date_logged":"2026-01-01T00:00:00+00:00",'
                 '"league":"EPL","fixture":"A v B","market":"O2.5","model_prob":0.5}]')
    leg = CLVLog(p).legs[0]
    assert leg.entry_fair_odds is None and leg.entry_edge_pct is None
    assert leg.closing_edge_pct is None
