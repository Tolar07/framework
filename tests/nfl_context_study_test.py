"""NFL context study: no peeking, thin data is PENDING. No network."""
from __future__ import annotations

import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import nfl_context_study as nc  # noqa: E402


def _games(n=3000):
    rnd = random.Random(3)  # noqa: S311
    out = []
    for i in range(n):
        s = 2008 + i // 250
        out.append({"season": s, "day": f"{s}-{i % 250:03d}", "home": f"H{i % 32}", "away": f"A{(i * 7) % 32}",
                    "hs": rnd.randint(10, 35), "as": rnd.randint(10, 35),
                    "hml": rnd.choice([-150.0, -110.0, 120.0]), "aml": rnd.choice([130.0, -110.0, -140.0]),
                    "hrest": 7.0, "arest": rnd.choice([6.0, 7.0, 10.0]), "hqb": "q1", "aqb": "q2", "div": i % 3 == 0})
    return out


def test_replay_uses_only_past_games():
    g = _games()
    rows, _ = nc.replay(g, 0.005)
    g2 = [dict(x) for x in g]
    g2[-1]["hs"], g2[-1]["as"] = 99, 0
    rows2, _ = nc.replay(g2, 0.005)
    assert [r["q"] for r in rows2[:-1]] == [r["q"] for r in rows[:-1]]


def test_no_signal_stays_near_price():
    rows, w = nc.replay(_games(), 0.005)
    assert max(abs(x) for x in w) < 1.0
    assert abs(sum(r["q"] - r["fair"] for r in rows)) / len(rows) < 0.05


def test_run_counts_tries_and_reports_held_out():
    text = nc.run(_games())
    assert "Settings tried: **3**" in text and "2016" in text and "Return/bet" in text


def test_thin_data_is_pending():
    assert "PENDING" in nc.run(_games(300))


def test_load_parses_csv():
    csvt = ("season,gameday,home_team,away_team,home_score,away_score,home_moneyline,away_moneyline,home_rest,"
            "away_rest,home_qb_id,away_qb_id,div_game\n2020,2020-09-10,KC,HOU,34,20,-400,300,7,7,a,b,0\n")
    g = nc.load(csvt)
    assert len(g) == 1 and g[0]["hml"] == -400.0 and g[0]["div"] is False
