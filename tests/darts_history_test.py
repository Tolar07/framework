from datetime import UTC, datetime

from backtest import darts_history_study as h
from data import darts_results as r

WT = """
| RD1 = {{nowrap|1='''First round''' <br>(best of 5 sets) <ref>the second source</ref>}}
| RD2 = {{nowrap|1='''Second round'''}}
| RD1-team01 = {{#invoke:DartsRankings|PDCFlag|Anna A|avg=90.1}}
| RD1-score01= '''3'''
| RD1-team02 = {{PDCFlag|Bob B|avg=80}}
| RD1-score02= 1
| RD1-team03 = {{PDCFlag|Cy C}}
| RD1-score03= 2
| RD1-team04 = {{PDCFlag|Di D}}
| RD1-score04=
| RD2-team01 = {{PDCFlag|Anna A}}
| RD2-score01= 3
| RD2-team02 = {{PDCFlag|Cy C}}
| RD2-score02= 0
"""


def test_parse_bracket_names_scores_order_and_skips_incomplete():
    g = r.parse_bracket(WT, 2024)
    assert [(x["home"], x["away"], x["winner"]) for x in g] == [("Anna A", "Bob B", 1), ("Anna A", "Cy C", 1)]
    assert g[0]["kickoff_utc"] < g[1]["kickoff_utc"]  # header text with "second" in a ref does not reorder


def test_failed_fetch_is_empty_not_invented():
    def boom(y):
        raise OSError("down")
    assert r.fetch_all([2024], get=boom) == []
    assert "NO DATA - PENDING" in h.render([], datetime(2026, 11, 7, tzinfo=UTC))


def _games(n):
    out = []
    for i in range(n):
        out.append({"home": "Strong S", "away": f"Weak {i % 5}", "winner": 1, "kickoff_utc": f"2024-01-{i:03d}",
                    "tournament": "2024 PDC World Championship"})
    return out


def test_walk_forward_scores_before_learning_and_pending_under_100():
    res = h.walk_forward(_games(40), 24.0, 1)
    assert res["scored"] > 0 and res["brier"] < 0.25
    assert h.verdict(res).startswith("PENDING")
    assert h.walk_forward([], 24.0, 1)["brier"] is None


def test_verdict_when_enough():
    assert h.verdict({"scored": 150, "brier": 0.2}) == "beats coin flip"
    assert h.verdict({"scored": 150, "brier": 0.26}) == "does NOT beat coin flip"


def test_render_lists_every_try():
    text = h.render(_games(30), datetime(2026, 11, 7, tzinfo=UTC))
    assert text.count("\n| ") >= len(h.TRIES) + 1 and "board setting" in text
