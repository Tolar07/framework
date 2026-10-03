"""Regression tests — SportyBet continental qualifier pricing (2026-08-11).

Pins the permanent NO DATA fix for the CL/EL/ConfL qualifier slate:

1. **TTL**: `load_sportybet_fixtures` default `max_age_hours` is 24, not 6.
   The 6h default meant any daily run >~6h after the last cache build lost
   EVERY league's prices at once — fixtures appeared (the orchestrator's
   fixture fallback already read 48h) but the price join
   (`get_sportybet_odds_for_leg`) and the booking-code driver silently returned
   "fixture not found in SportyBet cache". A 24h window keeps today's fixtures
   priceable all day; the booking driver re-reads LIVE prices at booking time.

2. **No-fuzzy forward resolver**: `resolve_team` is exact + normalized-exact
   only (HR35, mirroring `resolve_team_to_model`). The old fuzzy pass returned
   a DIFFERENT club when a board key wasn't in the table ("Celje" -> "Chelsea",
   "Iberia 1999" -> "Hibernian FC", "Larne" -> "Levante", "SK Brann" ->
   "SC Braga"), which would attach one club's real price to the wrong team.

3. **Continental aliases**: the board's model keys resolve to the SportyBet
   spellings in the cache ("Celje" -> "NK Celje", "Hapoel Be'er Sheva" ->
   "Hapoel Be`er Sheva FC" with the backtick, etc.).

4. **Live-cache join** (conditional): when the SportyBet cache is present,
   the 13 continental fixtures from the 2026-08-11 slate resolve through
   `get_sportybet_odds_for_leg`.

Run directly:  PYTHONIOENCODING=utf-8 py -3.12 tests/sportybet_continental_test.py
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def _check(name, cond, detail=""):
    assert cond, f"{name} FAILED {detail}"
    print(f"  ✓ {name}")


# --- 1. TTL default is 24h (was 6h until 2026-08-11) -------------------------
from booking.bridge import load_sportybet_fixtures

sig = inspect.signature(load_sportybet_fixtures)
ttl = sig.parameters["max_age_hours"].default
print(f"1. load_sportybet_fixtures max_age_hours default = {ttl}")
_check("default TTL is 24h", ttl == 24, f"got {ttl!r}")

# --- 2. resolve_team is exact-only — never a fuzzy guess across clubs --------
from booking.team_map import resolve_team, resolve_team_to_model

print("2. resolve_team continental aliases (exact, no wrong club):")
FORWARD = {
    "Celje": "NK Celje",                      # must NOT become "Chelsea"
    "Ararat-Armenia": "FC Ararat-Armenia",
    "Hapoel Be'er Sheva": "Hapoel Be`er Sheva FC",  # SportyBet backtick
    "Mjällby": "Mjallby AIF",
    "Kairat Almaty": "FC Kairat Almaty",
    "Levski Sofia": "PFC Levski Sofia",
    "Kauno Žalgiris": "FK Kauno Zalgiris",
    "Dinamo Zagreb": "GNK Dinamo Zagreb",
    "Sabah Baku": "Sabah Masazir",
    "Aarhus": "AGF Aarhus",
    "FK Crvena Zvezda": "Crvena Zvezda",
    "Iberia 1999": "FC Iberia 1999",          # must NOT become "Hibernian FC"
    "Larne": "Larne FC",                      # must NOT become "Levante"
    "SK Brann": "SK Brann",                   # must NOT become "SC Braga"
    "Slovan Bratislava": "Slovan Bratislava",
    "Panathinaikos": "Panathinaikos",
    "FC CSKA 1948": "FC CSKA 1948",
    "Apollon Limassol": "Apollon Limassol",
    "Bodo/Glimt": "Bodoe/Glimt",              # pre-existing, still exact
    "St. Gilloise": "Union Gilloise",
    "Nijmegen": "NEC Nijmegen",
    "Olympiakos Piraeus": "Olympiacos",
    "Sturm Graz": "SK Sturm Graz",
    "Sparta Praha": "Sparta Prague",
}
for key, expect in FORWARD.items():
    got = resolve_team(key, "sportybet")
    _check(f"{key} -> {expect}", got == expect, f"got '{got}'")

# --- 3. reverse resolver picks up the new SportyBet spellings ---------------
print("3. reverse (SportyBet -> model key):")
REVERSE = {
    "NK Celje": "Celje",
    "FC Ararat-Armenia": "Ararat-Armenia",
    "Mjallby AIF": "Mjällby",
    "FC Iberia 1999": "Iberia 1999",
    "Larne FC": "Larne",
    "Sabah Masazir": "Sabah Baku",
    "Bodoe/Glimt": "Bodo/Glimt",              # canonical key first-wins
    "Union Gilloise": "St. Gilloise",
    "Olympiacos": "Olympiakos Piraeus",
    "Sparta Prague": "Sparta Praha",
}
for sb_name, expect in REVERSE.items():
    got = resolve_team_to_model(sb_name)
    _check(f"{sb_name} -> {expect}", got == expect, f"got '{got}'")

# --- 4. live-cache join (conditional — skip gracefully without a cache) -----
CACHE = Path(__file__).parent.parent / "data" / "cache" / "sportybet" / "fixtures"
LEGS = [
    # (home, away, league) — the 2026-08-11 NO DATA slate
    ("Lyon", "Sparta Praha", "Champions League"),
    ("Bodo/Glimt", "St. Gilloise", "Champions League"),
    ("Nijmegen", "Olympiakos Piraeus", "Champions League"),
    ("Sturm Graz", "Fenerbahçe", "Champions League"),
    ("Celje", "Ararat-Armenia", "Champions League"),
    ("FK Crvena Zvezda", "Hapoel Be'er Sheva", "Champions League"),
    ("Slovan Bratislava", "Mjällby", "Champions League"),
    ("Kairat Almaty", "Levski Sofia", "Champions League"),
    ("Kauno Žalgiris", "Dinamo Zagreb", "Champions League"),
    ("Sabah Baku", "Aarhus", "Champions League"),
    ("Iberia 1999", "Larne", "Europa League"),
    ("Apollon Limassol", "SK Brann", "Conference League"),
    ("FC CSKA 1948", "Panathinaikos", "Conference League"),
]
if not any(CACHE.glob("*.json")):
    print("4. SKIPPED — no SportyBet cache on disk (live-join test needs one)")
else:
    from booking.bridge import get_sportybet_odds_for_leg

    print("4. live SportyBet cache join (24h window):")
    resolved = 0
    for home, away, league in LEGS:
        price = get_sportybet_odds_for_leg(home, away, league, "1X2_HOME")
        if price is not None:
            resolved += 1
        _check(f"{home} v {away} priced",
               price is not None, f"got home={price!r}")
    _check("all continental legs resolve", resolved == len(LEGS),
           f"{resolved}/{len(LEGS)} resolved")

print("\n[OK] ALL SPORTYBET-CONTINENTAL TESTS PASSED")
