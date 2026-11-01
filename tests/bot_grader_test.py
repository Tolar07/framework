"""
monitor/bot_grader.py: every bot bet graded by game + market + side, written back
beside each bot's ledger, and the daily report sent to the Architect's chat only.
Offline: SportyBet's share API and Telegram are stubbed; ledgers and the
universe archive are built in a temp folder.
"""
import gzip
import json
import os
import sys
import tempfile
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from monitor import bot_grader as bg  # noqa: E402
from output import notify  # noqa: E402

# ── settling on a score ──────────────────────────────────────────────────────
assert bg.settle_on("SB:18|total=3|Under 3", 2, 1) == "void", "whole line on the line is void"
assert bg.settle_on("SB:18|total=2.5|Under 2.5", 2, 1) == "lost"
assert bg.settle_on("SB:1||Home", 1, 3) == "lost" and bg.settle_on("SB:1||Away", 1, 3) == "won"
assert bg.settle_on("SB:16|hcp=-2.5|Away (+2.5)", 3, 1) == "won"
assert bg.settle_on("SB:60||Home", 0, 0, [1, 0]) == "won", "first half from the half-time score"
assert bg.settle_on("NBA:223|hcp=1.5|Home (+1.5)", 119, 98) == "won"
assert bg.settle_on("SB:999|x=1|Something", 1, 0) is None, "an unknown market is never guessed"

# ── a universe archive with three finished games ─────────────────────────────
tmp = Path(tempfile.mkdtemp())
uni = tmp / "universe"
uni.mkdir()
games = [
    {"sport": "football", "id": "sr:match:1", "ko": "2026-10-31T15:00Z", "home": "Exeter City",
     "away": "Fleetwood Town", "result": {"h": 2, "a": 1, "ht": [0, 0], "after_90": False}},
    {"sport": "football", "id": "sr:match:2", "ko": "2026-10-31T17:30Z", "home": "Bodo/Glimt",
     "away": "Viking FK", "result": {"h": 1, "a": 0, "ht": [0, 0], "after_90": False}},
    {"sport": "football", "id": "sr:match:3", "ko": "2026-10-31T19:00Z", "home": "Serik Belediyespor",
     "away": "Hakkari Zap Spor", "result": {"h": 2, "a": 2, "ht": [1, 0], "after_90": True}},
]
with gzip.open(uni / "graded_2026-11-01_0320.jsonl.gz", "wt", encoding="utf-8") as f:
    f.write("\n".join(json.dumps(g) for g in games) + "\n")
G = bg.Games("2026-10-25", folder=uni)
assert G.find({"event_id": "sr:match:1"})["home"] == "Exeter City", "by SportyBet event id"
assert G.find({"home": "FK Bodø/Glimt", "away": "Viking", "ko": "2026-10-31T17:30:00.000Z"})["id"] == "sr:match:2", \
    "by names when there is no id (Matchbook's spellings)"
assert G.find({"home": "Arsenal", "away": "Chelsea", "ko": "2026-10-31T15:00Z"}) is None

# ── one leg: universe first, SportyBet's settlement decides when they differ ─
t: dict = defaultdict(int)
leg = bg.grade_leg({"event_id": "sr:match:1", "key": "SB:18|total=3|Under 3"}, G, t)
assert (leg["result"], leg["source"]) == ("void", "universe")
leg = bg.grade_leg({"event_id": "sr:match:1", "key": "SB:1||Home",
                    "sb": {"ended": True, "mstatus": 3, "win": 0, "refund": 0}}, G, t)
assert leg["result"] == "lost" and t["disagree"] == 1, "SportyBet paid it as lost: counted, and it decides"
leg = bg.grade_leg({"event_id": "sr:match:3", "key": "SB:19|total=3.5|Under 3.5",
                    "sb": {"ended": False, "mstatus": 3, "win": 1, "refund": 0, "score": "6:5"}}, G, t)
assert (leg["result"], leg["source"]) == ("won", "sportybet"), "extra-time game: SportyBet's settlement, not the penalty score"
leg = bg.grade_leg({"event_id": "sr:match:9", "key": "SB:1||Home", "own": "won"}, G, t)
assert (leg["result"], leg["source"]) == ("won", "exchange")
leg = bg.grade_leg({"event_id": "sr:match:9", "key": "SB:1||Home"}, G, t)
assert leg["result"] is None and leg["source"] == "no game found"

