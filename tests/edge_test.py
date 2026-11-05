"""The edge plan: engine/exchange.py, engine/edge_book.py, engine/records/exchange.py,
engine/residual_model.py, monitor/edge_scoreboard.py (Architect 2026-11-04)."""
from __future__ import annotations

import random
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine import edge_book as eb  # noqa: E402
from engine import exchange as ex  # noqa: E402
from engine import residual_model as rm  # noqa: E402
from engine.records import exchange as rx  # noqa: E402
from monitor import edge_scoreboard as sc  # noqa: E402

NOW = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)
KO = NOW + timedelta(hours=6)


def _r(name, back=None, lay=None, liq=50.0, hc=None):
    prices = []
    if back:
        prices.append({"side": "back", "odds": back, "available-amount": liq})
    if lay:
        prices.append({"side": "lay", "odds": lay, "available-amount": liq})
    r = {"name": name, "status": "open", "prices": prices}
    if hc is not None:
        r["handicap"] = hc
    return r


def _event(start=KO):
    return {"id": 77, "name": "Arsenal vs Chelsea", "start": start.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "_sport": "football", "markets": [
                {"name": "Match Odds", "market-type": "one_x_two", "status": "open", "runners": [
                    _r("Arsenal", 2.0, 2.04), _r("Chelsea", 4.0, 4.1), _r("Draw", 3.6, 3.7)]},
                {"name": "Total", "market-type": "total", "status": "open", "handicap": 2.5, "runners": [
                    _r("Over 2.5", 1.9, None), _r("Under 2.5", 2.0, None)]},
                {"name": "Handicap", "market-type": "handicap", "status": "open", "runners": [
                    _r("Arsenal -1.5", 3.0, 3.1, hc=-1.5), _r("Chelsea +1.5", 1.48, 1.5, hc=1.5)]},
                {"name": "Match Result and Total Goals", "market-type": "x", "status": "open", "handicap": 3.5,
                 "runners": [_r("Chelsea and over 3.5", 22.0, None, liq=9.9),
                             _r("Arsenal and over 3.5", 9.0, None, liq=9.9)]},
            ]}


def test_fair_chances():
    idx = ex.index_event(_event())
    assert abs(idx["1x2|home"]["p"] - (1 / 2.0 + 1 / 2.04) / 2) < 1e-3        # back/lay midpoint
    over = 1 / 1.9 + 1 / 2.0
    assert abs(idx["total|2.5|over"]["p"] - (1 / 1.9) / over) < 1e-3          # back-only, de-vigged
    assert idx["hcp|-1.5|home"]["p"] and idx["hcp|1.5|away"]["p"]
    assert idx["rt|away|over|3.5"]["p"] is None                                # thin combo book: no number


def test_canonical_keys():
    c = ex.canonical
    assert c("SB:18|total=2.5|Over 2.5") == "total|2.5|over"
    assert c("SB:18|total=2|Over 2") is None                                   # whole line: push rules
    assert c("SB:10||Home or Draw") == "dc|home_or_draw"
    assert c("SB:16|hcp=1.5|Home (+1.5)") == "hcp|1.5|home"
    assert c("SB:14|hcp=0:1|Home (0:1)") == "hcp|-1.5|home"
    assert c("SB:31||Yes") == "tt|away|0.5|under"
    assert c("BTTS_YES") == "btts|yes"
    assert c("B:68|total=113.5|Under 113.5") == "fh|113.5|under"
    assert c("B:223|hcp=11.5|Away (-11.5)") == "hcp|-11.5|away"
    assert c("B:219||Home") == "ml|home"
    assert ex.nba_key({"market_id": "68", "specifier": "total=113.5", "outcome": "Under 113.5"}) == \
        "B:68|total=113.5|Under 113.5"


def test_match_event():
    e = _event()
    assert ex.match_event("Arsenal FC", "Chelsea", KO, [e]) is e
    assert ex.match_event("Arsenal", "Chelsea", KO + timedelta(hours=1), [e]) is None
    assert ex.match_event("Everton", "Chelsea", KO, [e]) is None


