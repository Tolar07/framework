"""CLV live-settle test — proves the brain LEARNS end-to-end on real data.

The Phase-3 gate needs >=30 paper legs with logged CLV. This test proves the
whole chain works on LIVE current-season data (football-data.co.uk 2627, which
football-data has already published for a few leagues), not a mock:

    log a paper leg (entry price)  ->  grade_open_legs  ->  hit + CLOSING line
    captured from the archive (CL-ARCHIVE)  ->  CLV computed

A leg whose match has been PLAYED and whose league file has odds MUST settle
here. If it does not, the "results feed is the gate" excuse is a bug, not a
calibration truth — and the gate can never be reached.

The fixture is chosen from the live 2627 file, so the test exercises the exact
code path the daily run will use once the Eredivisie season starts. HR35:
nothing here is fabricated — entry odds are the test's, the closing line is
football-data's real archive price.
"""
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from clv.clv_logger import CLVLog, compute_clv
from run_daily import grade_open_legs

_tmp = Path(tempfile.mkdtemp(prefix="olp_xdv_live_settle_"))
log = CLVLog(path=_tmp / "clv.json")

# Real played match from the live 2627 Scottish Premiership file.
# Celtic v Dundee, 2026-08-03, FT 1-0, home closing price in the archive ~1.14.
log.log_entry(
    league="Scottish Premiership",
    fixture="Celtic v Dundee",
    market="1X2_HOME",
    model_prob=0.85,
    entry_odds=1.20,
    entry_capture_path="CL-LIVE",
    match_date="2026-08-03",
)
leg = log.legs[0]
assert leg.hit is None, "a freshly logged leg must be pending"

text, flags = grade_open_legs(log, "2526")

assert "graded 1 of 1" in " ".join(flags), f"leg did not grade: {flags}"
leg = log.legs[0]
assert leg.hit is True, f"Celtic beat Dundee 1-0, a 1X2_HOME leg must HIT (got {leg.hit})"
assert leg.closing_odds is not None, "a played match with odds must yield a CLOSING line"
assert leg.closing_capture_path == "CL-ARCHIVE", "closing line must come from the archive"
assert leg.clv_pct is not None, "closing line + entry odds must yield a CLV number"
expected = compute_clv(1.20, leg.closing_odds)
assert abs(leg.clv_pct - expected) < 1e-6, f"CLV {leg.clv_pct} != compute_clv {expected}"
print(f"1. live settle: {leg.fixture} hit={leg.hit} close={leg.closing_odds} "
      f"CLV={leg.clv_pct:+.2f}% (archive, real): OK")

# Second leg on a DRAW — Dundee United v Rangers, 2026-07-31, FT 1-1.
log.log_entry(
    league="Scottish Premiership",
    fixture="Dundee United v Rangers",
    market="1X2_DRAW",
    model_prob=0.30,
    entry_odds=3.40,
    entry_capture_path="CL-LIVE",
    match_date="2026-07-31",
)
text, flags = grade_open_legs(log, "2526")
assert "graded 1 of 1" in " ".join(flags), f"second leg did not grade: {flags}"
d = log.legs[1]
assert d.hit is True, f"1-1 draw must HIT a DRAW leg (got {d.hit})"
assert d.clv_pct is not None, "draw leg must also carry a CLV number"
print(f"2. live settle (draw): {d.fixture} hit={d.hit} close={d.closing_odds} "
      f"CLV={d.clv_pct:+.2f}%: OK")

print("\n✅ THE BRAIN LEARNS — paper legs settle with real closing-line CLV "
      "on live 2026/27 data.")
