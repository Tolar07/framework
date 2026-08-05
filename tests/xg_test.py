"""xG third opinion tests: Understat source, engine prediction, wiring.

The source is mocked (no network): the test verifies the Understat response
shape parsing, team-name alias resolution, the Poisson-based prediction, the
BoardFixture wiring, the compact-board xG line, and that xG rows land in the
brain's predictions table under model_engine='xg'.
"""
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).parent.parent))

import orchestrator
from brain.store import Brain
from data import xg_source
from output.produce_bet import BoardFixture, _compact_fixture, _short_fixture

_tmp = Path(tempfile.mkdtemp(prefix="olp_xdv_xg_test_"))


# --- 1. Understat response parsing ------------------------------------------
def _fake_understat():
    """A minimal Understat response: 4 teams, each with a history of results."""
    def team(tid, title, xg_list, xga_list):
        return {"id": str(tid), "title": title,
                "history": [{"xG": x, "xGA": xa, "result": "w",
                             "scored": round(x), "missed": round(xa)}
                            for x, xa in zip(xg_list, xga_list)]}
    return {
        "teams": {
            "1": team(1, "Bayern Munich", [2.5, 3.0, 2.0], [0.5, 0.8, 0.6]),
            "2": team(2, "Borussia Dortmund", [1.5, 2.0, 1.0], [1.0, 1.2, 0.8]),
            "3": team(3, "RB Leipzig", [1.8, 1.5, 2.2], [0.9, 1.1, 0.7]),
            "4": team(4, "Hamburger SV", [0.8, 1.0, 0.6], [2.0, 2.5, 1.8]),
        },
        "dates": [],
    }


class _FakeCache:
    """Writes + reads from a fake cache dir keyed on path."""

    def __init__(self):
        self.store = {}

    def get(self, key):
        return self.store.get(key)

    def set(self, key, val):
        self.store[key] = val


# Mock _read_cache to bypass the real cache (we feed synthetic data directly)
_fake_cache = _FakeCache()
_orig_read = xg_source._read_cache
_orig_fetch = xg_source._fetch_understat
_orig_write = xg_source._write_cache
xg_source._read_cache = lambda league, season: _fake_cache.get(f"{league}{season}")
xg_source._write_cache = lambda league, season, data: _fake_cache.set(f"{league}{season}", data)
xg_source._fetch_understat = lambda league, season: _fake_understat()


def _reset():
    _fake_cache.store.clear()


# --- fit_xg parses the response -------------------------------------------------
_reset()
ratings = xg_source.fit_xg("Bundesliga", "2526")
assert len(ratings) == 4, f"expected 4 teams, got {len(ratings)}"
bav = ratings["Bayern Munich"]
assert abs(bav.xg_attack - 2.5) < 1e-9, f"avg xG wrong: {bav.xg_attack}"
assert abs(bav.xg_defence - 0.63333333333) < 1e-9, f"avg xGA wrong: {bav.xg_defence}"
assert bav.n_matches == 3
print("1. fit_xg parses Understat response: OK")

# --- 2. alias + fuzzy resolution -----------------------------------------------
_reset()
ratings = xg_source.fit_xg("Bundesliga", "2526")
# framework name 'Dortmund' -> Understat 'Borussia Dortmund'
p = xg_source.predict_xg("Dortmund", "Bayern Munich", ratings, league="Bundesliga")
assert p is not None, "alias resolution failed for Dortmund"
assert 0 < p.home < 1 and 0 < p.draw < 1 and 0 < p.away < 1
assert abs(p.home + p.draw + p.away - 1.0) < 1e-6, "1X2 must sum to 1"
print("2. alias resolution (Dortmund -> Borussia Dortmund): OK")

# --- 3. unknown team -> None (HR35, never fabricated) ---------------------------
_reset()
p = xg_source.predict_xg("AC Milan", "Inter Milan", ratings, league="Bundesliga")
assert p is None, "unknown team must yield None, never a guess"
print("3. unknown team returns None (HR35): OK")

# --- 4. BoardFixture wiring through orchestrator -------------------------------
class _FakeProbs:
    home_team = "Dortmund"
    away_team = "Bayern Munich"
    p_home, p_draw, p_away = 0.45, 0.25, 0.30
    p_over_15, p_over_25, p_over_35 = 0.75, 0.55, 0.30
    p_btts_yes, lambda_home, lambda_away = 0.62, 1.6, 1.4


_reset()
ratings = xg_source.fit_xg("Bundesliga", "2526")
px = xg_source.predict_xg("Dortmund", "Bayern Munich", ratings, league="Bundesliga")
# Build a BoardFixture with xg_probs like orchestrator does
bf = BoardFixture(
    fixture="Dortmund v Bayern Munich (Bundesliga)",
    probs=_FakeProbs(),
    verification=object(),
    xg_probs=(px.home, px.draw, px.away),
)
lines = _compact_fixture(bf)
xg_line = next((l for l in lines if "xG" in l), None)
assert xg_line is not None, f"xG line missing from compact board: {lines}"
assert "xG" in xg_line and "%" not in xg_line.split("xG")[1][:0], xg_line
print(f"4. compact board xG line: '{xg_line.strip()}'")

# fixture WITHOUT xg_probs must not fabricate a line
bf_noxg = BoardFixture(
    fixture="Nijmegen v Telstar (Eredivisie)", probs=_FakeProbs(),
    verification=object(), xg_probs=None,
)
lines_noxg = _compact_fixture(bf_noxg)
assert not any("xG" in l for l in lines_noxg), f"uncovered league fabricated xG: {lines_noxg}"
print("5. uncovered league omits xG line (HR35): OK")

# --- 6. predictions land in the brain under model_engine='xg' -------------------
brain = Brain(_tmp / "xg.db")
_orig_write_brain = None
rows = [dict(run_id="xgrun", predicted_at="2026-08-05T00:00:00+00:00",
             league="Bundesliga", fixture="Dortmund v Bayern Munich",
             match_date="2026-08-05", market=m, model_engine="xg",
             model_prob=prob, entry_odds=None, bookmaker=None, ev=None,
             softness_tier="A", on_deploy_shortlist=0, cal_adjustment=None)
        for m, prob in (("1X2_HOME", px.home), ("1X2_DRAW", px.draw),
                        ("1X2_AWAY", px.away))]
n = brain.append_predictions(rows)
assert n == 3, f"expected 3 xg rows, got {n}"
res = brain.predictions_for(fixture="Dortmund v Bayern Munich", engine="xg")
assert len(res) == 3, f"expected 3 xg predictions, got {len(res)}"
assert all(r["model_engine"] == "xg" for r in res)
print("6. xG predictions land in brain under model_engine='xg': OK")

# --- 7. run_daily._predictions_from_board writes xg rows -------------------------
from run_daily import _predictions_from_board
bf_full = BoardFixture(
    fixture="Dortmund v Bayern Munich (Bundesliga)",
    probs=_FakeProbs(), verification=object(),
    xg_probs=(px.home, px.draw, px.away),
    softness_tier="A", kickoff_date="2026-08-05", model_engine="dc",
)
n2 = _predictions_from_board([bf_full], "xgrun2", "2026-08-05T00:00:00+00:00", brain)
res2 = brain.predictions_for(run_id="xgrun2", engine="xg")
assert len(res2) == 3, f"expected 3 xg rows via _predictions_from_board, got {len(res2)}"
brain.close()
print("7. _predictions_from_board writes xg rows: OK")

print("\n✅ ALL XG TESTS PASSED")