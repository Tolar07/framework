"""FlashScore participant names must not carry the site's progress annotations.

The regression this pins: FlashScore nests cup-progress annotations INSIDE the
participant element, and `text_content()` returns the whole subtree
concatenated. On a cup tie that produced team names like

    "ArsenalAdvancing to next round: Arsenal"
    "LiverpoolAdvancing to next round: Liverpool"

which match no model key, so the fixture is rated NO DATA — PENDING and
silently leaves the board.

Measured on 2026-09-16: 34 of 37 EFL Cup fixtures came back unrated for this
reason alone, while the model behind them (2,300 pooled matches across four
English tiers) rated 92 clubs perfectly well. The board looked like a modelling
gap and was a scraping gap.

Plain script, no pytest (repo convention):
    py -3.12 tests/flashscore_name_test.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.scrape_live_odds_v3 import (  # noqa: E402
    FLASHSCORE_NAME_ANNOTATIONS,
    clean_flashscore_team,
)

FAILURES: list[str] = []


def check(label: str, got, want) -> None:
    if got == want:
        print(f"  [OK] {label}")
    else:
        print(f"  [FAIL] {label}: got {got!r}, want {want!r}")
        FAILURES.append(label)


def check_true(label, got):
    check(label, bool(got), True)


def test_strips_the_observed_corruptions() -> None:
    print("\ntest: the exact names seen on the live EFL Cup page")

    # Every one of these was on the board on 2026-09-16 and rated NO DATA.
    CASES = [
        ("ArsenalAdvancing to next round: Arsenal", "Arsenal"),
        ("LiverpoolAdvancing to next round: Liverpool", "Liverpool"),
        ("BrentfordAdvancing to next round: Brentford", "Brentford"),
        ("Crystal PalaceAdvancing to next round: Crystal Palace", "Crystal Palace"),
        ("BournemouthAdvancing to next round: Bournemouth", "Bournemouth"),
        ("Bradford CityAdvancing to next round: Bradford City", "Bradford City"),
        ("PeterboroughAdvancing to next round: Peterborough", "Peterborough"),
    ]
    for raw, want in CASES:
        check(f"{raw[:34]!r}...", clean_flashscore_team(raw), want)


def test_clean_names_are_untouched() -> None:
    print("\ntest: an ordinary name passes through unchanged")

    for name in ("Man Utd", "Everton", "Sheffield United", "Fleetwood Town",
                 "Atletico Madrid", "RC Deportivo de A Coruna"):
        check(f"{name!r} unchanged", clean_flashscore_team(name), name)


def test_annotation_only_yields_empty() -> None:
    print("\ntest: a name that is nothing but an annotation is dropped")

    # The caller already skips a row whose team name is empty. Returning ""
    # routes an unusable row into that existing check rather than inventing a
    # team out of the annotation text (HR35).
    check("annotation alone -> empty",
          clean_flashscore_team("Advancing to next round: Arsenal"), "")
    check("empty stays empty", clean_flashscore_team(""), "")
    check("whitespace stays empty", clean_flashscore_team("   "), "")


def test_every_known_annotation_is_cut() -> None:
    print("\ntest: each annotation in the table is actually cut")

    for marker in FLASHSCORE_NAME_ANNOTATIONS:
        raw = f"Chelsea{marker} something"
        check(f"{marker!r} is cut", clean_flashscore_team(raw), "Chelsea")


def test_whitespace_from_concatenation_is_collapsed() -> None:
    print("\ntest: the whitespace concatenation leaves behind is collapsed")

    check("internal runs collapse",
          clean_flashscore_team("Manchester   City"), "Manchester City")
    check("newlines collapse",
          clean_flashscore_team("Aston\n\tVilla"), "Aston Villa")
    check("trailing space before an annotation is trimmed",
          clean_flashscore_team("Norwich Advancing to next round: Norwich"), "Norwich")


if __name__ == "__main__":
    test_strips_the_observed_corruptions()
    test_clean_names_are_untouched()
    test_annotation_only_yields_empty()
    test_every_known_annotation_is_cut()
    test_whitespace_from_concatenation_is_collapsed()

    print()
    if FAILURES:
        print(f"=== {len(FAILURES)} FAILURE(S) ===")
        for f in FAILURES:
            print(f"  - {f}")
        sys.exit(1)
    print("=== all passed ===")