def test_edge_book_first_last_and_gap():
    ev: dict = {}
    idx = ex.index_event(_event())
    sides = {"SB:1||Home": 1.95, "SB:1||Away": 4.5}
    assert eb.update_event(ev, sides, idx, KO, NOW) == 2
    home, away = ev["k"]["SB:1||Home"], ev["k"]["SB:1||Away"]
    assert home["s0"] == 1.95 and home["x"] is None                          # below fair: no gap
    assert away["x"] and away["x"]["g"] >= eb.GAP_MIN and away["x"]["h"] == 6.0
    later = NOW + timedelta(hours=5)
    eb.update_event(ev, {"SB:1||Home": 2.2, "SB:1||Away": 4.5}, idx, KO, later)
    assert home["s0"] == 1.95 and home["s1"] == 2.2 and home["x"]["g"] > 0 and home["x"]["sm"] > 0
    assert eb.update_event(ev, {"SB:1||Home": 9.0}, idx, KO, KO) == 0          # after kick-off: frozen
    assert home["s1"] == 2.2


def test_update_and_finalize():
    with tempfile.TemporaryDirectory() as t:
        live, final = Path(t) / "live", Path(t) / "final"
        row = {"sport": "football", "id": "sr:match:1", "home": "Arsenal", "away": "Chelsea",
               "ko": KO.strftime("%Y-%m-%dT%H:%M:%SZ"), "covered": True, "sides": {"SB:1||Away": 4.5}}
        docs: dict = {}
        st = eb.update(docs, [row], [_event()], NOW)
        assert st["matched"] == 1 and st["new_gaps"] == 1
        eb.save(docs[KO.strftime("%Y-%m-%d")], live)
        assert eb.finalize(NOW, live, final) == []                                # today: still watched
        assert eb.finalize(NOW + timedelta(days=1), live, final) == [KO.strftime("%Y-%m-%d")]
        assert eb.load_all(live, final)[KO.strftime("%Y-%m-%d")]["events"]["sr:match:1"]["mb"] == 77


def test_grade_basketball():
    res = {"h": 110, "a": 100}
    assert sc.grade_basketball("B:219||Home", res) == 1
    assert sc.grade_basketball("B:225|total=209.5|Over 209.5", res) == 1
    assert sc.grade_basketball("B:225|total=210|Over 210", res) is None       # push
    assert sc.grade_basketball("B:223|hcp=-9.5|Home (-9.5)", res) == 1
    assert sc.grade_basketball("B:223|hcp=11.5|Away (+11.5)", res) == 1
    assert sc.grade_basketball("B:68|total=110.5|Under 110.5", res) is None   # half score unknown
    half = {"h": 110, "a": 100, "ht": [52, 50]}
    assert sc.grade_basketball("B:68|total=101.5|Over 101.5", half) == 1
    assert sc.grade_basketball("B:68|total=101.5|Under 101.5", half) == 0
    assert sc.grade_basketball("B:68|total=102|Over 102", half) is None       # push


def test_basketball_half_from_feed():
    from data import flashscore_results as fs
    from engine import universe as uv
    feed = ("~ZA÷USA: NBA¬~AA÷x1¬AD÷1762300000¬AB÷3¬AC÷3¬AE÷Home¬AF÷Away¬AG÷112¬AH÷117"
            "¬BA÷30¬BB÷26¬BC÷18¬BD÷33¬BE÷36¬BF÷31¬BG÷28¬BH÷27¬"
            "~ZA÷USA: NCAA¬~AA÷x2¬AD÷1762300000¬AB÷3¬AC÷3¬AE÷T¬AF÷W¬AG÷90¬AH÷59"
            "¬BA÷0¬BB÷0¬BC÷34¬BD÷31¬BE÷0¬BF÷0¬BG÷56¬BH÷28¬")
    nba, ncaa = fs.parse_feed(feed, 3)
    assert (nba["h1_home"], nba["h1_away"]) == (48, 59)          # Q1 + Q2
    assert (ncaa["h1_home"], ncaa["h1_away"]) == (34, 31)        # NCAA halves
    assert uv.result_of("basketball", ncaa) == {"h": 90, "a": 59, "ht": [34, 31]}
    assert "h1_home" not in fs.parse_feed(feed)[0]                # football: untouched


