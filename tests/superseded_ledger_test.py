"""
Every code that went out stays graded (Architect 2026-10-09: "all codes that
were generated should be kept for verification"). A rewrite of a day's
ledger that drops codes (a --refreeze) archives the old ledger under
output/picks/superseded/, which grade_all reads and the scorecard does not.
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine import picks_ledger as pl

with tempfile.TemporaryDirectory() as tmp:
    pl.LEDGER_DIR, pl.SUPERSEDED_DIR = Path(tmp), Path(tmp) / "superseded"
    path = pl.LEDGER_DIR / "picks_2026-10-09.json"
    old = {"date": "2026-10-09", "generated_at": "2026-10-08T20:51:54Z", "singles": [],
           "accas": [{"name": "Acca A", "code": "XBBKK0", "legs": [], "result": None}]}
    path.write_text(json.dumps(old), encoding="utf-8")
    same = dict(old, generated_at="2026-10-09T05:50:00Z")
    pl._archive_if_codes_change(path, same)
    assert not pl.SUPERSEDED_DIR.exists(), "same codes: nothing archived"
    new = dict(old, accas=[{"name": "Acca A", "code": "Q13HC7", "legs": [], "result": None}])
    pl._archive_if_codes_change(path, new)
    kept = list(pl.SUPERSEDED_DIR.glob("picks_2026-10-09_*.json"))
    assert len(kept) == 1 and "XBBKK0" in kept[0].read_text(encoding="utf-8"), kept

src = (Path(__file__).parent.parent / "engine" / "picks_ledger.py").read_text(encoding="utf-8")
assert 'SUPERSEDED_DIR.glob("picks_*.json")' in src.split("def grade_all")[1].split("\ndef ")[0], \
    "grade_all grades superseded ledgers too"
assert "_archive_if_codes_change(path, doc)" in src, "write_ledger archives before overwriting"
print("superseded_ledger_test: OK")

# Combined codes (Architect 2026-10-09): one slip for every acca / alt / value
_rd = (Path(__file__).parent.parent / "run_daily.py").read_text(encoding="utf-8")
assert '"accas_mega"' in _rd and '"alts_mega"' in _rd and '"value_mega"' in _rd, "combined codes booked"
_pb = (Path(__file__).parent.parent / "output" / "produce_bet.py").read_text(encoding="utf-8")
assert "ACCAS MEGA:" in _pb and "ALT MEGA:" in _pb and "VALUE MEGA:" in _pb, "combined codes in ALL CODES"
with tempfile.TemporaryDirectory() as tmp:
    pl.LEDGER_DIR, pl.SUPERSEDED_DIR = Path(tmp), Path(tmp) / "superseded"
    doc = {"date": "2026-10-01", "singles": [],
           "accas": [{"name": "Acca A", "legs": [], "result": "won"},
                     {"name": "Acca B", "legs": [], "result": "lost"}],
           "combined": [{"name": "ACCAS MEGA", "of": "accas", "code": "X", "result": None}]}
    (pl.LEDGER_DIR / "picks_2026-10-01.json").write_text(json.dumps(doc), encoding="utf-8")
    pl.grade_all([], today="2026-10-05")
    out = json.loads((pl.LEDGER_DIR / "picks_2026-10-01.json").read_text(encoding="utf-8"))
    assert out["combined"][0]["result"] == "lost", out["combined"]
print("combined codes: OK")

# TABLE 3D · BTTS (Architect 2026-10-10)
from types import SimpleNamespace as _NS
from output import produce_bet as _pb
def _bfx(i, praw, price, src="model"):
    return _NS(fixture=f"H{i} v A{i} (Serie A)", probs=_NS(p_btts_yes=praw, home_team=f"H{i}", away_team=f"A{i}"),
               prob_source=src, btts_price=price, kickoff_date="2026-10-11", kickoff_utc=None)
_brd = [_bfx(0, 0.80, 1.55), _bfx(1, 0.78, 1.60), _bfx(2, 0.30, 1.50), _bfx(3, 0.80, 2.40),
        _bfx(4, 0.80, 1.55, "market"), _bfx(5, 0.79, None)]
_bt = _pb._build_btts(_brd)
assert _bt and [r[0].fixture[:2] for r in _bt[0][1]] == ["H0", "H1"], _bt
assert all(r[2] >= _pb.BTTS_MIN and 1.20 <= r[4] <= 2.00 for r in _bt[0][1])
assert _pb._build_btts(_brd[:1]) == [], "one BTTS game is not a slip"
_rd2 = (Path(__file__).parent.parent / "run_daily.py").read_text(encoding="utf-8")
assert 'extra_codes["btts"]' in _rd2 and "btts=_btts_l(board)" in _rd2
_b3 = (Path(__file__).parent.parent / "output" / "bet365_board.py").read_text(encoding="utf-8")
assert "_build_btts(board)" in _b3, "bet365 board lists the BTTS games"
print("BTTS table: OK")
# Value first (Architect 2026-10-10): Acca A takes the best-value legs
from types import SimpleNamespace as _VNS
from output import produce_bet as _vpb
_vb = [_VNS(fixture=f"V{i} v W{i} (Serie A)", best_price=pr, probs=None)
       for i, pr in enumerate([1.20, 1.45, 1.25, 1.50])]
_vlegs = [(b, "pick", ch) for b, ch in zip(_vb, [0.86, 0.80, 0.84, 0.76])]
_orig_legs, _orig_s3 = _vpb._acca_legs, _vpb._build_safe3
try:
    _vpb._acca_legs = lambda sl: list(_vlegs)
    _vpb._build_safe3 = lambda sl: []
    _accs = _vpb._build_accas([])
    _first = [l[0].fixture[:2] for l in _accs[0][1]]
    assert _first[0] == "V1", _first      # 0.80 x 1.45 = 1.16, the best value, goes first
finally:
    _vpb._acca_legs, _vpb._build_safe3 = _orig_legs, _orig_s3
print("value-first accas: OK")
