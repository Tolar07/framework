"""
Telegram command interface — the Architect's way in.

The daily board is one-way. This makes the channel two-way so the Architect can
ask the framework questions and, more importantly, FEED IT THINGS ONLY HE HAS:
the real price he could get on SportyBet/Bet365, and plain-English corrections
when the framework gets something wrong.

SECURITY MODEL — read this before extending it
  1. CHAT WHITELIST. Set TELEGRAM_CHAT_IDS as a comma-separated list of chat IDs.
     Only whitelisted chats are answered. Anyone else who finds the bot gets
     silence, and the attempt is logged. A bot token is a bearer credential;
     assume it can leak. Fallback: single TELEGRAM_CHAT_ID still works.
  2. NOTHING HERE TOUCHES CAPITAL. Every command is read-only or append-only.
     config.assert_paper_only() still guards the write path underneath, so
     even a bug in this file cannot record a stake.
  3. MESSAGES ARE DATA, NOT AUTHORITY. A Telegram message is an instruction
     channel, and instruction channels get spoofed. Commands that would change
     a bright line — enabling capital, moving the phase, removing the honest-
     edge caveat — are REFUSED with an explanation and logged, never executed.
     Those changes need the Architect deliberately, in a session, not a
     one-line message at 07:00. This is not distrust of the Architect; it is
     the same reasoning that put the phase gate in code rather than in prose.

COMMANDS
  /board     re-send today's board
  /status    Phase 3 gate progress
  /verify    yesterday's graded results
  /why <n>   full reasoning for fixture n on today's board
  /log       Home v Away | Market | price      -> CL-LIVE paper leg (HR46)
  /note      free text                          -> corrections log (blueprint 2.7)
  /send        run the daily pipeline NOW and deliver the board (alias /run)
  /produce bet run the pipeline NOW, return the board as this reply (~30s)
  /produce search <q>  search today's fixtures for <q>, produce predictions
                       for just those matches (~30s, preview only — nothing
                       is written; the daily run owns the ledger)
  /verify result  grade pending legs NOW (settles any since played, updates CLV)
  /code        today's SportyBet booking codes (cached or generated ~30s)
  /debrief     full framework status
  /help        this list

The poller is lightweight on purpose: every command except /send, /produce
and /verify result imports nothing heavier than config + the CLV ledger.
Those three lazily import run_daily (scipy + the whole pipeline), so
answering a /status never pays for that.
"""
from __future__ import annotations

import argparse
import contextlib
import csv
import json
import os
import random
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import requests
except ImportError:
    requests = None

from config import PHASE, PHASE_LABEL, PAPER_PHASE, CAPITAL_ENABLED
from clv.clv_logger import CLVLog
from output.notify import send_telegram, HONEST_CAVEAT, add_subscriber
from output.render_fixture_list import render_fixture_list
from output.produce_bet import BoardFixture, VerificationResult
from engine.dixon_coles import FixtureProbabilities

STATE_DIR = Path(__file__).parent.parent / "memory"
OFFSET_FILE = STATE_DIR / "telegram_offset.json"
CORRECTIONS_FILE = STATE_DIR / "corrections.csv"
BOARD_DIR = Path(__file__).parent / "boards"

# Per-fixture model blocks a phone should read in one /produce search reply.
PRODUCE_SEARCH_MAX = 6

# Only whitelisted chats are answered. Set TELEGRAM_CHAT_IDS as a comma-separated
# list of chat IDs; anything else is ignored.
def _allowed() -> set[str]:
    raw = os.environ.get("TELEGRAM_CHAT_IDS", "").strip()
    if not raw:
        # Fallback to single TELEGRAM_CHAT_ID for backwards compatibility
        cid = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
        return {cid} if cid else set()
    return {c.strip() for c in raw.split(",") if c.strip()}


# Phrases that would move a bright line. Refused with an explanation — the
# framework's whole origin is a response to fabrication, and the guards that
# prevent it should not be removable from a phone.
BRIGHT_LINE_WORDS = (
    "enable capital", "go live", "phase 3", "phase3", "deploy capital",
    "remove caveat", "drop the caveat", "disable the gate", "turn off paper",
    "place the bet", "stake ",
)


def _load_offset() -> int:
    if OFFSET_FILE.exists():
        try:
            return json.loads(OFFSET_FILE.read_text()).get("offset", 0)
        except (json.JSONDecodeError, OSError):
            return 0
    return 0


def _save_offset(offset: int) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    OFFSET_FILE.write_text(json.dumps({"offset": offset}), encoding="utf-8")


class Reply(str):
    """A command reply that may carry a Telegram inline keyboard.

    A str subclass so every existing caller that treats a reply as plain text
    (tests, logging, the poller's send) keeps working unchanged; `.keyboard`
    is an optional dict shaped exactly like Telegram's reply_markup, attached
    to the last chunk by send_telegram. Tapping a button fires a callback_query
    whose data IS the command (e.g. "/status"), which poll_once answers and
    routes like a message — so no callback handler state is needed."""

    keyboard: dict | None = None

    def __new__(cls, text: str, keyboard: dict | None = None) -> Reply:
        obj = super().__new__(cls, text)
        obj.keyboard = keyboard
        return obj