# ── the slip: leg by leg, then the slip ──────────────────────────────────────
now = datetime(2026, 11, 1, 23, 5, tzinfo=UTC)
acca = {"bot": "sportybet", "cur": "NGN", "stake": 1000.0, "odds": 3.0, "paper": False, "legs": [
    {"event_id": "sr:match:1", "key": "SB:18|total=3|Under 3", "price": 1.5},
    {"event_id": "sr:match:2", "key": "SB:1||Home", "price": 2.0}]}
s = bg.grade_slip(acca, G, t, now)
assert s["result"] == "won" and s["payout"] == 2000.0 and s["profit"] == 1000.0, "a void leg divides its price out"
lost = {**acca, "legs": acca["legs"] + [{"event_id": "sr:match:2", "key": "SB:1||Away"}]}
assert bg.grade_slip(lost, G, t, now)["profit"] == -1000.0
waiting = {**acca, "legs": acca["legs"] + [{"event_id": "sr:match:7", "key": "SB:1||Home",
                                            "ko": "2026-11-01T21:00Z"}]}
w = bg.grade_slip(waiting, G, t, now)
assert w["result"] is None and w["profit"] is None and w["why"] == "not played yet"
mb = {"bot": "matchbook", "cur": "GBP", "stake": 3.0, "odds": 1.31, "paper": False, "own_pnl": -14.63,
      "own_settled": True, "legs": [{"event_id": "sr:match:2", "key": "SB:16|hcp=-2.5|Away (+2.5)", "own": "won"}]}
m = bg.grade_slip(mb, G, t, now)
assert m["result"] == "won" and m["profit"] == -14.63, "exchange money is the bot's own settled profit"

# ── Matchbook positions -> ladder keys ───────────────────────────────────────
def k(**r):
    return bg._mb_key(r)[0]
assert k(event_name="A vs B", market_name="Match Odds", runner_name="Draw") == "SB:1||Draw"
assert k(event_name="Kyoto Sanga vs Newcastle Jets", market_name="Match Odds", runner_name="Kyoto Sanga") == "SB:1||Home"
assert k(event_name="Suns at Warriors", market_name="Moneyline", runner_name="Warriors") == "NBA:219||Home"
assert k(event_name="A vs B", market_name="Total", runner_name="UNDER 1.5") == "SB:18|total=1.5|Under 1.5"
assert k(event_name="Benfica vs Celtic", market_name="Handicap", runner_name="Celtic +3.5") == "SB:16|hcp=-3.5|Away (+3.5)"
assert k(event_name="X vs Y", fw_key="codes|2026-11-01|X v Y|SB:29||Yes") == "SB:29||Yes"
assert k(event_name="X vs Y", vt_market="SB:14|hcp=2:0|Home (2:0)") == "SB:14|hcp=2:0|Home (2:0)"

# ── share API payload -> legs; cached once settled ───────────────────────────
payload = {"outcomes": [{"eventId": "sr:match:1", "homeTeamName": "Exeter City", "awayTeamName": "Fleetwood Town",
                         "estimateStartTime": 1793458800000, "matchStatus": "Ended", "setScore": "2:1",
                         "sport": {"id": "sr:sport:1"},
                         "markets": [{"id": "18", "specifier": "total=3", "status": 3,
                                      "outcomes": [{"desc": "Under 3", "odds": "1.41", "isWinning": 0,
                                                    "refundFactor": 1.0}]}]}]}
calls = []
cache: dict = {}
legs = bg.code_legs("ABC123", cache, fetch=lambda c: calls.append(c) or payload)
assert legs[0]["key"] == "SB:18|total=3|Under 3" and legs[0]["event_id"] == "sr:match:1"
assert bg.code_legs("ABC123", cache, fetch=lambda c: calls.append(c) or payload) == legs and calls == ["ABC123"], \
    "a settled code is read once"
assert bg.code_legs("NOPE", {}, fetch=lambda c: None) is None

# ── the bots' ledgers, the write-back and the report ─────────────────────────
bots = tmp / "bots"
sb = bots / "sportybet-agent" / "ledger" / "sportybet"
(sb / "rules").mkdir(parents=True)
(sb / "2026-10-31.json").write_text(json.dumps({"bets": {
    "ABC123": {"code": "ABC123", "status": "placed", "stake": 1000, "odds": 1.41, "bet_id": "1", "section": "singles"},
    "ZZZ999": {"code": "ZZZ999", "status": "failed", "stake": 1000, "odds": 2.0}}}))
(sb / "rules" / "ledger.json").write_text(json.dumps({"bets": [
    {"at": "2026-10-31T10:00:00+00:00", "rule": "value", "status": "placed", "code": "ABC123",
     "stake": 500, "odds": 1.41, "bet_id": "2"}]}))
