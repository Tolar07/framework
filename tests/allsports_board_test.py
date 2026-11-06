"""The Betfair board, every sport except football (Architect 2026-11-06). No network: files in a temp dir."""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from output import allsports_board as AB  # noqa: E402

NOW = datetime(2026, 11, 12, 10, tzinfo=UTC)
DAY = "2026-11-12"


def w(p: Path, d) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d), encoding="utf-8")


def fixture(td: Path) -> tuple[Path, Path, Path]:
    out, data, bots = td / "output", td / "data", td / "bots"
    w(out / "multisport" / "tennis" / f"ms_{DAY}.json", {"picks": [
        {"home": "Shelton, Ben", "away": "Paul, Tommy", "ko": "2026-11-12T13:00:00Z", "comp": "ATP Paris",
         "pick": "Ben Shelton to win", "price": 1.70, "fair": 0.62, "value": 0.054, "code": "TN1", "paper": False},
        {"home": "A, B", "away": "C, D", "ko": "2026-11-12T20:00:00Z", "pick": "B A to win", "price": 1.5,
         "fair": 0.7, "value": 0.05, "code": "TN2", "paper": False},
        {"home": "E, F", "away": "G, H", "ko": "2026-11-12T11:00:00Z", "pick": "F E to win", "price": 1.5,
         "fair": 0.7, "value": 0.05, "code": "TN3", "paper": False}],
        "games": {"g1": {"home": "Shelton, Ben", "away": "Paul, Tommy", "sides": {}}}})
    w(out / "multisport" / "darts" / f"ms_{DAY}.json", {"picks": [], "games": {"g": {
        "home": "Price, Gerwyn", "away": "Smith, Michael", "ko": "2026-11-12T19:00:00Z", "sides": {
            "darts:186||Home": {"last": {"price": 1.60, "fair": 0.60, "model": None}},
            "darts:186||Away": {"last": {"price": 9.0, "fair": None, "model": 0.3}}}}}})
    w(out / "multisport" / "table_tennis" / f"ms_{DAY}.json", {"picks": [
        {"home": "Lin, Yun-Ju", "away": "Wang, Chuqin", "ko": "2026-11-12T12:00:00Z", "pick": "Lin to win",
         "price": 1.8, "fair": 0.6, "value": 0.08, "code": "TT1"}], "games": {}})
    w(bots / "betfair-agent" / "ledger" / f"paper_{DAY}.json", {
        "bets": [{"code": "TN1", "sport": "tennis", "mode": "live", "stake": 1.0, "price": 1.74, "size_matched": 1.0,
                  "avg_price": 1.74, "result": "WON", "pnl": 0.72},
                 {"code": "FB1", "sport": "football", "mode": "live", "stake": 1, "size_matched": 1}],
        "skipped": {"TN3": "Shelton v Paul: price 1.15 < 1.2"}})
    w(bots / "betfair-agent" / "ledger" / "heartbeat.json", {"wallet": 24.5})
    w(data / "multisport" / "tennis" / "scoreboard.json", {"picks": 3, "won": 2, "pnl": 1.1, "clv_fair_avg": 0.012,
                                                           "all_sides_by_market": {"186": {"sides": 40}}})
    return out, data, bots


def test_board_sections_status_and_study_lines():
    with tempfile.TemporaryDirectory() as t:
        out, data, bots = fixture(Path(t))
        text = AB.render(DAY, NOW, "RUN1", out=out, bots=bots, data=data)
    assert "Run ID: RUN1" in text and "EVERY SPORT EXCEPT FOOTBALL" in text
    assert "LIVE: Betfair places these" in text
    assert "1 placed · 1 matched · 1 settled £+0.72 · wallet £24.50" in text, "football bets not counted"
    assert "Ben Shelton v Tommy Paul" in text and "Betfair: matched £1.00 @1.74 · won £+0.72" in text
    assert "Betfair: skipped — Shelton v Paul: price 1.15" in text
    assert "Betfair: waits (bets from 17:00, 3 h before)" in text, "20:00 UTC = 20:00 UK, window from 17:00"
    assert "DARTS — 0 picks" in text and "Gerwyn Price v Michael Smith: Home @1.60" in text
    assert "@9.00" not in text, "study lines keep to the pick price range"
    assert "Betfair: — (Betfair lists no table tennis)" in text
    assert "ICE HOCKEY: NO DATA — PENDING" in text, "a missing board file reads PENDING (HR35)"
    assert "tennis: picks 3 (won 2), +1.10u · value vs close +1.2%; 40 sides graded" in text
    heads = [ln for ln in text.splitlines() if " — " in ln and " pick" in ln]
    assert heads and not [h for h in heads if "FOOTBALL" in h and "AMERICAN" not in h], "no football section"


def test_one_sport_full_list_and_split():
    with tempfile.TemporaryDirectory() as t:
        out, data, bots = fixture(Path(t))
        one = AB.render(DAY, NOW, out=out, bots=bots, data=data, only="tennis")
        full = AB.render(DAY, NOW, out=out, bots=bots, data=data)
    assert "DARTS" not in one and one.count("Betfair:") == 3 and "SCORECARD" not in one
    parts = AB.split(full * 3)
    assert all(len(p) <= AB.MAX_CHARS for p in parts) and len(parts) >= 2
    assert AB.sport_alias("hockey") == "ice_hockey" and AB.sport_alias("NFL") == "american_football"
    assert AB.sport_alias("football") is None, "football is not on this board"


def test_shadow_header_before_12_nov():
    with tempfile.TemporaryDirectory() as t:
        out, data, bots = fixture(Path(t))
        text = AB.render("2026-11-11", NOW, out=out, bots=bots, data=data)
    assert "SHADOW until 12 Nov" in text


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("allsports_board_test: OK")
