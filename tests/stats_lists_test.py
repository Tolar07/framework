"""Stats lists (framework #581-#584): parsing, PENDING rules, the first-half model, corner spreads, and the
lower-league PAPER board. Synthetic rows only; no network, no private data."""
from __future__ import annotations

import math
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import corner_consistency as cc  # noqa: E402
from engine import first_half as fh  # noqa: E402
from engine import league_profile as lp  # noqa: E402
from engine import lower_league_value as lv  # noqa: E402
from engine import market_rates as mr  # noqa: E402
from engine import stats_history as sh  # noqa: E402

NOW = datetime(2026, 11, 12, 18, 0, tzinfo=UTC)
CSV = ("﻿Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR,HTHG,HTAG,HTR,HC,AC,AvgC>2.5,AvgC<2.5,PC>2.5\n"
       "E0,15/08/2026,20:00,Arsenal,Leeds,2,1,H,1,0,H,7,3,1.80,2.05,1.82\n"
       "E0,16/08/26,15:00,Spurs,Fulham,0,0,D,0,0,D,,,,,2.10\n"
       "E0,,15:00,Bad,Row,x,0,D,0,0,D,1,1,2,2,2\n")


def rows(n, league="L", **kw):
    out = []
    for i in range(n):
        r = {"league": league, "season": "2627", "date": f"2026-{8 + i // 28:02d}-{1 + i % 28:02d}",
             "home": f"H{i % 4}", "away": f"A{i % 4}", "hg": i % 3, "ag": (i + 1) % 2, "hthg": i % 2, "htag": 0,
             "hc": 4 + i % 3, "ac": 4, "o25": 1.9, "u25": 1.9, "source": "test"}
        r.update(kw)
        out.append(r)
    return out


def test_parse_rows():
    got = sh.parse_rows("Premier League", "2627", CSV)
    assert len(got) == 2, got
    a, b = got
    assert (a["date"], a["hthg"], a["hc"], a["o25"], a["u25"]) == ("2026-08-15", 1, 7, 1.80, 2.05)
    assert b["hc"] is None and b["o25"] == 2.10 and b["u25"] is None      # falls back to Pinnacle; absent = None


def test_profile_pending_and_rates():
    p = lp.profile(rows(10))
    assert p["btts"] == "PENDING" and p["gpg"] == "PENDING"              # under MIN_GAMES: never a number (HR35)
    rs = rows(40)
    p = lp.profile(rs)
    want = sum(1 for r in rs if r["hg"] > 0 and r["ag"] > 0) / 40
    assert abs(p["btts"] - want) < 1e-4
    fh_goals = sum(r["hthg"] + r["htag"] for r in rs)
    assert abs(p["fh_share"] - fh_goals / sum(r["hg"] + r["ag"] for r in rs)) < 1e-4
    assert p["more_before_ht"] is (p["fh_share"] > 0.5)


def test_build_ranks_and_late_share():
    hi = rows(30, league="High", hg=1, ag=1)
    lo = rows(30, league="Low", hg=1, ag=0)
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "2026-11.jsonl"
        f.write_text("\n".join('{"league": "High", "goals": [[80, 0, "h"], [10, 1, "a"]]}' for _ in range(25)),
                     encoding="utf-8")
        late = lp.late_shares(Path(d))
    doc = lp.build(hi + lo, [], NOW, late)
    names = [p["league"] for p in doc["leagues"]]
    assert names[:2] == ["High", "Low"] and doc["leagues"][0]["btts_rank"] == 1
    assert doc["leagues"][0]["late_share"] == 0.5 and doc["leagues"][1]["late_share"] == "PENDING"


def test_first_half_model():
    hist = rows(200)
    m = fh.FirstHalf(hist)
    p = m.predict("L", "H0", "A0")
    assert 0 < p["over05"] < 1 and p["over15"] < p["over05"]
    assert abs(sum(x["p"] for x in p["likely_ht"]) - sum(sorted([x["p"] for x in p["likely_ht"]]))) < 1e-9
    lh, la, _ = m.league_rates("L")
    assert abs(p["over05"] - (1 - math.exp(-(m.lambdas("L", "H0", "A0")[0] + m.lambdas("L", "H0", "A0")[1])))) < 0.02
    unknown = m.predict("L", "Nobody", "Ghost")
    assert unknown["home_basis"] == "league" and abs(unknown["over05"] - m.league_over05("L")) < 0.01
    tops = fh.top_home(hist, min_games=6, top=3)
    assert len(tops) == 3 and tops[0]["fh_per_game"] >= tops[-1]["fh_per_game"]


