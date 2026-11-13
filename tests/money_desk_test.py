"""The money desk (engine/money_desk.py): paper lanes promoted, stepped up, dropped back, inside the hard caps;
veto and agree; the kill switch; booking. Synthetic books only; no network, no private data."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import money_desk as md  # noqa: E402

NOW = datetime(2026, 11, 20, 9, 0, tzinfo=UTC)
os.environ.pop("MONEY_DESK", None)


def _iso(t: datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%MZ")


def _lp(lid, i, key="draw", price=3.0, result=None, ko=None):
    ko = ko or _iso(NOW - timedelta(days=2))
    return {"list": lid, "title": lid, "date": ko[:10], "ko": ko, "event": f"sr:match:{lid}{i}", "home": f"H{i}",
            "away": f"A{i}", "pick": key, "key": key, "price": price, "sport": "football", "result": result}


def _root(universe=None, lines=None, verdicts=None, lower=None, config=None) -> Path:
    root = Path(tempfile.mkdtemp())
    (root / "data" / "list_picks").mkdir(parents=True)
    (root / "data" / "analyst").mkdir(parents=True)
    (root / "data" / "list_picks" / "book_universe.json").write_text(json.dumps({"picks": universe or {}}))
    (root / "data" / "list_picks" / "book_lines.json").write_text(json.dumps({"picks": lines or {}}))
    (root / "data" / "analyst" / "state.json").write_text(json.dumps(verdicts or {}))
    if lower is not None:
        (root / "data" / "lower_league_value").mkdir(parents=True)
        (root / "data" / "lower_league_value" / "book.json").write_text(json.dumps({"picks": lower}))
    if config is not None:
        (root / "config").mkdir()
        (root / "config" / "money_desk.json").write_text(json.dumps(config))
    return root


def _winners(lid, n=40, key="corners|9.5|over", price=2.0, won=24, start=0):
    """n graded picks of a lines list, `won` of them winners (2.0: 24/40 = +20%, 60% v 50% priced)."""
    return {f"{lid}|{i}": _lp(lid, i, key, price, 1 if i - start < won else 0) for i in range(start, start + n)}


def _event(mid, spec, desc):
    return {"data": {"eventId": "e1", "markets": [{"id": mid, "specifier": spec, "status": 0, "outcomes": [
        {"id": "12", "desc": desc, "odds": "1.90", "isActive": 1}, {"id": "13", "desc": "x", "odds": "1.9"}]}]}}


CORNERS = lambda u: _event("166", "total=9.5", "Over 9.5")  # noqa: E731
CODE = lambda s: "ABC123"  # noqa: E731


def _state(root):
    return json.loads((root / "output" / "money_desk" / "state.json").read_text())


def _dec(root):
    return json.loads((root / "output" / "money_desk" / "decisions.json").read_text())["decisions"]


def test_promote_needs_30_graded_a_profit_and_a_win_rate_above_the_price():
    lines = {**_winners("team_corners"), **_winners("cards", n=29, key="bookings|4.5|over", won=20),      # too few
             **_winners("fouls", n=40, key="bookings|4.5|over", won=18)}                                   # losing
    root = _root(lines=lines)
    out = md.attach(NOW, root, CORNERS, CODE, votes_text="")
    lanes = _state(root)["lanes"]
    assert lanes["list:team_corners"]["stake"] == 200 and lanes["list:team_corners"]["since"]
    assert lanes["list:cards"]["stake"] == 0 and lanes["list:fouls"]["stake"] == 0
    d = _dec(root)
    assert [x["id"] for x in d] == ["MD-1"] and d[0]["from"] == 0 and d[0]["to"] == 200 and d[0]["status"] == "acting"
    assert d[0]["evidence"]["paper"]["graded"] == 40 and "promote" in d[0]["rule"] and "1 decision(s)" in out
    md.attach(NOW + timedelta(hours=3), root, CORNERS, CODE, votes_text="")           # once a UTC day
    assert len(_dec(root)) == 1


def test_no_decision_before_the_decide_hour_and_basketball_totals_never_promoted():
    uni = {f"us_totals|{i}": _lp("us_totals", i, "bb_over", 2.0, 1) for i in range(40)}
    root = _root(universe=uni, lines=_winners("team_corners"))
    md.attach(NOW.replace(hour=3), root, CORNERS, CODE, votes_text="")
    assert _dec(root) == []
    md.attach(NOW, root, CORNERS, CODE, votes_text="")
    lanes = _state(root)["lanes"]
    assert lanes["list:us_totals"]["stake"] == 0 and lanes["list:us_totals"]["bookable"] is False
    assert "analyst:disagree:us_totals" not in lanes and lanes["list:team_corners"]["stake"] == 200


def test_agree_picks_are_never_a_desk_lane_and_never_booked():
    ko = _iso(NOW + timedelta(hours=2))
    uni = {f"draws|{i}": _lp("draws", i, "draw", 3.0, 1 if i < 20 else 0) for i in range(40)}
    verdicts = {pid: {"verdict": "disagree"} for pid in uni}
    uni["draws|agree"] = _lp("draws", "agree", "draw", 3.0, None, ko)
    uni["draws|new"] = _lp("draws", "new", "draw", 3.0, None, ko)
    verdicts["draws|agree"] = {"verdict": "agree"}
    verdicts["draws|new"] = {"verdict": "disagree"}
    root = _root(universe=uni, verdicts=verdicts)
    md.attach(NOW, root, lambda u: _event("1", "", "Draw"), CODE, votes_text="")
    lanes = _state(root)["lanes"]
    assert lanes["analyst:disagree:draws"]["stake"] == 200 and lanes["analyst:disagree:draws"]["paper"]["graded"] == 40
    doc = json.loads((root / "output" / "money_desk" / f"stake_{ko[:10]}.json").read_text())
    assert [p["id"] for p in doc["picks"]] == ["draws|new"]                      # one stake, the specific lane
    assert doc["picks"][0]["lane"] in ("analyst:disagree:draws", "list:draws")
    # the framework changes its mind before kick-off: the analyst's NGN 500 covers it, the desk lets go
    verdicts["draws|new"] = {"verdict": "agree"}
    (root / "data" / "analyst" / "state.json").write_text(json.dumps(verdicts))
    md.attach(NOW + timedelta(minutes=30), root, lambda u: _event("1", "", "Draw"), CODE, votes_text="")
    assert json.loads((root / "output" / "money_desk" / f"stake_{ko[:10]}.json").read_text())["picks"] == []


def _on_money(root, lane="list:team_corners", stake=200, since=None, last_step=None):
    """Put a lane on money by hand, with a desk book of real picks to grade it on."""
    since = since or _iso(NOW - timedelta(days=10))
    out = root / "output" / "money_desk"
    out.mkdir(parents=True, exist_ok=True)
    (out / "state.json").write_text(json.dumps({"lanes": {lane: {
        "stake": stake, "since": since, "last_step": last_step or since, "paper_from": None, "blocks": {}}}}))


def _real_book(root, picks, lane="list:team_corners", stake=200, price=2.0):
    (root / "data" / "money_desk").mkdir(parents=True, exist_ok=True)
    (root / "data" / "money_desk" / "book.json").write_text(json.dumps({
        pid: {"lane": lane, "stake": stake, "code": "C", "price": price, "ko": p["ko"], "event": p["event"],
              "home": "h", "away": "a", "pick": "x", "booked": _iso(NOW - timedelta(days=9)), "market_id": "166",
              "specifier": "", "outcome_id": "1"} for pid, p in picks.items()}))


def test_step_up_one_step_with_a_7_day_cool_down():
    lines = _winners("team_corners", n=30, won=18)                     # real: 30 graded at +20%
    root = _root(lines=lines)
    _on_money(root)
    _real_book(root, lines)
    md.attach(NOW, root, CORNERS, CODE, votes_text="")
    d = _dec(root)
    assert len(d) == 1 and (d[0]["from"], d[0]["to"]) == (200, 500) and "step up" in d[0]["rule"]
    md.attach(NOW + timedelta(days=1), root, CORNERS, CODE, votes_text="")      # 500 -> 1,000 must wait 7 days
    assert len(_dec(root)) == 1
    md.attach(NOW + timedelta(days=8), root, CORNERS, CODE, votes_text="")
    d = _dec(root)
    assert len(d) == 2 and (d[1]["from"], d[1]["to"]) == (500, 1000)
    md.attach(NOW + timedelta(days=20), root, CORNERS, CODE, votes_text="")     # NGN 1,000 is the top
    assert len(_dec(root)) == 2 and _state(root)["lanes"]["list:team_corners"]["stake"] == 1000


def test_step_up_needs_30_real_picks():
    lines = _winners("team_corners", n=29, won=20)
    root = _root(lines=lines)
    _on_money(root)
    _real_book(root, lines)
    md.attach(NOW, root, CORNERS, CODE, votes_text="")
    assert _dec(root) == []


def test_back_to_paper_then_30_new_paper_picks_before_promotion():
    lines = _winners("team_corners", n=40, won=24)
    real = dict(list(lines.items())[24:] + list(lines.items())[:4])      # 16 losers and 4 winners = 20 real
    root = _root(lines=lines)
    _on_money(root, stake=500)
    _real_book(root, real, stake=500)                                    # 4 of 20 at 2.0 = -60%
    md.attach(NOW, root, CORNERS, CODE, votes_text="")
    d = _dec(root)
    assert len(d) == 1 and (d[0]["from"], d[0]["to"]) == (500, 0) and "back to paper" in d[0]["rule"]
    ln = _state(root)["lanes"]["list:team_corners"]
    assert ln["stake"] == 0 and ln["paper_from"] and ln["paper"]["graded"] == 40      # the paper record keeps running
    md.attach(NOW + timedelta(days=1), root, CORNERS, CODE, votes_text="")           # +20% on paper, but none of it new
    assert len(_dec(root)) == 1
    later = NOW + timedelta(days=30)
    new = {f"team_corners|{i}": _lp("team_corners", i, "corners|9.5|over", 2.0, 1 if i < 118 else 0,
                                    _iso(NOW + timedelta(days=2))) for i in range(100, 130)}
    (root / "data" / "list_picks" / "book_lines.json").write_text(json.dumps({"picks": {**lines, **new}}))
    md.attach(later, root, CORNERS, CODE, votes_text="")
    d = _dec(root)
    assert len(d) == 2 and (d[1]["from"], d[1]["to"]) == (0, 200) and d[1]["evidence"]["paper"]["graded"] == 30


def test_cap_five_lanes_on_money():
    lists = ["team_corners", "cards", "fouls", "steady_corners", "early_goal", "second_half", "first_half_leagues"]
    lines = {}
    for lid in lists:
        lines.update(_winners(lid))
    root = _root(lines=lines)
    md.attach(NOW, root, CORNERS, CODE, votes_text="")
    lanes = _state(root)["lanes"]
    assert sum(1 for ln in lanes.values() if ln["stake"] > 0) == md.MAX_LANES == 5 and len(_dec(root)) == 5
    md.attach(NOW + timedelta(days=1), root, CORNERS, CODE, votes_text="")
    assert len(_dec(root)) == 5


def test_caps_per_pick_and_per_day_soonest_first():
    assert md.MAX_STAKE == 1000 and md.DAY_CAP == 5000 and md.ACCOUNTS == [1]
    cfg = {"promote": {"stake": 50000}, "step_up": {"ladder": [200, 500, 1000, 9000]}}
    lines = _winners("team_corners")
    day = (NOW + timedelta(hours=1)).strftime("%Y-%m-%d")
    for i in range(8):                                                    # 8 coming picks, 30 min apart
        lines[f"team_corners|n{i}"] = _lp("team_corners", f"n{i}", "corners|9.5|over", 2.0, None,
                                          _iso(NOW + timedelta(minutes=40 + 20 * i)))
    root = _root(lines=lines, config=cfg)
    r = md.rules(root)
    assert r["promote"]["stake"] == 1000 and r["step_up"]["ladder"] == [200, 500, 1000]   # the config cannot lift a cap
    out = md.attach(NOW, root, CORNERS, CODE, votes_text="")
    doc = json.loads((root / "output" / "money_desk" / f"stake_{day}.json").read_text())
    assert [p["id"] for p in doc["picks"]] == [f"team_corners|n{i}" for i in range(5)]       # soonest first
    assert all(p["stake_ngn"] == 1000 and p["accounts"] == [1] and p["code"] == "ABC123" for p in doc["picks"])
    assert sum(p["stake_ngn"] for p in doc["picks"]) == 5000 and "3 over the day cap" in out
    p = doc["picks"][0]
    assert {"code", "market_id", "ko", "home", "away", "pick", "price", "accounts", "stake_ngn", "lane"} <= set(p)
    assert p["market_id"] == "166" and p["specifier"] == "total=9.5" and p["outcome_id"] == "12" and p["price"] == 1.9


def test_no_booking_within_20_minutes_or_beyond_the_window_or_without_the_market():
    lines = _winners("team_corners")
    lines["team_corners|soon"] = _lp("team_corners", "soon", "corners|9.5|over", 2.0, None, _iso(NOW + timedelta(minutes=15)))
    lines["team_corners|far"] = _lp("team_corners", "far", "corners|9.5|over", 2.0, None, _iso(NOW + timedelta(hours=9)))
    lines["team_corners|gone"] = _lp("team_corners", "gone", "corners|10.5|over", 2.0, None, _iso(NOW + timedelta(hours=1)))
    lines["team_corners|ok"] = _lp("team_corners", "ok", "corners|9.5|over", 2.0, None, _iso(NOW + timedelta(hours=1)))
    root = _root(lines=lines)
    md.attach(NOW, root, CORNERS, CODE, votes_text="")
    book = json.loads((root / "data" / "money_desk" / "book.json").read_text())
    assert {pid for pid, e in book.items() if e.get("code")} == {"team_corners|ok"}
    assert md.selection(CORNERS("")["data"], ("166", "total=9.5", "Under 9.5")) is None
    closed = {"eventId": "e", "markets": [{"id": "166", "specifier": "total=9.5", "status": 2,
                                           "outcomes": [{"id": "1", "desc": "Over 9.5", "odds": "2"}]}]}
    assert md.selection(closed, ("166", "total=9.5", "Over 9.5")) is None


def test_veto_undoes_at_once_and_blocks_the_move_for_14_days():
    lines = _winners("team_corners")
    lines["team_corners|ok"] = _lp("team_corners", "ok", "corners|9.5|over", 2.0, None, _iso(NOW + timedelta(hours=2)))
    root = _root(lines=lines)
    md.attach(NOW, root, CORNERS, CODE, votes_text="")
    day = (NOW + timedelta(hours=2)).strftime("%Y-%m-%d")
    stake = root / "output" / "money_desk" / f"stake_{day}.json"
    assert len(json.loads(stake.read_text())["picks"]) == 1
    assert "No desk decision" in md.vote("MD-9", "veto", NOW, root)
    msg = md.vote("md-1", "veto", NOW + timedelta(minutes=5), root)
    assert msg.startswith("VETOED MD-1") and "14 days" in msg
    assert json.loads(stake.read_text())["picks"] == []                              # out of the bot's file at once
    ln = _state(root)["lanes"]["list:team_corners"]
    assert ln["stake"] == 0 and ln["since"] is None and _dec(root)[0]["status"] == "vetoed"
    assert "already vetoed" in md.vote("MD-1", "agree", NOW + timedelta(minutes=6), root)
    votes = (root / md.VOTES).read_text().strip().splitlines()
    assert len(votes) == 1 and json.loads(votes[0])["vote"] == "veto"
    md.attach(NOW + timedelta(days=13), root, CORNERS, CODE)                         # still blocked
    assert len(_dec(root)) == 1
    md.attach(NOW + timedelta(days=15), root, CORNERS, CODE)                         # the block has run out
    d = _dec(root)
    assert len(d) == 2 and d[1]["to"] == 200 and d[1]["status"] == "acting"


def test_veto_of_a_step_up_puts_the_old_stake_back_and_agree_confirms():
    lines = _winners("team_corners", n=30, won=18)
    root = _root(lines=lines)
    _on_money(root)
    _real_book(root, lines)
    md.attach(NOW, root, CORNERS, CODE, votes_text="")
    assert _state(root)["lanes"]["list:team_corners"]["stake"] == 500
    assert md.vote("MD-1", "agree", NOW, root).startswith("AGREED MD-1") and _dec(root)[0]["status"] == "agreed"
    assert md.vote("MD-1", "veto", NOW + timedelta(hours=1), root).startswith("VETOED MD-1")     # he may still change it
    ln = _state(root)["lanes"]["list:team_corners"]
    assert ln["stake"] == 200 and ln["since"] and "200>500" in ln["blocks"]


def test_a_vote_lost_to_a_clobbered_file_is_replayed_from_the_log():
    lines = _winners("team_corners")
    root = _root(lines=lines)
    md.attach(NOW, root, CORNERS, CODE, votes_text="")
    line = json.dumps({"id": "MD-1", "vote": "veto", "at": _iso(NOW + timedelta(minutes=10))})
    out = md.attach(NOW + timedelta(hours=3), root, CORNERS, CODE, votes_text=line + "\n" + line + "\nnot json\n")
    assert "1 vote(s) applied" in out and _dec(root)[0]["status"] == "vetoed"
    assert _state(root)["lanes"]["list:team_corners"]["stake"] == 0
    out = md.attach(NOW + timedelta(hours=6), root, CORNERS, CODE, votes_text=line)
    assert "0 vote(s) applied" in out


def test_kill_switch_no_lane_on_money():
    lines = _winners("team_corners")
    lines["team_corners|ok"] = _lp("team_corners", "ok", "corners|9.5|over", 2.0, None, _iso(NOW + timedelta(hours=2)))
    lines["team_corners|ok2"] = _lp("team_corners", "ok2", "corners|9.5|over", 2.0, None, _iso(NOW + timedelta(hours=7)))
    root = _root(lines=lines)
    day = (NOW + timedelta(hours=2)).strftime("%Y-%m-%d")
    os.environ["MONEY_DESK"] = "0"
    try:
        out = md.attach(NOW, root, CORNERS, CODE, votes_text="")
        assert "OFF" in out and _dec(root) == [] and _state(root)["enabled"] is False
        assert not (root / "output" / "money_desk" / f"stake_{day}.json").exists()
    finally:
        del os.environ["MONEY_DESK"]
    md.attach(NOW, root, CORNERS, CODE, votes_text="")                                  # on: promoted and booked
    stake = root / "output" / "money_desk" / f"stake_{day}.json"
    assert len(json.loads(stake.read_text())["picks"]) == 1
    os.environ["MONEY_DESK"] = "0"
    try:
        out = md.attach(NOW + timedelta(hours=3, minutes=30), root, CORNERS, CODE, votes_text="")
        assert "0 booked" in out and "OFF" in md.summary(root)
        md.attach(NOW + timedelta(minutes=10), root, CORNERS, CODE, votes_text="")
        assert json.loads(stake.read_text())["picks"] == []                             # unplayed picks leave the file
    finally:
        del os.environ["MONEY_DESK"]


def test_lower_league_board_is_a_lane_by_gap_band():
    lower = {f"sr:match:{i}": {"id": f"sr:match:{i}", "ko": _iso(NOW - timedelta(days=3)), "home": "h", "away": "a",
                              "option": "Under 2.5", "price": 2.0, "band": "5-10%", "won": i < 24} for i in range(40)}
    lower["sr:match:new"] = {"id": "sr:match:new", "ko": _iso(NOW + timedelta(hours=2)), "home": "h", "away": "a",
                             "option": "Under 2.5", "price": 2.0, "band": "5-10%"}
    root = _root(lower=lower)
    md.attach(NOW, root, lambda u: _event("18", "total=2.5", "Under 2.5"), CODE, votes_text="")
    assert _state(root)["lanes"]["lower:5-10"]["stake"] == 200
    day = (NOW + timedelta(hours=2)).strftime("%Y-%m-%d")
    doc = json.loads((root / "output" / "money_desk" / f"stake_{day}.json").read_text())
    assert doc["picks"][0]["lane"] == "lower:5-10" and doc["picks"][0]["stake_ngn"] == 200


def test_telegram_veto_is_the_architects_chat_only():
    from output import telegram_commands as tc
    old = os.environ.get("TELEGRAM_CHAT_ID")
    os.environ["TELEGRAM_CHAT_ID"] = "111"
    try:
        assert tc.handle("/veto MD-1", "999").startswith("REFUSED")
        assert tc.handle("/agree MD-1", None).startswith("REFUSED")
        assert tc.handle("/veto", "111") == "Usage: /veto MD-3"
    finally:
        if old is None:
            del os.environ["TELEGRAM_CHAT_ID"]
        else:
            os.environ["TELEGRAM_CHAT_ID"] = old


def test_the_sweep_runs_the_desk_and_the_workflow_passes_the_switch():
    assert "money_desk.attach(now)" in (ROOT / "monitor" / "universe_sweep.py").read_text(encoding="utf-8")
    assert '"output/money_desk"' in (ROOT / "monitor" / "universe_sweep.py").read_text(encoding="utf-8")
    assert "MONEY_DESK: ${{ vars.MONEY_DESK }}" in (ROOT / ".github" / "workflows" / "universe.yml").read_text(encoding="utf-8")


def main() -> None:
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("money_desk_test OK")


if __name__ == "__main__":
    main()