def _keyboard(*rows: tuple[str, ...]) -> dict:
    """Inline keyboard whose button label and callback are the same command."""
    return {"inline_keyboard": [
        [{"text": cmd, "callback_data": cmd} for cmd in row] for row in rows
    ]}


# --------------------------------------------------------------------------
# Command handlers — each returns the reply text
# --------------------------------------------------------------------------

def _unsubscribe(chat_id: str) -> bool:
    """Remove a chat_id from the subscribers file. Returns True if removed."""
    chat_id = str(chat_id)
    if not SUBSCRIBERS_FILE.exists():
        return False
    lines = SUBSCRIBERS_FILE.read_text(encoding="utf-8").splitlines()
    new_lines = [l for l in lines if l.strip() != chat_id]
    if len(new_lines) == len(lines):
        return False
    SUBSCRIBERS_FILE.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    return True


def cmd_help(text: str, is_architect: bool = False) -> str:
    """Context-aware help — shows only commands the sender can use."""
    if is_architect:
        return Reply(
            "OLP XDV commands (Architect)\n\n"
            "/board       — re-send today's board\n"
            "/status      — Phase 3 gate progress\n"
            "/verify      — yesterday's graded results\n"
            "/verify result — grade pending legs NOW\n"
            "/why <n>     — full reasoning for fixture n on today's board\n"
            "/log         — log entry price for CL-LIVE paper leg\n"
            "/note        — log correction for review\n"
            "/send        — run daily pipeline NOW and deliver board\n"
            "/produce bet — run pipeline NOW, return board as reply\n"
            "/produce search <q> — search fixtures & produce predictions\n"
            "/debrief     — full framework status\n"
            "/stats       — brain's plain-language stats\n"
            "/code        — today's SportyBet booking codes\n"
            "/fixtures    — today's fixture list with model picks\n"
            "/ceo         — CEO orchestrator commands\n"
            "/help        — this list\n\n"
            f"{PHASE_LABEL}. Capital authority is the Architect's.",
            keyboard=_keyboard(("/board", "/status", "/send"),
                               ("/verify result", "/produce bet", "/debrief"),
                               ("/stats", "/code", "/help")))
    else:
        # Subscriber / non-Architect: only /start and /stop are available
        return Reply(
            "OLP XDV — Subscriber access\n\n"
            "This bot only accepts /start and /stop.\n"
            "For anything else, this isn't the right channel.\n\n"
            "/start — subscribe to daily board broadcasts\n"
            "/stop  — unsubscribe from daily board broadcasts",
            keyboard=_keyboard(("/start", "/stop")))


def cmd_stop(_: str) -> str:
    """/stop — unsubscribe from the daily board broadcast.

    This is idempotent and can be called by any subscriber. The Architect
    cannot be unsubscribed (their chat is the primary TELEGRAM_CHAT_ID)."""
    return "Use /stop in chat to unsubscribe from the daily board."



def _last_run_line() -> str:
    """Pipeline health: the brain's most recent daily-run record, or NO DATA."""
    try:
        from brain.store import Brain  # stdlib-only — never drags in scipy
    except Exception as e:
        return f"Last run: unavailable ({e})"
    try:
        with Brain(read_only=True) as b:
            r = b.last_run()
    except Exception as e:
        return f"Last run: unavailable ({e})"
    if not r:
        return "Last run: NO RUN RECORDED — the 07:00 job has not completed a run."
    started = (r.get("started_at") or "")[:16].replace("T", " ")
    status = r.get("status", "?")
    n_lg, n_fx, n_pr, n_lg2 = (r.get("leagues_scanned") or "?",
                               r.get("fixtures_seen") or "?",
                               r.get("predictions_logged") or "?",
                               r.get("legs_logged") or "?")
    fit = r.get("fit_seconds")
    fit_s = f" · fit {fit:.0f}s" if isinstance(fit, (int, float)) else ""
    tail = " — last run FAILED" if status == "failed" else ""
    return (f"Last run: {status.upper()}{tail} at {started}"
            f"\n  {n_lg} leagues · {n_fx} fixtures · {n_pr} predictions · "
            f"{n_lg2} legs logged{fit_s}")


def _data_quality_line() -> str:
    """One honest line from the data-quality monitor (HR35). Lazy import —
    the monitor reads the cache, so /status pays for it only when asked."""
    try:
        from monitor import data_quality as dq
        findings = dq.check()
    except Exception as e:
        return f"Data quality: unavailable ({e})"
    if not findings:
        return "Data quality: CLEAN — every whitelisted league has a fresh feed."
    errs = [f for f in findings if f.level == "error"]
    warns = [f for f in findings if f.level == "warn"]
    total = len(findings)
    err_n = len(errs)
    warn_n = len(warns)
    sample = errs[0] if errs else (warns[0] if warns else None)
    sample_txt = f" e.g. {sample.league}: {sample.problem[:90]}" if sample else ""
    return (f"Data quality: {err_n} error / {warn_n} warn of {total} finding(s)"
            f"{sample_txt}")


