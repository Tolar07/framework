"""Tests for monitor/data_quality.py — the instrument that notices when the
DATA went bad (distinct from run_monitor, which watches machinery).

Proves each check on a throwaway temp cache (the real cache is never touched):
  1. a clean cache yields no findings
  2. a missing STANDARD league file  -> coverage gap (warn)
  3. a missing EXTRA league _all.csv -> coverage gap (warn)
  4. uncovered leagues (HNL, EFL Cup, continental) are never flagged
  5. a stale completed-season file   -> stale warning
  6. duplicate (date,home,away) rows -> error
  7. an _all.csv covering an extra league is recognized as covered
  8. render_report formats findings, and a clean cache has its own line
"""
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from monitor import data_quality as dq

_TMP = Path(tempfile.mkdtemp(prefix="olp_xdv_dq_"))
HEADER = "Date,HomeTeam,AwayTeam,FTHG,FTAG,FTR\n"
SERIE_A_ROW = "01/08/2026,CCC,DDD,1,1,D\n"


def _write(name: str, body: str, age_days: float | None = None) -> Path:
    p = _TMP / name
    p.write_text(HEADER + body, encoding="utf-8")
    if age_days is not None:
        old = time.time() - age_days * 24 * 3600
        os.utime(p, (old, old))
    return p


def _run() -> dict:
    """check() with CACHE_DIR pointed at the throwaway dir, keyed by league."""
    dq.CACHE_DIR = _TMP
    return {f.league: f for f in dq.check("2526")}


# --- 1. clean cache -----------------------------------------------------------
_write("Eredivisie_2526.csv", "01/08/2026,AAA,BBB,2,1,H\n")
_write("Serie_A_2526.csv", SERIE_A_ROW)
_write("Danish_Superliga_all.csv", "Season,Date,Home,Away,HG,AG,Res\n"
                                   "2025/2026,01/08/2026,GGG,HHH,2,2,D\n")
# only these three exist; the rest of the whitelist is uncovered or absent —
# but a clean check is defined against the leagues that ARE present, so verify
# the covered ones never fire and the absent standard ones DO.
f = _run()
assert "Eredivisie" not in f, "fresh standard file must not be flagged"
assert "Serie A" not in f, "fresh standard file must not be flagged"
assert "Danish Superliga" not in f, "_all.csv must satisfy extra coverage"
print("1. clean cache: covered leagues not flagged: OK")

# --- 2. missing standard league -> coverage gap -------------------------------
for p in _TMP.glob("Serie_A_2526.csv"):
    p.unlink()
f = _run()
assert "Serie A" in f and f["Serie A"].level == "warn", \
    f"missing standard file must warn: {f.get('Serie A')}"
assert "results cache" in f["Serie A"].problem
print("2. missing standard league -> coverage gap warn: OK")

# --- 3. missing extra league -> coverage gap ----------------------------------
for p in _TMP.glob("Danish_Superliga_all.csv"):
    p.unlink()
f = _run()
assert "Danish Superliga" in f and f["Danish Superliga"].level == "warn", \
    f"missing extra _all.csv must warn: {f.get('Danish Superliga')}"
print("3. missing extra _all.csv -> coverage gap warn: OK")

# --- 4. uncovered leagues never flagged ---------------------------------------
for league in ("HNL", "EFL Cup", "Champions League", "Europa League"):
    assert league not in f, f"{league} has no football-data file BY DESIGN"
print("4. uncovered leagues (HNL/EFL/continental) never flagged: OK")

# --- 5. stale completed-season file -------------------------------------------
_write("Serie_A_2526.csv", SERIE_A_ROW, age_days=35)  # TTL for 2526 is 30d
f = _run()
assert "Serie A" in f and f["Serie A"].level == "warn", "35d-old file must warn"
assert "old" in f["Serie A"].problem
print("5. stale completed-season file (35d > 30d TTL) -> warn: OK")

# --- 6. duplicate rows -> error ------------------------------------------------
_write("Championship_2526.csv",
       "01/08/2026,EEE,FFF,1,0,H\n01/08/2026,EEE,FFF,1,0,H\n")
f = _run()
assert "Championship" in f and f["Championship"].level == "error", \
    f"duplicate rows must error: {f.get('Championship')}"
assert "duplicate" in f["Championship"].problem.lower()
print("6. duplicate (date,home,away) rows -> error: OK")

# --- 7. _all.csv restores extra coverage (and clears the gap) ------------------
_write("Danish_Superliga_all.csv", "Season,Date,Home,Away,HG,AG,Res\n"
                                   "2025/2026,01/08/2026,GGG,HHH,2,2,D\n")
f = _run()
assert "Danish Superliga" not in f, "restored _all.csv must clear the gap"
print("7. _all.csv recognized as extra coverage: OK")

# --- 8. render_report ----------------------------------------------------------
lines = dq.render_report(list(f.values())).splitlines()
assert lines[0].startswith("DATA QUALITY:") and f"[{list(f.values())[0].level.upper()}]" in lines[1]
clean_line = dq.render_report([])
assert "CLEAN" in clean_line
print("8. render_report formats findings + clean line: OK")

print("\n✅ ALL DATA-QUALITY TESTS PASSED")
