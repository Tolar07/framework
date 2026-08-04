"""
Telegram command layer tests.

Routing and safety only — NOTHING here runs the pipeline. /send deliberately
executes a full live run (network, ledger writes), so this suite asserts the
mapping exists and that /send is the same handler as /run, without invoking
either. A real end-to-end check belongs in the stress test, not here.
"""
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from output import telegram_commands as tc
from output.telegram_commands import (handle, cmd_send, cmd_produce, cmd_verify,
                                      cmd_help, HANDLERS, BRIGHT_LINE_WORDS)

# Point the module's state files at a throwaway dir so no real ledger state
# (corrections.csv / offset) is mutated by this suite.
_tmp = Path(tempfile.mkdtemp(prefix="olp_xdv_cmds_test_"))
tc.STATE_DIR = _tmp
tc.OFFSET_FILE = _tmp / "telegram_offset.json"
tc.CORRECTIONS_FILE = _tmp / "corrections.csv"

# --- the poller stays lightweight: importing the module must NOT drag in the
# --- whole pipeline (scipy). /send lazy-imports run_daily exactly so the
# --- other commands never pay for it.
assert "run_daily" not in sys.modules, "run_daily must not be imported at module load"
assert "scipy" not in sys.modules, "scipy must not be imported at module load"
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

# --- help advertises the pipeline commands ----------------------------------
h = cmd_help("")
for advert in ("/send", "/produce bet", "/verify result", "~30s"):
    assert advert in h, f"help must advertise {advert!r}"
print("Help advertises /send, /produce bet, /verify result: OK")

print("\n✅ ALL TELEGRAM COMMANDS TESTS PASSED")
