"""The reverse-precedence block in booking/team_map.py.

SPORTYBET_TEAMS maps model key -> SportyBet name, and _MODEL_BY_SPORTYBET is
built from it with setdefault, so for any SportyBet spelling the FIRST entry
wins the reverse lookup. Several clubs have more than one entry claiming the
same SportyBet name, and for these the later one was winning with a key the
Dixon-Coles fit has never heard of.

Found 2026-09-16: of the four La Liga fixtures that evening only one could be
priced. Every club involved was rated by the model; the whole gap was here.

Plain script, no pytest (repo convention):
    py -3.12 tests/team_map_reverse_precedence_test.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from booking.team_map import SPORTYBET_TEAMS, resolve_team_to_model  # noqa: E402

FAILURES: list[str] = []


def check(label: str, got, want) -> None:
    if got == want:
        print(f"  [OK] {label}")
    else:
        print(f"  [FAIL] {label}: got {got!r}, want {want!r}")
        FAILURES.append(label)


def test_reverse_resolves_to_football_data_keys() -> None:
    print("\ntest: SportyBet spellings resolve to real football-data keys")

    # Left: exactly what SportyBet's feed returns. Right: the key football-data
    # uses, which is what engine.dixon_coles fits on.
    CASES = [
        ("Athletic Bilbao",          "Ath Bilbao"),
        ("Atletico Madrid",          "Ath Madrid"),
        ("RC Deportivo de A Coruna", "La Coruna"),
        ("Racing Santander",         "Santander"),
    ]
    for sb_name, model_key in CASES:
        check(f"{sb_name} -> {model_key}", resolve_team_to_model(sb_name), model_key)


def test_precedence_block_is_first() -> None:
    print("\ntest: the block stays ahead of the entries it overrides")

    # Order is the mechanism, not a formatting preference: move these below the
    # conflicting entries and the reverse lookup silently reverts. The rest of
    # the file is alphabetical, so nothing but this test protects the position.
    keys = list(SPORTYBET_TEAMS)
    for model_key in ("Ath Bilbao", "Ath Madrid", "La Coruna", "Santander"):
        check(f"{model_key} present", model_key in SPORTYBET_TEAMS, True)

    # "Athletic Club" is a legitimate forward mapping -- it is how the fixtures
    # feed spells the club (see engine/cross_league.py) -- so it must still be
    # in the table. It simply must not win the reverse lookup for
    # "Athletic Bilbao".
    check("the phantom-key entry is still present for forward lookups",
          "Athletic Club" in SPORTYBET_TEAMS, True)
    check("but it does not win the reverse",
          resolve_team_to_model("Athletic Bilbao") != "Athletic Club", True)

    if "Athletic Club" in keys and "Ath Bilbao" in keys:
        check("Ath Bilbao is declared before Athletic Club",
              keys.index("Ath Bilbao") < keys.index("Athletic Club"), True)


def test_flashscore_spellings_resolve_too() -> None:
    print("\ntest: the FlashScore spelling family resolves as well")

    # FlashScore is the PRIMARY fixtures source (priority 9) and names clubs
    # differently from SportyBet. SPORTYBET_TEAMS is model_key -> name, so one
    # model key holds exactly ONE spelling; adding these there OVERWRITES the
    # SportyBet one (it did, on the first attempt -- "Athletic Bilbao" stopped
    # resolving the moment "Ath. Bilbao" was added beside it). They live in
    # EXTRA_REVERSE_ALIASES instead.
    CASES = [
        ("A Coruna",       "La Coruna"),
        ("Ath. Bilbao",    "Ath Bilbao"),
        ("Atl. Madrid",    "Ath Madrid"),
        ("Celta Vigo",     "Celta"),
        ("Rayo Vallecano", "Vallecano"),
        ("Real Sociedad",  "Sociedad"),
        ("Nottm Forest",   "Nott'm Forest"),
        ("AS Roma",        "Roma"),
        ("Lecce",          "Lecce"),
        ("Torino",         "Torino"),
        ("Venezia",        "Venezia"),
    ]
    for feed_name, model_key in CASES:
        check(f"{feed_name} -> {model_key}",
              resolve_team_to_model(feed_name), model_key)


def test_both_spelling_families_coexist() -> None:
    print("\ntest: adding one feed's spellings does not displace the other's")

    # This is the regression that the separate table exists to prevent: both
    # names for the SAME club must resolve to the SAME model key.
    PAIRS = [
        ("Athletic Bilbao",          "Ath. Bilbao", "Ath Bilbao"),
        ("Atletico Madrid",          "Atl. Madrid", "Ath Madrid"),
        ("RC Deportivo de A Coruna", "A Coruna",    "La Coruna"),
    ]
    for sportybet, flashscore, model_key in PAIRS:
        check(f"SportyBet {sportybet!r}", resolve_team_to_model(sportybet), model_key)
        check(f"FlashScore {flashscore!r}", resolve_team_to_model(flashscore), model_key)


def test_aliases_win_the_reverse_lookup() -> None:
    print("\ntest: the explicit alias table beats a derived entry")

    from booking.team_map import EXTRA_REVERSE_ALIASES, _MODEL_BY_SPORTYBET

    # Merged before the derived entries precisely so a stale derived mapping
    # cannot displace a verified one -- "Lecce" derived to "US Lecce" before.
    for feed_name, model_key in EXTRA_REVERSE_ALIASES.items():
        check(f"{feed_name!r} kept its alias",
              _MODEL_BY_SPORTYBET.get(feed_name), model_key)


def test_unknown_names_are_unchanged() -> None:
    print("\ntest: an unmapped name is returned unchanged, never guessed")

    # HR35. resolve_team_to_model is exact + normalized-exact only; attaching a
    # real price to the wrong club is worse than an honest NO DATA — PENDING.
    for made_up in ("Nonexistent Rovers FC", "Placeholder United"):
        check(f"{made_up} returned unchanged",
              resolve_team_to_model(made_up), made_up)


if __name__ == "__main__":
    test_reverse_resolves_to_football_data_keys()
    test_precedence_block_is_first()
    test_flashscore_spellings_resolve_too()
    test_both_spelling_families_coexist()
    test_aliases_win_the_reverse_lookup()
    test_unknown_names_are_unchanged()

    print()
    if FAILURES:
        print(f"=== {len(FAILURES)} FAILURE(S) ===")
        for f in FAILURES:
            print(f"  - {f}")
        sys.exit(1)
    print("=== all passed ===")