def test_corners():
    hist = rows(120)
    doc = cc.build(hist, "2026", NOW)
    assert doc["population"] > 0 and all(t["games"] >= cc.MIN_GAMES for t in doc["teams"])
    sds = [t["sd"] for t in doc["teams"]]
    assert sds == sorted(sds)                                             # steadiest first
    few = cc.build(rows(30), "2026", NOW)
    assert few["population"] == 0                                         # under 20 games: not listed


def test_lower_league_rules():
    assert lv.is_lower({"country": "England", "comp": "League Two"})
    assert lv.is_lower({"country": "Spain", "comp": "Segunda Federacion"})
    assert not lv.is_lower({"country": "England", "comp": "Premier League"})
    assert not lv.is_lower({"country": "England", "comp": "Premier League 2, U21"})
    assert not lv.is_lower({"country": "Germany", "comp": "2. Bundesliga, Women"})
    pr = lv.probs(1.4, 1.1)
    for a, b in (("BTTS Yes", "BTTS No"), ("Over 2.5", "Under 2.5"), ("Over 1.5", "Under 1.5")):
        assert abs(pr[a] + pr[b] - 1) < 1e-6
    assert lv.won("Under 2.5", 1, 1) and not lv.won("BTTS Yes", 2, 0) and lv.won("Over 3.5", 3, 1)
    assert lv.band(0.03) == "under 5%" and lv.band(0.25) == "over 20%"


def test_paper_board_cycle():
    m = lv.Goals()
    for i in range(40):
        m.add("England: League Two", f"T{i % 6}", f"T{(i + 3) % 6}", 2, 1)
    row = {"id": "g1", "sport": "football", "country": "England", "comp": "League Two", "home": "T0", "away": "T3",
           "ko": "2026-11-13T15:00Z",
           "last": {"p": {"btts": [3.9, 1.2], "ou2.5": [3.5, 1.3], "ou1.5": [1.05, 8.0], "ou3.5": [3.9, 1.25]}}}
    book = {"picks": {}}
    assert lv.add_picks(book, [row], NOW, m) == 1
    p = book["picks"]["g1"]
    assert p["paper"] is True and p["value"] > 0 and lv.PRICE_MIN <= p["price"] <= lv.PRICE_MAX
    assert lv.add_picks(book, [row], NOW, m) == 0                         # once per game
    started = dict(row, id="g2", ko="2026-11-12T17:00Z")
    assert lv.add_picks(book, [started], NOW, m) == 0                     # never after kick-off
    assert lv.grade(book, [{"id": "g1", "result": {"h": 2, "a": 1, "after_90": False}}]) == 1
    rec = lv.record(book)
    assert rec["all"]["graded"] == 1 and rec["all"]["ready_to_propose"] is False
    src = (ROOT / "engine" / "lower_league_value.py").read_text(encoding="utf-8")
    assert "output\" / \"picks" not in src and "multisport\" /" not in src  # never where a bot reads


def test_market_rates_every_sport():
    assert mr.norm_key("football", "SB:18|total=2.5|Over 2.5") == "SB:18|total=2.5|Over 2.5"   # fixed lines kept
    assert mr.norm_key("tennis", "tennis:189|total=22.5|over 22.5") == "tennis:#|total=#|over #"
    assert mr.family("basketball", "total|221.5|over") == "total|#"
    assert abs(mr._devig("t:1||Home", {"t:1||Home": 1.8, "t:1||Away": 2.0}) - (1 / 1.8) / (1 / 1.8 + 1 / 2.0)) < 1e-9
    assert mr._devig("t:1||Home", {"t:1||Home": 2.5, "t:1||Draw": 3.2, "t:1||Away": 2.9}) is None   # two-way only
    r = mr.Rates()
    g = {"sport": "volleyball", "league": "X: Y", "home": "A", "away": "B", "ko": "2026-11-01"}
    assert r.predict("volleyball", "X: Y", "A", "B", "v:1||Home") is None                          # no league yet
    for i in range(30):
        r.add(dict(g, home="A" if i % 2 else "C", away="B" if i % 3 else "D",
                   sides=[("v:1||Home", int(i % 4 != 0), 1.6, None), ("v:1||Away", int(i % 4 == 0), 2.3, None)]))
    m = r.predict("volleyball", "X: Y", "A", "B", "v:1||Home")
    assert m and 0 < m["p"] < 1 and m["league_n"] == 30 and m["teams"]
    assert abs(m["league_rate"] - (22 + 1) / 32) < 1e-9
    best = mr.best_side(r, g, [("v:1||Home", 1.9), ("v:1||Away", 9.0)])
    assert best is None or best["key"] == "v:1||Home"                       # 9.0 is outside the price range
    assert r.predict("volleyball", "X: Y", "A", "B", "v:1||Home")["p"] == m["p"]   # predicting adds nothing


def main() -> None:
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("stats_lists_test OK")


if __name__ == "__main__":
    main()
