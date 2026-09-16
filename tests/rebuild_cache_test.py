"""Tests for booking/rebuild_cache.py — league contamination + odds extraction.

Plain script, no pytest (repo convention):
    py -3.12 tests/rebuild_cache_test.py

Covers the bugs that let one league's fixtures be written into another
league's cache file with the wrong `league` label, and the hardcoded empty
raw_market that left every fixture priceless.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from booking.rebuild_cache import (  # noqa: E402
    SPORTYBET_CATEGORY_TOURNAMENT,
    _combine_date_time,
    _extract_row_odds,
    _parse_sportybet_date,
    _resolve_direct_targets,
    _verify_league_page,
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


# --- Fakes -----------------------------------------------------------------

class FakeEl:
    def __init__(self, text: str = "", attrs: dict | None = None, children=None):
        self._text = text
        self._attrs = attrs or {}
        self._children = children or {}

    async def inner_text(self) -> str:
        return self._text

    async def get_attribute(self, name: str):
        return self._attrs.get(name)

    async def query_selector(self, sel: str):
        got = self._children.get(sel)
        return got[0] if isinstance(got, list) and got else got

    async def query_selector_all(self, sel: str):
        got = self._children.get(sel)
        if got is None:
            return []
        return got if isinstance(got, list) else [got]


class FakeLocator:
    def __init__(self, els): self._els = els
    async def all(self): return self._els


class FakePage:
    """Minimal page stand-in: a url plus a selector -> elements map."""

    def __init__(self, url: str = "", locators: dict | None = None, body: str = ""):
        self.url = url
        self._locators = locators or {}
        self._body = body

    def locator(self, sel: str):
        return FakeLocator(self._locators.get(sel, []))

    async def inner_text(self, sel: str):
        if sel == "body":
            return self._body
        raise AssertionError(
            "inner_text('body') must not be used for league verification — "
            "the sidebar names every league, so it always matches"
        )

    async def title(self):
        return ""


def row_with_odds(prices: list[str]) -> FakeEl:
    outcome_els = [FakeEl(text=p) for p in prices]
    market = FakeEl(children={".m-outcome-odds": outcome_els})
    return FakeEl(children={".market": market})


# --- Tests -----------------------------------------------------------------

def test_ids_are_correct() -> None:
    print("\ntest: SPORTYBET_CATEGORY_TOURNAMENT holds the REAL ids")

    # Derived 2026-09-16 from SportyBet's own tournament tree
    # (/api/ng/factsCenter/sportList) and each one confirmed by scraping it and
    # reading the teams back. Before that rebuild the values were shifted by
    # one row, so every league carried its neighbour's ids and scraped another
    # competition's fixtures. These assertions are the guard against that
    # shift ever returning.
    KNOWN = {
        "Premier League": (1, 17),    # England
        "Championship":   (1, 18),    # England
        "EFL Cup":        (1, 21),    # England
        "La Liga":        (32, 8),    # Spain
        "Serie A":        (31, 23),   # Italy
        "Bundesliga":     (30, 35),   # Germany
        "Ligue 1":        (7, 34),    # France
        "Europa League":  (393, 679), # International Clubs
    }
    for name, want in KNOWN.items():
        check(f"{name} -> {want}", SPORTYBET_CATEGORY_TOURNAMENT[name], want)

    # The specific mis-pairings that were live before the rebuild. Each of
    # these WAS the shipped value and each pointed at another competition.
    WAS_WRONG = {
        "Premier League": (32, 8),    # that is Spain/LaLiga
        "La Liga":        (31, 23),   # that is Italy/Serie A
        "Serie A":        (30, 35),   # that is Germany/Bundesliga
        "Bundesliga":     (7, 34),    # that is France/Ligue 1
        "Championship":   (1, 17),    # that is England/Premier League
    }
    for name, old in WAS_WRONG.items():
        check(f"{name} no longer carries its old wrong id {old}",
              SPORTYBET_CATEGORY_TOURNAMENT[name] != old, True)


def test_collision_machinery() -> None:
    print("\ntest: collision resolution still works (on synthetic data)")

    # The live table no longer collides, so this exercises the mechanism
    # itself rather than asserting against real entries -- otherwise the test
    # would silently stop testing anything the day the data got fixed.
    from booking.rebuild_cache import _competition_key

    resolved = _resolve_direct_targets()
    by_target: dict[tuple[int, int], list[str]] = {}
    for name, target in resolved.items():
        if all(target):
            by_target.setdefault(target, []).append(name)

    bad = []
    for target, names in by_target.items():
        if len(names) > 1 and len({_competition_key(n) for n in names}) > 1:
            bad.append((target, sorted(names)))
    check("no two DIFFERENT competitions share a target", bad, [])

    # Spelling aliases for one competition SHOULD share a target and must not
    # be disabled -- La Liga / LaLiga are the same Spanish league.
    check("La Liga and LaLiga share their target",
          resolved["La Liga"], resolved["LaLiga"])
    check("alias pair is left enabled", all(resolved["La Liga"]), True)


def test_verify_rejects_wrong_league() -> None:
    print("\ntest: league verification refuses the wrong page")

    # A Premier League page, while we asked for Bundesliga. The old code
    # returned True here because the body text contains every league name
    # from the sidebar.
    pl_page = FakePage(
        url="https://www.sportybet.com/ng/sport/football/sr:category:32/sr:tournament:8",
        locators={".tournament-name": [FakeEl("Premier League")]},
        body="Bundesliga Premier League La Liga Serie A Ligue 1",
    )
    got = asyncio.run(_verify_league_page(pl_page, "Bundesliga"))
    check_false("Bundesliga rejected on a Premier League page", got)

    # Same page, asked for Premier League -> accepted.
    got = asyncio.run(_verify_league_page(pl_page, "Premier League"))
    check_true("Premier League accepted on its own page", got)

    # No header at all -> cannot confirm -> refuse.
    bare = FakePage(url="https://www.sportybet.com/ng/sport/football", body="Bundesliga")
    got = asyncio.run(_verify_league_page(bare, "Bundesliga"))
    check_false("refused when no header/breadcrumb present", got)

    # Matching sr:category/sr:tournament ids in the URL must NOT be accepted as
    # proof. It is circular -- it confirms we navigated where
    # SPORTYBET_CATEGORY_TOURNAMENT pointed, not that the entry is right.
    # Caught live 2026-09-16: "La Liga" -> sr:category:31/sr:tournament:23
    # served Serie A, the URL-id check passed it, and 10 Italian fixtures were
    # written into La_Liga.json.
    got = asyncio.run(_verify_league_page(bare, "Bundesliga", (7, 34)))
    check_false("absent ids in URL do not prove the league", got)

    id_page = FakePage(
        url="https://www.sportybet.com/ng/sport/football/sr:category:7/sr:tournament:34?sort=2",
    )
    got = asyncio.run(_verify_league_page(id_page, "Bundesliga", (7, 34)))
    check_false("matching ids in URL do NOT prove the league (circular)", got)


def test_league_purity() -> None:
    print("\ntest: scraped TEAMS must belong to the requested league")
    from booking.rebuild_cache import _fixtures_match_league, MIN_LEAGUE_PURITY

    class _CF:
        def __init__(self, h, a): self.home, self.away = h, a

    def mk(pairs):
        return [_CF(h, a) for h, a in pairs]

    # The live failure: "La Liga" served a page of Serie A clubs. Both the
    # URL-id check and `.tournament-name` passed it; only the team check fails.
    serie_a = mk([("Monza", "Sassuolo"), ("Bologna", "Torino"),
                  ("Udinese", "Cagliari"), ("Roma", "Inter"),
                  ("Fiorentina", "Napoli")])
    ok, why = _fixtures_match_league("La Liga", serie_a)
    check_false("Serie A clubs rejected when La Liga was requested", ok)
    check_true("rejection explains itself", "La Liga teams" in why)

    # The second live failure: an "all football" page with 64 rows. The
    # requested league WAS the best-scoring one, so a best-match check passed
    # it. Purity is what catches it.
    mixed = mk([("Brentford", "Chelsea"), ("Tottenham", "Aston Villa"),
                ("Brighton", "Arsenal"), ("Everton", "Ipswich"),
                ("Inter", "Roma")])
    ok, _ = _fixtures_match_league("Serie A", mixed)
    check_false("mixed all-football page rejected for Serie A", ok)

    # A genuinely correct page passes.
    ok, why = _fixtures_match_league("Serie A", serie_a)
    check_true("real Serie A page accepted", ok)

    # Leagues with no squad list (continental cups) are passed through
    # unjudged rather than guessed at.
    ok, _ = _fixtures_match_league("Europa League", serie_a)
    check_true("league with no squad list is not judged", ok)

    # Empty input is not evidence of anything.
    ok, _ = _fixtures_match_league("Serie A", [])
    check_true("no fixtures -> no verdict", ok)

    check_true("purity bar is a real threshold", 0.0 < MIN_LEAGUE_PURITY <= 1.0)


def test_extract_row_odds() -> None:
    print("\ntest: 1X2 odds extraction")

    got = asyncio.run(_extract_row_odds(row_with_odds(["2.10", "3.40", "3.60"])))
    check("three valid prices parsed",
          got, {"1x2": {"home": 2.10, "draw": 3.40, "away": 3.60}})

    got = asyncio.run(_extract_row_odds(row_with_odds(["2.10", "3.40"])))
    check("fewer than three outcomes -> {}", got, {})

    got = asyncio.run(_extract_row_odds(row_with_odds(["2.10", "-", "3.60"])))
    check("unparseable price -> {}", got, {})

    got = asyncio.run(_extract_row_odds(row_with_odds(["1.00", "3.40", "3.60"])))
    check("price at 1.00 is a placeholder, not a quote -> {}", got, {})

    got = asyncio.run(_extract_row_odds(FakeEl(children={})))
    check("no .market cell -> {}", got, {})


def test_date_helpers() -> None:
    print("\ntest: date parsing and combination")

    from datetime import date, timedelta
    today = date.today()

    check("'Today' header", _parse_sportybet_date("Today"), today.isoformat())
    check("'Tomorrow' header",
          _parse_sportybet_date("Tomorrow"), (today + timedelta(days=1)).isoformat())
    check("explicit ISO date",
          _parse_sportybet_date("2026-09-16"), "2026-09-16")

    check("date + time combined",
          _combine_date_time("2026-09-16", "20:00"), "2026-09-16T20:00:00")
    check("malformed time falls back to midnight",
          _combine_date_time("2026-09-16", "LIVE"), "2026-09-16T00:00:00")
    check("out-of-range hour falls back to midnight",
          _combine_date_time("2026-09-16", "99:00"), "2026-09-16T00:00:00")


if __name__ == "__main__":
    test_ids_are_correct()
    test_collision_machinery()
    test_verify_rejects_wrong_league()
    test_league_purity()
    test_extract_row_odds()
    test_date_helpers()

    print()
    if FAILURES:
        print(f"=== {len(FAILURES)} FAILURE(S) ===")
        for f in FAILURES:
            print(f"  - {f}")
        sys.exit(1)
    print("=== all passed ===")