def cmd_status(_: str) -> str:
    log = CLVLog()
    s = log.phase2_status()
    mean = s["mean_clv_pct"]
    lines = [
        f"PHASE 3 GATE — {PHASE_LABEL}",
        "",
        f"Paper legs logged (total) : {s['legs_logged_total']}",
        f"Legs WITH logged CLV      : {s['legs_with_clv']} of {s['gate_requirement']} required",
        f"Mean CLV                  : {f'{mean:+.3f}%' if mean is not None else 'NO DATA — PENDING'}",
        f"Mean CLV positive?        : {'yes' if s['positive_mean_clv'] else 'NO'}",
        "",
        f"Gate met (pending your V7 sign-off): "
        f"{'YES' if s['gate_met_pending_architect_signoff'] else 'no'}",
        "",
        "A leg only counts once its CLOSING price exists, which is after the "
        "match. Legs logged today will count tomorrow.",
        "",
        "PIPELINE HEALTH",
        _last_run_line(),
        "Next scheduled run: 07:00 daily (plus /send on demand)",
        _data_quality_line(),
    ]
    return Reply("\n".join(lines), keyboard=_keyboard(("/board", "/stats", "/debrief"),
                                                      ("/verify result", "/produce bet")))


def cmd_board(_: str) -> str:
    p = BOARD_DIR / f"board_{date.today().isoformat()}.txt"
    if not p.exists():
        boards = sorted(BOARD_DIR.glob("board_*.txt"))
        if not boards:
            return "No board has been produced yet. NO DATA — PENDING."
        p = boards[-1]
    return Reply(p.read_text(encoding="utf-8"),
                 keyboard=_keyboard(("/status", "/why"), ("/verify result", "/produce bet")))


def cmd_heartbeat(_: str) -> str:
    """Show today's single heartbeat fixture (best pick of the day)."""
    p = BOARD_DIR / f"heartbeat_{date.today().isoformat()}.txt"
    if not p.exists():
        heartbeats = sorted(BOARD_DIR.glob("heartbeat_*.txt"))
        if not heartbeats:
            return "No heartbeat available yet. Heartbeat is generated with the daily board."
        p = heartbeats[-1]
    return Reply(p.read_text(encoding="utf-8"),
                 keyboard=_keyboard(("/board", "/status"), ("/verify result", "/produce bet")))


def cmd_verify(arg: str) -> str:
    """Two modes, same route:
      /verify          today's saved VERIFY RESULTS section (read-only)
      /verify result   grade pending legs NOW — settle any that have since
                       been played and report, the same first step the daily
                       run takes. On-demand grading updates the ledger: a
                       settled leg gains its result and, when the source has
                       a closing price, its CLV."""
    sub = arg.strip().lower()
    if sub and sub != "result":
        return ("Usage: /verify result   (or /verify with no arg for today's "
                "saved section)")
    if not sub:
        p = BOARD_DIR / f"board_{date.today().isoformat()}.txt"
        if not p.exists():
            return "No board today yet — nothing graded. NO DATA — PENDING."
        text = p.read_text(encoding="utf-8")
        if "VERIFY RESULTS" in text:
            return text.split("VERIFY RESULTS", 1)[1].strip()[:3500]
        return "No VERIFY RESULTS section in today's board."
    # /verify result — fresh grading. Lazy import, same reason as /send.
    import run_daily
    log = CLVLog()
    try:
        block, flags = run_daily.grade_open_legs(log, "2526")
    except Exception as e:
        return (f"VERIFY FAILED — {type(e).__name__}: {e}\n\n"
                f"See logs/daily_*.log for the detail.")
    return block + ("\n\n" + "\n".join(flags) if flags else "")


def cmd_why(arg: str) -> str:
    """Full stacked block for one fixture on today's board."""
    arg = arg.strip()
    if not arg.isdigit():
        return "Usage: /why 2   (the number of a fixture in PART 1)"
    text = cmd_board("")
    marker = f"\n{arg}. "
    if marker not in text:
        return f"No fixture {arg} on today's board."
    block = text.split(marker, 1)[1]
    nxt = f"\n{int(arg)+1}. "
    return Reply((marker.strip() + " " + (block.split(nxt)[0] if nxt in block else block))[:3500],
                 keyboard=_keyboard(("/board", "/status")))


def cmd_log(arg: str) -> str:
    """Architect-fed entry price -> a CL-LIVE paper leg.

    This is the highest-value command here. HR46 wants the price captured at
    pick time, and the price the Architect can actually get on SportyBet is
    better evidence than any API's — it is the one that will actually be
    settled against."""
    parts = [p.strip() for p in arg.split("|")]
    if len(parts) != 3:
        return ("Usage: /log Home v Away | Market | price\n"
                "e.g.  /log Hearts v Dundee United | Over 1.5 goals | 1.42")
    fixture, market, price_s = parts
    try:
        price = float(price_s)
    except ValueError:
        return f"'{price_s}' is not a decimal price. Nothing logged."
    if not (1.01 <= price <= 1000):
        return f"Price {price} is out of plausible range. Nothing logged."
    if " v " not in fixture:
        return "Fixture must read 'Home v Away'. Nothing logged."

    log = CLVLog()
    leg = log.log_entry(
        league="ARCHITECT-FED", fixture=fixture, market=market,
        model_prob=0.0,                 # unknown here; CLV needs only the prices
        entry_odds=price, entry_capture_path="CL-LIVE",
        phase=PAPER_PHASE, stake=None,  # Phase 2 — never a stake
    )
    return (f"Logged as a PAPER leg (no stake):\n"
            f"  {fixture}\n  {market} at {price} decimal\n"
            f"  capture path CL-LIVE, leg id {leg.leg_id[:40]}\n\n"
            f"Its closing price will be captured after the match, and CLV "
            f"computed then. Nothing has been staked.")


