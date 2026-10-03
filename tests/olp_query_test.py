"""scripts/olp_query.py answers from saved records only, and says PENDING
when a record is missing (HR35)."""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import olp_query as q  # noqa: E402


def test_missing_records_read_pending():
    with tempfile.TemporaryDirectory() as d:
        q.BOARDS, q.PICKS = Path(d), Path(d)
        assert q.board(None)["board"] == q.PENDING
        assert q.picks("2026-01-01")["singles"] == q.PENDING
        assert q.lookup("Nobody FC")["rows"] == q.PENDING


def test_reads_saved_ledger():
    with tempfile.TemporaryDirectory() as d:
        q.PICKS = Path(d)
        doc = {"date": "2026-10-03", "singles": [
            {"fixture": "Hearts v Celtic", "league": "Scottish Premiership", "pick": "Celtic",
             "price": 1.5, "chance": 0.6, "certainty": "HIGH", "code": "ABC", "result": "won",
             "ft": "0-2"}],
               "rated": [{"fixture": "Hearts v Celtic", "src": "model",
                          "p": [0.2, 0.2, 0.6, 0.8, 0.5, 0.3, 0.5], "ft": "0-2"}]}
        (Path(d) / "picks_2026-10-03.json").write_text(json.dumps(doc))
        assert q.picks(None)["singles"][0]["result"] == "won"
        rows = q.lookup("celtic")["rows"]
        assert len(rows) == 2 and rows[1]["p_home_draw_away"] == [0.2, 0.2, 0.6]


def test_status_and_leagues_run():
    s = q.status()
    assert "Phase 3" in s["phase"] and "legs_with_clv" in s["clv"]
    assert q.leagues()["leagues"], "whitelist must not be empty"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"{name}: OK")
    print("olp_query_test: OK")
