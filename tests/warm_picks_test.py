"""Warm-up picks on the new-sport boards (Architect 2026-11-08 23:17: "allow picks for them ... if the engine does not
get warmed up ... it does not learn, it does not retrain"; real money at the bots' minimum stake from the live date).

A game with no value pick gets its best side inside the band (chance 50%+) as a pick marked warm=True, at most
WARM_MAX per sport and day; a value pick still wins when there is one; MS_WARM=0 turns warm-up picks off; the
value picks' record is kept apart from the warm-up record. Offline."""
import json
import os
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine import ice_hockey as ih  # noqa: E402
from engine import multisport as ms  # noqa: E402

NOW = datetime(2026, 11, 9, 12, tzinfo=UTC)
ELO = {"ratings": {}, "games": {}, "seen": [], "brier": [0.0, 0]}


def row(i: int, home: float = 1.70, away: float = 2.10) -> dict:
    return {"id": f"e{i}", "sport": "volleyball", "country": "Italy", "comp": "SuperLega", "home": f"Team {i}A",
            "away": f"Team {i}B", "ko": "2026-11-09T18:00:00Z",
            "sides": {"volleyball:186||Home": home, "volleyball:186||Away": away},
            "oids": {"volleyball:186||Home": "4", "volleyball:186||Away": "5"}}


def test_no_value_game_gets_a_warm_pick_capped_per_day():
    with tempfile.TemporaryDirectory() as td:
        seen, added = ms.update("volleyball", [row(i) for i in range(14)], [], ELO, NOW, folder=Path(td),
                                book=lambda s: "C")
        assert (seen, added) == (14, ms.WARM_MAX), (seen, added)
        doc = json.loads((Path(td) / "volleyball" / "ms_2026-11-09.json").read_text(encoding="utf-8"))
        p = doc["picks"][0]
        assert p["warm"] is True and p["key"] == "volleyball:186||Home", p
        assert p["source"] == "SportyBet, margin removed" and p["value"] < 0, "no value bar: below fair is allowed"
        assert p["code"] == "C" and p["paper"] is True, "paper before the live date"
        assert len(doc["games"]) == 14, "every game still recorded"


def test_side_outside_band_or_below_half_is_never_a_warm_pick():
    r = row(1, home=1.10, away=6.50)          # favourite below 1.20, outsider below 50%
    assert ms.warm_candidate(r, {}, {}) is None


def test_value_pick_beats_warm_pick():
    r = row(1, home=1.90, away=1.95)
    idx = {"ml|home": {"p": 0.56, "liq": 50}}                  # Matchbook says 56%: 1.90 x 0.56 = +6.4%
    orig = ms.canonical
    ms.canonical = lambda key: ["ml|home"] if key.endswith("Home") else ["ml|away"]
    try:
        c = ms.candidates(r, idx, {})
    finally:
        ms.canonical = orig
    assert c and not c[0].get("warm") and c[0]["source"] == "matchbook"


def test_switch_off():
    os.environ["MS_WARM"] = "0"
    try:
        with tempfile.TemporaryDirectory() as td:
            assert ms.update("volleyball", [row(1)], [], ELO, NOW, folder=Path(td), book=lambda s: "C") == (1, 0)
    finally:
        del os.environ["MS_WARM"]


def test_records_kept_apart():
    docs = [("d", {"picks": [{"result": "won", "pnl": 0.8, "warm": True}, {"result": "lost", "pnl": -1.0},
                             {"result": "lost", "pnl": -1.0, "warm": True}], "games": {}})]
    sb = ms.scoreboard(docs)
    assert sb["picks"] == 1 and sb["pnl"] == -1.0, "value record holds value picks only"
    assert sb["warm"] == {"picks": 2, "won": 1, "pnl": -0.2}
    sb = ih.scoreboard(docs)
    assert sb["picks"] == 1 and sb["warm"]["picks"] == 2


def test_ice_hockey_warm_candidate():
    r = {"sides": {"H:406||Home": 1.65, "H:406||Away": 2.25}}
    c = ih.warm_candidate(r, {}, {})
    assert c and c["warm"] and c["key"] == "H:406||Home" and 0.5 <= c["fair"] < 0.6


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("warm_picks_test OK")