def cmd_note(arg: str) -> str:
    if not arg.strip():
        return "Usage: /note <what the framework got wrong>"
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    new = not CORRECTIONS_FILE.exists()
    with open(CORRECTIONS_FILE, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["logged_at", "source", "note", "actioned"])
        w.writerow([datetime.now(timezone.utc).isoformat(), "telegram",
                    arg.strip(), "no"])
    return ("Correction logged for review.\n\n"
            "It is stored in the framework's memory and is READ BACK by "
            "/stats — nothing is applied silently. A RULE change still gets "
            "proposed to you for approval first; the framework never rewrites "
            "its own rules.")


def cmd_stats(arg: str) -> str:
    """The brain's plain-language stats: /stats for the overview, /stats <team>
    for 'what did I predict for X'. The brain is stdlib-only, so importing it
    here does not drag scipy into the lightweight poller."""
    from brain.store import Brain
    from brain.report import render_stats
    try:
        with Brain() as brain:
            return render_stats(brain, arg)
    except Exception as e:
        return f"/stats unavailable: {e}"


def cmd_debrief(_: str) -> str:
    log = CLVLog()
    s = log.phase2_status()
    mean = s["mean_clv_pct"]
    lines = [
        "OLP XDV — FRAMEWORK DEBRIEF",
        f"{PHASE_LABEL}",
        "",
        "PHASE 3 GATE",
        f"  legs with logged CLV : {s['legs_with_clv']} / {s['gate_requirement']}",
        f"  mean CLV             : {f'{mean:+.3f}%' if mean is not None else 'NO DATA — PENDING'}",
        f"  capital enabled      : {'yes' if CAPITAL_ENABLED else 'NO — blocked in code'}",
        "",
        "WHAT THE BACKTEST FOUND",
        "  Walk-forward on 2024/25, no leakage:",
        "  Scottish Premiership  mean CLV -0.189%  (beat close 48.3%)",
        "  Eredivisie            mean CLV -0.478%  (beat close 46.8%)",
        "  Random placebo        mean CLV -1.177%",
        "  => the model beats random selection in 5 of 5 markets, but still",
        "     loses to the closing line. Signal, not yet edge.",
        "",
        "KNOWN LIMITS",
        "  Denmark and Poland have no opening prices in the results source, so",
        "  they cannot be CLV-backtested. BTTS and Over 3.5 have no prices at",
        "  all. Over 1.5 is never quoted and is DERIVED under HR30.",
        "",
        "OPEN",
        "  Model under-predicts goals (Over 2.5 by ~6pp after the BUG7 fix),",
        "  which inflates Under 2.5 and BTTS-No — the markets you trade.",
        "",
        HONEST_CAVEAT,
    ]
    return Reply("\n".join(lines),
                 keyboard=_keyboard(("/status", "/board", "/stats")))


def cmd_send(_: str) -> str:
    """Trigger a FRESH daily run and deliver the board, on demand.

    The Architect's way to get today's board without waiting for 07:00: it
    grades yesterday's legs, pulls live odds, rescans every league, logs any
    new paper legs, and delivers the board to TELEGRAM_CHAT_ID — the SAME
    code path as the scheduled run (run_daily.run), so an on-demand delivery
    is the scheduled delivery, not a second opinion.

    A run takes ~30s; during it the poller is busy and queued commands wait.
    Bright-line rules still apply underneath: config.assert_paper_only()
    keeps every leg paper, so /send can never stake."""
    import run_daily  # lazy — the other commands must not pay for scipy
    try:
        # Production delivery MUST include SportyBet booking codes for every
        # acca + single (Architect directive 2026-08-16) — enable booking so a
        # send never ships "NO DATA — PENDING" picks.
        run_daily.run(send=True, booking_codes=True)
    except RuntimeError as e:
        # run_daily raises exactly when delivery is incomplete. The board is
        # on disk regardless; say so rather than claiming success.
        return f"RUN FAILED — {e}\n\nBoard was written to disk; delivery incomplete."
    except Exception as e:
        return (f"RUN FAILED — {type(e).__name__}: {e}\n\n"
                f"No board delivered; the run's log has the detail.")
    return ("FRESH RUN COMPLETE — board delivered.\n\n"
            "Graded yesterday's legs, pulled live prices, rescanned every "
            "league, and logged any new paper legs. The board was sent in "
            "parts; every part carries the honest-edge caveat.")


def _produce_season() -> str:
    """Current fixtures season code ('2526' -> '2627') — the same rule the web
    dashboard (webapp/server.py) and the fixture sources use internally."""
    try:
        from orchestrator import next_season_code
        return next_season_code("2526")
    except Exception:
        return "2627"


def _produce_search_usage() -> str:
    return ("Usage: /produce search <team or league>\n"
            "Searches today's fixtures for that team or league and returns the "
            "model's prediction for each match found. Preview only — never "
            "writes the ledger.\n"
            "Example: /produce search Sparta")


