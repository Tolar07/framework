"""Multi-sport backtests (framework#352): shared walk-forward Elo, snooker wikitext feed, baseball ESPN parse,
darts pooled feeds, table tennis CSV. No network."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import baseball_backtest as bb  # noqa: E402
from backtest import darts_backtest as db  # noqa: E402
from backtest import results_walkforward as wf  # noqa: E402
from backtest import snooker_backtest as sb  # noqa: E402
from backtest import table_tennis_backtest as tt  # noqa: E402
from data import snooker_results as sr  # noqa: E402


def _games(n=600):
    names = ["a", "b", "c", "d", "e", "f"]
    out = []
    for i in range(n):
        x, y = names[i % 6], names[(i * 5 + 1) % 6]
        if x == y:
            y = names[(i + 1) % 6]
        a, b = min(x, y), max(x, y)
        out.append({"key": f"2024-{1 + i // 60:02d}-{1 + i % 28:02d}-{i:04d}", "a": a, "b": b,
                    "y": 1.0 if names.index(a) < 3 else 0.0})
    return out


def test_replay_no_lookahead():
    g = _games()
    p = wf.replay(g, 24.0, 3)
    assert p[0] is None and any(x is not None for x in p)
    g2 = [dict(x) for x in g]
    g2[-1]["y"] = 1.0 - g2[-1]["y"]
    assert wf.replay(g2, 24.0, 3)[:-1] == p[:-1]


def test_results_only_study_counts_every_try():
    res = wf.results_only_study(_games(), [(16.0, 1), (24.0, 3)], "2024-06-01", (24.0, 3), min_tuned=10)
    assert res["tries"] == 2 and res["best"] is not None
    text = "\n".join(wf.results_only_lines(res))
    assert "(board)" in text and "never an edge" in text


ROUNDN = """{{Start and end dates|2024|11|23|2024|12|1|df=y}}
{{#invoke:RoundN|main|columns=2
|RD1 = '''Semi-finals'''<br/>Best of 11 frames
|RD2 = '''Final'''<br/>Best of 19 frames
|| {{flagathlete|[[Ronnie O'Sullivan]]|ENG}} {{tooltip|(1)|player seeding}}
|6
| {{flagathlete|[[Mark Williams (snooker player)|Mark Williams]]|WAL}}
|4
|| {{flagathlete|[[Judd Trump]]|ENG}}
|w/o
| {{flagathlete|[[Ding Junhui]]|CHN}}
|
|| {{flagathlete|[[Ronnie O'Sullivan]]|ENG}}
|10
| {{flagathlete|[[Judd Trump]]|ENG}}
|7
}}
{{16TeamBracket
| RD1=Last 128<br/>Best of 11 frames
|RD1-team01='''{{flagathlete|[[Ali Carter]]|ENG}}'''
|RD1-score01='''6'''
|RD1-team02={{flagathlete|[[Ross Bulman]]|IRL}}
|RD1-score02=0
}}"""


def test_snooker_parse_event_orders_rounds_and_skips_walkovers():
    g = sr.parse_event(ROUNDN, "2024 UK Championship")
    pairs = [(x["home"], x["away"], x["round_players"]) for x in g]
    assert pairs == [("Ali Carter", "Ross Bulman", 128), ("Ronnie O'Sullivan", "Mark Williams", 4),
                     ("Ronnie O'Sullivan", "Judd Trump", 2)]
    assert all(x["date"] == "2024-11-23" for x in g) and g[-1]["winner"] == 1
    assert sr.parse_event("no infobox", "x") == []


def test_snooker_season_events_reads_wst_table_only():
    text = ("==Calendar==\n===World Snooker Tour===\n| [[2023 UK Championship|UK Championship]]\n"
            "| [[2023 Snooker Shoot Out|Shoot Out]]\n===Seniors===\n| [[2023 World Seniors Championship|x]]\n")
    assert sr.season_events(text) == ["2023 UK Championship"]


def test_snooker_games_by_name_not_winner():
    g = sb.to_games([{"kickoff_utc": "2024-01-01-01-0000", "home": "Zed", "away": "Abe", "winner": 1}])
    assert g[0]["a"] == "abe" and g[0]["y"] == 0.0


def test_baseball_espn_parse_and_close():
    board = {"events": [{"id": "1", "date": "2024-07-04T17:05Z", "season": {"type": 2, "year": 2024},
                         "competitions": [{"status": {"type": {"completed": True}}, "competitors": [
                             {"homeAway": "home", "score": "3", "team": {"abbreviation": "WSH"}},
                             {"homeAway": "away", "score": "5", "team": {"abbreviation": "BOS"}}]}]},
                        {"id": "2", "season": {"type": 1, "year": 2024}, "competitions": [{}]}]}
    g = bb.games_of_day(board)
    assert len(g) == 1 and g[0]["a"] == "BOS" and g[0]["b"] == "WSH" and g[0]["y"] == 1.0
    odds = {"items": [
        {"provider": {"name": "Book A"}, "awayTeamOdds": {"moneyLine": -120}, "homeTeamOdds": {"moneyLine": 110}},
        {"provider": {"name": "Book A - Live Odds"}, "awayTeamOdds": {"moneyLine": 900},
         "homeTeamOdds": {"moneyLine": -2000}},
        {"provider": {"name": "teamrankings"}, "awayTeamOdds": {"moneyLine": 300}, "homeTeamOdds": {"moneyLine": -300}}]}
    pa, ph = bb.close_prices(odds)
    assert abs(pa - (1 + 100 / 120)) < 1e-9 and abs(ph - 2.1) < 1e-9
    assert bb.american("NL") is None and bb.american(-50) is None


def test_baseball_run_reports_heldout():
    games = []
    for i in range(3000):
        s = 2019 + i // 430
        a, b = ("NYY", "BOS") if i % 2 else ("BOS", "NYY")
        games.append({"key": f"{s}-05-{1 + i % 28:02d}T{i:05d}", "season": s, "a": a, "b": b, "y": float(i % 3 == 0),
                      "neutral": False, "pa": 1.9, "pb": 1.95, "mkt": bb.devig(1.9, 1.95)})
    text = bb.run(games)
    assert "reported on **2023-2025 only**" in text and "Record only" in text


def test_darts_pool_dedupes_and_orders():
    wc = [{"home": "Luke Humphries", "away": "Luke Littler", "winner": 1, "kickoff_utc": "2024-07-01-001"}]
    pl = [{"home": "Luke Littler", "away": "Luke Humphries", "winner": 1, "date": "2024-02-01",
           "kickoff_utc": "2024-02-01-0001"}] * 2
    g = db.keyed(wc, pl, [])
    assert len(g) == 2 and g[0]["src"] == "World Championship" and g[1]["src"] == "Premier League"


def test_table_tennis_parse():
    text = ("X,Date,Time,Player1,Player2,Sets_P1,Sets_P2\n1,6/10/2022,1:05:00,Zed Z.,Abe A.,3,1\n"
            "2,6/10/2022,1:25:00,Abe A.,Abe A.,3,0\n3,bad,1:00:00,a,b,3,0\n")
    g = tt.parse(text)
    assert len(g) == 1 and g[0]["a"] < g[0]["b"] and g[0]["y"] == 0.0 and g[0]["key"].startswith("2022-06-10T01:05")
