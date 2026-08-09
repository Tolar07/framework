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
assert not any(w in BRIGHT_LINE_WORDS for w in ("produce", "verify")), \
    "the new commands must never trip a bright-line word"
print("/produce bet + /verify result registered, wrong subcommands refused: OK")

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
import unittest.mock as mock

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

print("\n[OK] ALL TELEGRAM COMMANDS TESTS PASSED")