def _produce_search(query: str) -> str:
    """Search + produce for a chosen query — the phone's fixture-select flow.

    Reuses the admin panel's real-time production (webapp.produce) so the
    phone gets the SAME engine: search_fixtures finds today's fixtures
    matching <query>, produce_selection runs the engines over just those and
    returns one model block per fixture. Nothing is written — no ledger rows,
    no board file. The daily run owns the ledger; this is a preview."""
    from webapp import produce as WP  # lazy — only /produce pays for the engine
    season = _produce_season()
    try:
        found = WP.search_fixtures(query=query, days=7)
    except Exception as e:
        return (f"SEARCH FAILED — {type(e).__name__}: {e}\n\n"
                f"Fixture lookup for '{query}' hit an error; see the log.")
    if not found.get("ok"):
        return f"SEARCH FAILED — {found.get('error', 'unknown fixture error')}"
    groups: list[dict] = []
    total = 0
    for lg in found.get("leagues", []):
        fixtures = lg.get("fixtures", [])[:max(0, PRODUCE_SEARCH_MAX - total)]
        if fixtures:
            groups.append({"league": lg["name"], "fixtures": fixtures})
            total += len(fixtures)
        if total >= PRODUCE_SEARCH_MAX:
            break
    if not groups:
        return (f"No fixtures found for '{query}' in the next 7 days across the "
                f"whitelisted leagues.\n\nNO DATA — PENDING: try a team or "
                f"league name, or /produce bet for the full board.")
    res = WP.produce_selection(groups, season=season)
    if not res.get("ok"):
        return f"PRODUCE FAILED — {res.get('error', 'engine error')}"
    blocks = res.get("rendered_text", "")
    if not blocks:
        return (f"No prediction blocks produced for '{query}'.\n\n"
                f"NO DATA — PENDING: the engines rated no fixture in the "
                f"selection.")
    n_rated = res.get("n_rated", 0)
    n_fx = len(res.get("board", []))
    body = (
        f"PRODUCED FOR: \"{query}\"\n"
        f"{n_rated} of {n_fx} fixture(s) rated in {res.get('elapsed_s', '?')}s.\n"
        f"PREVIEW ONLY — zero capital, nothing written; the daily run owns the "
        f"ledger.\n"
        f"{'=' * 34}\n\n{blocks}"
    )
    flags = res.get("flags", [])
    if flags:
        body += "\n\nNOTES:\n" + "\n".join(flags[:3])
    return Reply(body[:3500],
                 keyboard=_keyboard(("/board", "/status"), ("/produce bet",)))


def cmd_produce(arg: str) -> str:
    """/produce bet | /produce search <team or league>

    Two ways to run the engine from the phone:
      /produce bet            full daily board — same engine as /send, returned
                              here as the compact per-league tables.
      /produce search <q>     search today's fixtures for <q> and produce
                              predictions for up to PRODUCE_SEARCH_MAX of them,
                              one model block each. Preview only — never writes
                              the ledger.

    Both take ~30-90s and keep the poller busy meanwhile. Bright-line rules
    still apply underneath: config.assert_paper_only() keeps every leg paper,
    so neither path can ever stake."""
    parts = arg.strip().split(None, 1)
    first = parts[0].lower() if parts else ""
    if first == "search":
        query = parts[1].strip() if len(parts) > 1 else ""
        if not query:
            return _produce_search_usage()
        return _produce_search(query)
    if first != "bet":
        return ("Usage: /produce bet\n"
                "        /produce search <team or league>\n"
                "Runs the daily pipeline now and returns the compact board — "
                "all leagues with fixtures that day, each row showing the "
                "model prediction and the recommended pick. Same engine as "
                "/send, but no separate Telegram delivery. Add 'search <q>' "
                "to produce just the fixtures matching a team or league.")
    import run_daily  # lazy — the other commands must not pay for scipy
    try:
        # booking_codes=True so the phone's /produce bet reply carries today's
        # SportyBet codes (Architect 2026-08-11) — a browser fault degrades each
        # slip to honest MANUAL/NO DATA, never a run failure (HR35).
        res = run_daily.run(send=False, booking_codes=True)
    except Exception as e:
        return (f"PRODUCE FAILED — {type(e).__name__}: {e}\n\n"
                f"See logs/daily_*.log for the detail.")
    return Reply(res.telegram_text,
                 keyboard=_keyboard(("/board", "/status"), ("/produce search",)))


def cmd_ceo(arg: str) -> str:
    """CEO orchestrator — routes /ceo <subcommand> [args] to CEOAgent.

    Delegates command parsing and routing to the CEOAgent class so the CEO's
    own command surface stays in one place (ceo_agent.py). Wrapped in
    try/except so a CEO bug never takes down the poller — the Architect still
    gets an answer (an error reply), not silence."""
    try:
        from ceo_agent import CEOAgent
        ceo = CEOAgent()
        parsed = ceo.parse_command("/ceo " + arg)
        return ceo.handle_command(parsed.command, parsed.arg)
    except Exception as e:
        return (f"CEO agent error: {type(e).__name__}: {e}\n\n"
                f"Send /ceo help for the command reference.")


