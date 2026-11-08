"""
monitor/bot_grader.py covers every rollout sport (framework#357, standing orders 50 and 53): ice hockey and the
nine multisport-board sports. Each bot's bets on them (Matchbook live + paper, Betfair live + paper, SportyBet both
accounts by code) are graded on the framework's own graded boards (output/ice_hockey, output/multisport), and the
23:02 report has one line per sport. Offline: boards, ledgers and SportyBet's share API are built in a temp folder.
"""
import json
import sys
import tempfile
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from engine import multisport as ms  # noqa: E402
from monitor import bot_grader as bg  # noqa: E402

tmp = Path(tempfile.mkdtemp())
ih_dir, ms_dir = tmp / "ice_hockey", tmp / "multisport"

# every rollout sport is known, with its SportyBet sport id
assert set(bg.ROLLOUT_SPORTS) == {"ice_hockey", *ms.SPORTS} and len(bg.ROLLOUT_SPORTS) == 10
assert set(bg.SB_SPORT_IDS.values()) == set(bg.ROLLOUT_SPORTS)
assert all(s in bg.SPORT_NAMES for s in bg.ROLLOUT_SPORTS)
assert bg.rollout_key("MS:tennis:186||Home") == ("tennis", "186", "", "Home")
assert bg.rollout_key("MS:ice_hockey:406||Away") == ("ice_hockey", "406", "", "Away")
assert bg.rollout_key("SB:1||Home") is None and bg.rollout_key("NBA:219||Home") is None
assert bg.rollout_key("MS:curling:1||Home") is None, "a sport outside the rollout is not guessed"

# ── the boards: one graded game per sport family, one not yet graded ─────────
(ih_dir).mkdir(parents=True)
(ih_dir / "ih_2026-11-12.json").write_text(json.dumps({"date": "2026-11-12", "games": {
    "sr:match:h1": {"home": "Toronto Maple Leafs", "away": "Boston Bruins", "ko": "2026-11-12T00:00:00Z",
                    "result": {"reg": [2, 2], "final": [3, 2]},
                    "sides": {"H:406||Home": {"won": 1}, "H:1||Home": {"won": 0}}},
}, "picks": [{"sb_event_id": "sr:match:h1", "home": "Toronto Maple Leafs", "away": "Boston Bruins",
              "ko": "2026-11-12T00:00:00Z", "market_id": "406", "specifier": "", "outcome": "Home",
              "price": 1.8, "code": "IHCODE", "paper": False}]}), encoding="utf-8")
(ms_dir / "tennis").mkdir(parents=True)
(ms_dir / "tennis" / "ms_2026-11-12.json").write_text(json.dumps({"date": "2026-11-12", "games": {
    "sr:match:t1": {"home": "Monteiro, Thiago", "away": "Ruud, Casper", "ko": "2026-11-12T12:00:00Z",
                    "result": {"final": [2, 1], "periods": [[6, 4], [3, 6], [6, 2]], "winner": 1},
                    "sides": {"tennis:186||Home": {"won": 1}, "tennis:186||Away": {"won": 0}}},
    "sr:match:t2": {"home": "Sinner, Jannik", "away": "Alcaraz, Carlos", "ko": "2026-11-12T18:00:00Z",
                    "result": None, "sides": {}},
}, "picks": [{"sb_event_id": "sr:match:t1", "home": "Monteiro, Thiago", "away": "Ruud, Casper",
              "ko": "2026-11-12T12:00:00Z", "market_id": "186", "specifier": "", "outcome": "Home",
              "price": 1.9, "code": None, "paper": False}]}), encoding="utf-8")
(ms_dir / "darts").mkdir(parents=True)
(ms_dir / "darts" / "ms_2026-11-12.json").write_text(json.dumps({"date": "2026-11-12", "games": {
    "sr:match:d1": {"home": "Littler, Luke", "away": "Humphries, Luke", "ko": "2026-11-12T20:00:00Z",
                    "result": {"final": [4, 6], "periods": [], "winner": 2}, "sides": {}},
}, "picks": []}), encoding="utf-8")

RG = bg.RolloutGames("2026-11-01", ih_dir=ih_dir, ms_dir=ms_dir)
G = bg.Games("2026-11-01", folder=tmp / "no-universe", rollout=RG)
assert RG.find({"event_id": "sr:match:t1"}, "tennis")["home"] == "Monteiro, Thiago"
assert RG.find({"home": "Thiago Monteiro", "away": "Casper Ruud", "ko": "2026-11-12T12:05Z"}, "tennis")["id"] == \
    "sr:match:t1", "the exchanges' 'First Last' finds SportyBet's 'Last, First'"
assert RG.find({"home": "Thiago Monteiro", "away": "Casper Ruud", "ko": "2026-11-12T12:05Z"}, "darts") is None

