"""Feed-name -> model-name resolution: the 2026-10-03 misses resolve, and
nothing ambiguous or different-club ever does."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.name_match import resolve, same_club  # noqa: E402

LEAGUE_ONE = ["AFC Wimbledon", "Barnsley", "Blackpool", "Bromley", "Cambridge",
              "Doncaster", "Oxford", "Peterboro", "Sheffield Weds", "Stevenage",
              "Stockport", "Wycombe"]


def test_real_misses_resolve():
    feed = ["Blackpool FC", "Bromley FC", "Cambridge United", "Doncaster Rovers",
            "Oxford United", "Peterborough United", "Stevenage FC",
            "Stockport County FC", "Wycombe Wanderers"]
    got = resolve(feed, LEAGUE_ONE)
    assert got == {"Blackpool FC": "Blackpool", "Bromley FC": "Bromley",
                   "Cambridge United": "Cambridge", "Doncaster Rovers": "Doncaster",
                   "Oxford United": "Oxford", "Peterborough United": "Peterboro",
                   "Stevenage FC": "Stevenage", "Stockport County FC": "Stockport",
                   "Wycombe Wanderers": "Wycombe"}, got


def test_explicit_entries():
    assert resolve(["Sheffield Wednesday"], LEAGUE_ONE) == {"Sheffield Wednesday": "Sheffield Weds"}
    assert resolve(["Sheffield Wednesday"], ["Barnsley"]) == {}   # only if the model has it


def test_other_leagues():
    assert same_club("Hellas Verona", "Verona")
    assert same_club("Ascoli Calcio 1898", "Ascoli")
    assert same_club("L.R. Vicenza", "Vicenza")
    assert same_club("SC Pisa", "Pisa")
    assert same_club("FC St. Pauli", "St Pauli")
    assert same_club("VfL 1899 Osnabruck", "Osnabruck")
    assert same_club("Energie Cottbus", "Cottbus")
    assert same_club("Forest Green Rovers", "Forest Green")
    assert same_club("York City FC", "York")


def test_different_clubs_never_match():
    assert not same_club("Bristol Rovers", "Bristol City")
    assert not same_club("Manchester United", "Man City")
    assert not same_club("Sheffield United", "Sheffield Weds")
    assert not same_club("Real Madrid", "Madrid")      # 'real' is not noise
    assert not same_club("Inter Milan", "Milan")


def test_ambiguous_stays_unmapped():
    # Two model teams fit -> no guess.
    assert resolve(["Cambridge United"], ["Cambridge", "Cambridge City"]) == {}


def test_two_feed_names_one_target_dropped():
    assert resolve(["Oxford United", "Oxford City"], ["Oxford"]) == {}


def test_target_already_used_exactly_is_dropped():
    assert resolve(["Blackpool", "Blackpool FC"], ["Blackpool"]) == {}


def test_known_names_untouched():
    assert resolve(["Blackpool"], ["Blackpool"]) == {}


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"{name}: OK")
    print("name_match_test: OK")