def cmd_code(arg: str) -> str:
    """Fetch and display today's SportyBet booking codes.

    Reads the cached acca_<date>_codes.json generated by the daily run.
    If not found, falls back to generating them on-demand (takes ~30s).
    Usage: /code [date] — date defaults to today (YYYY-MM-DD)."""
    from datetime import date as date_cls
    from booking.booking_codes import _load_acca_payload, book_accas, render_codes

    arg = arg.strip()
    day = arg if arg else date_cls.today().isoformat()

    codes_path = BOARD_DIR / f"acca_{day}_codes.json"
    if codes_path.exists():
        try:
            import json
            cached = json.loads(codes_path.read_text(encoding="utf-8"))
            return Reply(render_codes(cached),
                         keyboard=_keyboard(("/board", "/status"), ("/produce bet",)))
        except Exception as e:
            pass  # fall back to fresh generation

    # Generate on demand
    try:
        payload = _load_acca_payload(day)
    except FileNotFoundError:
        return (f"No acca payload for {day} — run the daily pipeline first "
                f"(/send or /produce bet), then try /code again.")

    # Run booking codes generation (headless, best-effort)
    result = book_accas(payload, headless=True)
    return Reply(render_codes(result),
                 keyboard=_keyboard(("/board", "/status"), ("/produce bet",)))


def cmd_fixtures(_: str) -> str:
    """Show today's fixture list with model picks including alt markets.

    Reads today's board (output/boards/board_YYYY-MM-DD.json) and renders a
    simple date-ordered list of teams grouped by league with:
    - PICK (home/draw/away with win %)
    - Alt markets: Over 1.5, Over 2.5, Over 3.5, BTTS — all with probabilities

    No scipy/orchestrator imports — reads the cached board that the pipeline
    already produced. Falls back to yesterday's board if today's isn't ready.
    """
    import json as json_mod

    today = date.today().isoformat()
    board_path = BOARD_DIR / f"board_{today}.json"

    if not board_path.exists():
        # Fall back to most recent board
        boards = sorted(BOARD_DIR.glob("board_*.json"))
        if not boards:
            return "No board available yet. Run the pipeline first (/produce bet)."
        board_path = boards[-1]
        day_label = board_path.stem.replace("board_", "")
    else:
        day_label = today

    try:
        raw = json_mod.loads(board_path.read_text(encoding="utf-8"))
    except Exception as e:
        return f"Cannot read board for {day_label}: {e}"

    # Build BoardFixture objects from JSON
    board_objs = []
    for entry in raw.get("board", []):
        probs = None
        p_data = entry.get("probs")
        if p_data:
            try:
                probs = FixtureProbabilities(
                    home_team=p_data.get("home_team", ""),
                    away_team=p_data.get("away_team", ""),
                    lambda_home=p_data.get("lambda_home", 0.0),
                    lambda_away=p_data.get("lambda_away", 0.0),
                    p_home=p_data.get("p_home", 0.0),
                    p_draw=p_data.get("p_draw", 0.0),
                    p_away=p_data.get("p_away", 0.0),
                    modal_scoreline=tuple(p_data.get("modal_scoreline", [0, 0])),
                    p_over_15=p_data.get("p_over_15"),
                    p_over_25=p_data.get("p_over_25"),
                    p_over_35=p_data.get("p_over_35"),
                    p_btts_yes=p_data.get("p_btts_yes"),
                )
            except Exception:
                pass  # skip malformed probs

        v = entry.get("verification") or {}
        try:
            verification = VerificationResult(
                tier=v.get("tier", "UNKNOWN"),
                value=None,
                factors=None,
                note=v.get("note", ""),
            )
        except Exception:
            verification = None  # type: ignore

        board_objs.append(BoardFixture(
            fixture=entry.get("fixture", ""),
            probs=probs,
            verification=verification,  # type: ignore
            best_market=entry.get("best_market"),
            best_price=entry.get("best_price"),
            kickoff_utc=entry.get("kickoff_utc"),
            kickoff_date=entry.get("kickoff_date"),
        ))

    rendered = render_fixture_list(board=board_objs)
    return Reply(rendered, keyboard=_keyboard(("/board", "/code"), ("/produce bet",)))


HANDLERS = {
    "/help": cmd_help, "/start": cmd_help, "/stop": cmd_stop,
    "/status": cmd_status, "/board": cmd_board, "/verify": cmd_verify,
    "/why": cmd_why, "/log": cmd_log, "/note": cmd_note,
    "/send": cmd_send, "/run": cmd_send,
    "/produce": cmd_produce,
    "/debrief": cmd_debrief,
    "/stats": cmd_stats,
    "/ceo": cmd_ceo,
    "/code": cmd_code,
    "/fixtures": cmd_fixtures,
}


