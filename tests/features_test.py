"""
Offline test of the richer-data features (autonomy plan item 5):
engine/features.py (PENDING when missing, no look-ahead on xG, margin removed),
engine/walkforward.py (a real signal is found, noise is not, bets split into
halves), data/fixture_features.py (team news captured for every rated fixture
inside the window, re-read until confirmed, strict matching, saved per day;
feature files built) and backtest/features_study.py (report on PENDING data).
"""
import json
import random
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "backtest"))

from data import fixture_features as ff  # noqa: E402
from engine import features as F  # noqa: E402
from engine import walkforward as wf  # noqa: E402

P = F.PENDING


def stat(day, home, away, xh, xa):
    return {"date": day, "home": home, "away": away, "stats": {"xg": [xh, xa]}}


def test_xg_form_no_lookahead_and_pending():
    rows = [stat("2026-10-01", "A", "B", 2.0, 1.0), stat("2026-10-05", "C", "A", 0.5, 1.5),
            stat("2026-10-10", "A", "D", 3.0, 0.0)]          # on/after the match day: never read
    f = F.xg_form("A", "2026-10-10", rows)
    assert f["n"] == 2 and f["xgf"] == 1.75 and f["xga"] == 0.75 and f["trend"] == P
    assert F.xg_form("B", "2026-10-10", rows)["xgf"] == P      # one match only -> PENDING
    x = F.xg_features("A", "B", "2026-10-10", rows)
    assert x["edge"] == P and x["total"] == P                   # B unknown -> PENDING, never 0
    rows += [stat("2026-10-02", "B", "E", 1.0, 1.0), stat("2026-10-03", "E", "B", 1.0, 2.0)]
    x = F.xg_features("A", "B", "2026-10-10", rows)
    assert x["edge"] == 1.0                                     # A +1.0 net, B (3 matches) level
    rows4 = [stat(f"2026-10-0{i}", "A", "Z", g, 1.0) for i, g in ((1, 1), (2, 1), (3, 2), (4, 2))]
    assert F.xg_form("A", "2026-10-09", rows4)["trend"] == 1.0


def test_news_and_close_pending():
    n = F.news_features(None)
    assert all(v == P for v in n.values())
    n = F.news_features({"lineup_type": "confirmed", "home_missing_share": 0.1, "away_missing_share": 0.3})
    assert n["edge"] == 0.2 and n["lineup"] == "confirmed" and n["absent"] == P
    assert F.news_features({"home_missing_share": None, "away_missing_share": 0.3})["edge"] == P
    assert F.fair([2.0, 2.0]) == [0.5, 0.5] and F.fair([2.0, None]) is None
    c = F.close_features({"last": {"at": "t", "p": {"1x2": [2.0, 4.0, 4.0]}}})
    assert c["soft"]["home"] == 0.5 and c["soft"]["over25"] == P and c["sharp"]["home"] == P
    fx = {"home": "A", "away": "B", "src": "market", "p": [0.5] * 7}
    assert F.build(fx, "2026-10-10", [], None, None)["model_p"] == P   # market numbers are not the model's


def test_feature_test_finds_signal_not_noise():
    rng = random.Random(7)  # noqa: S311 (test data)
    sig, noise = [], []
    for i in range(400):
        day = f"2026-{10 + i // 200:02d}-{1 + (i // 10) % 20:02d}"
        x = rng.uniform(-1, 1)
        y = int(rng.random() < 1 / (1 + 2.718 ** (-2.0 * x)))     # truth depends on x; model says 0.5
        sig.append((day, 0.5, y, x))
        noise.append((day, 0.5, y, rng.uniform(-1, 1)))
    s, n = wf.feature_test(sig), wf.feature_test(noise)
    assert s["verdict"] == "ADDS INFORMATION", s
    assert n["verdict"] in ("NO CLEAR EFFECT", "HURTS"), n
    few = wf.feature_test(sig[:60])
    assert few["verdict"] == "NOT ENOUGH DATA"
    assert wf.feature_test([(d, p, y, None) for d, p, y, _ in sig])["scored"] == 0


def test_betfair_close():
    csv_text = ("Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,BFECH,BFECD,BFECA,BFEC>2.5,BFEC<2.5\n"
                "E0,19/10/2026,Alpha,Beta Utd,2,1,2.0,4.0,4.0,2.0,2.0\n"
                "E0,19/10/2026,Gamma,Delta,0,0,,,,,\n")
    b = ff.betfair_index({"Premier League", "Danish Superliga"}, "2627", lambda lg, s: csv_text)
    assert len(b) == 1                                  # no exchange price: not indexed
    fx = {"home": "Alpha", "away": "Beta Utd"}
    row = ff.find_betfair(fx, "2026-10-20", b)          # a day either side
    c = F.close_features(None, row)
    assert c["betfair"]["home"] == 0.5 and c["betfair"]["over25"] == 0.5 and c["betfair"]["btts"] == P
    assert F.close_features(None, None)["betfair"]["home"] == P
    assert ff.find_betfair({"home": "Alpha FC", "away": "Beta Utd"}, "2026-10-19", b) is None   # exact only
    assert ff.season_of("2026-10-20") == "2627" and ff.season_of("2027-03-01") == "2627"


