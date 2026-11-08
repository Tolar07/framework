"""Experiment engine sport slots (framework#355, order 50): every rollout sport has its own slot,
strategies compete on the sport board's graded picks and every-game favourites, the promotion test
is the same, and the slot is RECORD-ONLY (a qualifying shadow is flagged, never swapped in)."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import experiments as X  # noqa: E402
from engine import multisport as ms  # noqa: E402


def _pick(gid: str, price: float, won: bool, market: str = "186", value: float = 0.05,
          source: str = "matchbook", clv: float | None = 0.02) -> dict:
    return {"sb_event_id": gid, "home": f"A{gid}", "away": f"B{gid}", "market_id": market, "price": price,
            "fair": 0.62, "chance": 0.62, "value": value, "source": source,
            "result": "won" if won else "lost", "pnl": price - 1 if won else -1.0, "clv_fair": clv}


def _game(fav: float, dog: float, fav_won: bool, sport: str = "tennis") -> dict:
    return {"home": "H", "away": "A", "ko": "2026-11-08T12:00:00Z", "result": {"final": [2, 0]},
            "sides": {f"{sport}:186||Home": {"first": {"price": fav, "fair": 0.6}, "last": {"price": fav, "fair": 0.62},
                                             "won": int(fav_won)},
                      f"{sport}:186||Away": {"first": {"price": dog, "fair": 0.4}, "last": {"price": dog, "fair": 0.38},
                                             "won": int(not fav_won)},
                      f"{sport}:189|total=22.5|Over": {"first": {"price": 1.4}, "won": 1}}}


def test_every_rollout_sport_has_a_slot():
    assert set(X.SPORT_SLOTS) == {"ice_hockey", *ms.SPORTS}, "one slot per rollout sport (engine/multisport.SPORTS)"
    ro = json.loads((ROOT / "config" / "sport_rollout.json").read_text(encoding="utf-8"))
    want = {c for s in ro["sports"] for c in (s.get("covers") or [s["sport"]])}
    assert want == set(X.SPORT_SLOTS), f"rollout sports without a slot: {sorted(want - set(X.SPORT_SLOTS))}"
    sts = X.strategies()
    names = [s.name for s in sts]
    assert len(names) == len(set(names)), "strategy names are unique"
    for sp in X.SPORT_SLOTS:
        mine = [s for s in sts if s.slot == sp]
        assert X.DEFAULT[sp] in {s.name for s in mine} and len(mine) >= 8, f"{sp}: default + shadows"
        assert all(not s.wireable for s in mine), f"{sp}: record-only, never wired"
    assert X.SLOTS == ("singles", "accas", "safe3", "nba"), "the boards' own slots are unchanged"


def test_load_days_and_bets():
    with tempfile.TemporaryDirectory() as t:
        ms_dir, ih_dir, picks = Path(t) / "ms", Path(t) / "ih", Path(t) / "picks"
        picks.mkdir()
        (ms_dir / "tennis").mkdir(parents=True)
        ih_dir.mkdir()
        doc = {"date": "2026-11-08", "sport": "tennis",
               "picks": [_pick("1", 1.40, True), _pick("2", 1.80, False, market="189", value=0.10, source="elo")],
               "games": {"1": _game(1.40, 2.90, True), "2": _game(2.40, 1.55, False), "3": _game(1.10, 7.0, True)}}
        (ms_dir / "tennis" / "ms_2026-11-08.json").write_text(json.dumps(doc), encoding="utf-8")
        hdoc = {"date": "2026-11-07", "picks": [_pick("9", 1.70, True, market="406")],
                "games": {"9": {"home": "H", "away": "A", "sides": {
                    "H:406||Home": {"first": {"price": 1.70}, "last": {"price": 1.65, "fair": 0.6}, "won": 1},
                    "H:406||Away": {"first": {"price": 2.20}, "won": 0}}}}}
        (ih_dir / "ih_2026-11-07.json").write_text(json.dumps(hdoc), encoding="utf-8")
        days = X.load_days(picks, picks, ih_dir=ih_dir, ms_dir=ms_dir)
    by = {d["day"]: d for d in days}
    ten = by["2026-11-08"]
    assert len(ten["sports"]["tennis"]) == 2
    fav = ten["sport_sides"]["tennis"]
    # game 1: home 1.40 won; game 2: away 1.55 is the shorter side and won; game 3: 1.10 is outside the band
    assert [(f["price"], f["result"]) for f in fav] == [(1.40, "won"), (1.55, "won")]
    assert all(1.20 <= f["price"] <= 2.00 for f in fav), "favourites inside the board band only"
    assert by["2026-11-07"]["sport_sides"]["ice_hockey"][0]["price"] == 1.70
    st = {s.name: s for s in X.strategies()}
    allp = X.board_bets(st[X.DEFAULT["tennis"]], days)
    assert len(allp) == 2 and abs(sum(b["pnl"] for b in allp) - (0.40 - 1.0)) < 1e-9
    win = X.board_bets(st["TE1 tennis: winner only"], days)
    assert len(win) == 1 and win[0]["clv"] == 0.02
    assert len(X.board_bets(st["TE3 tennis: value +8% or more"], days)) == 1
    assert len(X.board_bets(st["TE6 tennis: exchange-priced only"], days)) == 1
    assert len(X.board_bets(st["TE8 tennis: every-game favourite"], days)) == 2
    assert len(X.board_bets(st["IH0 ice hockey board picks"], days)) == 1
    assert X.sport_bet({"result": "void", "price": 1.5, "clv": None}, "d") is None, "a void is no bet"


def _bulk_days(n: int) -> list[dict]:
    """Winner picks win at 1.60 and beat the close; line picks lose."""
    out = []
    for k in range(n):
        day = f"2026-11-{9 + k // 10:02d}"
        legs = []
        for i in range(10):
            w = i % 2 == 0
            legs.append({"fixture": f"{k}-{i}", "market": "186" if w else "189", "price": 1.60, "chance": 0.62,
                         "value": 0.05, "source": "matchbook", "result": "won" if (w and i != 8) else "lost",
                         "clv": 0.04 + 0.001 * (i % 3) if w else -0.03 - 0.001 * (i % 3)})
        out.append({"day": day, "legs": [], "slips": {"accas": [], "safe3": []}, "sports": {"darts": legs}})
    return out


def test_record_only_flag_never_swap():
    days = _bulk_days(30)   # 300 picks, 150 on the winner market
    reg0 = X.load_registry(Path(tempfile.gettempdir()) / "no_such_registry.json")
    reg0["live"]["darts"] = "DA1 darts: winner only"          # even a hand-edited registry is not obeyed
    reg, events = X.evaluate(days, {}, reg0, "2026-12-15")
    assert reg["live"]["darts"] == X.DEFAULT["darts"], "a sport slot is always the board's own picks"
    row = reg["standings"]["DA1 darts: winner only"]
    assert row["status"] == "shadow" and row["counted"]["n"] == 150
    ev = [e for e in events if e["strategy"] == "DA1 darts: winner only"]
    assert ev and ev[0]["event"] == "qualifies-not-wireable", "a qualifying sport shadow is flagged"
    assert not [e for e in events if e["event"] == "promote" and e["slot"] in X.SPORT_SLOTS], "never promoted"
    assert "DA1 darts: winner only" in reg["flagged"]
    _reg2, ev2 = X.evaluate(days, {}, reg, "2026-12-16")
    assert not [e for e in ev2 if e["strategy"] == "DA1 darts: winner only"], "flagged once"
    assert "sports (record-only): darts 300 bets" in X.brief(reg)
    assert "darts" not in X.live_rules(Path(tempfile.gettempdir()) / "no_such_registry.json")


def test_registry_forces_sport_defaults():
    with tempfile.TemporaryDirectory() as t:
        p = Path(t) / "s.json"
        p.write_text(json.dumps({"live": {"tennis": "TE4 tennis: price 1.20-1.50"}}), encoding="utf-8")
        reg = X.load_registry(p)
    assert all(reg["live"][sp] == X.DEFAULT[sp] for sp in X.SPORT_SLOTS)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("experiment_sports_test: OK")