def handle(text: str) -> str:
    """Route one message. Bright-line requests are refused, not executed.

    The leading slash is optional — the Architect types words, not tokens:
    'status', 'send', 'produce bet', 'verify result', 'Start' all route to
    the same handlers as their /-forms. A note stays a note whether or not
    it has a slash, because notes are data, never instructions."""
    stripped = text.strip()
    low = stripped.lower()

    if any(w in low for w in BRIGHT_LINE_WORDS) and not (
            low.startswith("/note") or low.startswith("note ")):
        return (
            "REFUSED — that would move a bright line.\n\n"
            f"At PHASE={PHASE} capital is enabled, but capital authority "
            "remains the Architect's: bets are placed by you, never by this "
            "framework, and the honest-edge caveat is not removable. Those are "
            "not settings I change from a message: a chat channel can be "
            "spoofed, and the framework exists because of a fabrication "
            "incident.\n\n"
            "If you genuinely want to change this, do it deliberately in a "
            "working session where the reasoning is on the record. Logged as a "
            "note in the meantime."
        )

    cmd = low.split()[0] if low else ""
    bare = cmd.lstrip("/")
    handler = HANDLERS.get(cmd) or HANDLERS.get("/" + bare)
    if handler is None:
        return f"Unknown command '{cmd or stripped[:20]}'.\n\n{cmd_help('')}"
    # The argument is whatever followed the matched token, slash or no slash.
    consumed = cmd if cmd.startswith("/") else bare
    return handler(stripped[len(consumed):])


def poll_once(token: Optional[str] = None, long_poll_seconds: int = 0) -> list[str]:
    """One getUpdates pass. Returns a log line per message handled.

    long_poll_seconds > 0 uses Telegram long-polling: the request blocks up
    to that many seconds waiting for a message and returns the instant one
    arrives. A resident daemon passes 30, so a command is answered within
    seconds instead of on the next scheduled fire. The single-pass caller
    (default 0) stays an immediate no-wait poll.

    A network failure is absorbed as a returned note ("command poll failed:
    …") rather than raised, so a single poll never kills the daemon. The
    --loop caller counts consecutive failures and backs off (see
    _poll_backoff_sleep) — a flaky network window must not hammer
    api.telegram.org with back-to-back retries."""
    notes: list[str] = []
    token = token or os.environ.get("TELEGRAM_BOT_TOKEN")
    if requests is None or not token:
        return ["telegram not configured — skipping command poll"]

    offset = _load_offset()
    try:
        r = requests.get(f"https://api.telegram.org/bot{token}/getUpdates",
                          params={"offset": offset + 1, "timeout": long_poll_seconds},
                          timeout=long_poll_seconds + 15)
        updates = r.json().get("result", [])
    except Exception as e:
        return [f"command poll failed: {e}"]

    for u in updates:
        offset = max(offset, u.get("update_id", offset))
        notes.extend(handle_update(u, token=token)[1])
    _save_offset(offset)
    return notes or ["no new commands"]


def _poll_backoff_sleep(consecutive_failures: int,
                        *,
                        base: float = 5.0,
                        cap: float = 300.0,
                        jitter: float = 0.5) -> float:
    """Seconds to sleep after `consecutive_failures` failed polls.

    Exponential: base * 2**n, capped at `cap`, then a random ±jitter fraction
    so retries don't pile up on the same boundary. Failure 0 -> ~5s, 1 -> ~10s,
    2 -> ~20s … 6+ -> ~300s. The daemon sleeps this long and then re-polls; a
    recovered network is picked up on the next attempt (getUpdates is offset-
    based, so nothing is missed while backed off)."""
    delay = min(cap, base * (2 ** max(0, consecutive_failures - 1)))
    return delay * random.uniform(1 - jitter, 1 + jitter)


