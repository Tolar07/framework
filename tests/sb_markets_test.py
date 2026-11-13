"""engine/sb_markets.py (framework#567): catalogue, mapping, model-vs-price value rows, grading. Offline."""
import json
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import sb_markets as sb  # noqa: E402
from engine import stat_lines as sl  # noqa: E402

NOW = datetime(2026, 11, 13, 18, 0, tzinfo=UTC)
KO = NOW + timedelta(hours=1)


def mk(mid, name, spec, o, u, status=0):
    t = spec.split("=")[1]
    return {"id": mid, "desc": name, "specifier": spec, "status": status,
            "outcomes": [{"desc": f"Over {t}", "odds": str(o)}, {"desc": f"Under {t}", "odds": str(u)}]}


assert sb.classify("Corners - Over/Under") == ("corners", "match")
assert sb.classify("Home Team Shots on Target") == ("sot", "home")
assert sb.classify("1st Half - Corners") == ("corners", "h1")
assert sb.classify("Away Team Offsides") == ("offsides", "away")
assert sb.classify("Correct Score") is None and sb.classify("Over/Under") is None

EVENT = {"eventId": "sr:match:9", "estimateStartTime": int(KO.timestamp() * 1000),
         "homeTeamName": "Brighton & Hove Albion", "awayTeamName": "Leeds United",
         "markets": [mk(166, "Corners - Over/Under", "total=9.5", 2.10, 1.70),
                     mk(166, "Corners - Over/Under", "total=10.5", 2.60, 1.45, status=2),
                     mk(900, "Home Team Shots on Target", "total=3.5", 1.90, 1.85),
                     mk(901, "Mystery Stat", "total=1.5", 1.9, 1.9),
                     mk(18, "Over/Under", "total=2.5", 1.8, 2.0)]}
cat: dict = {}
sb.catalogue_update(cat, EVENT)
assert cat["166"]["stat"] == "corners" and cat["166"]["events"] == 2
assert cat["901"]["stat"] is None and cat["18"]["stat"] is None      # UNMAPPED, never guessed
wide = sb.wide_lines(EVENT)
assert wide == {"corners:match": {"9.5": [2.1, 1.7]}, "sot:home": {"3.5": [1.9, 1.85]}}, wide

GAME = {"home": "Brighton", "away": "Leeds", "events": {
    "corners": {"over": {"9.5": 0.55}}, "sot": {"home_over": {"3.5": 0.50}}}}
rows = sb.watch_rows(wide, GAME)
by = {(r["stat"], r["side"]): r for r in rows}
assert by[("corners", "over")]["edge"] == round(0.55 * 2.1 - 1, 4) and by[("corners", "over")]["target"]
assert not by[("corners", "under")]["target"]            # 0.45 x 1.70 < 1
assert not by[("sot", "over")]["target"]                 # 0.50 x 1.90 = -5%
assert sb.watch_rows({"offsides:match": {"4.5": [2, 2]}}, GAME) == []     # model silent -> PENDING, no row
assert sb.find_game([GAME], "Brighton & Hove Albion", "Leeds United") is GAME
assert sb.find_game([GAME], "Chelsea", "Leeds United") is None

store: dict = {}
sb.observe(store, EVENT, "t1", [GAME])
sb.observe(store, EVENT, "t2", [GAME])
assert store["sr:match:9"]["first"]["at"] == "t1" and store["sr:match:9"]["last"]["at"] == "t2"
rep = sb.family_report(list(store.values()))
assert rep["corners:match"]["target"] == 1 and rep["sot:home"]["target"] == 0

# end to end through stat_lines.run: catalogue + wide file, then graded after the match
with tempfile.TemporaryDirectory() as d:
    root = Path(d)
    (root / "output/events").mkdir(parents=True)
    (root / "output/events/events_2026-11-13.json").write_text(json.dumps({"games": [GAME]}))

    def get(url):
        if "pcUpcomingEvents" in url:
            return {"data": {"tournaments": [{"events": [EVENT]}]}} if url.endswith("pageNum=1") \
                else {"data": {"tournaments": []}}
        return {"data": EVENT}

    sl.run(now=NOW, root=root, get=get)
    w = json.loads((root / "data/stat_lines/wide_pending.json").read_text())
    assert w["sr:match:9"]["model_found"] and w["sr:match:9"]["last"]["watch"]
    assert json.loads((root / "data/stat_lines/market_catalogue.json").read_text())["900"]["stat"] == "sot"
    (root / "data/world_facts").mkdir(parents=True)
    (root / "data/world_facts_detail").mkdir(parents=True)
    fs = {"id": "Z1", "ko": KO.strftime("%Y-%m-%dT%H:%MZ"), "league": "ENGLAND: Premier League",
          "home": "Brighton", "away": "Leeds", "ft": [2, 1], "ht": [1, 0]}
    (root / "data/world_facts/2026-11.jsonl").write_text(json.dumps(fs) + "\n")
    (root / "data/world_facts_detail/2026-11.jsonl").write_text(json.dumps(
        {**fs, "stats": {"match": {"corners": [6, 4], "yellow": [2, 1], "red": [0, 0]}}}) + "\n")
    sl.run(now=KO + timedelta(hours=4), root=root, get=lambda u: {"data": {"tournaments": []}})
    g = [json.loads(x) for x in (root / "data/stat_lines/graded/wide/2026-11.jsonl").read_text().splitlines()]
    by = {(r["stat"], r["side"]): r for r in g[0]["watch"]}
    assert by[("corners", "over")]["won"] == 1 and by[("corners", "over")]["pnl"] == 1.1   # 10 corners > 9.5
    assert by[("sot", "over")]["won"] is None and by[("sot", "over")]["actual"] is None     # no count -> PENDING
    assert json.loads((root / "data/stat_lines/wide_pending.json").read_text()) == {}
print("sb_markets_test OK")
