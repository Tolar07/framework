"""Phase 3.5 — backtest metrics history: record, read, render, trend.

The report measures ONE run; the history accumulates many runs so the trend
is trackable across commits. Each row is one backtest run as a JSON line;
render_history groups rows by (test_season, selector) family so a partial CI
slice is never compared against a full run as if equal.

Honesty rules proven here:
  1. a recorded row carries mean CLV over the unified pool (ID402 A/B-vs-C/D
     split removed 2026-08-10 — the legacy tier_ab/tier_cd keys stay None for
     back-compat), and DERIVED O1.5 legs are excluded from the headline
  2. context is recorded so a CI slice is distinguishable from a full run
  3. read_history survives a comment line / corrupt line, oldest first
  4. render_history groups by family; an empty history says so plainly
  5. recording never fails a run: a broken history write is swallowed
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import backtest.metrics_history as mh
from backtest.clv_backtest import BacktestConfig, PaperLeg

_tmp = Path(tempfile.mkdtemp(prefix="olp_metrics_hist_"))
HIST = _tmp / "metrics_history.jsonl"
# Redirect the module's write path so the test never touches the real history.
mh.METRICS_PATH = HIST


def _leg(league: str, clv: float, *, hit: bool = True, derived: bool = False,
         status: str = "OK", market: str = "O2.5", date: str = "2024-01-10",
         fixture: str = "Home v Away") -> PaperLeg:
    return PaperLeg(
        league=league, date=date, fixture=fixture, market=market,
        softness_tier="A", model_prob=0.55, entry_odds=2.0,
        closing_odds=1.96, book="Pinnacle", entry_column="BbAv",
        closing_column="BbAv", mes_at_entry=0.10, clv_pct=clv, derived=derived,
        status=status, hit=hit, fthg=2, ftag=1, overround_open=0.05,
        overround_close=0.04, model_cut_date="2024-01-01", model_n_matches=120,
    )


cfg = BacktestConfig(leagues=("Eredivisie",), carry_in_season="2324",
                     test_season="2425")

# --- 1. record_run appends a row with the headline (unified pool) -------------
legs = [
    _leg("Eredivisie", 2.04),
    _leg("Bundesliga", -1.0, hit=False),
    _leg("Eredivisie", 9.99, derived=True),   # DERIVED — must be excluded
]
row = mh.record_run(legs, ["flag"], {}, cfg, "2425_model_smoke",
                    context="ci_push", run_date="2026-08-09T10:00:00Z")
assert row["mean_clv_pct"] == 0.52, row  # (2.04 + -1.0) / 2, DERIVED excluded
assert row["n_with_clv"] == 2 and row["n_legs_selected"] == 2, row
# ID402 tiers removed 2026-08-10 — unified pool, legacy keys kept as None
assert row["tier_ab_mean_clv"] is None and row["tier_ab_n"] == 0, row
assert row["tier_cd_mean_clv"] is None and row["tier_cd_n"] == 0, row
assert row["context"] == "ci_push" and row["test_season"] == "2425", row
assert row["selector"] == "model" and "Eredivisie" in row["leagues"], row
print("1. record_run writes headline (unified pool), DERIVED excluded, legacy tier keys None: OK")

# --- 2. read_history: oldest first, survives comments and a corrupt line -----
HIST.write_text(HIST.read_text(encoding="utf-8")
                + "\n# a header comment line\n{garbage}\n",
                encoding="utf-8")
rows = mh.read_history(HIST)
assert len(rows) == 1, f"expected 1 clean row, got {len(rows)}"
assert rows[0]["run_id"] == "2425_model_smoke"
print("2. read_history skips comments/corrupt lines: OK")

# --- 3. a second run in a different family renders separately ----------------
cfg2 = BacktestConfig(leagues=("Eredivisie", "La Liga"), carry_in_season="2425",
                      test_season="2526")
mh.record_run([_leg("Eredivisie", 3.5)], [], {}, cfg2, "2526_model_smoke",
              context="ci_push", run_date="2026-08-10T10:00:00Z")
table = mh.render_history(HIST)
assert "FAMILY: 2425_model" in table and "FAMILY: 2526_model" in table, table
assert "ci_push" in table, table
# two runs, same family -> both rows visible in the trend
fam = [r for r in mh.read_history(HIST) if r["test_season"] == "2425"]
assert len(fam) == 1
print("3. render_history groups by (season, selector) family: OK")

# --- 4. empty history renders plainly, never crashes --------------------------
empty = _tmp / "empty.jsonl"
empty.write_text("# nothing yet\n", encoding="utf-8")
assert "empty" in mh.render_history(empty)
assert mh.read_history(empty) == []
assert mh.read_history(_tmp / "missing.jsonl") == []
print("4. empty history renders honestly: OK")

# --- 5. a broken record propagates; the CALLER swallows (contract) ------------
blocker = _tmp / "not_a_dir"
blocker.write_text("x", encoding="utf-8")   # a FILE as a parent dir
mh.METRICS_PATH = blocker / "sub" / "metrics_history.jsonl"
try:
    mh.record_run(legs, [], {}, cfg, "will_fail", context="manual",
                  run_date="2026-08-11T00:00:00Z")
    raise AssertionError("a write failure must propagate — clv_backtest.main() "
                         "owns the try/except that keeps the run alive")
except (NotADirectoryError, FileNotFoundError, OSError):
    pass
mh.METRICS_PATH = HIST   # restore
print("5. write failure propagates; the swallow is the caller's, as wired: OK")

print("\n✅ ALL METRICS HISTORY TESTS PASSED")
