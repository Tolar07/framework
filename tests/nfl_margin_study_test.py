"""NFL margin study: no peeking, thin data is PENDING. No network."""
from __future__ import annotations

import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import nfl_margin_study as nm  # noqa: E402


def _games(n=2600):
    rnd = random.Random(1)
    out = []
    for i in range(n):
        sp = rnd.choice([-7.0, -3.0, 0.0, 3.0, 7.0])
        m = rnd.choice([3, -3, 7, -7, 10, -10, 14, -14, 1, -1])
        out.append({"season": 2006 + i // 130, "day": f"{2006 + i // 130}-{i % 100:02d}", "home": f"T{i}",
                    "margin": m, "spread": sp})
    return out


def test_replay_uses_only_past_games():
    g = _games()
    p = nm.replay(g)
    assert p[0] is None and p[nm.WARMUP - 1] is None and p[nm.WARMUP] is not None
    g2 = [dict(x) for x in g]
    g2[-1]["margin"] = 99
    assert nm.replay(g2)[:-1] == p[:-1]


def test_run_counts_tries_and_reports():
    text = nm.run(_games())
    assert "Settings tried: **3**" in text and "Key-number" in text and "2016" in text


def test_thin_data_is_pending():
    assert "PENDING" in nm.run(_games(300))


def test_load_parses_csv():
    csvt = ("game_id,season,gameday,home_team,home_score,away_score,spread_line\n"
            "a,2020,2020-09-10,KC,34,20,-9.5\nb,2020,2020-09-11,X,1,2,\n")
    g = nm.load(csvt)
    assert len(g) == 1 and g[0]["margin"] == 14 and g[0]["spread"] == -9.5
