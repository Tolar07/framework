"""
Offline tests for the agents' automated jobs: the supervisor status after
every board (monitor/supervisor.py) and the weekly results review
(scripts/weekly_review.py). No network.
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from monitor import supervisor as sv
from scripts import weekly_review as wr

with tempfile.TemporaryDirectory() as d:
    boards, picks = Path(d) / "boards", Path(d) / "picks"
    boards.mkdir()
    picks.mkdir()
    (boards / "sent_2026-10-03_evening").write_text("2026-10-03T22:36:16Z")
    (boards / "sent_2026-10-04_morning").write_text("2026-10-04T06:07:12Z")
    (boards / "sent_2026-10-04_evening").write_text("2026-10-03T22:30:00Z")
    assert sv.latest_slot(boards) == ("2026-10-04", "morning"), "newest marker by its own time"

    (boards / "board_2026-10-04.txt").write_text(
        "Run ID: OLPXDV-20261004-0547-a4f91c | Phase 3\n"
        "⚠ 2 fixture(s) unresolved — NO DATA — PENDING (no market data): A v B · C v D\n")
    facts = sv.board_facts("2026-10-04", boards)
    assert facts == {"board": True, "run_id": True, "no_data": 2, "bet365": False}, facts

    singles = [{"market": "SB:10||Home or Away", "code": "C1"}] * 9 + \
              [{"market": "SB:18|total=1.5|Over 1.5", "code": None}]
    (picks / "picks_2026-10-04.json").write_text(json.dumps({
        "date": "2026-10-04", "singles": singles,
        "accas": [{"code": "A1"}, {"code": None}], "safe3": [], "megas": [],
        "alts": [{"code": "ALT1"}]}))
    st = sv.pick_stats("2026-10-04", picks)
    assert st["picks"] == 10 and st["families"] == 2 and st["top_share"] == 0.9
    assert (st["single_codes"], st["slips"], st["slip_codes"], st["alts"], st["alt_codes"]) == \
        (9, 2, 1, 1, 1), st
    text = sv.report("2026-10-04", "morning", "success", facts, st,
                     {"tests.yml": "success", "watchdog.yml": "failure"})
    assert text.startswith("🛡 SUPERVISOR · 2026-10-04 morning — ") and "issue(s)" in text
    for must in ("⚠ bet365 board MISSING", "⚠ 2 fixture(s) NO DATA",
                 "⚠ 90% of picks are Double chance", "⚠ codes: 9/10 singles, 1/2 slips",
                 "⚠ watchdog: failure", "✓ tests on main: success", "✓ Run ID present"):
        assert must in text, (must, text)
    assert "pre-kickoff" not in text, "a status that wasn't read is not reported"
    assert "subscribers" not in text, "subscribers not checked -> not reported"
    clean = sv.report("2026-10-04", "morning", "success",
                      {"board": True, "run_id": True, "no_data": 0, "bet365": True},
                      dict(st, top_share=0.4, single_codes=10, slip_codes=2), {}, subscribers=3)
    assert "ALL CLEAR" in clean and "✓ subscribers: 3 chat(s)" in clean, clean
    # Order 33: an empty subscriber secret is a problem, not silence.
    nosubs = sv.report("2026-10-04", "morning", "success",
                       {"board": True, "run_id": True, "no_data": 0, "bet365": True},
                       dict(st, top_share=0.4, single_codes=10, slip_codes=2), {}, subscribers=0)
    assert "1 issue(s)" in nosubs and "⚠ subscribers: none" in nosubs, nosubs
print("supervisor status: OK")

with tempfile.TemporaryDirectory() as d:
    picks = Path(d)
    def day(dt, rows):
        (picks / f"picks_{dt}.json").write_text(json.dumps({"date": dt, "singles": [
            {"market": m, "league": lg, "chance": 0.8, "price": 1.25, "result": r,
             "kickoff": dt} for m, lg, r in rows], "accas": [{"result": "won"}],
            "alts": [{"result": "lost"}]}))
    # Asian handicaps called at 80% won 4/12 over 3 days -> proposed for review.
    for i, dt in enumerate(("2026-09-30", "2026-10-01", "2026-10-02")):
        day(dt, [("SB:16|hcp=1.5|Away", "League One", "won" if i == 0 else "lost")] * 2 +
                [("SB:16|hcp=1.5|Away", "League One", "won" if i < 2 else "lost")] * 2 +
                [("SB:10||Home or Away", "Serie B", "won")] * 3)
    text = wr.review(7, today="2026-10-04", picks=picks)
    assert text.startswith("📈 WEEKLY REVIEW") and "By market family (worst first):" in text
    fam_lines = text.split("By market family (worst first):")[1].split("By league")[0]
    assert fam_lines.strip().startswith("Asian handicap"), "worst family first"
    assert "Accas: 3/3 landed" in text and "Alt-market accas: 0/3 landed" in text
    assert "Asian handicap: won" in text.split("PROPOSALS")[1], "losing family proposed for review"
    assert "nothing is changed automatically" in text
    # Order 32: switched picks are compared with the originals they replaced.
    (picks / "picks_2026-10-03.json").write_text(json.dumps({"date": "2026-10-03", "singles": [
        {"market": "SB:18|total=1.5|Over 1.5", "league": "UEFA Nations League", "chance": 0.74,
         "price": 1.3, "result": "won", "kickoff": "2026-10-03",
         "orig_market": "SB:16|hcp=-3.5|Away (+3.5)", "orig_result": "lost"}]}))
    sw_text = wr.review(7, today="2026-10-04", picks=picks)
    assert "Switched picks (order 32): 1/1 won; the original picks would have won 0/1" in sw_text
    empty = wr.review(7, today="2030-01-01", picks=picks)
    assert "No graded singles" in empty
print("weekly review: OK")
print("\n✅ ALL SUPERVISOR + WEEKLY REVIEW TESTS PASSED")
