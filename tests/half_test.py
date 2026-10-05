"""First-half result markets (engine/half.py). Offline."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine import half, markets as mkt  # noqa: E402
from data.flashscore_results import _first_half  # noqa: E402

RAW = [{"id": "60", "specifier": "", "outcomes": [
            {"desc": "Home", "odds": "2.10"}, {"desc": "Draw", "odds": "2.30"},
            {"desc": "Away", "odds": "5.50"}]},
       {"id": "63", "specifier": "", "outcomes": [
            {"desc": "Home or Draw", "odds": "1.20"}, {"desc": "Home or Away", "odds": "1.60"},
            {"desc": "Draw or Away", "odds": "1.65"}]},
       {"id": "64", "specifier": "", "outcomes": [
            {"desc": "Home", "odds": "1.45"}, {"desc": "Away", "odds": "3.80"}]},
       {"id": "68", "specifier": "total=1.5", "outcomes": [{"desc": "Over 1.5", "odds": "2.5"}]}]


def test_candidates() -> None:
    probs = NS(lambda_home=1.7, lambda_away=0.9)
    c = half.candidates(RAW, probs, "Premier League", 0.25)
    keys = {x[2] for x in c}
    assert "SB:63||Home or Draw" in keys, keys                     # ~80%, @1.20
    assert all(1.20 <= x[5].price <= 2.00 and x[0] >= 0.5 for x in c)
    assert not any("68" in k for k in keys), "first-half goals are not used"
    assert half.candidates(RAW[1:], probs, "Premier League", 0.25) == [], \
        "no first-half 1X2 price -> no market anchor -> nothing"
    h, d, a = half.model_probs(1.7, 0.9, "Premier League")
    assert abs(h + d + a - 1) < 1e-9 and d > 0.3, "first halves are draw-heavy"


def test_settle_and_display() -> None:
    assert half.settle("SB:60||Home", 1, 0) == "won" and half.settle("SB:60||Draw", 1, 0) == "lost"
    assert half.settle("SB:63||Draw or Away", 0, 0) == "won"
    assert half.settle("SB:64||Home", 1, 1) == "void" and half.settle("SB:64||Away", 0, 1) == "won"
    assert half.settle("SB:60||Home", None, 0) is None, "no half-time score -> ungraded"
    assert half.is_first_half("SB:63||Home or Draw")
    assert not half.is_first_half("SB:10||Home or Draw")
    assert mkt.display("SB:63||Home or Draw", "Arsenal", "Leeds") == "Arsenal or level at half-time"
    assert mkt.display("SB:60||Away", "Arsenal", "Leeds") == "Leeds to lead at half-time"
    # Flashscore BC/BD are second-half goals: first half = full time - second half
    assert _first_half(3, "1") == 2 and _first_half(1, "2") is None and _first_half(2, None) is None


def test_ledger_settles_first_half_legs() -> None:
    from engine.picks_ledger import _settle_ev
    ev = {"fthg": 2, "ftag": 1, "fh_home": 0, "fh_away": 1}
    assert _settle_ev("SB:60||Away", ev) == "won"
    assert _settle_ev("SB:1||Home", ev) == "won", "full-time markets use the full-time score"
    assert _settle_ev("SB:60||Away", {"fthg": 2, "ftag": 1}) is None


def test_never_main_pick_or_alt_leg() -> None:
    from pipeline.odds import MarketQuote as MQ
    from output import produce_bet as pb
    bf = NS(probs=NS(home_team="A", away_team="B"), best_market_key="SB:10||Home or Draw",
            prob_source="model",
            best_model_prob=0.80, team_news=None, kickoff_date="2026-10-10",
            cand_pool=[(0.85, 0.01, "SB:63||Home or Draw", 0.86, 0.85, MQ(price=1.22)),
                       (0.62, -0.02, "SB:18|total=1.5|Over 1.5", 0.63, 0.62, MQ(price=1.55))])
    a = pb.alt_leg(bf)
    assert a and a[0] == "SB:18|total=1.5|Over 1.5", "a first-half leg is never the alt leg"
    assert pb.steadier_pick(bf) is None or not half.is_first_half(pb.steadier_pick(bf)[2])


if __name__ == "__main__":
    test_never_main_pick_or_alt_leg()
    test_candidates()
    test_settle_and_display()
    test_ledger_settles_first_half_legs()
    print("first-half markets: OK")
