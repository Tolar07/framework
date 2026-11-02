"""engine/claude_reader.py + engine/claude_review.py — Claude as reader and brain (2026-11-02)."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine import claude_reader as CRD  # noqa: E402
from engine import claude_review as CRV  # noqa: E402
from engine import fact_sheet as FS  # noqa: E402

SINGLE = {"fixture": "Ajax v PSV", "home": "Ajax", "away": "PSV", "league": "Eredivisie",
          "kickoff_utc": "2026-11-02T13:30:00Z", "market": "SB:1||Home", "pick": "Ajax to win", "price": "2.10"}
PICKS = {"date": "2026-11-02", "generated_at": "2026-11-02T00:40:00Z", "singles": [SINGLE]}


def sheet(nvidia: dict) -> dict:
    fx = {"id": 0, "fixture": "Ajax v PSV", "home": "Ajax", "away": "PSV", "evidence": "PENDING",
          "answers": {"nvidia": nvidia}, "agreed": {}, "support": {}}
    return {"date": "2026-11-02", "picks_generated_at": PICKS["generated_at"],
            "members": {"nvidia": {"answered": 1}}, "fixtures": [fx]}


@pytest.fixture
def dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(FS, "OUT_DIR", tmp_path / "facts")
    monkeypatch.setattr(FS, "LEDGER_DIR", tmp_path / "picks")
    (tmp_path / "picks").mkdir()
    (tmp_path / "facts").mkdir()
    (tmp_path / "picks" / "picks_2026-11-02.json").write_text(json.dumps(PICKS), encoding="utf-8")
    monkeypatch.setattr(FS, "load_news", lambda day, folder=None: {})
    return tmp_path


def test_claude_plus_one_free_model_agrees_a_fact():
    out = FS.merge_outside(sheet({"derby": True, "rest_days_home": 6}), PICKS,
                           {"claude": {"fixtures": {"Ajax v PSV": {"derby": True, "rest_days_home": 7,
                                                                   "rest_days_away": 3}}}}, news={})
    fx = out["fixtures"][0]
    assert fx["agreed"]["derby"] is True and fx["agreed"]["rest_days_home"] in (6, 7)
    assert "rest_days_away" not in fx["agreed"]        # Claude alone never agrees a fact
    assert out["members"]["claude"]["answered"] == 1 and out["fields_agreed"] == 2


def test_outside_reading_of_another_board_is_ignored(dirs):
    FS.outside_path("2026-11-02", "claude").write_text(json.dumps(
        {"picks_generated_at": "older board", "fixtures": {"Ajax v PSV": {"derby": True}}}), encoding="utf-8")
    assert FS.load_outside(PICKS) == {}


def test_pending_then_save_folds_into_the_sheet(dirs, monkeypatch):
    (dirs / "facts" / "facts_2026-11-02.json").write_text(json.dumps(sheet({"derby": True})), encoding="utf-8")
    early = datetime(2026, 11, 2, 9, tzinfo=UTC)
    assert CRD.pending(early) == ["2026-11-02"]
    assert CRD.pending(datetime(2026, 11, 2, 14, tzinfo=UTC)) == []      # every game kicked off
    monkeypatch.setattr(CRD, "datetime", type("D", (), {"now": staticmethod(lambda tz=None: early),
                                                         "fromisoformat": staticmethod(datetime.fromisoformat)}))
    assert '"fixture": "Ajax v PSV"' in CRD.prompt("2026-11-02")
    r = CRD.save("2026-11-02", 'Here you go:\n```json\n{"fixtures": [{"id": 0, "derby": "yes", '
                               '"referee": "Makkelie", "evidence": "BBC: derby."}]}\n```', model="sonnet")
    assert r["answered"] == 1 and r["fields_agreed"] == 1
    merged = json.loads((dirs / "facts" / "facts_2026-11-02.json").read_text(encoding="utf-8"))
    assert merged["fixtures"][0]["agreed"] == {"derby": True}
    assert CRD.pending(early) == []


def test_save_ignores_unknown_ids_and_junk(dirs, monkeypatch):
    early = datetime(2026, 11, 2, 9, tzinfo=UTC)
    monkeypatch.setattr(CRD, "datetime", type("D", (), {"now": staticmethod(lambda tz=None: early),
                                                         "fromisoformat": staticmethod(datetime.fromisoformat)}))
    r = CRD.save("2026-11-02", '{"fixtures": [{"id": 9, "derby": true}, {"id": "0", "derby": true}]}')
    assert r["answered"] == 0 and "fields_agreed" not in r


def test_review_saves_lessons_and_reasoning_reads_them(tmp_path, monkeypatch):
    path = tmp_path / "claude_review.json"
    assert CRV.due("2026-11-02", path)
    with pytest.raises(SystemExit):
        CRV.save("no json here", path=path)
    rev = CRV.save('{"right": ["backs won 60%"], "wrong": ["vetoes win 79%"], '
                   '"lessons": ["veto only on a confirmed starter out"], "summary": "s"}', path=path)
    assert rev["lessons"] == ["veto only on a confirmed starter out"] and rev["lowers_only"]
    assert CRV.fresh_lessons(path, rev["date"])[1] == rev["lessons"]
    assert CRV.fresh_lessons(path, "2099-01-01") == (None, [])
    from engine import reasoning as R
    monkeypatch.setattr(CRV, "REVIEW", path)
    monkeypatch.setattr(CRV, "fresh_lessons", lambda: (rev["date"], rev["lessons"]))
    text = R.teaching("football", out_dir=tmp_path, ledger_dir=tmp_path, lessons_path=tmp_path / "x.json")
    assert "THE BRAIN'S REVIEW" in text and "confirmed starter out" in text
    monkeypatch.setenv("BRAIN_REVIEW", "0")
    assert "THE BRAIN'S REVIEW" not in R.teaching("football", out_dir=tmp_path, ledger_dir=tmp_path,
                                                  lessons_path=tmp_path / "x.json")