(bots / "matchbook-agent" / "ledger").mkdir(parents=True)
(bots / "matchbook-agent" / "ledger" / "ledger.jsonl").write_text(json.dumps(
    {"pos_id": "p1", "source": "survivor", "event_name": "Bodo/Glimt vs Viking FK", "start": "2026-10-31T17:30:00.000Z",
     "market_name": "Handicap", "runner_name": "Viking FK +2.5", "status": "WON", "cost_gbp": 3.0,
     "avg_odds": 1.31, "pnl_gbp": 0.93}) + "\n")
(bots / "betfair-agent" / "ledger").mkdir(parents=True)
(bots / "betfair-agent" / "ledger" / "paper_2026-10-31.json").write_text(json.dumps({"mode": "paper", "bets": [
    {"bet_id": "b1", "mode": "live", "code": "ABC123", "section": "singles", "rule": "R1", "stake": 1.0,
     "avg_price": 1.45, "result": "WON", "pnl": 0.45, "kickoff_utc": "2026-10-31T15:00:00+00:00"},
    {"bet_id": "b2", "mode": "paper-uncapped", "code": "ABC123", "stake": 1.0, "result": "WON", "pnl": 0.45}]}))
sbets = bg.sportybet_bets(bots / "sportybet-agent", "2026-10-25", cache)
assert sorted(b["kind"] for b in sbets) == ["rule value", "singles"], "placed only; rule bets too"
mbets = bg.matchbook_bets(bots / "matchbook-agent", "2026-10-25")
bfb = bg.betfair_bets(bots / "betfair-agent", "2026-10-25", cache)
assert len(mbets) == 1 and len(bfb) == 1, "Betfair: the bot's live bets only, not its paper study"
graded = [bg.grade_slip(b, G, defaultdict(int), now) for b in sbets + mbets + bfb]
assert all(b["result"] == "void" for b in graded if b["bot"] == "sportybet")
changed = bg.write_back(graded, now, root=bots)
assert set(changed) == {"sportybet-agent", "matchbook-agent", "betfair-agent"}
side = json.loads((bots / "sportybet-agent/ledger/sportybet/graded/2026-10-31.json").read_text(encoding="utf-8"))
assert side["bets"]["1"]["result"] == "void" and side["bets"]["1"]["legs"][0]["source"] == "universe"
assert bg.write_back(graded, now, root=bots) == {}, "unchanged grades are not rewritten"

text = bg.build_report(graded, "2026-10-31", {"disagree": 1})
for part in ("TODAY", "LAST 7 DAYS", "LAST 30 DAYS", "BY MARKET AND SIDE", "BY RULE AND SLIP TYPE",
             "Matchbook:", "Betfair:", "SportyBet acct 1:", "Total:", "per £", "Could not grade yet: 0 bets",
             "differs from the universe result: 1"):
    assert part in text, part
assert "WEEKLY" in bg.weekly_summary(graded, "2026-11-01")

# report timing: from 23:00 UK, once a day; a missed 23:00 run is caught up before 06:00
bg.NOTE_DIR = tmp / "notes"
assert bg.report_day(datetime(2026, 11, 1, 22, 59, tzinfo=UTC)) is None
assert bg.report_day(datetime(2026, 11, 1, 23, 2, tzinfo=UTC)) == "2026-11-01"
assert bg.report_day(datetime(2026, 11, 2, 0, 20, tzinfo=UTC)) == "2026-11-01"
assert bg.report_day(datetime(2026, 11, 2, 9, 0, tzinfo=UTC)) is None

# the Architect's own chat only
sent = []
real = notify.send_telegram
notify.send_telegram = lambda text, chat_id=None: (sent.append((chat_id, text)) or True, ["ok"])
os.environ.update({"TELEGRAM_BOT_TOKEN": "t", "TELEGRAM_CHAT_ID": "main", "TELEGRAM_OWNER_CHAT_ID": "owner"})
try:
    assert bg.send("a_b *c*")[0] and sent == [("owner", "a b c")], "owner chat, no Markdown breakers"
finally:
    notify.send_telegram = real

# the public log line carries counts only
bg.BOTS, bg.CACHE, bg.GRADED_DIR, bg.PICKS_DIR = bots, tmp / "codes.json", uni, tmp / "nopicks"
bg._fetch_code = lambda c: payload
line = bg.run(now, dry=True)
assert "bets read" in line and "NGN" not in line and "£" not in line and "ABC123" not in line, line
# ── pushing: a bot's own push lands in between; its files are never reverted ─
import subprocess  # noqa: E402


def sh(*a, cwd):
    r = subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True)  # noqa: S603,S607 (fixed git args)
    assert r.returncode == 0, (a, r.stderr)
    return r.stdout


