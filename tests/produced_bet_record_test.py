"""PRODUCED-BET RECORD tests — the ID415 produced-bet JSON + brain mirror.

Regression for the `pick_market` KeyError: `_leg_from_board` must write the
schema-v6 `pick_market` column (canonical key of the fixture's best EV market,
falling back to the 1X2 result pick), or `brain.sync_produced_bets` raises
KeyError('pick_market') on every run that has a rated fixture today — and the
produced-bet brain mirror silently never syncs (the JSON itself was already
written). Covers the record path end-to-end on a throwaway brain.

Run directly:  PYTHONIOENCODING=utf-8 py -3.12 tests/produced_bet_record_test.py
"""
from __future__ import annotations

import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent))

from bets import produced_bet
from brain.store import Brain
from output.produce_bet import BoardFixture
from verification.id403 import verify

TODAY = date.today().isoformat()


def _probs(home, away, h=0.55, d=0.25, a=0.20):
    return SimpleNamespace(
        home_team=home, away_team=away,
        lambda_home=1.4, lambda_away=1.0,
        p_home=h, p_draw=d, p_away=a,
        p_over_15=0.8, p_over_25=0.5, p_over_35=0.3, p_btts_yes=0.5,
        modal_scoreline=(1, 0))


def _bf(fixture, probs, day=TODAY, best_market_key="OVER_1_5"):
    return BoardFixture(
        fixture=fixture, probs=probs, verification=verify([]),
        on_deploy_shortlist=True, kickoff_date=day,
        best_market_key=best_market_key, best_price=1.8,
        best_model_prob=0.8, best_mes_ev=0.44,
        best_market="Over 1.5 goals")


def _check(name, cond, detail=""):
    assert cond, f"{name} FAILED {detail}"
    print(f"  ✓ {name}")


# --- 0. redirect BOARD_DIR to a tempdir (never touch real output/boards) ----
_tmp = Path(tempfile.mkdtemp(prefix="olp_xdv_produced_test_"))
produced_bet.BOARD_DIR = _tmp / "boards"
produced_bet.BOARD_DIR.mkdir(parents=True, exist_ok=True)

# --- 1. record path no longer raises; mirror row carries pick_market --------
db = _tmp / "t1.db"
b = Brain(db)

# Two rated fixtures today: one with a best EV market key, one unpriced (so its
# pick_market must fall back to the 1X2 result pick).
rated = _bf("Hellas Verona v Genoa", _probs("Hellas Verona", "Genoa"),
            best_market_key="OVER_1_5")
unpriced = BoardFixture(
    fixture="Cittadella v Pisa", probs=_probs("Cittadella", "Pisa", 0.1, 0.2, 0.7),
    verification=verify([]), on_deploy_shortlist=False, kickoff_date=TODAY,
    best_market_key=None, best_price=None, best_model_prob=None,
    best_mes_ev=None, best_market=None)
off_day = _bf("Treviso v Conegliano", _probs("Treviso", "Conegliano"),
              day=(date.today() + timedelta(days=1)).isoformat())  # excluded

try:
    rec = produced_bet.record_produced_bet([rated, unpriced, off_day], TODAY, b)
except Exception as e:
    raise AssertionError(f"record_produced_bet raised {e!r}") from e

_check("record produced with 2 legs (off-day excluded)",
       rec["produced"] and rec["n_legs"] == 2)

# JSON leg shape: pick_market present on every leg.
priced, plain = rec["legs"][0], rec["legs"][1]
_check("priced leg pick_market == best EV market key",
       priced.get("pick_market") == "OVER_1_5", str(priced.get("pick_market")))
_check("unpriced leg pick_market falls back to 1X2 result pick",
       plain.get("pick_market") == "1X2_AWAY", str(plain.get("pick_market")))

# Brain mirror rows landed (sync no longer raises) with the same keys.
rows = b.query(
    "SELECT fixture, pick, pick_market FROM produced_bets WHERE date=? "
    "ORDER BY fixture", (TODAY,))
_check("brain mirror has 2 produced_bets rows", len(rows) == 2, str(rows))
by_fx = {r["fixture"]: r for r in rows}
_check("mirror pick_market matches record",
       by_fx["Hellas Verona v Genoa"]["pick_market"] == "OVER_1_5"
       and by_fx["Cittadella v Pisa"]["pick_market"] == "1X2_AWAY", str(rows))

# --- 2. legacy record (no pick_market key) still syncs defensively ----------
db2 = _tmp / "t2.db"
b2 = Brain(db2)
legacy = [{"date": TODAY, "leg_id": "Feyenoord v Ajax_1X2_HOME",
           "fixture": "Feyenoord v Ajax", "league": "Eredivisie",
           "pick": "1X2_HOME", "pick_name": "Feyenoord to win", "model_prob": 0.6,
           "on_deploy_shortlist": True, "best_market": "Feyenoord to win",
           "best_price": 1.9, "best_mes_ev": 0.14, "kickoff_date": TODAY,
           "ft_result": None, "hit": None, "settled": False}]
try:
    n = b2.sync_produced_bets(legacy)
except Exception as e:
    raise AssertionError(f"sync_produced_bets legacy raised {e!r}") from e
_check("legacy row syncs (pick_market fallback to pick)", n == 1)
rows2 = b2.query(
    "SELECT pick, pick_market FROM produced_bets WHERE date=?", (TODAY,))
_check("legacy mirror pick_market == pick",
       rows2 and rows2[0]["pick_market"] == "1X2_HOME", str(rows2))

b.close()
b2.close()
print("\nALL PRODUCED-BET RECORD TESTS PASSED")
