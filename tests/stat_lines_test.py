"""
engine/stat_lines.py + backtest/stat_lines_study.py + backtest/stats_claims_proof.py helpers. Offline, no network:
a fake SportyBet feed and a fake world_facts archive in a temp folder.
"""
import json
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backtest"))
import stat_lines_study  # noqa: E402
import stats_claims_proof as scp  # noqa: E402

from engine import stat_lines as sl  # noqa: E402

NOW = datetime(2026, 11, 12, 18, 0, tzinfo=UTC)
KO = NOW + timedelta(hours=1)


def mk(mid, spec, over, under, status=0):
    t = spec.split("=")[1]
    return {"id": mid, "specifier": spec, "status": status,
            "outcomes": [{"desc": f"Over {t}", "odds": str(over)}, {"desc": f"Under {t}", "odds": str(under)}]}


EVENT = {"eventId": "sr:match:1", "estimateStartTime": int(KO.timestamp() * 1000),
         "homeTeamName": "Brighton & Hove Albion", "awayTeamName": "Leeds United",
         "markets": [mk(166, "total=9.5", 1.85, 1.85), mk(166, "total=10", 2.2, 1.6), mk(139, "total=3.5", 1.9, 1.8),
                     mk(68, "total=0.5", 1.35, 3.0), mk(68, "total=1.5", 2.6, 1.45, status=2), mk(18, "total=2.5", 1.8, 2.0)]}

# lines_of keeps only the three stats markets, open lines only
lines = sl.lines_of(EVENT)
assert lines == {"corners": {"9.5": [1.85, 1.85], "10": [2.2, 1.6]}, "bookings": {"3.5": [1.9, 1.8]},
                 "first_half": {"0.5": [1.35, 3.0]}}, lines

# settle: whole line landing exactly is a push
assert sl.settle("10", 10) == {"over": None, "under": None}
assert sl.settle("9.5", 10) == {"over": 1, "under": 0}

# result_from: bookings only without a red card
base = {"ht": [1, 0]}
assert sl.result_from(base, {"stats": {"match": {"corners": [6, 4], "yellow": [2, 1], "red": [0, 0]}}}) == \
    {"first_half": 1, "corners": 10, "bookings": 3}
assert "bookings" not in sl.result_from(base, {"stats": {"match": {"yellow": [2, 1], "red": [1, 0]}}})


def fake_get(url):
    if "pcUpcomingEvents" in url:
        return {"data": {"tournaments": [{"events": [EVENT]}]}} if "pageNum=1&" in url or url.endswith("pageNum=1") else {"data": {"tournaments": []}}
    return {"data": EVENT}


with tempfile.TemporaryDirectory() as d:
    root = Path(d)
    out = sl.run(now=NOW, root=root, get=fake_get)
    assert "1 pages read (1 new)" in out, out
    pend = json.loads((root / "data/stat_lines/pending.json").read_text())
    assert pend["sr:match:1"]["first"]["lines"]["corners"]["9.5"] == [1.85, 1.85]
    # a second look keeps the first, replaces the last
    sl.run(now=NOW + timedelta(minutes=30), root=root, get=fake_get)
    pend = json.loads((root / "data/stat_lines/pending.json").read_text())
    assert pend["sr:match:1"]["looks"] == 2
    # world_facts archive (Flashscore spelling differs) -> graded after kick-off + 3 h
    (root / "data/world_facts").mkdir(parents=True)
    (root / "data/world_facts_detail").mkdir(parents=True)
    fs = {"id": "AbC123", "ko": KO.strftime("%Y-%m-%dT%H:%MZ"), "league": "ENGLAND: Premier League",
          "home": "Brighton", "away": "Leeds", "ft": [2, 1], "ht": [1, 0]}
    (root / "data/world_facts/2026-11.jsonl").write_text(json.dumps(fs) + "\n")
    (root / "data/world_facts_detail/2026-11.jsonl").write_text(json.dumps(
        {**fs, "goals": None, "stats": {"match": {"corners": [6, 4], "yellow": [2, 1], "red": [0, 0]}}}) + "\n")
    out = sl.run(now=KO + timedelta(hours=4), root=root, get=lambda u: {"data": {"tournaments": []}})
    assert "graded 1" in out, out
    g = [json.loads(x) for x in (root / "data/stat_lines/graded/2026-11.jsonl").read_text().splitlines()]
    assert g[0]["fs_id"] == "AbC123" and g[0]["result"] == {"first_half": 1, "corners": 10, "bookings": 3}
    assert g[0]["graded"]["corners"]["9.5"] == {"over": 1, "under": 0}
    assert g[0]["graded"]["corners"]["10"] == {"over": None, "under": None}
    assert g[0]["graded"]["first_half"]["0.5"] == {"over": 1, "under": 0}
    assert json.loads((root / "data/stat_lines/pending.json").read_text()) == {}
    # the study runs on it and says PENDING below the bar
    msg = stat_lines_study.main(root)
    assert "1 graded matches" in msg, msg
    rep = (root / "output/stat_lines/STAT_LINES_STUDY.md").read_text()
    assert "PENDING (too few)" in rep

# proof-study helpers
lo, hi = scp.wilson(70, 100)
assert 0.62 < lo < 0.70 < hi < 0.78
r, ci, n = scp.corr([1, 2, 3, 4, 5], [2, 4, 6, 8, 11])
assert r > 0.98 and n == 5
assert scp.money_verdict(50, 0.1, 0.2) == "TOO FEW BETS"
assert scp.money_verdict(500, -0.08, -0.02).startswith("LOSS")
assert scp._season_key("2019/2020") == 2019 and scp._season_key("2016") == 2016
print("stat_lines_test OK")
