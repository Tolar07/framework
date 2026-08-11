"""`resolve_team_to_model` regression tests — the reverse (SportyBet -> model) resolver.

The regression this pins: `sportybet_fixtures.py` used to call `resolve_team`
(sportybet_name, "sportybet") expecting MODEL keys back, but `resolve_team`
maps OLP->SportyBet and was fed a SportyBet name — so model_home/model_away
stored SPORTYBET spellings and the fuzzy pass then matched one club against
another, attaching a real price to the WRONG team:

    "Excelsior Rotterdam" -> "Sparta Rotterdam"
    "Club Brugge"         -> "Cercle Brugge"
    "Millwall FC"         -> "AC Milan"

The fix (HR35): reverse lookup is EXACT + normalized-exact ONLY. A name that
isn't in the reverse table returns UNCHANGED so the caller reports NO DATA —
PENDING rather than guess across clubs. This test pins both directions.

Run directly:  PYTHONIOENCODING=utf-8 py -3.12 tests/team_map_reverse_test.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from booking.team_map import resolve_team_to_model


def _check(name, cond, detail=""):
    assert cond, f"{name} FAILED {detail}"
    print(f"  ✓ {name}")


# --- 1. known SportyBet league-page spelling -> real model key ---------------
CASES = [
    # (sportybet spelling, expected model key)
    ("Heart of Midlothian FC", "Hearts"),
    ("Hibernian FC", "Hibernian"),
    ("Motherwell FC", "Motherwell"),
    ("St Mirren FC", "St Mirren"),
    ("Kilmarnock FC", "Kilmarnock"),
    ("Falkirk FC", "Falkirk"),
    ("St Johnstone", "St Johnstone"),
    ("Millwall FC", "Millwall"),            # must NOT become "AC Milan"
    ("Club Brugge", "Club Brugge"),         # must NOT become "Cercle Brugge"
    ("Cercle Brugge", "Cercle Brugge"),
    ("Excelsior Rotterdam", "Excelsior"),   # must NOT become "Sparta Rotterdam"
    ("Union Gilloise", "St. Gilloise"),
    ("Standard Liege", "Standard"),
    ("KV Kortrijk", "Kortrijk"),
    ("Yellow-Red KV Mechelen", "Mechelen"),
    ("Fortuna Sittard", "For Sittard"),
    ("Willem II Tilburg", "Willem II"),
    ("NEC Nijmegen", "Nijmegen"),
    ("Broendby IF", "Brondby"),
    ("Legia Warszawa", "Legia"),
]
print("1. SportyBet spelling -> model key (exact reverse):")
for sb_name, expect in CASES:
    got = resolve_team_to_model(sb_name)
    _check(f"{sb_name} -> {expect}", got == expect, f"got '{got}'")

# --- 2. normalized-exact still works through accents/suffixes ---------------
print("2. normalized-exact reverse:")
_check("Fenerbahce -> Fenerbahce (identity passthrough)",
       resolve_team_to_model("Fenerbahce") == "Fenerbahce")

# --- 3. UNKNOWN names pass through UNCHANGED (HR35, no fuzzy cross-club) -----
print("3. unknown names pass through unchanged — NO fuzzy guess:")
UNKNOWN = ["RKS Radomiak Radom", "Bodo/Glimt", "Olympiakos Piraeus",
           "Sparta Praha", "Aarhus"]
for name in UNKNOWN:
    _check(f"{name} unchanged", resolve_team_to_model(name) == name,
           f"got '{resolve_team_to_model(name)}'")

# --- 4. forward resolver still maps model key -> SportyBet spelling ----------
from booking.team_map import resolve_team

print("4. forward (model -> SportyBet) still intact:")
for model_key, sb_name in (("Hearts", "Heart of Midlothian FC"),
                           ("Millwall", "Millwall FC"),
                           ("Club Brugge", "Club Brugge"),
                           ("Excelsior", "Excelsior Rotterdam"),
                           ("Kilmarnock", "Kilmarnock FC")):
    got = resolve_team(model_key, "sportybet")
    _check(f"{model_key} -> {sb_name}", got == sb_name, f"got '{got}'")

print("\n[OK] ALL TEAM-MAP REVERSE TESTS PASSED")
