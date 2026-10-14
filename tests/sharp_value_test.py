"""
SHARP VALUE TEST — the parallel list's one rule, offline.

What it pins down (engine/sharp_value.py, monitor/sharp_list.py):
  * a price at or below the exchange's fair price is never taken, however
    likely the outcome — this is the whole difference from the board;
  * the pick is the biggest edge above fair inside the band, not the
    shortest price and not the most likely outcome;
  * a price too far above fair is reported as suspect, never picked (a stale
    line or a mismatched fixture would otherwise look like free money);
  * a suspended or closed market's stale price is ignored;
  * a fixture the exchange does not price produces nothing (HR35), and the
    rendered list says NO PICK rather than showing an empty table.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine import sharp_value as sv  # noqa: E402
from monitor import sharp_list  # noqa: E402

FAILED: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"{'  OK  ' if ok else ' FAIL '} {name}" + (f"  ({detail})" if detail else ""))
    if not ok:
        FAILED.append(name)


def mkt(mid, spec, outcomes, status=0):
    return {"id": mid, "specifier": spec, "status": status,
            "outcomes": [{"id": f"{mid}-{i}", "desc": d, "odds": str(o)}
                         for i, (d, o) in enumerate(outcomes, 1)]}


# The exchange: home 60%, draw 24%, away 16%; over 2.5 55%, under 45%.
FAIR = {"h": 0.60, "d": 0.24, "a": 0.16, "o25": 0.55, "u25": 0.45}
BOOK = {("E0", "Arsenal", "Chelsea"): FAIR}

# --------------------------------------------------------------------------
# fair_row: only a fixture football-data carries, in a league it has a code for
check("fair_row: finds the fixture by league code",
      sv.fair_row(BOOK, "Premier League", "Arsenal", "Chelsea") == FAIR)
check("fair_row: unknown league -> None (HR35)",
      sv.fair_row(BOOK, "Not A League", "Arsenal", "Chelsea") is None)
check("fair_row: fixture not in fixtures.csv -> None (HR35)",
      sv.fair_row(BOOK, "Premier League", "Arsenal", "Spurs") is None)

# --------------------------------------------------------------------------
# A board-shaped ladder: the home favourite is priced BELOW fair (1.60 vs the
# exchange's 1.667) — exactly the pick the board takes every day. The value is
# elsewhere: Draw or Away at 2.60 against a fair 2.50, and the 16% away side at
# 6.80 against a fair 6.25 — real value, but outside the band.
LADDER = [
    mkt("1", "", [("Home", 1.60), ("Draw", 3.90), ("Away", 6.80)]),
    mkt("10", "", [("Home or Draw", 1.17), ("Draw or Away", 2.60), ("Home or Away", 1.28)]),
    mkt("18", "total=2.5", [("Over 2.5", 1.80), ("Under 2.5", 2.05)]),
]
rows = sv.scan(LADDER, FAIR)
by_outcome = {r["outcome"]: r for r in rows}
check("scan: prices every outcome the exchange covers", len(rows) == 8, f"{len(rows)} rows")
check("scan: the short favourite is BELOW fair",
      by_outcome["Home"]["sharp_ev"] < 0, f'{by_outcome["Home"]["sharp_ev"]:+.3f}')
check("scan: fair price is the exchange's, not ours",
      abs(by_outcome["Home"]["fair_price"] - 1.667) < 0.002)

best = sv.pick(rows)
check("pick: takes the value, not the favourite",
      best is not None and best["outcome"] == "Draw or Away", best["outcome"] if best else "none")
check("pick: the 16% side's +8.8% is outside the band, so not taken",
      best is not None and best["price"] <= sv.BAND[1]
      and by_outcome["Away"]["sharp_ev"] > best["sharp_ev"],
      f'away +{by_outcome["Away"]["sharp_ev"]*100:.1f}% @ {by_outcome["Away"]["price"]}')
check("pick: the edge taken is real", best is not None and best["sharp_ev"] >= sv.MIN_EV,
      f'{best["sharp_ev"]:+.3f}' if best else "")

# Two candidates above fair: the bigger edge wins, not the shorter price.
two = sv.scan([mkt("18", "total=2.5", [("Over 2.5", 1.90), ("Under 2.5", 2.40)])], FAIR)
pick_two = sv.pick(two)
check("pick: biggest edge above fair wins, not the shorter price",
      pick_two is not None and pick_two["outcome"] == "Under 2.5",
      f'{[(r["outcome"], round(r["sharp_ev"], 3)) for r in two]}')

# Nothing above fair -> no pick. The normal answer, and the point.
none_above = sv.scan([mkt("1", "", [("Home", 1.60), ("Draw", 3.80), ("Away", 5.80)])], FAIR)
check("pick: nothing above fair -> None, never a best-of-a-bad-lot",
      sv.pick(none_above) is None)

# --------------------------------------------------------------------------
# Too good to be true: 2.60 on a 55% chance is +43% over fair — inside the band
# and the biggest edge on the ladder, and still not a pick.
stale = sv.scan([mkt("18", "total=2.5", [("Over 2.5", 2.60)])], FAIR)
check("suspect: an impossible edge is reported", len(sv.suspect(stale)) == 1)
check("suspect: and never picked", sv.pick(stale) is None)

# A closed line carries a stale price; it is not an offer.
closed = sv.scan([mkt("18", "total=2.5", [("Over 2.5", 1.80), ("Under 2.5", 2.05)], status=2)],
                 FAIR)
check("price_of: a closed market is ignored", closed == [], f"{len(closed)} rows")

# Double chance is the sum of two exchange prices, not one.
dc = {r["outcome"]: r for r in sv.scan(
    [mkt("10", "", [("Draw or Away", 2.40)])], FAIR)}
check("scan: double chance uses the summed exchange chance",
      abs(dc["Draw or Away"]["sharp_p"] - 0.40) < 1e-6,
      f'{dc["Draw or Away"]["sharp_p"]}')

# --------------------------------------------------------------------------
# An empty day is stated, never shown as a blank list (HR35).
empty = {"date": "2026-10-15", "run_id": "SHARP-test", "fetched_utc": "2026-10-14T00:00:00Z",
         "rule": {"min_ev": sv.MIN_EV, "band": list(sv.BAND), "max_ev": sv.MAX_EV},
         "fixtures_on_day": 9, "fixtures_priced_by_exchange": 4,
         "picks": [], "suspect": [], "flags": []}
text = sharp_list.render(empty)
check("render: an empty list says NO PICK — PENDING", "NO PICK — PENDING" in text)
check("render: never claims to be the board", "not the board" in text)

# --------------------------------------------------------------------------
# GRADING — the measurement is the point, so the settle path is exercised on a
# scratch store with a stubbed result feed (no network in a test).
import json  # noqa: E402
import tempfile  # noqa: E402

import data.flashscore_results as _fs  # noqa: E402

_store = Path(tempfile.mkdtemp()) / "sharp"
_store.mkdir()
(_store / "sharp_2026-10-01.json").write_text(json.dumps({
    "date": "2026-10-01", "picks": [
        {"home": "Norwich", "away": "Southampton", "kickoff": "2026-10-01T18:45:00Z",
         "fixture": "Norwich v Southampton (Championship)", "key": "SB:18|total=2.5|Over 2.5",
         "outcome": "Over 2.5", "price": 1.60, "sharp_p": 0.643, "sharp_ev": 0.029,
         "result": None, "ft": None},
        {"home": "Leeds", "away": "Hull", "kickoff": "2026-10-01T18:45:00Z",
         "fixture": "Leeds v Hull (Championship)", "key": "SB:1||Home",
         "outcome": "Home", "price": 2.10, "sharp_p": 0.50, "sharp_ev": 0.05,
         "result": None, "ft": None},
    ]}), encoding="utf-8")
_events = [
    {"home": "Norwich", "away": "Southampton", "date": "2026-10-01", "fthg": 2, "ftag": 1,
     "fh_home": 1, "fh_away": 0, "finished_regular": True, "finished_other": False},
    {"home": "Leeds", "away": "Hull", "date": "2026-10-01", "fthg": 0, "ftag": 1,
     "fh_home": 0, "fh_away": 0, "finished_regular": True, "finished_other": False},
]
_real_since, _real_find = _fs.results_since, _fs.find_result
_fs.results_since = lambda *a, **k: _events
_fs.find_result = lambda events, home, away, day: next(
    (e for e in events if e["home"] == home and e["away"] == away), None)
_saved_store = sharp_list.STORE
sharp_list.STORE = _store
try:
    _report = sharp_list.grade(today="2026-10-02")
finally:
    sharp_list.STORE = _saved_store
    _fs.results_since, _fs.find_result = _real_since, _real_find

_doc = json.loads((_store / "sharp_2026-10-01.json").read_text(encoding="utf-8"))
_res = [p["result"] for p in _doc["picks"]]
check("grade: 2-1 settles Over 2.5 as won", _res[0] == "won", f"{_res[0]} ({_doc['picks'][0]['ft']})")
check("grade: 0-1 settles the home side as lost", _res[1] == "lost", f"{_res[1]}")
check("grade: the record is stated in units, not a win rate alone",
      "1 won, 1 lost" in _report and "-0.40u" in _report, _report)
check("grade: the sharp edge taken is reported beside the result",
      "+4.0%" in _report, _report)

print()
if FAILED:
    print(f"FAILED: {len(FAILED)}")
    for n in FAILED:
        print(f"  - {n}")
    sys.exit(1)
print("sharp value: all checks passed")
