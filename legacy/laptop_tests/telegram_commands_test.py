"""
Telegram command layer tests.

Routing and safety only — NOTHING here runs the pipeline. /send deliberately
executes a full live run (network, ledger writes), so this suite asserts the
mapping exists and that /send is the same handler as /run, without invoking
either. A real end-to-end check belongs in the stress test, not here.
"""
import os
import sys
import tempfile
import unittest.mock as mock
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Snapshot the module set BEFORE telegram_commands loads, so the lightweight
# assertions below test what THIS module dragged in — not what earlier test
# files (e.g. api_football_odds_test importing run_daily) happened to load
# first under pytest's collection order. The claim under test is unchanged:
# importing the command layer must not pay for the pipeline.
_before = set(sys.modules)

from output import telegram_commands as tc
from output.telegram_commands import (handle, cmd_send, cmd_produce, cmd_verify,
                                      cmd_help, HANDLERS, BRIGHT_LINE_WORDS,
                                      Reply, _keyboard)

# Point the module's state files at a throwaway dir so no real ledger state
# (corrections.csv / offset) is mutated by this suite.
_tmp = Path(tempfile.mkdtemp(prefix="olp_xdv_cmds_test_"))
tc.STATE_DIR = _tmp
tc.OFFSET_FILE = _tmp / "telegram_offset.json"
tc.CORRECTIONS_FILE = _tmp / "corrections.csv"

# --- the poller stays lightweight: importing the module must NOT drag in the
# --- whole pipeline (scipy). /send lazy-imports run_daily exactly so the
# --- other commands never pay for it.
_imported = set(sys.modules) - _before
assert "run_daily" not in _imported, "importing telegram_commands must not drag in run_daily"
assert "scipy" not in _imported, "importing telegram_commands must not drag in scipy"
print("Poller stays lightweight — /send lazy-imports run_daily: OK")

# --- /send and /run are the same handler, registered -----------------------
assert HANDLERS["/send"] is cmd_send, "/send must route to cmd_send"
assert HANDLERS["/run"] is cmd_send, "/run must be an alias for /send"
print("/send and /run both route to cmd_send: OK")

# --- /produce bet and /verify result ---------------------------------------
assert HANDLERS["/produce"] is cmd_produce, "/produce must route to cmd_produce"
assert HANDLERS["/verify"] is cmd_verify, "/verify must route to cmd_verify"
# These branches must NOT execute the pipeline: wrong/missing subcommands
# return usage, so invoking them is safe here.
assert handle("/produce").startswith("Usage: /produce bet"), \
    "bare /produce must ask for the 'bet' subcommand"
assert handle("/produce nonsense").startswith("Usage: /produce bet"), \
    "unknown /produce subcommand must be refused"
assert handle("/verify nonsense").startswith("Usage: /verify result"), \
    "unknown /verify subcommand must be refused"
assert not any(w in BRIGHT_LINE_WORDS for w in ("produce", "verify", "search")), \
    "the new commands must never trip a bright-line word"
print("/produce bet + /verify result registered, wrong subcommands refused: OK")

# --- /produce search: fixture-select flow (Phase 5.2) ----------------------
# The search path lazily imports webapp.produce and runs the engines, so this
# suite must never execute it. Mock both entry points — the assertion under
# test is the WIRING (query -> search_fixtures -> produce_selection -> Reply),
# not the engine.
assert handle("/produce search").startswith("Usage: /produce search"), \
    "bare '/produce search' must ask for a team or league"
assert handle("/produce nonsense").startswith("Usage: /produce bet"), \
    "an unknown subcommand must still be refused"
_fixtures = {"ok": True,
             "leagues": [{"name": "Eredivisie",
                          "fixtures": [{"home": "Sparta Rotterdam",
                                        "away": "FC Utrecht",
                                        "date": "2026-08-09"}]}],
             "flags": []}
_prod = {"ok": True,
         "board": [{"fixture": "Sparta Rotterdam v FC Utrecht"}],
         "rendered_text": "1. Sparta Rotterdam v FC Utrecht — Over 2.5 (52%)",
         "flags": [], "elapsed_s": 1.2, "n_rated": 1, "n_deploy": 1}
with mock.patch.object(tc, "_produce_season", return_value="2627"), \
     mock.patch("webapp.produce.search_fixtures", return_value=_fixtures) as _sf, \
     mock.patch("webapp.produce.produce_selection", return_value=_prod) as _ps:
    reply = handle("/produce search Sparta")
assert isinstance(reply, Reply), "a produced search must return a Reply"
assert "PRODUCED FOR: \"Sparta\"" in reply, "reply must name the query"
assert "Sparta Rotterdam v FC Utrecht" in reply, "reply must carry the blocks"
assert "PREVIEW ONLY" in reply, "reply must stay honest about paper-only"
assert not reply.startswith("SEARCH FAILED"), "mocked search must not fail"
_sf.assert_called_once()
_groups = _ps.call_args[0][0]
assert _groups[0]["league"] == "Eredivisie", \
    "the selection must carry the matched league"