def test_bet_test_halves():
    good = [(f"d{i:03d}", int(i % 2 == 0), 2.2, 2.0) for i in range(100)]   # 50% at 2.2, beat the close
    assert wf.bet_test(good)["verdict"] == "ACCEPT AS SHADOW"
    bad = [(f"d{i:03d}", int(i % 3 == 0), 2.0, 2.2) for i in range(100)]
    assert wf.bet_test(bad)["verdict"] == "REJECT"
    assert wf.bet_test(good[:20])["verdict"] == "NOT ENOUGH DATA"
    r = wf.bet_test(good)
    assert r["all"]["n"] == 100 and r["early"]["n"] == 50 and abs(r["all"]["roi"] - 0.1) < 1e-9


class FakeFM:
    def __init__(self, ko, lineup="predicted"):
        self.ko, self.lineup, self.calls = ko, lineup, 0

    def matches_on(self, day):
        return [{"id": 1, "home": "Alpha FC", "away": "Beta United", "kickoff_utc": self.ko},
                {"id": 2, "home": "Gamma", "away": "Delta", "kickoff_utc": self.ko}]

    def find_match(self, matches, home, away):
        from data.fotmob import find_match
        return find_match(matches, home, away)

    def team_news(self, mid):
        self.calls += 1
        side = {"missing_share": 0.2, "missing": [{"name": "X", "type": "injury"}]}
        return {"lineup_type": self.lineup, "home": side, "away": dict(side, missing_share=0.05)}


def _ledger(tmp: Path, day: str, rated: list) -> Path:
    led = tmp / "picks"
    led.mkdir(exist_ok=True)
    (led / f"picks_{day}.json").write_text(json.dumps({"date": day, "rated": rated}), encoding="utf-8")
    return led


def test_capture_news_window_and_confirm():
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        day = "2026-10-20"
        led = _ledger(tmp, day, [{"home": "Alpha", "away": "Beta Utd", "src": "model", "p": [0.4] * 7},
                                 {"home": "Nobody", "away": "Elsewhere"}])
        fm = FakeFM("2026-10-20T19:00:00.000Z")
        early = datetime(2026, 10, 20, 9, 0, tzinfo=UTC)               # 10 h before: not yet
        assert "0 captured" in ff.capture_news(early, day, fm, tmp, led, pause=0) and fm.calls == 0
        r = ff.capture_news(datetime(2026, 10, 20, 14, 0, tzinfo=UTC), day, fm, tmp, led, pause=0)
        assert "1 captured" in r and "1 not on FotMob" in r, r
        snap = json.loads((tmp / f"news_{day}.json").read_text())["Alpha v Beta Utd"]
        assert snap["lineup_type"] == "predicted" and snap["home_missing_share"] == 0.2 and snap["fotmob_id"] == 1
        ff.capture_news(datetime(2026, 10, 20, 16, 0, tzinfo=UTC), day, fm, tmp, led, pause=0)
        assert fm.calls == 1                                            # predicted held; not inside 90 min
        fm.lineup = "confirmed"
        ff.capture_news(datetime(2026, 10, 20, 18, 0, tzinfo=UTC), day, fm, tmp, led, pause=0)
        ff.capture_news(datetime(2026, 10, 20, 18, 20, tzinfo=UTC), day, fm, tmp, led, pause=0)
        assert fm.calls == 2                                            # confirmed: no more reads
        assert json.loads((tmp / f"news_{day}.json").read_text())["Alpha v Beta Utd"]["lineup_type"] == "confirmed"
        assert ff.capture_news(datetime(2026, 10, 20, 20, 0, tzinfo=UTC), day, fm, tmp, led, pause=0)
        assert "no rated fixtures" in ff.capture_news(early, "2026-10-21", fm, tmp, led)


def test_build_day_and_study():
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        day = "2026-10-20"
        led = _ledger(tmp, day, [{"home": "Alpha", "away": "Beta Utd", "src": "model",
                                  "p": [0.4, 0.3, 0.3, 0.7, 0.5, 0.3, 0.5], "ft": "2-1"}])
        urows = [{"sport": "football", "covered": True, "ko": "2026-10-20T19:00Z", "home": "Alpha FC",
                  "away": "Beta United", "last": {"at": "x", "p": {"1x2": [2.0, 4.0, 4.0]}},
                  "mb_last": {"at": "y", "p": {"ou2.5": [2.0, 2.0]}}},
                 {"sport": "football", "covered": False, "ko": "2026-10-20T19:00Z", "home": "Gamma",
                  "away": "Delta"}]
        uidx = ff.universe_index(urows)
        assert len(uidx[day]) == 1                                      # uncovered games left out
        assert ff.build_day(day, [], uidx, tmp, led) == 1
        f = json.loads((tmp / f"features_{day}.json").read_text())["Alpha v Beta Utd"]
        assert f["close"]["soft"]["home"] == 0.5 and f["close"]["sharp"]["over25"] == 0.5
        assert f["xg"]["edge"] == P and f["news"]["edge"] == P and f["ft"] == "2-1"
        import features_study as fs
        recs = fs.collect(led, tmp, [], urows, {})
        assert len(recs) == 1
        text = fs.report(recs)
        assert "NOT ENOUGH DATA" in text and "| with SportyBet close | 1 |" in text
        assert "NO DATA — PENDING" in fs.report([])


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