# ── one leg per case ─────────────────────────────────────────────────────────
t: dict = defaultdict(int)
leg = bg.grade_leg({"event_id": "sr:match:h1", "key": "MS:ice_hockey:406||Home"}, G, t)
assert (leg["result"], leg["source"], leg["game"]) == ("won", "ice_hockey board", "ice_hockey:sr:match:h1")
leg = bg.grade_leg({"event_id": "sr:match:h1", "key": "MS:ice_hockey:18|total=4.5|Under 4.5"}, G, t)
assert leg["result"] == "won", "a side the board did not record: the hockey rule on the regulation score (2-2)"
leg = bg.grade_leg({"home": "Thiago Monteiro", "away": "Casper Ruud", "ko": "2026-11-12T12:00Z",
                    "key": "MS:tennis:186||Away", "own": "won"}, G, t)
assert (leg["result"], leg["source"]) == ("lost", "tennis board"), "the board's result, not the exchange's word"
leg = bg.grade_leg({"event_id": "sr:match:t1", "key": "MS:tennis:189|total=22.5|Over 22.5"}, G, t)
assert leg["result"] == "won", "27 games, from the periods"
leg = bg.grade_leg({"event_id": "sr:match:d1", "key": "MS:darts:186||Away"}, G, t)
assert (leg["result"], leg["source"]) == ("won", "darts board")
leg = bg.grade_leg({"event_id": "sr:match:t2", "key": "MS:tennis:186||Home"}, G, t)
assert (leg["result"], leg["source"]) == (None, "not graded yet")
leg = bg.grade_leg({"event_id": "sr:match:t2", "key": "MS:tennis:186||Home", "own": "lost"}, G, t)
assert (leg["result"], leg["source"]) == ("lost", "exchange"), "the exchange's settlement while the board waits"
leg = bg.grade_leg({"event_id": "sr:match:zz", "key": "MS:rugby:1||Home",
                    "sb": {"ended": True, "mstatus": 3, "win": 1, "refund": 0}}, G, t)
assert (leg["result"], leg["source"]) == ("won", "sportybet"), "SportyBet's own settlement when no board has it"
leg = bg.grade_leg({"event_id": "sr:match:h1", "key": "MS:ice_hockey:406||Home",
                    "sb": {"ended": True, "mstatus": 3, "win": 0, "refund": 0}}, G, t)
assert leg["result"] == "lost" and t["disagree"] == 1, "SportyBet's payout decides, the difference is counted"

# ── SportyBet codes decode to rollout keys by sport id ──────────────────────
share = {"outcomes": [{"eventId": "sr:match:t1", "homeTeamName": "Monteiro, Thiago", "awayTeamName": "Ruud, Casper",
                       "estimateStartTime": 1794571200000, "sport": {"id": "sr:sport:5"}, "matchStatus": "Ended",
                       "setScore": "2:1",
                       "markets": [{"id": "186", "specifier": "", "status": 0,
                                    "outcomes": [{"desc": "Home", "odds": "1.90"}]}]}]}
legs = bg.legs_from_share(share)
assert legs[0]["key"] == "MS:tennis:186||Home" and legs[0]["sport"] == "tennis"
assert bg.grade_leg(legs[0], G, defaultdict(int))["result"] == "won"

# ── the bots' ledgers ────────────────────────────────────────────────────────
bots = tmp / "bots"
# SportyBet (both accounts): a rollout single is filed under "nba" by the placer; decoded, it is tennis
for acct in bg.SPORTYBET_ACCOUNTS:
    sbd = bots / "sportybet-agent" / "ledger" / acct
    sbd.mkdir(parents=True)
    (sbd / "2026-11-12.json").write_text(json.dumps({"bets": {"TEN1": {
        "code": "TEN1", "section": "nba", "status": "placed", "stake": 1000, "odds": 1.9, "bet_id": f"x-{acct}"}}}),
        encoding="utf-8")
sbb = bg.sportybet_bets(bots / "sportybet-agent", "2026-11-01", {"TEN1": {"legs": legs, "final": True}})
assert [(b["bot"], b["kind"], b["legs"][0]["key"]) for b in sbb] == [
    ("sportybet", "tennis", "MS:tennis:186||Home"), ("sportybet2", "tennis", "MS:tennis:186||Home")]
assert all(bg.grade_slip(b, G, defaultdict(int))["profit"] == 900 for b in sbb), "naira: 1,000 at 1.90 won"
mb = bots / "matchbook-agent" / "ledger"
mb.mkdir(parents=True)
(mb / "ledger.jsonl").write_text(json.dumps({
    "pos_id": "fw_1", "opened_at": "2026-11-11T20:00:00+00:00", "start": "2026-11-12T00:00:00.000Z",
    "event_name": "Boston Bruins at Toronto Maple Leafs", "market_name": "Moneyline", "runner_name": "Toronto",
    "source": "framework", "fw_key": "MS:ice_hockey:2026-11-12|Toronto Maple Leafs v Boston Bruins|"
                                     "MS:ice_hockey:406||Home",
    "cost_gbp": 2.0, "avg_odds": 1.8, "status": "WON", "pnl_gbp": 1.57}) + "\n", encoding="utf-8")
(mb / "multisport_paper.jsonl").write_text(json.dumps({
    "key": "MS|tennis|sr:match:t1|tennis:186||Home", "sport": "tennis", "sb_event_id": "sr:match:t1",
    "home": "Thiago Monteiro", "away": "Casper Ruud", "ko": "2026-11-12T12:00:00Z", "odds": 1.95,
    "paper": True, "result": "won"}) + "\n", encoding="utf-8")
