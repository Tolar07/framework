"""Tests for booking/sportybet_discovery.py — availability-first competition discovery.

Plain script, no pytest (repo convention):
    py -3.12 tests/sportybet_discovery_test.py

Everything here runs against captured payload shapes, not the live feed, so it
is deterministic and offline.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from booking.sportybet_discovery import (  # noqa: E402
    Competition,
    _collect,
    _parse_1x2,
    _parse_event,
    is_simulated,
    olp_league_name,
    to_cached_fixtures,
)

FAILURES: list[str] = []


def check(label: str, got, want) -> None:
    if got == want:
        print(f"  [OK] {label}")
    else:
        print(f"  [FAIL] {label}: got {got!r}, want {want!r}")
        FAILURES.append(label)


def check_true(label: str, got) -> None:
    check(label, bool(got), True)


def check_false(label: str, got) -> None:
    check(label, bool(got), False)


# --- Fixture payloads ------------------------------------------------------

def mk_market(outcomes, market_id="1", status=0, specifier=""):
    return {"id": market_id, "specifier": specifier, "status": status,
            "desc": "1X2", "outcomes": outcomes}


def oc(oid, odds, active=1):
    return {"id": oid, "odds": odds, "isActive": active}


def mk_event(home="Everton", away="Wolves", ts=1789580700000, markets=None,
             event_id="sr:match:74158489", game_id="22929"):
    return {
        "eventId": event_id,
        "gameId": game_id,
        "estimateStartTime": ts,
        "homeTeamName": home,
        "awayTeamName": away,
        "homeTeamId": "sr:competitor:1",
        "awayTeamId": "sr:competitor:2",
        "fixtureVenue": {"name": "Goodison Park"},
        "markets": markets if markets is not None else [
            mk_market([oc("1", "1.52"), oc("2", "4.77"), oc("3", "6.55")])
        ],
    }


def mk_payload(tournaments):
    return {"bizCode": 10000, "data": {"totalNum": 1, "tournaments": tournaments}}


def mk_tournament(category="England", name="EFL Cup", cat_id="sr:category:1",
                  tour_id="sr:tournament:21", events=None):
    return {"categoryName": category, "name": name, "categoryId": cat_id,
            "id": tour_id, "events": events if events is not None else [mk_event()]}


# --- Tests -----------------------------------------------------------------

def test_1x2_parsing() -> None:
    print("\ntest: 1X2 odds come off the market block")

    got = _parse_1x2([mk_market([oc("1", "1.52"), oc("2", "4.77"), oc("3", "6.55")])])
    check("three outcomes parsed into named slots",
          got, {"home": 1.52, "draw": 4.77, "away": 6.55})

    check("a partial market is not a quote",
          _parse_1x2([mk_market([oc("1", "1.52"), oc("2", "4.77")])]), {})

    check("an inactive outcome makes the market partial",
          _parse_1x2([mk_market([oc("1", "1.52"), oc("2", "4.77", 0), oc("3", "6.55")])]), {})

    check("a suspended market is skipped",
          _parse_1x2([mk_market([oc("1", "1.52"), oc("2", "4.77"), oc("3", "6.55")],
                                status=1)]), {})

    # 1.00 is the feed's "no price" placeholder, not a real quote. Same rule as
    # _extract_row_odds in rebuild_cache.py.
    check("a 1.00 placeholder is not a price",
          _parse_1x2([mk_market([oc("1", "1.00"), oc("2", "4.77"), oc("3", "6.55")])]), {})

    check("unparseable odds -> no quote",
          _parse_1x2([mk_market([oc("1", "-"), oc("2", "4.77"), oc("3", "6.55")])]), {})

    # marketId 1 with a specifier is a different market (e.g. a handicap),
    # not the plain 1X2.
    check("1X2 with a specifier is a different market",
          _parse_1x2([mk_market([oc("1", "1.52"), oc("2", "4.77"), oc("3", "6.55")],
                                specifier="hcp=1.5")]), {})

    check("over/under is not mistaken for 1X2",
          _parse_1x2([mk_market([oc("12", "1.04"), oc("13", "13.50")],
                                market_id="18")]), {})

    check("no markets at all -> no quote", _parse_1x2([]), {})


def test_event_parsing() -> None:
    print("\ntest: an event row becomes a DiscoveredEvent")

    ev = _parse_event(mk_event())
    check_true("event parsed", ev is not None)
    check("home", ev.home, "Everton")
    check("away", ev.away, "Wolves")
    check("Betradar id kept for cross-source joins", ev.event_id, "sr:match:74158489")
    check("SportyBet game id kept for booking", ev.game_id, "22929")
    check_true("has odds", ev.has_odds)
    check("kickoff is ISO UTC", ev.kickoff,
          datetime.fromtimestamp(1789580700, tz=timezone.utc).isoformat())
    check("kickoff_date is the date half", ev.kickoff_date, ev.kickoff[:10])

    # A row missing any of the three things that make it a fixture is dropped
    # rather than filled in (HR35).
    check("no kickoff -> dropped",
          _parse_event({**mk_event(), "estimateStartTime": None}), None)
    check("no home team -> dropped",
          _parse_event({**mk_event(), "homeTeamName": None}), None)
    check("no away team -> dropped",
          _parse_event({**mk_event(), "awayTeamName": ""}), None)

    # A fixture with no open market is still a fixture; it just has no price.
    ev = _parse_event(mk_event(markets=[]))
    check_true("priceless fixture still parses", ev is not None)
    check_false("but reports no odds", ev.has_odds)


def test_collect_groups_by_tournament() -> None:
    print("\ntest: events group under the competition the feed gives them")

    found: dict = {}
    added = _collect(mk_payload([
        mk_tournament(events=[mk_event("Everton", "Wolves"),
                              mk_event("Man Utd", "Brighton")]),
        mk_tournament(category="Spain", name="LaLiga", cat_id="sr:category:32",
                      tour_id="sr:tournament:8",
                      events=[mk_event("Atletico Madrid", "Osasuna")]),
    ]), found)

    check("all events collected", added, 3)
    check("two competitions", len(found), 2)

    efl = found[("sr:category:1", "sr:tournament:21")]
    check("EFL Cup holds its own two", len(efl.events), 2)
    check("and is labelled from the feed", efl.label, "England / EFL Cup")
    check("ids read back as plain integers", efl.numeric_ids, (1, 21))

    # A second page adds to the same competition rather than replacing it.
    _collect(mk_payload([mk_tournament(events=[mk_event("Coventry City", "Aston Villa")])]),
             found)
    check("a later page appends", len(found[("sr:category:1", "sr:tournament:21")].events), 3)
    check("without creating a duplicate competition", len(found), 2)


def test_simulated_are_excluded() -> None:
    print("\ntest: simulated fixtures never enter the pipeline")

    # SportyBet runs engine-generated matches between real clubs, priced and
    # bookable. Observed 2026-09-16: "LaLiga SRL -- Atletico Madrid SRL v
    # Osasuna SRL" at 08:00, a simulation of the same card as the real 17:00
    # fixture. Nothing downstream tells them apart.
    check_true("category id is excluded",
               is_simulated("Simulated Reality League", "sr:category:2123", "LaLiga SRL"))
    check_true("category name is excluded, whatever its id",
               is_simulated("Simulated Reality League", "sr:category:9999", "LaLiga SRL"))
    check_true("an SRL tournament under any category is excluded",
               is_simulated("Spain", "sr:category:32", "Copa Libertadores SRL"))

    check_false("the real LaLiga is untouched",
                is_simulated("Spain", "sr:category:32", "LaLiga"))
    check_false("the real Europa League is untouched",
                is_simulated("International Clubs", "sr:category:393", "UEFA Europa League"))

    # And the filter is applied where competitions are built, not left to the
    # caller to remember.
    found: dict = {}
    _collect(mk_payload([
        mk_tournament(category="Simulated Reality League", name="LaLiga SRL",
                      cat_id="sr:category:2123", tour_id="sr:tournament:32219",
                      events=[mk_event("Atletico Madrid SRL", "Osasuna SRL")]),
        mk_tournament(category="Spain", name="LaLiga", cat_id="sr:category:32",
                      tour_id="sr:tournament:8",
                      events=[mk_event("Atletico Madrid", "Osasuna")]),
    ]), found)
    check("only the real competition survives collection", len(found), 1)
    check("and it is the real one",
          found[("sr:category:32", "sr:tournament:8")].tournament, "LaLiga")


def test_olp_names() -> None:
    print("\ntest: competitions map to the names the framework indexes on")

    # The feed's spelling differs from ours; these are the pairs seen live.
    check("LaLiga -> La Liga", olp_league_name("Spain", "LaLiga"), "La Liga")
    check("UEFA Europa League -> Europa League",
          olp_league_name("International Clubs", "UEFA Europa League"), "Europa League")
    check("EFL Cup", olp_league_name("England", "EFL Cup"), "EFL Cup")

    # Where SPORTYBET_LEAGUES holds several names for one competition, the
    # canonical one wins -- the one the rest of the codebase indexes on. A
    # length or alphabetical tie-break picks the alias here.
    check("Liga Portugal -> Primeira Liga",
          olp_league_name("Portugal", "Liga Portugal"), "Primeira Liga")
    check("Allsvenskan -> Swedish Allsvenskan",
          olp_league_name("Sweden", "Allsvenskan"), "Swedish Allsvenskan")
    check("Super League -> Swiss Super League",
          olp_league_name("Switzerland", "Super League"), "Swiss Super League")
    check("Pro League -> Belgian Pro League",
          olp_league_name("Belgium", "Pro League"), "Belgian Pro League")

    # An unknown competition is reported unknown, never guessed at the nearest
    # name. "Egypt Second Division B" must not become "Serie B".
    check("unmapped stays unmapped",
          olp_league_name("Egypt", "Egypt Second Division B"), None)
    check("Italian regional groups are not Serie A",
          olp_league_name("Italy", "Serie D, Group G"), None)


def test_to_cached_fixtures() -> None:
    print("\ntest: a competition converts to cache rows")

    comp = Competition("England", "EFL Cup", "sr:category:1", "sr:tournament:21",
                       events=[_parse_event(mk_event("Everton", "Wolves"))])
    rows = to_cached_fixtures(comp)
    check("one row", len(rows), 1)
    row = rows[0]
    check("labelled with the OLP name", row.league, "EFL Cup")
    check("id is SportyBet's game id", row.id, "22929")
    check("price carried as 1x2", row.raw_market["1x2"],
          {"home": 1.52, "draw": 4.77, "away": 6.55})
    check("Betradar id travels with the row",
          row.raw_market["event_id"], "sr:match:74158489")
    check("provenance recorded", row.raw_market["source"], "sportybet_api")

    # An unmapped competition must raise rather than invent a league label --
    # a cache file is keyed by league name and a wrong key is contamination.
    unmapped = Competition("Egypt", "Egypt Second Division B",
                           "sr:category:111111160", "sr:tournament:111111118050",
                           events=[_parse_event(mk_event())])
    try:
        to_cached_fixtures(unmapped)
        check("unmapped competition refuses to cache", "no raise", "ValueError")
    except ValueError:
        check("unmapped competition refuses to cache", "ValueError", "ValueError")


def test_priced_split() -> None:
    print("\ntest: priced and unpriced fixtures are counted apart")

    comp = Competition("England", "EFL Cup", "sr:category:1", "sr:tournament:21",
                       events=[_parse_event(mk_event("Everton", "Wolves")),
                               _parse_event(mk_event("Man Utd", "Brighton", markets=[]))])
    check("two fixtures", len(comp.events), 2)
    check("one of them priced", len(comp.priced_events), 1)
    check_true("competition is mapped", comp.is_mapped)


if __name__ == "__main__":
    test_1x2_parsing()
    test_event_parsing()
    test_collect_groups_by_tournament()
    test_simulated_are_excluded()
    test_olp_names()
    test_to_cached_fixtures()
    test_priced_split()

    print()
    if FAILURES:
        print(f"=== {len(FAILURES)} FAILURE(S) ===")
        for f in FAILURES:
            print(f"  - {f}")
        sys.exit(1)
    print("=== all passed ===")
