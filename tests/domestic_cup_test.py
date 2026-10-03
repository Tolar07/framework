"""engine/domestic_cup.py — fitting a cup from the league tiers that feed it.

Offline and deterministic: the connectivity logic is exercised on synthetic
pools, so nothing here touches football-data.co.uk.

Plain script, no pytest (repo convention):
    py -3.12 tests/domestic_cup_test.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.domestic_cup import (  # noqa: E402
    CUP_FEEDER_LEAGUES,
    MIN_MATCHES_FOR_CUP_RATING,
    MIN_TIER_BRIDGES,
    _tier_bridges,
    check_connected,
    is_domestic_cup,
)

FAILURES: list[str] = []


def check(label: str, got, want) -> None:
    if got == want:
        print(f"  [OK] {label}")
    else:
        print(f"  [FAIL] {label}: got {got!r}, want {want!r}")
        FAILURES.append(label)


def check_true(label, got): check(label, bool(got), True)
def check_false(label, got): check(label, bool(got), False)


def test_recognises_cups() -> None:
    print("\ntest: which competitions this module claims")

    for cup in ("EFL Cup", "FA Cup", "Copa del Rey", "Coppa Italia",
                "DFB-Pokal", "Coupe de France"):
        check_true(f"{cup} is a domestic cup", is_domestic_cup(cup))

    # A continental competition must NOT be routed here -- it belongs to
    # engine/cross_league.py, whose pool is the European graph. Pooling
    # England's tiers would not rate a single Europa League entrant.
    for other in ("Europa League", "Champions League", "Premier League",
                  "La Liga", "Russian Premier League"):
        check_false(f"{other} is not a domestic cup", is_domestic_cup(other))


def test_feeders_are_real_leagues() -> None:
    print("\ntest: every feeder tier is a league the pipeline can load")
    from data.football_data_source import LEAGUE_CODES

    for cup, tiers in CUP_FEEDER_LEAGUES.items():
        for tier in tiers:
            # A feeder with no football_data code cannot contribute matches,
            # which would silently shrink the pool rather than fail loudly.
            check(f"{cup}: {tier} has a football-data code",
                  bool(LEAGUE_CODES.get(tier)), True)


def test_bridges_only_count_adjacent_tiers() -> None:
    print("\ntest: bridges are counted between ADJACENT tiers only")

    # Promotion and relegation move a club one division at a time, so E0 and
    # E2 share clubs only by way of E1. Counting non-adjacent pairs would
    # report a chain as connected when a middle link is missing.
    order = ("T1", "T2", "T3")
    by_tier = {
        "T1": {"a", "b", "shared12"},
        "T2": {"shared12", "c", "shared23"},
        "T3": {"shared23", "d"},
    }
    bridges = _tier_bridges(order, by_tier)
    check("two adjacent pairs", sorted(bridges), ["T1 <-> T2", "T2 <-> T3"])
    check("T1<->T2 count", bridges["T1 <-> T2"]["count"], 1)
    check("no T1<->T3 pair reported", "T1 <-> T3" in bridges, False)


def test_refuses_disconnected_pool() -> None:
    print("\ntest: an unlinked tier is refused, not fitted")

    # This is the important one. Dixon-Coles will fit a disconnected graph and
    # return numbers, but the scale offset between two unlinked components is
    # arbitrary -- and an arbitrary offset reads downstream as an enormous
    # edge on every fixture that crosses it.
    linked = {f"club{i}" for i in range(MIN_TIER_BRIDGES)}
    info_ok = {
        "tiers": ["T1", "T2"],
        "bridges": {"T1 <-> T2": {"count": MIN_TIER_BRIDGES,
                                  "clubs": sorted(linked)}},
    }
    ok, problems = check_connected(info_ok)
    check_true("a pool at the bridge floor is accepted", ok)
    check("and reports no problems", problems, [])

    info_thin = {
        "tiers": ["T1", "T2"],
        "bridges": {"T1 <-> T2": {"count": MIN_TIER_BRIDGES - 1, "clubs": []}},
    }
    ok, problems = check_connected(info_thin)
    check_false("one below the floor is refused", ok)
    check_true("and says which pair", any("T1 <-> T2" in p for p in problems))

    # A broken middle link must fail even when the outer tiers are fine.
    info_gap = {
        "tiers": ["T1", "T2", "T3"],
        "bridges": {
            "T1 <-> T2": {"count": 9, "clubs": []},
            "T2 <-> T3": {"count": 0, "clubs": []},
        },
    }
    ok, problems = check_connected(info_gap)
    check_false("a gap anywhere in the chain is refused", ok)

    ok, problems = check_connected({"tiers": ["T1"], "bridges": {}})
    check_false("a single tier has nothing to bridge", ok)


def test_floor_is_stricter_than_the_library_default() -> None:
    print("\ntest: the cup rating floor is deliberately high")
    from engine.dixon_coles import PRODUCTION_MIN_MATCHES_PER_TEAM

    # A cup pool mixes divisions, so a club with only a handful of matches
    # takes its rating almost entirely from the tier offset rather than from
    # its own results.
    check_true("cup floor is at least the production floor",
               MIN_MATCHES_FOR_CUP_RATING >= PRODUCTION_MIN_MATCHES_PER_TEAM)
    check_true("production floor is above the library default of 4",
               PRODUCTION_MIN_MATCHES_PER_TEAM > 4)


if __name__ == "__main__":
    test_recognises_cups()
    test_feeders_are_real_leagues()
    test_bridges_only_count_adjacent_tiers()
    test_refuses_disconnected_pool()
    test_floor_is_stricter_than_the_library_default()

    print()
    if FAILURES:
        print(f"=== {len(FAILURES)} FAILURE(S) ===")
        for f in FAILURES:
            print(f"  - {f}")
        sys.exit(1)
    print("=== all passed ===")