assert _groups[0]["fixtures"][0]["home"] == "Sparta Rotterdam", \
    "the selection must carry the matched fixture"
assert _ps.call_args.kwargs.get("season") == "2627", \
    "production must use the same fixtures season as the search"
assert reply.keyboard and "inline_keyboard" in reply.keyboard, \
    "a produced search must offer the follow-up buttons"
print("/produce search Sparta searched, produced, returned as a Reply: OK")

# An empty search result must answer honestly and NEVER run the engines.
with mock.patch.object(tc, "_produce_season", return_value="2627"), \
     mock.patch("webapp.produce.search_fixtures",
                return_value={"ok": True, "leagues": [], "flags": []}) as _sf2, \
     mock.patch("webapp.produce.produce_selection") as _ps2:
    miss = handle("/produce search ZzzNoTeamZzz")
assert "No fixtures found" in miss and "NO DATA — PENDING" in miss, \
    "an empty search must be honest NO DATA"
assert _sf2.call_count == 1, "the query must reach the fixture search"
assert not _ps2.called, "an empty search must never run the engines"
print("empty search is honest NO DATA and never runs the engine: OK")

# --- existing commands still registered -------------------------------------
for cmd in ("/board", "/status", "/verify", "/why", "/log", "/note",
            "/debrief", "/help", "/start"):
    assert cmd in HANDLERS, f"{cmd} must still be registered"
print("All existing commands still registered: OK")

# --- routing without executing /send ---------------------------------------
assert handle("  /help  ").strip().startswith("OLP XDV commands"), \
    "whitespace-padded /help should route to help"
unknown = handle("/frobnicate")
assert unknown.startswith("Unknown command"), f"unknown command should be refused, got: {unknown[:40]}"
print("Routing: help routes, unknown command refused: OK")

# --- the leading slash is optional ------------------------------------------
assert handle("status").startswith("PHASE 3 GATE"), \
    "'status' without a slash must route to /status"
assert handle("Start").strip().startswith("OLP XDV commands"), \
    "'Start' must route to /start (help), not be an unknown command"
assert handle("produce").startswith("Usage: /produce bet"), \
    "'produce' without a slash must route to cmd_produce"
assert handle("verify nonsense").startswith("Usage: /verify result"), \
    "'verify' without a slash must route to cmd_verify"
note2 = handle("note enable capital")
assert note2.startswith("Correction logged"), \
    "'note ...' without a slash must be exempt from the bright-line refusal"
assert handle("frobnicate").startswith("Unknown command"), \
    "an unknown bare word must still be refused"
print("Leading slash optional; slash-less 'note' exempt from bright-line: OK")

# --- bright lines refused (never removable from a message) ------------------
for phrase in ("enable capital", "go live", "remove caveat", "stake 100"):
    r = handle(phrase)
    assert r.startswith("REFUSED"), f"'{phrase}' must be refused"
assert not BRIGHT_LINE_WORDS or all(
    w not in BRIGHT_LINE_WORDS for w in ("send", "run")), \
    "/send must never trip a bright-line word"
print("Bright-line phrases refused; /send not a bright-line phrase: OK")

# --- /note is exempt (a note is data, not an instruction) -------------------
note = handle("/note we should discuss go live later")
assert note.startswith("Correction logged"), f"/note must be exempt, got: {note[:40]}"
print("/note records corrections even if they mention bright-line words: OK")

# --- /note honesty: nothing is claimed to be applied automatically ----------
note = handle("/note honesty check")
assert "applied automatically" not in note, \
    "/note must not claim corrections auto-apply"
assert "/stats" in note, "/note must point the Architect at /stats to read back"
print("/note no longer claims auto-apply; points at /stats: OK")

# --- /stats is registered; empty brain renders honest NO DATA ---------------
from brain.store import Brain
from brain.report import render_stats
assert HANDLERS["/stats"] is tc.cmd_stats, "/stats must route to cmd_stats"
_sb = _tmp / "empty_brain.db"
if _sb.exists():
    _sb.unlink()
_b = Brain(_sb)
s = render_stats(_b, "")
assert "OLP XDV — STATS" in s, "/stats must render the header"
assert "NO DATA — PENDING" in s, "empty brain must surface NO DATA, never a guess"
s2 = render_stats(_b, "ZzzNoTeamZzz")
assert "NO DATA — PENDING" in s2, "missing-team lookup must be honest NO DATA"
_b.close()
print("/stats registered; empty brain renders honest NO DATA: OK")

# --- help advertises the pipeline commands ----------------------------------
h = cmd_help("")
for advert in ("/send", "/produce bet", "/verify result", "~30s"):
    assert advert in h, f"help must advertise {advert!r}"
print("Help advertises /send, /produce bet, /verify result: OK")

