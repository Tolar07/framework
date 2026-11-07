from datetime import UTC, datetime

from backtest import darts_dated_study as s
from data import darts_pl_results as r

WT = """
===6 February – Night 1===
{{#invoke:bracket|8TeamBracket
| RD1= {{nowrap|1='''Quarter-finals'''}}
| RD2= {{nowrap|1='''Semi-finals'''}}
| RD1-team1   = {{PDCFlag|Anna A|avg=97}}
| RD1-score1  = 6
| RD1-team2   = {{PDCFlag|Bob B|avg=96}}
| RD1-score2  = 4
| RD2-team1   = {{PDCFlag|Anna A}}
| RD2-score1  = 6
| RD2-team2   = {{PDCFlag|Cy C}}
| RD2-score2  = 5
}}
===13 February – Night 2===
{{#invoke:bracket|8TeamBracket
| RD1= {{nowrap|1='''Quarter-finals'''}}
| RD1-team1   = {{PDCFlag|Bob B}}
| RD1-score1  = 2
| RD1-team2   = {{PDCFlag|Cy C}}
| RD1-score2  = 6
}}
===31 February – Night 3===
| RD1-team1   = {{PDCFlag|X X}}
| RD1-score1  = 6
| RD1-team2   = {{PDCFlag|Y Y}}
| RD1-score2  = 1
"""


def test_nights_get_real_dates_and_bad_date_is_skipped():
    g = r.parse_nights(WT, 2025)
    assert [(x["date"], x["home"], x["winner"]) for x in g] == [
        ("2025-02-06", "Anna A", 1), ("2025-02-06", "Anna A", 1), ("2025-02-13", "Bob B", 2)]
    assert not any(x["home"] == "X X" for x in g)


def test_failed_fetch_is_empty_not_invented():
    def boom(y):
        raise OSError("down")
    assert r.fetch_all([2025], get=boom) == []
    assert "NO DATA - PENDING" in s.render([], datetime(2026, 11, 7, tzinfo=UTC))


def _games(n):
    return [{"home": "Strong S", "away": f"Weak {i % 5}", "winner": 1, "date": f"2024-01-{i % 28 + 1:02d}",
             "kickoff_utc": f"2024-01-{i % 28 + 1:02d}-{i:03d}"} for i in range(n)]


def test_walk_forward_before_learning_and_pending_under_100():
    res = s.walk_forward(_games(40), 24.0, 1)
    assert res["scored"] > 0 and res["brier"] < 0.25 and "2024" in res["by_year"]
    assert s.verdict(res).startswith("PENDING")
    assert s.walk_forward([], 24.0, 1)["brier"] is None


def test_render_lists_every_try():
    text = s.render(_games(30), datetime(2026, 11, 7, tzinfo=UTC))
    assert text.count("\n| ") >= len(s.TRIES) + 1 and "board setting" in text