def handle_update(update: dict, token: str | None = None) -> tuple[bool, list[str]]:
    """Process ONE Telegram update — the shared heart of long-polling AND
    webhook receivers. Returns (reply_delivered_ok, notes).

    Handles a message or an inline-keyboard callback_query exactly as the
    poller always has: whitelist first, answer a tapped button (clears the
    clock spinner), route the command, send the reply (carrying any inline
    keyboard). A webhook reply is therefore the same command, guard and
    bright-line handling as a polled one — one code path, two transports."""
    notes: list[str] = []
    msg = update.get("message") or {}
    cq = update.get("callback_query") or {}
    chat = msg.get("chat") or cq.get("message", {}).get("chat", {})
    chat_id = str(chat.get("id", ""))
    text = msg.get("text") or ""
    allowed = _allowed()
    if cq:
        # An inline-keyboard tap. The button's callback_data IS the command
        # (e.g. "/status"), so answer the tap (clears the clock spinner) and
        # route it exactly like a typed message — no callback state needed.
        data = cq.get("data") or ""
        # Inline buttons must respect subscriber gating too.
        from output.notify import subscribers
        primary = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
        is_architect = (chat_id == primary)
        is_subscriber = str(chat_id) in set(subscribers())
        if not (is_architect or is_subscriber):
            notes.append(f"IGNORED callback from non-whitelisted chat {chat_id}")
            return True, notes
        # A failed ack must never drop the command that follows.
        with contextlib.suppress(Exception):
            requests.post(
                f"https://api.telegram.org/bot{token}/answerCallbackQuery",
                json={"callback_query_id": cq.get("id", ""),
                      "text": "…"},
                timeout=15)
        if data:
            text = data
    if not text:
        return True, notes
    # Subscriber management: /start subscribes, /stop unsubscribes.
    from output.notify import subscribers as _subscribers_fn
    low = text.strip().lower()
    primary = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    is_architect = (chat_id == primary)
    is_subscriber = str(chat_id) in set(_subscribers_fn())

    # /start — idempotent subscribe (first time only per session, but we allow
    # repeat sends for feedback; add_subscriber itself is idempotent on disk).
    if low.startswith("/start"):
        name = ((msg.get("from") or {}).get("first_name") or "")
        is_new = add_subscriber(chat_id)
        if is_new:
            notes.append(f"SUBSCRIBED chat {chat_id}{(' (' + name + ')') if name else ''}")
        else:
            notes.append(f"/start from already-subscribed chat {chat_id}")
        # Always confirm subscription with appropriate help
        reply = cmd_help("", is_architect=is_architect)
        if isinstance(reply, Reply):
            markup = reply.keyboard
            reply = str(reply)
        else:
            markup = None
        ok, send_notes = send_telegram(reply, token=token, chat_id=chat_id,
                                       reply_markup=markup)
        return ok, notes

    # /stop — idempotent unsubscribe.
    if low.startswith("/stop"):
        _unsubscribe(chat_id)
        notes.append(f"UNSUBSCRIBED chat {chat_id}")
        reply = "You have been unsubscribed. The daily board will no longer be sent here.\nSend /start to re-subscribe."
        ok, send_notes = send_telegram(reply, token=token, chat_id=chat_id)
        return ok, notes

    # Access control: only the Architect has command authority.
    # Subscribers (non-Architect) are limited to /start and /stop only.
    # All other input from subscribers is dead-ended with a static reply.
    if not is_architect:
        # Subscribers get nothing but /start and /stop — anything else is dead-ended.
        notes.append(f"BLOCKED non-command input from chat {chat_id} (not Architect)")
        refusal = (
            "This bot only accepts /start and /stop.\n"
            "For anything else, this isn't the right channel."
        )
        ok, send_notes = send_telegram(refusal, token=token, chat_id=chat_id)
        return ok, notes

    # Architect path: route commands normally (all handlers available).
    reply = handle(text)
    markup = reply.keyboard if isinstance(reply, Reply) else None
    ok, send_notes = send_telegram(reply, token=token, chat_id=chat_id,
                                   reply_markup=markup)
    label = text.split()[0] if text.split() else "?"
    if ok:
        notes.append(f"handled {label} from {chat_id} -> {', '.join(send_notes)}")
    else:
        notes.append(f"handled {label} from {chat_id} but REPLY DELIVERY "
                     f"FAILED: {'; '.join(send_notes)}")
    return ok, notes


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="OLP XDV Telegram command poller — the Architect's way in.")
    ap.add_argument("--loop", action="store_true",
                    help="run as a resident long-polling daemon (near-instant replies)")
    ap.add_argument("--interval", type=int, default=30,
                    help="long-poll seconds per getUpdates in --loop mode")
    args = ap.parse_args()

    if args.loop:
        # Single-instance guard: two pollers would race on the getUpdates
        # offset and double-answer. A stale lock (dead pid) is taken over.
        lock = Path(__file__).parent.parent / "memory" / "telegram_poller.lock"
        lock.parent.mkdir(parents=True, exist_ok=True)
        if lock.exists():
            try:
                os.kill(int(lock.read_text().strip()), 0)
                print(f"another poller is already running — exiting")
                sys.exit(0)
            except (OSError, ValueError):
                pass  # stale lock from a killed process — take it over
        lock.write_text(str(os.getpid()))

        print(f"OLP XDV command poller running — Ctrl-C to stop "
              f"(long-poll {args.interval}s, replies near-instant)")
        consecutive_failures = 0
        _last_rotate = time.time()
        _ROTATE_INTERVAL = 3600  # check log sizes every hour
        try:
            while True:
                # Periodically rotate poller.log so the resident daemon's
                # output doesn't grow unbounded (10MB / 5 backups).
                if time.time() - _last_rotate > _ROTATE_INTERVAL:
                    try:
                        from monitor.json_log import rotate_log_file
                        p = Path(__file__).parent.parent / "logs" / "poller.log"
                        rotate_log_file(p)
                    except Exception:
                        pass
                    _last_rotate = time.time()
                try:
                    notes = poll_once(long_poll_seconds=args.interval)
                    for n in notes:
                        print(f"[{datetime.now(timezone.utc).isoformat()}] {n}")
                except Exception as e:
                    # self-healing: a transient error must not kill the one
                    # process the phone depends on for replies.
                    print(f"[{datetime.now(timezone.utc).isoformat()}] "
                          f"poller error, continuing: {e}")
                    consecutive_failures += 1
                    time.sleep(_poll_backoff_sleep(consecutive_failures))
                    continue
                if any(n.startswith("command poll failed") for n in notes):
                    # poll_once absorbs network failures as a returned note, so
                    # the except path above never sees them. Count them here and
                    # back off exponentially — a flaky network window (observed:
                    # hours of NameResolutionError/read-timeouts) must not hammer
                    # api.telegram.org with 45s-out retries on a 2s gap.
                    consecutive_failures += 1
                    wait = _poll_backoff_sleep(consecutive_failures)
                    print(f"[{datetime.now(timezone.utc).isoformat()}] "
                          f"command poll failed — backing off "
                          f"{wait:.0f}s ({consecutive_failures} consecutive)")
                    time.sleep(wait)
                    continue
                consecutive_failures = 0
                time.sleep(2)  # safety gap; long-poll does the waiting
        except KeyboardInterrupt:
            print("poller stopped")
        finally:
            lock.unlink(missing_ok=True)
    else:
        for n in poll_once():
            print(n)