gt = tmp / "git"
remote, seed, bot, wb = gt / "remote.git", gt / "seed", gt / "bot", gt / "wb" / "matchbook-agent"
gt.mkdir()
sh("init", "-q", "--bare", "-b", "main", str(remote), cwd=gt)
sh("clone", "-q", str(remote), str(seed), cwd=gt)
ident = ["-c", "user.name=t", "-c", "user.email=t@t"]
(seed / "ledger").mkdir()
(seed / "ledger" / "ledger.jsonl").write_text("v1\n")
sh("add", ".", cwd=seed)
sh(*ident, "commit", "-q", "-m", "seed", cwd=seed)
sh("push", "-q", "origin", "HEAD:main", cwd=seed)
sh("clone", "-q", "--depth=1", "file://" + str(remote).replace("\\", "/"), str(wb), cwd=gt)
sh("clone", "-q", str(remote), str(bot), cwd=gt)
(bot / "ledger" / "ledger.jsonl").write_text("v2 from the bot\n")           # the bot pushes meanwhile
sh(*ident, "commit", "-qam", "bot ledger", cwd=bot)
sh("push", "-q", "origin", "HEAD:main", cwd=bot)
(wb / "ledger" / "graded").mkdir(parents=True)
(wb / "ledger" / "graded" / "2026-10-31.json").write_text("{}\n")
assert bg.push_repos({"matchbook-agent": 1}, now, root=gt / "wb") == ["matchbook-agent saved"]
sh("pull", "-q", "origin", "main", cwd=bot)
assert (bot / "ledger" / "ledger.jsonl").read_text() == "v2 from the bot\n", "the bot's ledger kept"
assert (bot / "ledger" / "graded" / "2026-10-31.json").exists(), "the grades landed"

# ── rules on paper (2026-11-01): read from each bot, graded, never in the money totals ──
(sb / "steam").mkdir(parents=True, exist_ok=True)
(sb / "rules" / "ledger.json").write_text(json.dumps({"bets": [], "paper": [
    {"at": "2026-10-31T10:00:00+00:00", "rule": "edge", "status": "paper", "code": "ABC123", "stake": 700,
     "odds": 1.41}]}))
(sb / "steam" / "ledger.json").write_text(json.dumps({"bets": [], "paper": [
    {"at": "2026-10-31T12:00:00+00:00", "status": "paper", "sb_event": "sr:match:2", "outcome": "Home",
     "key": "SEL:sr:match:2|1||1", "stake": 1000, "odds": 2.3, "start": "2026-10-31T17:30:00.000Z"}]}))
(bots / "matchbook-agent" / "ledger" / "inplay_paper.jsonl").write_text(json.dumps(
    {"source": "inplay", "mode": "paper", "event_name": "Bodo/Glimt vs Viking FK", "start": "2026-10-31T17:30:00.000Z",
     "market_name": "Total", "runner_name": "UNDER 1.5", "odds": 1.8, "stake_gbp": 1.0}) + "\n")
bfp = bots / "betfair-agent" / "ledger" / "paper_2026-10-31.json"
bfj = json.loads(bfp.read_text())
bfj["paper_rules"] = [{"code": "ABC123", "rule": "R4", "section": "value", "stake": 1.0, "price": 1.45,
                       "kickoff_utc": "2026-10-31T15:00:00+00:00", "mode": "paper-rule"}]
bfp.write_text(json.dumps(bfj))
allb = (bg.sportybet_bets(bots / "sportybet-agent", "2026-10-25", cache)
        + bg.matchbook_bets(bots / "matchbook-agent", "2026-10-25") + bg.betfair_bets(bots / "betfair-agent", "2026-10-25", cache))
pg = {b["kind"]: bg.grade_slip(b, G, defaultdict(int), now) for b in allb if b["paper"]}
assert set(pg) == {"rule edge (paper)", "steam (paper)", "inplay (paper)", "value R4 (paper)"}, set(pg)
assert pg["steam (paper)"]["result"] == "won", "steam paper leg rebuilt from its selection key (Bodo 1-0, Home)"
assert pg["inplay (paper)"]["result"] == "won" and pg["rule edge (paper)"]["result"] == "void"
gall = [bg.grade_slip(b, G, defaultdict(int), now) for b in allb]
rep_txt = bg.build_report(gall, "2026-10-31", {})
assert "RULES ON PAPER" in rep_txt and "matchbook inplay (paper): 1 bets, 1 won" in rep_txt, rep_txt
assert "Matchbook: 1 bets" in rep_txt, "paper never counts in a bot's money"

print("ALL BOT GRADER TESTS PASSED")
