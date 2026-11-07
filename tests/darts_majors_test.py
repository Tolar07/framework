from datetime import UTC, date, datetime

from backtest import darts_majors_study as s
from data import darts_majors_results as r

WT = """
{{32TeamBracket
| RD1='''First round''' ''(best of 19 legs)''<br>13–15 July
| RD2='''Second round''' ''(best of 21 legs)''<br>16–17 July
| RD3='''Final''' ''(best of 35 legs)''
| RD1-team01 = {{PDCFlag|Anna A|avg=97}}
| RD1-score01= 10
| RD1-team02 = {{PDCFlag|Bob B|avg=96}}
| RD1-score02= 4
| RD2-team01 = {{PDCFlag|Anna A}}
| RD2-score01= 11
| RD2-team02 = {{PDCFlag|Cy C}}
| RD2-score02= 9
| RD3-team01 = {{PDCFlag|Anna A}}
| RD3-score01= 18
| RD3-team02 = {{PDCFlag|Dee D}}
| RD3-score02= 12
}}
"""


def _g(d, i, h, a, w):
    return {"date": d, "kickoff_utc": f"{d}-{i:03d}", "home": h, "away": a, "winner": w}


def test_header_dates():
    assert r.header_start("'''First round'''<br>19–21 July", 2025) == date(2025, 7, 19)
    assert r.header_start("x<br>30 June – 2 July", 2025) == date(2025, 6, 30)
    assert r.header_start("'''Final''' (best of 35 legs)", 2025) is None
    assert r.header_start("<br>31 February", 2025) is None


def test_event_matches_get_round_start_date_and_undated_round_is_dropped():
    g = r.parse_event(WT, 2024, "World Matchplay")
    assert [(x["home"], x["date"]) for x in g] == [("Anna A", "2024-07-13"), ("Anna A", "2024-07-16")]
    assert all(x["tournament"] == "2024 World Matchplay" for x in g)


def test_fetch_all_skips_missing_pages():
    assert r.fetch_all(years=[2024], get=lambda y, p: None) == []


def test_empty_and_small_sample_read_pending():
    assert "PENDING" in s.render([], datetime(2026, 1, 1, tzinfo=UTC))
    out = s.render([_g("2025-01-01", 0, "A A", "B B", 1)], datetime(2026, 1, 1, tzinfo=UTC))
    assert "PENDING" in out and "Record only" in out


def test_combine_dedupes_and_orders_and_scoring_uses_earlier_only():
    a = _g("2025-01-02", 0, "A A", "B B", 1)
    b = _g("2025-01-01", 0, "A A", "C C", 0)
    both = s.combine([a], [b, dict(a, kickoff_utc="2025-01-02-9999")])
    assert [x["date"] for x in both] == ["2025-01-01", "2025-01-02"]
    rows = s.scored(both, 24.0, 0)
    assert rows[0][1] == 0.5 and rows[1][1] != 0.5
