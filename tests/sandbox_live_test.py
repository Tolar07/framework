"""Friendly live-watch tests: state transitions + in-play score honesty.

state_of/_line are pure functions over a TheSportsDB event dict — no network.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sandbox import live


def _ev(status: str, hs=None, as_=None, ts="2026-08-05T11:00:00"):
    return {"strStatus": status, "strTimestamp": ts,
            "intHomeScore": hs, "intAwayScore": as_, "idEvent": "x",
            "strEvent": "AC Milan vs Inter Milan"}


# --- 1. NOT STARTED + countdown ---------------------------------------------
st, sc, note = live.state_of(_ev("NS"))
assert st == "NOT STARTED" and sc is None
assert "kickoff" in note or "about" in note, note
print("1. NOT STARTED -> countdown: OK")

# --- 2. LIVE with and without an in-play score ------------------------------
st, sc, note = live.state_of(_ev("1H", "1", "0"))
assert st == "LIVE" and sc == "1-0" and "LIVE 1-0" in note
st, sc, note = live.state_of(_ev("2H"))
assert st == "LIVE" and sc is None and "NO DATA" in note, \
    "a live match without a source score must be honest, never 0-0"
assert "LIVE 0-0" not in note
print("2. LIVE with/without in-play score (honesty): OK")

# --- 3. FT with score --------------------------------------------------------
st, sc, note = live.state_of(_ev("FT", "2", "1"))
assert st == "FT" and sc == "2-1"
print("3. FT with score: OK")

# --- 4. a cancelled/finished-friendly does not read LIVE ---------------------
st, _, _ = live.state_of(_ev("CANC"))
assert st != "LIVE", "a cancelled match must not be reported live"
print("4. non-live statuses never read LIVE: OK")

print("\n✅ ALL SANDBOX LIVE TESTS PASSED")