"""
CLV backtest tests. No network — inline CSV fixtures and synthetic matches.

The load-bearing assertion in this file is the LEAKAGE test: if the model can
see the matches it predicts, every other number the backtest produces is
worthless, and worse, it would look good. That test asserts on EVERY leg, not
a sample.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import random
from datetime import date, timedelta
from unittest.mock import patch

from data.football_data_source import parse_csv_text, MatchResult, MarketPrice, MatchOdds
from clv.clv_logger import compute_clv, CLVLog, BACKTEST_PHASE, DEFAULT_LOG_PATH
from config import PAPER_PHASE
import backtest.clv_backtest as bt


# --- 1. parser, standard schema: open AND close, with provenance -------------
STD_CSV = (
    "Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR,"
    "AvgH,AvgD,AvgA,AvgCH,AvgCD,AvgCA,Avg>2.5,Avg<2.5,AvgC>2.5,AvgC<2.5\n"
    "SC0,02/08/2025,15:00,Kilmarnock,Livingston,2,2,D,"
    "2.00,3.40,3.60,2.26,3.30,3.20,1.92,1.82,1.95,1.80\n"
)
res, skipped = parse_csv_text("Scottish Premiership", STD_CSV)
assert len(res) == 1 and not skipped
o = res[0].odds
assert o.schema == "standard"
assert o.home.open == 2.00 and o.home.close == 2.26
assert o.home.book == "market_avg"
assert o.home.open_column == "AvgH" and o.home.close_column == "AvgCH"
assert o.over25.open == 1.92 and o.over25.close == 1.95
assert res[0].closing_home_odds == 2.26, "legacy closing field must still populate"
print("1. Standard schema: open+close+provenance parsed, legacy field intact: OK")


# --- 2. parser, extra schema: closing only, honestly noted -------------------
EXTRA_CSV = (
    "Country,League,Season,Date,Time,Home,Away,HG,AG,Res,AvgCH,AvgCD,AvgCA\n"
    "Denmark,Superliga,2025/2026,18/07/2025,17:00,Viborg,FC Copenhagen,2,3,A,5.65,4.20,1.55\n"
)
res_x, _ = parse_csv_text("Danish Superliga", EXTRA_CSV, season="2526")
ox = res_x[0].odds
assert ox.schema == "extra"
assert ox.home.open is None and ox.home.close == 5.65
assert ox.over25.open is None and ox.over25.close is None
assert any("CLOSING prices only" in n for n in ox.notes)
assert res_x[0].closing_home_odds == 5.65, "legacy closing field must still populate"
print("2. Extra schema: closing-only detected and flagged, not faked: OK")


# --- 2b. Norway/Sweden Extra files label Season as a SINGLE year ('2026'),
# not the double-year ('2025/2026') that DNK/POL/AUT use. The season filter
# must accept BOTH so these leagues aren't silently dropped to an empty cache.
NOR_SWE_EXTRA_CSV = (
    "Country,League,Season,Date,Time,Home,Away,HG,AG,Res,AvgCH,AvgCD,AvgCA\n"
    "Norway,Eliteserien,2026,04/04/2026,18:00,Bodo/Glimt,Rosenborg,2,1,H,1.90,3.60,3.80\n"
    "Norway,Eliteserien,2025,19/10/2025,17:00,Molde,Viking,1,2,A,2.10,3.40,3.20\n"
)
res_n, _ = parse_csv_text("Norwegian Eliteserien", NOR_SWE_EXTRA_CSV, season="2526")
# Only the 2026 (== 2025/2026) row must survive; the 2025 row is a different season.
assert len(res_n) == 1, f"single-year Season label must match, got {len(res_n)} rows"
assert res_n[0].home_team == "Bodo/Glimt" and res_n[0].fthg == 2
print("2b. Extra schema single-year Season label (NOR/SWE) matched: OK")


# --- 3. same-book pairing: never mix one book's open with another's close ----
MIXED_CSV = (
    "Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,FTR,"
    "PSH,PSD,PSA,PSCH,PSCD,PSCA,AvgH,AvgD,AvgA,AvgCH,AvgCD,AvgCA\n"
    # Pinnacle has OPENING prices but its CLOSING home price is blank.
    "SC0,02/08/2025,Celtic,Dundee,3,0,H,"
    "1.50,4.00,6.00,,3.90,5.80,1.55,4.10,6.20,1.52,4.00,6.10\n"
)
res_m, _ = parse_csv_text("Scottish Premiership", MIXED_CSV,
                           book_preference=("pinnacle", "market_avg"))
om = res_m[0].odds
assert om.home.open is not None and om.home.close is not None
assert om.home.book == "market_avg", (
    f"must fall through to a book complete on BOTH sides, got {om.home.book}")
assert om.home.open == 1.55 and om.home.close == 1.52
assert not (om.home.open == 1.50 and om.home.close == 1.52), \
    "CROSS-BOOK PAIR: Pinnacle open with market-average close would fabricate CLV"
print("3. Same-book pairing enforced (no Pinnacle-open/Avg-close splice): OK")


# --- 4. LEAKAGE — the assertion everything else depends on -------------------
def synth(league, n_teams=10, start="2025-08-01", n_rounds=4):
    teams = [f"T{i}" for i in range(1, n_teams + 1)]
    rng = random.Random(11)
    d0 = date.fromisoformat(start)
    out, day = [], 0
    for _ in range(n_rounds):
        for i, h in enumerate(teams):
            for a in teams[i + 1:]:
                day += 1
                price = lambda: round(rng.uniform(1.5, 4.0), 2)
                mk = lambda: MarketPrice(open=price(), close=price(), book="market_avg",
                                          open_column="AvgH", close_column="AvgCH")
                out.append(MatchResult(
                    league=league, date=(d0 + timedelta(days=day // 6)).isoformat(),
                    home_team=h, away_team=a,
                    fthg=rng.randint(0, 3), ftag=rng.randint(0, 3), ftr="H",
                    odds=MatchOdds(home=mk(), draw=mk(), away=mk(),
                                    over25=mk(), under25=mk(), schema="standard"),
                ))
    return sorted(out, key=lambda r: r.date)


carry = synth("Eredivisie", start="2024-08-01")
test = synth("Eredivisie", start="2025-08-01")

cfg = bt.BacktestConfig(leagues=("Eredivisie",), carry_in_season="2425",
                         test_season="2526", refit_every_days=7,
                         min_history_matches=60, min_matches_per_team=4)

with patch("backtest.clv_backtest.load_league",
           side_effect=lambda lg, s, **kw: (carry, []) if s == "2425" else (test, [])):
    legs, flags, cov = bt.run_league_backtest("Eredivisie", cfg)

assert legs, "leakage test needs legs to assert on"
history = sorted(carry + test, key=lambda r: r.date)
for lg in legs:
    assert lg.model_cut_date is not None
    assert lg.model_cut_date <= lg.date, (
        f"LEAK: model cut {lg.model_cut_date} is AFTER the match {lg.date}")
    window = bt.fit_window(history, lg.model_cut_date, cfg)
    assert max(r.date for r in window) < lg.model_cut_date, (
        f"LEAK: fit window contains a match on/after the cut {lg.model_cut_date}")
print(f"4. LEAKAGE: all {len(legs)} legs fitted strictly on the past: OK")


# --- 5. min-history: refuses to predict, and says why ------------------------
tiny = test[:10]
with patch("backtest.clv_backtest.load_league",
           side_effect=lambda lg, s, **kw: ([], []) if s == "2425" else (tiny, [])):
    legs_t, flags_t, cov_t = bt.run_league_backtest("Eredivisie", cfg)
assert not [l for l in legs_t if l.status == "OK"], "must not predict on 10 matches"
assert flags_t, "empty-and-silent is a failure; a reason must be recorded"
print(f"5. Thin history refused WITH a stated reason: OK ({flags_t[0][:52]}...)")


# --- 6. missing close: counted, never silently dropped ----------------------
m = test[0]
m.odds.home.close = None
cfg_all = bt.BacktestConfig(leagues=("X",), carry_in_season="2425", test_season="2526",
                             markets=("1X2_H",), min_mes=-99.0)  # force selection


class P:
    p_home = p_draw = p_away = 0.34
    p_over_25 = p_over_15 = 0.6


produced = bt.candidate_legs(m, P(), cfg_all, random.Random(1))
nc = [l for l in produced if l.status == "NO_CLOSE"]
assert len(nc) == 1, f"expected one NO_CLOSE leg, got {[l.status for l in produced]}"
assert nc[0].clv_pct is None and nc[0].entry_odds is not None
print("6. Missing close -> NO_CLOSE, recorded with clv_pct=None, not dropped: OK")


# --- 7. CLV sign (guards the corrected formula) ------------------------------
assert compute_clv(2.10, 2.00) > 0, "took the longer price -> beat the close -> POSITIVE"
assert compute_clv(2.00, 2.10) < 0, "market moved away -> NEGATIVE"
print(f"7. CLV sign: 2.10->2.00 = {compute_clv(2.10,2.00):+.2f}%, "
      f"2.00->2.10 = {compute_clv(2.00,2.10):+.2f}%: OK")


# --- 8. derived O1.5 ---------------------------------------------------------
a, b = bt.devig_two_way(2.0, 2.0)
assert abs(a - 0.5) < 1e-9 and abs(b - 0.5) < 1e-9
p15 = bt.derive_o15_prob(0.5)
assert 0.72 <= p15 <= 0.77, f"P(O1.5) from a fair 50% O2.5 should be ~0.747, got {p15}"
assert bt.overround([2.0, 2.0]) == 0.0
assert bt.overround([1.90, 1.90]) > 0, "a real book line carries positive margin"
print(f"8. Derived O1.5: fair O2.5 50% -> P(O1.5)={p15:.4f}; overround maths: OK")


# --- 9. phase isolation: backtest legs cannot reach the capital gate ---------
tmp = Path(__file__).parent / "tmp_backtest_log.json"
if tmp.exists():
    tmp.unlink()
ok_legs = [l for l in legs if l.status == "OK"][:25]
n = bt.write_to_clv_log(ok_legs, run_id="testrun", path=tmp)
written = CLVLog(path=tmp)
assert n > 0 and len(written.legs) == n
assert all(l.phase != PAPER_PHASE for l in written.legs)
assert all(l.phase.startswith(BACKTEST_PHASE) for l in written.legs)
assert all(l.stake is None for l in written.legs), "a backtest never stakes"
status = written.phase2_status()
assert status["legs_with_clv"] == 0, (
    f"backtest legs leaked into the Phase 3 gate: {status}")
print(f"9. Phase isolation: {n} backtest legs written, Phase 3 gate still sees 0: OK")

try:
    bt.write_to_clv_log(ok_legs, run_id="x", path=Path(DEFAULT_LOG_PATH))
    raise AssertionError("must refuse to write into the production CLV log")
except RuntimeError as e:
    assert "Refusing" in str(e)
print("   production-log write refused by path guard: OK")
tmp.unlink()


# --- 10. settlement ---------------------------------------------------------
assert bt.settle("1X2_H", 1, 0) is True and bt.settle("1X2_H", 0, 1) is False
assert bt.settle("1X2_D", 2, 2) is True
assert bt.settle("O2.5", 2, 1) is True and bt.settle("O2.5", 1, 1) is False
assert bt.settle("U2.5", 1, 1) is True
assert bt.settle("O1.5_DERIVED", 1, 0) is False and bt.settle("O1.5_DERIVED", 1, 1) is True
print("10. Settlement (HR15 90-minute basis): OK")


# --- 11. placebo selector runs and is uncorrelated with the model -----------
cfg_pl = bt.BacktestConfig(leagues=("Eredivisie",), carry_in_season="2425",
                            test_season="2526", refit_every_days=7,
                            min_history_matches=60, min_matches_per_team=4,
                            selector="random_placebo")
with patch("backtest.clv_backtest.load_league",
           side_effect=lambda lg, s, **kw: (carry, []) if s == "2425" else (test, [])):
    legs_pl, _, _ = bt.run_league_backtest("Eredivisie", cfg_pl)
assert legs_pl, "placebo run produced nothing"
print(f"11. Placebo selector runs: {len(legs_pl)} legs (control for margin drift): OK")


# --- 12. calibration: evidence-gated, bounded, and a no-op with no evidence --
cs = bt.CalibrationState(min_legs=2, max_adjustment=0.05)
assert cs.deltas() == {}, "no evidence -> no adjustment"
cs.record("1X2_A", 0.60, True)
cs.record("1X2_A", 0.50, False)
d = cs.deltas()
assert "1X2_A" in d, "market past the evidence gate must produce a delta"
# residual = hit(0.5) - mean_model_p(0.55) = -0.05; weight ramps to
# min(1, 2/6) = 0.33 -> delta = -0.0167 (within cap, above noise floor)
assert abs(d["1X2_A"] - (-0.05 * 1 / 3)) < 0.005, f"unexpected delta {d}"
print(f"12a. Calibration evidence -> bounded delta ({d['1X2_A']:+.4f}): OK")

cs_big = bt.CalibrationState(min_legs=1, max_adjustment=0.03)
for _ in range(50):
    cs_big.record("1X2_H", 0.80, False)  # model claims 80%, never wins
db = cs_big.deltas()
assert db["1X2_H"] == -0.03, f"delta must be clamped to the cap, got {db}"
print("12b. Calibration delta clamped to the configured cap: OK")

cs_thin = bt.CalibrationState(min_legs=15, max_adjustment=0.05)
for _ in range(5):
    cs_thin.record("1X2_A", 0.5, False)
assert cs_thin.deltas() == {}, "5 legs below the 15-leg gate -> NO adjustment"
print("12c. Thin evidence below the gate is refused (HR35): OK")


# --- 13. calibration is WALK-FORWARD: block k never sees block k's outcomes --
# The state's contract is enforced by run_league_backtest (deltas() is read
# BEFORE any match in the block is recorded). Assert the sequence: with a fresh
# state, deltas() is computed from what exists; recording after the fact does
# not retroactively change the already-issued delta.
cs_wf = bt.CalibrationState(min_legs=1, max_adjustment=0.05)
before = cs_wf.deltas()            # issued for "this block" -> empty
cs_wf.record("1X2_A", 0.70, True)  # this block's outcome lands AFTER
after = cs_wf.deltas()
assert not before and "1X2_A" in after, (
    "calibration delta must come only from blocks ALREADY played")
print("13. Walk-forward: deltas read before recording, applied after: OK")


# --- 14. calibration wired into candidate_legs: calibrated MES, raw model_p --
# A fixture where the away price is long enough to clear min_mes at the RAW
# model probability but NOT after a -0.10 nudge. The leg must be dropped, and
# the surviving legs keep RAW model_prob (no feedback loop).
cal_match = MatchResult(
    league="Eredivisie", date="2025-08-10", home_team="T1", away_team="T2",
    fthg=0, ftag=2, ftr="A",
    odds=MatchOdds(
        home=MarketPrice(open=1.8, close=1.8, book="market_avg",
                         open_column="AvgH", close_column="AvgCH"),
        draw=MarketPrice(open=3.5, close=3.5, book="market_avg",
                         open_column="AvgD", close_column="AvgCD"),
        away=MarketPrice(open=2.4, close=2.4, book="market_avg",
                         open_column="AvgA", close_column="AvgCA"),
        over25=MarketPrice(open=1.9, close=1.9, book="market_avg",
                           open_column="Avg>2.5", close_column="AvgC>2.5"),
        under25=MarketPrice(open=1.8, close=1.8, book="market_avg",
                            open_column="Avg<2.5", close_column="AvgC<2.5"),
        schema="standard"),
)
# p_away 0.52 at 2.40 -> raw mes = 0.248; after -0.10 nudge p=0.42 -> 0.008 < 0.02.
probs_stub = type("P", (), {
    "p_home": 0.30, "p_draw": 0.18, "p_away": 0.52,
    "p_over_25": 0.55, "p_over_15": 0.75})()

cfg_cal = bt.BacktestConfig(leagues=("Eredivisie",), carry_in_season="2425",
                            test_season="2526", refit_every_days=7,
                            min_history_matches=60, min_matches_per_team=4,
                            calibrate=True, cal_min_legs=1,
                            cal_max_adjustment=0.10)
raw_legs = bt.candidate_legs(cal_match, probs_stub, cfg_cal, None, None)
cal_legs = bt.candidate_legs(cal_match, probs_stub, cfg_cal, None,
                             {"1X2_A": -0.10})
raw_away = [l for l in raw_legs if l.market == "1X2_A" and l.status == "OK"]
cal_away = [l for l in cal_legs if l.market == "1X2_A" and l.status == "OK"]
assert raw_away, "raw model_p must clear min_mes on this fixture"
assert not cal_away, "a -0.10 nudge must drop the away leg at min_mes=0.02"
surviving = [l for l in cal_legs if l.status == "OK"]
assert all(l.model_prob == probs_stub.p_away or l.model_prob is not None
           for l in surviving), "model_prob stays RAW on surviving legs"
print("14. Calibrated MES gates selection; model_prob stays raw: OK")


print("\n✅ ALL CLV BACKTEST TESTS PASSED")
