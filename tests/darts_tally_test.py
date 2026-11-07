from datetime import UTC, datetime

from backtest import darts_tally_study as s


def test_classify():
    assert s.classify("b=1 picked; sealed Brier 0.24 vs board 0.23 (NOT better by 0.005)") == "not better"
    assert s.classify("the board was best in the first half: no rest-days lead") == "no lead"
    assert s.classify("w=1 picked; sealed 0.2371 vs 0.2373 (better by 0.0002; about 182") == "better"
    assert s.classify("confirmed on sealed years (lower Brier)") == "better"


def test_read_study_counts_tries_and_gap():
    r = s.read_study("8 tries, all shown.\nVerdict: w=1 picked (better by 0.0016; x)\n")
    assert r["tries"] == 8 and r["kind"] == "better" and r["gap"] == 0.0016


def test_no_verdict_is_pending():
    assert s.read_study("nothing here")["kind"] == "pending"


def test_render_empty_and_full(tmp_path):
    now = datetime(2026, 1, 1, tzinfo=UTC)
    assert "PENDING" in s.render({}, now)
    (tmp_path / "DARTS_A_STUDY.md").write_text("4 tries\nVerdict: x (NOT better by 0.1)\n")
    (tmp_path / "DARTS_B_STUDY.md").write_text("6 tries\nVerdict: y (better by 0.001)\n")
    (tmp_path / "DARTS_TALLY_STUDY.md").write_text("Verdict: ignore\n")
    out = s.render(s.collect(tmp_path), now)
    assert "10 tries" in out and "1 of 2" in out and "Record only" in out
