"""One outcome, one slip (Architect 2026-11-03)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from engine import slip_overlap as so  # noqa: E402

L = lambda fx, mk: {"fixture": fx, "market": mk}  # noqa: E731
doc = {
    "safe3": [{"leg_detail": [L("A v B", "DC_12"), L("C v D", "O15"), L("E v F", "DC_1X")]}],
    "clv_accas": [{"leg_detail": [L("A v B", "DC_12"), L("G v H", "O15")]},      # repeats A v B DC_12
                  {"leg_detail": [L("A v B", "BTTS_YES"), L("G v H", "O15")]}],  # same match, other outcome
    "accas": [{"leg_detail": [L("G v H", "O15"), L("I v J", "DC_X2")]}],         # repeats G v H (2nd clv kept)
    "btts": [{"alt_legs": [{"fixture": "A v B", "key": "DC_12"}]}],                  # a single: left alone
    "combined": [{"name": "ACCAS MEGA"}],
}
note = so.apply(doc)
assert "overlap" not in doc["safe3"][0]
assert doc["clv_accas"][0]["overlap"] == ["A v B: DC_12"]
assert "overlap" not in doc["clv_accas"][1], "same match, different outcome is allowed"
assert doc["accas"][0]["overlap"] == ["G v H: O15"]
assert "overlap" not in doc["btts"][0]
assert doc["combined"][0]["overlap"]
assert "1 clv_accas" in note and "1 accas" in note
print("slip_overlap_test: OK")
