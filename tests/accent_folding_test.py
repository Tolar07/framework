"""Diacritic folding must cover every Latin script, not a curated subset.

_ACCENTS was a hand-written str.maketrans of ~30 Western European letters. It
folded "Kraków" but left Romanian, Turkish, Polish, Czech, Hungarian and Baltic
diacritics untouched, so on 2026-09-18:

    FlashScore  "Arges"          normalised to  "arges"
    TheSportsDB "Argeș Pitești"  normalised to  "argeș pitești"

never matched, and ONE Romanian fixture became two records — one VERIFIED, one
SINGLE-SOURCE. The same held for every Turkish and Polish club. That is a
whole-league class of missed verification.

A hand-written table is always incomplete; NFKD decomposition is not.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from verification.fixture_matcher import normalize_team_name as norm, names_match


@pytest.mark.parametrize("raw,expected", [
    # Romanian — comma-below, the letters that started this
    ("Argeș Pitești", "arges pitesti"),
    ("Ștefan", "stefan"),
    # Turkish — dotless i, cedilla, breve
    ("Kasımpaşa", "kasimpasa"),
    ("Beşiktaş", "besiktas"),
    ("Göztepe", "goztepe"),
    # Polish — L-stroke has NO decomposition and needs the explicit map
    ("Śląsk Wrocław", "slask wroclaw"),
    ("Wisła Kraków", "wisla krakow"),
    # Hungarian / Czech / Croatian
    ("Ferencváros", "ferencvaros"),
    ("Tikveš", "tikves"),
    # Western European, which the old table already handled — must not regress
    ("Atlético Madrid", "atletico madrid"),
    ("Mönchengladbach", "monchengladbach"),
])
def test_diacritics_fold_to_ascii(raw, expected):
    assert norm(raw) == expected


def test_folding_makes_the_real_split_fixtures_match():
    """The exact pairs that were splitting real fixtures on 2026-09-18."""
    assert names_match(norm("Argeș Pitești"), norm("Arges"))
    assert names_match(norm("Kasımpaşa"), norm("Kasimpasa"))
    assert names_match(norm("Wisła Kraków"), norm("Wisla Krakow"))


def test_folding_does_not_collapse_distinct_clubs():
    """Folding must not become a looser gate.

    The verification rule is never weakened to raise the verified count — if
    the number is low the fix is better reconciliation, never a looser match.
    """
    assert not names_match(norm("Real Madrid"), norm("Real Sociedad"))
    assert not names_match(norm("Manchester United"), norm("Manchester City"))
    assert not names_match(norm("Kaisar"), norm("Kaspii Aktau"))
    assert not names_match(norm("Sepsi"), norm("Sileks"))


def test_non_decomposing_letters_are_mapped():
    """Letters with no NFKD decomposition need the explicit table.

    NFKD turns "ó" into o + combining acute, but "ł", "ø", "đ", "ı" and "ß" are
    atomic — decomposition alone leaves them untouched.
    """
    assert norm("Łódź") == "lodz"
    assert norm("Ørsted") == "orsted"
    assert norm("Đorđe") == "dorde"
    assert "ı" not in norm("Sivasspor Iğdır")
