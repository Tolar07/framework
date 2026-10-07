"""
Offline test of the external NBA model adapter (shadow only): read-only load
from an NBA_Betting-shaped SQLite, ESPN -> NBA_Betting team matching across the
US/UTC date gap, the opening-line guard, and the shadow scorecard split.
"""
import sqlite3
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine import nba_ext_model as xm

tmp = Path(tempfile.mkdtemp()) / "nba_betting.db"
con = sqlite3.connect(tmp)
con.executescript("""
    CREATE TABLE games (game_id TEXT PRIMARY KEY, game_datetime TEXT, home_team TEXT, away_team TEXT,
                        open_line REAL, home_score INT, away_score INT);
    CREATE TABLE predictions (game_id TEXT, model_variant TEXT, predicted_at TEXT, open_spread REAL,
                              prediction_spread REAL, home_cover_prob REAL, home_cover_pred INT,
                              predicted_margin REAL, pick TEXT, confidence REAL);
    INSERT INTO games VALUES ('202610210GSW', '2026-10-21 19:30:00', 'GSW', 'NOP', -5.5, NULL, NULL);
    INSERT INTO predictions VALUES ('202610210GSW', 'standard', '2026-10-21 09:00:00', 5.5, 5.5, 0.41, 0, 3.2, 'Away', 59);
    INSERT INTO predictions VALUES ('202610210GSW', 'vegas', '2026-10-21 09:00:00', 5.5, 5.5, 0.38, 0, 2.9, 'Away', 62);
    INSERT INTO games VALUES ('202610210BOS', '2026-10-21 19:00:00', 'BOS', 'NYK', -7.0, NULL, NULL);
    INSERT INTO predictions VALUES ('202610210BOS', 'vegas', '2026-10-21 09:00:00', 7, 7, 0.55, 1, 8.1, 'Home', 55);
""")
con.commit()
con.close()

# ESPN tips at 02:30 UTC on the 22nd; NBA_Betting dates the game the 21st (US)
rows = xm.load(tmp, [date(2026, 10, 22)])
assert len(rows) == 3, rows
m = xm.match(rows, "GS", "NO", date(2026, 10, 22))
assert set(m) == {"standard", "vegas"}, m
assert xm.match(rows, "GS", "NO", date(2026, 10, 25)) == {}, "more than a day apart: no match"
assert xm.match(rows, "NO", "GS", date(2026, 10, 22)) == {}, "home/away must not swap"
assert xm.load(tmp.parent / "missing.db", [date(2026, 10, 22)]) == []
print("read-only load + ESPN team/date matching: OK")

away = {"market_id": "223", "specifier": "hcp=-5.5", "outcome": "Away (+5.5)", "price": 1.95}
v = xm.view(away, m)
assert v["vegas"]["applies"] and v["vegas"]["agrees"] and abs(v["vegas"]["side_prob"] - 0.62) < 1e-9
far = {**away, "specifier": "hcp=-9.5", "outcome": "Away (+9.5)"}
assert not xm.view(far, m)["vegas"]["applies"], "4 points off the opening line: not comparable"
total = {"market_id": "225", "specifier": "total=221.5", "outcome": "Over 221.5", "price": 1.9}
assert not any(r["applies"] for r in xm.view(total, m).values()), "the model says nothing about totals"
assert xm.view(away, {}) is None
print("model view only on handicaps near the opening line: OK")

graded = [
    {**away, "stage": "regular", "result": "won", "ext_model": v},
    {**away, "stage": "regular", "result": "lost",
     "ext_model": xm.view({**away, "outcome": "Home (-5.5)"}, m)},
    {**away, "stage": "preseason", "result": "won", "ext_model": v},
]
s = xm.shadow_record(graded)
assert "agreed: 1 · won 1 · £1 each +0.95" in s and "disagreed: 1 · won 0 · £1 each -1.00" in s, s
print("shadow record (regular season only): OK")

print("ALL NBA EXTERNAL-MODEL TESTS PASSED")
