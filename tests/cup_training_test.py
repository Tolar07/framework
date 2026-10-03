"""Cup-training tests: log O1.5 + priced paper legs on every cup fixture,
settle them with real results, and prove the brain learns WITHOUT the
Phase-3 capital gate counting them.

The honest rules under test:
  - O1.5 is logged on every fixture (outcome evidence), model_prob=None
    (the monitor doesn't run the DC model — a fabricated probability would
    poison the engine's hit-vs-model residual).
  - Priced markets (1X2, O2.5, U2.5) are logged ONLY where the feed quotes
    them, with the REAL price.
  - phase="cup_training" separates cup legs from the capital gate.
  - settle never overwrites, never matches the wrong fixture (HR48).
"""
import sys
import tempfile
import datetime
from pathlib import Path
from unittest import mock
sys.path.insert(0, str(Path(__file__).parent.parent))

import monitor.cup_training as ct
from clv.clv_logger import CLVLog
from brain.store import Brain

_tmp = Path(tempfile.mkdtemp(prefix="olp_xdv_cup_"))
log = CLVLog(path=_tmp / "clv.json")
brain = Brain(_tmp / "brain.db")
now = datetime.datetime(2026, 8, 6, 12, 0, 0, tzinfo=datetime.timezone.utc)

# A fake odds index with prices for the fixture pair (mapped names).
class _Q:
    def __init__(self, price, avail=True):
        self.price, self.available = price, avail
class _FX:
    def __init__(self, home, away, price):
        self.home_team, self.away_team = home, away
        self.kickoff_utc = "2026-08-06T18:45:00Z"
        self.home = _Q(price)
        self.draw = _Q(price)
        self.away = _Q(price)
        self.over25 = _Q(price)
        self.under25 = _Q(price)

index = {"Bristol City v Walsall": _FX("Bristol City", "Walsall", 1.8)}
index = {(f.home_team, f.away_team): f for f in index.values()}

# Score-feed events (odds-API names, the /scores shape).
evt_up = {"commence_time": "2026-08-06T18:45:00Z", "home_team": "Bristol City",
          "away_team": "Walsall", "completed": False, "scores": []}

# --- 1. O1.5 on every fixture, plus priced markets, phase cup_training -------
n, flags = ct.log_cup_legs(log, "EFL Cup", [evt_up], odds_index=index, now=now)
assert n == 6, f"expected O1.5 + 5 priced = 6 legs, got {n}: {flags}"
markets = {(l.market, l.entry_odds) for l in log.legs}
assert (ct.mkt.OVER_15, None) in markets, "O1.5 logged unpriced (outcome evidence)"
for m in ct.PRICED_LEGS:
    assert (m, 1.8) in markets, f"{m} should be priced at 1.8"
assert all(l.phase == ct.CUP_PHASE for l in log.legs), "phase must be cup_training"
assert all(l.model_prob is None for l in log.legs), "no fabricated model_prob"
print("1. O1.5 + priced markets logged on every fixture, phase cup_training: OK")

# --- 2. idempotent: a repeated call logs nothing new --------------------------
n2, _ = ct.log_cup_legs(log, "EFL Cup", [evt_up], odds_index=index, now=now)
assert n2 == 0, f"repeat call must be idempotent, logged {n2}"
assert len(log.legs) == n
print("2. idempotent (no duplicate legs on re-run): OK")

# --- 3. settle a completed event -> hit + CLV path + brain outcome -----------
for leg in log.legs:
    if leg.market == ct.mkt.OVER_15:
        over15_id = leg.leg_id
evt_done = {"commence_time": "2026-08-06T20:30:00Z", "home_team": "Bristol City",
            "away_team": "Walsall", "completed": True,
            "scores": [{"position": 0, "score": "2"}, {"position": 1, "score": "1"}]}
ns, cflags = ct.settle_cup_legs(log, brain, "EFL Cup", [evt_done])
assert ns == 6, f"all 6 legs settle, got {ns}: {cflags}"
o15 = next(l for l in log.legs if l.leg_id == over15_id)
assert o15.hit is True, "2-1 -> O1.5 HIT"
assert o15.ft_result == "2-1"
assert not any(l.hit is None for l in log.legs), "every leg settled"
print("3. settled 2-1 -> O1.5 hit, all 6 legs graded: OK")

# --- 4. brain mirrors cup legs (hit evidence); gate does NOT count them ------
brain.sync_legs([_tmp / "clv.json"])
rows = brain._conn.execute(
    "SELECT COUNT(*) AS n FROM legs WHERE phase=? AND hit IS NOT NULL",
    (ct.CUP_PHASE,)).fetchone()["n"]
assert rows == 6, f"settled cup legs mirrored to brain: {rows}"
o15_hit = brain._conn.execute(
    "SELECT hit FROM legs WHERE phase=? AND market=?",
    (ct.CUP_PHASE, ct.mkt.OVER_15)).fetchone()["hit"]
assert o15_hit == 1, f"O1.5 hit evidence must reach the brain, got {o15_hit}"
# A CLOSING LINE captured on a priced leg -> CLV lands in per-market evidence.
priced = next(l for l in log.legs if l.market == ct.mkt.HOME)
log.log_close(priced.leg_id, closing_odds=1.7, closing_capture_path="CL-LIVE")
brain.sync_legs([_tmp / "clv.json"])
ev = brain.clv_by_market(phase=ct.CUP_PHASE)
assert ev, "priced cup leg with a closing line must appear in CLV evidence"
by_market = {r["market"]: r for r in ev}
assert by_market[ct.mkt.HOME]["n"] == 1 and by_market[ct.mkt.HOME]["mean_clv_pct"] is not None
# Predictions table stays EMPTY for cup legs — model_prob is NOT NULL there
# and cup legs honestly carry None (no fabricated probability).
assert brain._conn.execute("SELECT COUNT(*) AS n FROM predictions").fetchone()["n"] == 0
gate = brain.gate_status()
assert gate["legs_with_clv"] == 0, \
    f"cup legs must NEVER count toward the capital gate: {gate}"
print("4. brain mirrors cup legs; CLV lands on capture; gate untouched: OK")

# --- 5. wrong fixture/date is never settled (HR48) ---------------------------
log2 = CLVLog(path=_tmp / "clv2.json")
ct.log_cup_legs(log2, "EFL Cup", [evt_up], odds_index=index, now=now)
wrong = {"commence_time": "2026-08-06T20:30:00Z", "home_team": "Bristol City",
         "away_team": "Swindon", "completed": True,
         "scores": [{"position": 0, "score": "1"}, {"position": 1, "score": "0"}]}
ns, _ = ct.settle_cup_legs(log2, None, "EFL Cup", [wrong])
assert ns == 0, f"wrong fixture must not settle, got {ns}"
assert all(l.hit is None for l in log2.legs)
print("5. wrong fixture never settles (HR48): OK")

print("\n✅ CUP TRAINING WORKS — every cup fixture is logged, settled, and "
      "teaches the brain without touching the capital gate.")