def test_world_basketball_every_side_group():
    """Every non-NBA basketball side over the world board's bars at its first gap is graded."""
    import tempfile
    from pathlib import Path
    x = {"s": 1.80, "p": 0.60, "g": 0.08, "h": 3.0, "pm": 0.0}             # +8% total line: clears
    small = {"s": 1.80, "p": 0.57, "g": 0.026, "h": 3.0, "pm": 0.0}       # +2.6%: below the +5% line bar
    obs = {"2026-11-04": {"events": {
        "sr:match:9": {"sport": "basketball", "covered": False, "k": {
            "B:225|total=160.5|Over 160.5": {"x": x, "p1": 0.61},
            "B:223|hcp=-3.5|Home (-3.5)": {"x": small, "p1": 0.57}}},
        "sr:match:8": {"sport": "basketball", "covered": True, "k": {      # an NBA game: not this group
            "B:225|total=220.5|Over 220.5": {"x": x, "p1": 0.6}}}}}}
    res = {"sr:match:9": {"__res__": {"h": 85, "a": 80}}, "sr:match:8": {"__res__": {"h": 120, "a": 110}}}
    with tempfile.TemporaryDirectory() as t:
        groups = {g["name"]: g for g in sc.collect(obs, res, Path(t))["groups"]}
    assert groups["world basketball: every side over the bars"]["n"] == 1
    assert groups["world basketball every side: market 225"]["hit"] == 1.0
    assert "world basketball every side: market 223" not in groups


def test_summary_and_promotion():
    rows = [{"price": 2.0, "won": i % 2, "p_entry": 0.52, "p_close": 0.53} for i in range(250)]
    good = sc.summarize("strong", rows)
    assert good["n"] == 250 and abs(good["clv"] - 0.06) < 1e-9 and good["roi"] == 0.0
    noisy = [{"price": 2.0, "won": 1 if i % 5 else 0, "p_close": 0.5 + (0.1 if i % 2 else -0.1)}
             for i in range(250)]
    groups = [{**good, "clv_se": 0.01, "roi": 0.05}, sc.summarize("flat", noisy),
              sc.summarize("small", rows[:20]), sc.summarize("base", rows, "baseline")]
    status = {p["name"]: p["status"] for p in sc.promotion(groups)}
    assert status["strong"] == "READY FOR ARCHITECT"
    assert status["flat"] == "NO EDGE YET" and status["small"].startswith("COLLECTING")
    assert "base" not in status                                                # baselines never promoted


def test_residual_model_finds_only_real_information():
    rng = random.Random(7)  # noqa: S311 (synthetic test data)
    rows = []
    for i in range(1500):
        p = rng.uniform(0.3, 0.8)
        price = round(1 / p * rng.uniform(0.9, 1.1), 3)
        gap = price * p - 1
        truth = min(0.97, max(0.03, p + 1.5 * gap))                           # SportyBet's gap is informative
        rows.append({"day": f"2026-10-{1 + i // 60:02d}", "key": "SB:1||Home", "sport": "football",
                     "price": price, "p": p, "won": int(rng.random() < truth)})
    out = rm.study(rows, "synthetic")
    assert out["weights"]["gap"] > 0 and out["walk_forward"]["gain"] > 0
    assert rm.study(rows[:50], "few")["status"].startswith("COLLECTING")


def test_records_exchange_entry_only():
    rx._EVENTS = [_event()]
    doc = {"singles": [
        {"home": "Arsenal", "away": "Chelsea", "kickoff_utc": KO.isoformat(), "market": "SB:1||Away", "price": 4.5},
        {"home": "Arsenal", "away": "Chelsea", "kickoff_utc": (NOW - timedelta(hours=1)).isoformat(),
         "market": "SB:1||Home", "price": 2.0},
        {"home": "Arsenal", "away": "Chelsea", "kickoff_utc": KO.isoformat(), "market": "SB:1||Draw",
         "price": 3.5, "exchange": {"p": 0.3}}]}
    rx.annotate_doc(doc, "2026-11-04", now=NOW)
    s0, s1, s2 = doc["singles"]
    assert s0["exchange"]["gap"] > 0 and s0["exchange"]["best"] == "sportybet"
    assert "exchange" not in s1                                                  # kicked off: never in-play
    assert s2["exchange"] == {"p": 0.3}                                          # entry price kept
    rx._EVENTS = None


def main() -> None:
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("edge_test OK")


if __name__ == "__main__":
    main()