# --- inline keyboards (Phase 5.1): replies carry them, buttons are commands --
help_reply = handle("/help")
assert isinstance(help_reply, Reply), "/help must return a Reply carrying a keyboard"
assert help_reply.keyboard and "inline_keyboard" in help_reply.keyboard, \
    "/help must carry an inline keyboard"
flat = [b["text"] for row in help_reply.keyboard["inline_keyboard"] for b in row]
for expect in ("/board", "/status", "/why", "/produce bet", "/note"):
    assert expect in flat, f"/help keyboard must offer {expect}"
print("Inline keyboard on /help with the quick commands: OK")

# /status carries a keyboard AND reports pipeline health (Phase 5.3).
status_reply = handle("/status")
assert isinstance(status_reply, Reply) and status_reply.keyboard, \
    "/status must carry an inline keyboard"
assert "PIPELINE HEALTH" in status_reply, \
    "/status must show the pipeline health block (Phase 5.3)"
assert "Next scheduled run: 07:00 daily" in status_reply
print("Inline keyboard + PIPELINE HEALTH block on /status: OK")

# --- callback_query tap (Phase 5.1): answered, then routed as the command ----
_update = {"update_id": 7,
           "callback_query": {"id": "cq1",
                              "from": {"id": 999, "is_bot": False,
                                       "first_name": "T"},
                              "message": {"message_id": 1,
                                          "chat": {"id": 888, "type": "private"}},
                              "data": "/status"}}
fake = mock.MagicMock()
fake.get.return_value.json.return_value = {"ok": True, "result": [_update]}
fake.post.return_value.json.return_value = {"ok": True}
_old_cid = os.environ.get("TELEGRAM_CHAT_ID")
os.environ["TELEGRAM_CHAT_ID"] = "888"  # whitelist the test chat, like the real one
try:
    # send_telegram lives in notify.py and uses ITS OWN requests import, so
    # mock it here (poll_once's send step) rather than trying to intercept
    # the real HTTP call with a fake token.
    with mock.patch.object(tc, "requests", fake), \
         mock.patch.object(tc, "send_telegram",
                           return_value=(True, ["delivered 1 part(s) to Telegram"])) as _sent:
        _notes = tc.poll_once(token="fake-token")
finally:
    if _old_cid is None:
        os.environ.pop("TELEGRAM_CHAT_ID", None)
    else:
        os.environ["TELEGRAM_CHAT_ID"] = _old_cid
calls = fake.post.call_args_list
assert any("answerCallbackQuery" in str(c) for c in calls), \
    "a tapped button must be answered first"
assert _sent.call_count == 1, "the callback's command must produce one reply"
_reply_call = _sent.call_args
assert "PHASE 3 GATE" in _reply_call.args[0], \
    "the routed callback must be /status's reply"
assert _reply_call.kwargs.get("reply_markup", {}).get("inline_keyboard"), \
    "the routed reply must keep its inline keyboard"
print("callback_query tap answered + routed to the command with keyboard: OK")

# --- poll backoff (flaky-network resilience) --------------------------------
# A failed poll is absorbed as a note by poll_once, so the loop must detect it
# and back off exponentially instead of hammering api.telegram.org on a 2s gap
# (observed: 6170 failures during one flaky window). _poll_backoff_sleep grows
# with consecutive failures, stays within cap, and never sleeps <= 0.
# Monotonic growth below the cap: each consecutive failure must back off no
# shorter than the last. Compare median of many draws (jitter makes any single
# draw noisy). Failures 1..6 are 5,10,20,40,80,160s — all strictly below the
# 300s cap; 7+ saturate at the cap, so growth is checked only up to 6.
_mids = []
for n in (1, 2, 3, 4, 5, 6):
    draws = sorted(tc._poll_backoff_sleep(n, cap=300.0) for _ in range(101))
    _mids.append((n, draws[50]))  # median
for (n1, m1), (n2, m2) in zip(_mids, _mids[1:]):
    assert m1 < m2, f"median backoff must grow: failure {n1} -> {n2}"
assert _mids[-1][1] < 300.0, "growth must be checked strictly below the cap"
assert all(s > 0 for s in [m for _, m in _mids]), "backoff must never be <= 0"
# Failure 1 backoff is ~5s (base), scaled by jitter — the point is a failed
# poll stops the tight 2s loop immediately.
assert tc._poll_backoff_sleep(1, jitter=0.0) == 5.0, \
    "first failure must back off the base 5s (jitter disabled)"
assert tc._poll_backoff_sleep(2, jitter=0.0) == 10.0, \
    "second failure must double to 10s (jitter disabled)"
assert tc._poll_backoff_sleep(100, jitter=0.0) == 300.0, \
    "long outage must saturate at the 300s cap"
print("poll backoff grows exponentially, caps at 300s, jitters: OK")

print("\n[OK] ALL TELEGRAM COMMANDS TESTS PASSED")
