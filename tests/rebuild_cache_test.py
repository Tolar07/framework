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

def test_direct_target_collisions() -> None:
    print("\ntest: genuinely-colliding direct-URL targets are disabled")

    resolved = _resolve_direct_targets()

    # The real contamination: two DIFFERENT competitions on one target.
    # England's Premier League and Portugal's Liga Portugal both shipped
    # pointing at sr:category:32/sr:tournament:8.
    check("Premier League disabled (collides with Liga Portugal)",
          resolved["Premier League"], (0, 0))
    check("Liga Portugal disabled (collides with Premier League)",
          resolved["Liga Portugal"], (0, 0))

    # Primeira Liga is the same competition as Liga Portugal but shipped with
    # a different target — one of the two is wrong, so both are disabled.
    check("Primeira Liga disabled (target disagrees with its alias)",
          resolved["Primeira Liga"], (0, 0))

    # Spelling aliases for ONE competition sharing a target are correct and
    # must be left working — disabling them would be a regression.
    check("La Liga preserved (alias pair, not a collision)",
          resolved["La Liga"], SPORTYBET_CATEGORY_TOURNAMENT["La Liga"])
    check("LaLiga preserved (alias pair, not a collision)",
          resolved["LaLiga"], SPORTYBET_CATEGORY_TOURNAMENT["LaLiga"])

    # Unambiguous entries are untouched.
    for name in ("Bundesliga", "Championship", "Serie A", "Serie B",
                 "Ligue 1", "Ligue 2", "La Liga 2", "EFL Cup"):
        check(f"{name} preserved", resolved[name],
              SPORTYBET_CATEGORY_TOURNAMENT[name])

    # After resolution, any target still claimed more than once must be
    # claimed only by aliases of a single competition.
    from booking.rebuild_cache import _competition_key
    by_target: dict[tuple[int, int], list[str]] = {}
    for name, target in resolved.items():
        if all(target):
            by_target.setdefault(target, []).append(name)
    bad = []
    for target, names in by_target.items():
        if len(names) > 1 and len({_competition_key(n) for n in names}) > 1:
            bad.append((target, sorted(names)))
    check("no cross-competition collisions remain", bad, [])


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

    # Direct-URL ids in the URL are accepted as proof on their own.
    got = asyncio.run(_verify_league_page(bare, "Bundesliga", (7, 34)))
    check_false("absent ids in URL do not prove the league", got)

    id_page = FakePage(
        url="https://www.sportybet.com/ng/sport/football/sr:category:7/sr:tournament:34?sort=2",
    )
    got = asyncio.run(_verify_league_page(id_page, "Bundesliga", (7, 34)))
    check_true("matching ids in URL prove the league", got)


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
    test_direct_target_collisions()
    test_verify_rejects_wrong_league()
    test_extract_row_odds()
    test_date_helpers()

    print()
    if FAILURES:
        print(f"=== {len(FAILURES)} FAILURE(S) ===")
        for f in FAILURES:
            print(f"  - {f}")
        sys.exit(1)
    print("=== all passed ===")