(mb / "hockey_paper.jsonl").write_text(json.dumps({
    "key": "IH|sr:match:h1|H:1||Home", "sb_event_id": "sr:match:h1", "home": "Toronto Maple Leafs",
    "away": "Boston Bruins", "ko": "2026-11-12T00:00:00Z", "odds": 2.4, "paper": True, "result": None}) + "\n",
    encoding="utf-8")
mbb = bg.matchbook_bets(bots / "matchbook-agent", "2026-11-01")
assert [b["legs"][0]["key"] for b in mbb] == ["MS:ice_hockey:406||Home", "MS:ice_hockey:1||Home", "MS:tennis:186||Home"]
assert mbb[0]["legs"][0]["home"] == "Toronto Maple Leafs" and not mbb[0]["paper"] and mbb[1]["paper"] and mbb[2]["paper"]

bf = bots / "betfair-agent" / "ledger"
bf.mkdir(parents=True)
(bf / "paper_2026-11-12.json").write_text(json.dumps({"date": "2026-11-12", "bets": [
    {"code": "DARTS-sr:match:d1", "section": "darts", "sport": "darts", "fixture": "Luke Littler v Luke Humphries",
     "sb_market": "MS:darts:186||Away", "kickoff_utc": "2026-11-12T20:00:00Z", "price": 2.1, "stake": 1.0,
     "mode": "live", "bet_id": "b1", "size_matched": 1.0, "avg_price": 2.1, "result": "WON", "pnl": 1.1},
    {"code": "TENNIS-sr:match:t1", "section": "tennis", "sport": "tennis", "fixture": "Thiago Monteiro v Casper Ruud",
     "sb_market": "MS:tennis:186||Away", "kickoff_utc": "2026-11-12T12:00:00Z", "price": 2.2, "stake": 1.0,
     "mode": "paper", "result": None},
    {"code": "FB1", "sport": "football", "fixture": "A v B", "sb_market": "SB:1||Home", "mode": "paper"},
]}), encoding="utf-8")
bfb = bg.betfair_bets(bots / "betfair-agent", "2026-11-01", {})
assert sorted((b["legs"][0]["sport"], b["paper"]) for b in bfb) == [("darts", False), ("tennis", True)], \
    "rollout paper rows are kept (order 53); football paper rows stay the bot's own study"

# ── graded, written back, and one line per sport in the 23:02 report ────────
board = bg.rollout_board_bets(RG, "2026-11-01")
assert {b["legs"][0]["key"] for b in board} == {"MS:ice_hockey:406||Home", "MS:tennis:186||Home"}
gr = [bg.grade_slip(b, G, defaultdict(int), datetime(2026, 11, 13, 9, tzinfo=UTC)) for b in mbb + bfb + board]
res = {(b["bot"], b["legs"][0]["key"], b["paper"]): b["result"] for b in gr}
assert res[("matchbook", "MS:ice_hockey:406||Home", False)] == "won"
assert res[("matchbook", "MS:ice_hockey:1||Home", True)] == "lost", "graded by the board, not left at None"
assert res[("betfair", "MS:tennis:186||Away", True)] == "lost"
assert res[("betfair", "MS:darts:186||Away", False)] == "won"
assert res[("board", "MS:tennis:186||Home", True)] == "won"
assert next(b for b in gr if b["bot"] == "matchbook" and not b["paper"])["profit"] == 1.57, "the bot's own money"

written = bg.write_back(gr, datetime(2026, 11, 13, 9, tzinfo=UTC), root=bots)
assert written.get("matchbook-agent") and written.get("betfair-agent")
assert (mb / "graded" / "paper_2026-11-12.json").exists() and (mb / "graded" / "2026-11-12.json").exists()

lines = bg.sport_lines(gr, "2026-11-01", "2026-11-12")
names = [x.split(":")[0] for x in lines]
for sport in bg.ROLLOUT_SPORTS:
    assert bg.SPORT_NAMES[sport] in names, f"{sport} has its own line in the 23:02 report"
hockey = next(x for x in lines if x.startswith("Ice hockey:"))
assert "real 1 bets, 1 won" in hockey and "bots' paper 1" in hockey and "board 1 picks" in hockey, hockey
assert next(x for x in lines if x.startswith("Baseball:")) == "Baseball: nothing graded yet"
text = bg.build_report(gr, "2026-11-12", {})
assert "BY SPORT" in text and "Tennis:" in text and "Darts:" in text
assert bg._label("MS:ice_hockey:406||Home") == ("Ice hockey Winner incl. OT", "Home")
assert bg._label("MS:tennis:189|total=22.5|Over 22.5") == ("Tennis Total games", "Over N")

# the rollout boards' own picks are reported, never decision-layer evidence (record-only)
_real, paper_in = bg.decision_inputs(gr)
assert not paper_in, paper_in
print("ALL BOT GRADER MULTISPORT TESTS PASSED")
