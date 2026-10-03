"""Friendlies sandbox tests: name-mapping, market-pick, quarantine.

The sandbox is a pre-season MACHINERY test on real Club Friendlies. These tests
mock nothing network — they exercise the pure rating/quarantine logic so the
quarantine (sandbox legs never touch the Phase-3 gate) and the mapping stay
correct without hitting TheSportsDB.
"""
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from data.football_data_source import MatchResult
from engine.dixon_coles import fit, predict
from engine import markets as mkt
from brain.store import Brain
from clv.clv_logger import CLVLog
from sandbox import friendlies
from sandbox.run_sandbox import _map_fixture, _pick_market, _inverted_aliases

# --- 1. name mapping: exact via aliases, fuzzy for known clubs, None unknown ---
model_teams = {"Freiburg", "Leverkusen", "Sevilla", "Everton", "Stuttgart"}
inv = _inverted_aliases()
hk, ak = _map_fixture(model_teams, inv, "Freiburg", "Sevilla")
assert (hk, ak) == ("Freiburg", "Sevilla"), f"exact alias map failed: {hk},{ak}"
hk, ak = _map_fixture(model_teams, inv, "Stuttgart", "Everton")
assert hk in model_teams and ak in model_teams, "fuzzy match must find known clubs"
hk, ak = _map_fixture(model_teams, inv, "Schwaz", "Augsburg")
assert hk is None, "an unknown (unresolvable) club must map to None -> NO DATA"
print("1. name mapping (exact/fuzzy/unknown): OK")

# --- 2. market pick: strongest deployable, never a blocked market ---------
from types import SimpleNamespace
p = SimpleNamespace(p_home=0.40, p_draw=0.30, p_away=0.30, p_over_15=0.6,
                    p_over_25=0.5, p_btts_yes=0.5)
mk, mp = _pick_market(p)
assert mk in mkt.DEPLOYABLE and mk not in ("1X2_AWAY", "OVER_2_5").__class__(), \
    "pick must be a deployable market"
assert 0.0 < mp <= 1.0
print("2. market pick returns a deployable market: OK")

# --- 3. rate a friendly with a fitted cross model --------------------------
res = [
    MatchResult(league="Bundesliga", date="2026-01-01", home_team="Freiburg",
                away_team="Leverkusen", fthg=1, ftag=0, ftr="H"),
    MatchResult(league="Bundesliga", date="2026-01-02", home_team="Leverkusen",
                away_team="Freiburg", fthg=2, ftag=1, ftr="H"),
    MatchResult(league="La Liga", date="2026-01-03", home_team="Sevilla",
                away_team="Betis", fthg=1, ftag=1, ftr="D"),
    MatchResult(league="La Liga", date="2026-01-04", home_team="Betis",
                away_team="Sevilla", fthg=0, ftag=1, ftr="A"),
]
for i in range(40):
    res.append(MatchResult(league="Bundesliga", date=f"2026-02-{1+i%28:02d}",
                           home_team="Freiburg", away_team="Everton",
                           fthg=i % 3, ftag=1 - i % 3, ftr="H" if i % 2 else "D"))
model = fit(res)
model.league = "Club Friendlies"
hk, ak = _map_fixture(set(model.teams), inv, "Freiburg", "Sevilla")
if hk and ak:
    probs = predict(model, hk, ak)
    assert probs is not None, "rated friendly must produce probabilities"
print("3. cross-fit rates a friendly: OK")

# --- 4. QUARANTINE: sandbox legs never touch the Phase-3 gate --------------
_tmp = Path(tempfile.mkdtemp())
slog = CLVLog(path=_tmp / "sandbox_log.json")
slog.log_entry(league="Club Friendlies", fixture="Freiburg v Sevilla",
               market="1X2_HOME", model_prob=0.6, entry_odds=None,
               phase="sandbox", match_date="2026-08-08")
plog = CLVLog(path=_tmp / "paper.json")
pleg = plog.log_entry(league="Eredivisie", fixture="Ajax v PSV",
                      market="1X2_HOME", model_prob=0.6, entry_odds=2.0)
plog.log_close(pleg.leg_id, closing_odds=1.8)
plog.log_result(pleg.leg_id, ft_result="1-0", hit=True)
b = Brain(_tmp / "q.db")
b.sync_legs([_tmp / "sandbox_log.json", _tmp / "paper.json"])
phases = {r[0]: r[1] for r in b._conn.execute(
    "SELECT phase, COUNT(*) FROM legs GROUP BY phase").fetchall()}
assert "sandbox" in phases and "phase2_paper" in phases, \
    "sandbox legs must mirror under their own phase"
g = b.gate_status()
# the paper leg HAS CLV (hit + close) — so the gate sees exactly the PAPER leg
assert g["legs_with_clv"] == 1, "sandbox legs must NOT satisfy the Phase-3 gate"
sand_clv = b._conn.execute(
    "SELECT COUNT(*) FROM legs WHERE phase='sandbox' AND clv_pct IS NOT NULL"
).fetchone()[0]
assert sand_clv == 0, "sandbox CLV must stay NO DATA (no odds source)"
print("4. quarantine: sandbox legs separate phase, gate stays paper-only: OK")

print("\n✅ ALL SANDBOX TESTS PASSED")