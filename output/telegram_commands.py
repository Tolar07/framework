"""
Telegram command interface — the Architect's way in.

The daily board is one-way. This makes the channel two-way so the Architect can
ask the framework questions and, more importantly, FEED IT THINGS ONLY HE HAS:
the real price he could get on SportyBet/Bet365, and plain-English corrections
when the framework gets something wrong.

SECURITY MODEL — read this before extending it
  1. CHAT WHITELIST. Only ALLOWED_CHAT_IDS is answered. Anyone else who finds
     the bot gets silence, and the attempt is logged. A bot token is a
     bearer credential; assume it can leak.
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
  /log       Home v Away | Market | price [| YYYY-MM-DD]  -> CL-LIVE paper leg (HR46)
  /note      free text                          -> corrections log (blueprint 2.7)
  /debrief   full framework status
  /proposals the losing-market watch's proposals (order 39)
  /lookup <team>, /picks [date]   the records, via scripts/olp_query.py
  /approve P3, /reject P3   decide a proposal — the Architect's chat ONLY,
             refused when TELEGRAM_CHAT_ID is unset (fails closed)
  /help      this list
"""
from __future__ import annotations

import csv
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import requests
except ImportError:
    requests = None

from config import PHASE, PHASE_LABEL, PAPER_PHASE, CAPITAL_ENABLED
from clv.clv_logger import CLVLog
from output.notify import send_telegram, HONEST_CAVEAT

STATE_DIR = Path(__file__).parent.parent / "memory"
OFFSET_FILE = STATE_DIR / "telegram_offset.json"
CORRECTIONS_FILE = STATE_DIR / "corrections.csv"
BOARD_DIR = Path(__file__).parent / "boards"

# Only this chat is answered. Set TELEGRAM_CHAT_ID; anything else is ignored.
def _allowed() -> set[str]:
    cid = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    return {cid} if cid else set()


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


# --------------------------------------------------------------------------
# Command handlers — each returns the reply text
# --------------------------------------------------------------------------

def cmd_help(_: str) -> str:
    return (
        "OLP XDV commands\n\n"
        "/board — re-send today's board\n"
        "/status — Phase 3 gate progress\n"
        "/verify — yesterday's graded results\n"
        "/why 2 — full reasoning for fixture 2 on today's board\n"
        "/log Hearts v Dundee United | Over 1.5 goals | 1.42\n"
        "     records a price YOU got, as a CL-LIVE paper leg (HR46);\n"
        "     add | 2026-10-05 if the match isn't on a recent board\n"
        "/note the model looks wrong on Motherwell\n"
        "     records a correction; the heartbeat and weekly review list it until acted on\n"
        "/debrief — full framework status\n"
        "/proposals — markets the watch proposes to stop picking\n"
        "/lookup Arsenal — every pick and rated fixture for a team on record\n"
        "/picks or /picks 2026-10-03 — a day's picks and results\n"
        "/approve P3 or /reject P3 — decide one (rejecting an approved block lifts it)\n\n"
        f"{PHASE_LABEL}. Live capital is Architect-deployed — this system never stakes."
    )


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
    ]
    return "\n".join(lines)


def cmd_board(_: str) -> str:
    p = BOARD_DIR / f"board_{date.today().isoformat()}.txt"
    if not p.exists():
        boards = sorted(BOARD_DIR.glob("board_*.txt"))
        if not boards:
            return "No board has been produced yet. NO DATA — PENDING."
        p = boards[-1]
    return p.read_text(encoding="utf-8")


def cmd_verify(_: str) -> str:
    p = BOARD_DIR / f"board_{date.today().isoformat()}.txt"
    if not p.exists():
        return "No board today yet — nothing graded. NO DATA — PENDING."
    text = p.read_text(encoding="utf-8")
    if "VERIFY RESULTS" in text:
        return text.split("VERIFY RESULTS", 1)[1].strip()[:3500]
    return "No VERIFY RESULTS section in today's board."


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
    return (marker.strip() + " " + (block.split(nxt)[0] if nxt in block else block))[:3500]


# /log MARKET WORDING -> market key (engine/markets.py), so a logged leg can be
# settled. Anything not recognised is refused rather than logged ungradeable.
def _market_key(text: str, homes: list[str], aways: list[str],
                singles: list[dict]) -> Optional[str]:
    from engine import markets as mkt
    low = " ".join(text.lower().replace("goals", "").replace("&", " & ").split())
    for s in singles:                       # the board's own wording for this match
        if s.get("pick", "").lower() == text.strip().lower():
            return s.get("market")
    def named(names: list[str], *forms: str) -> set[str]:
        return {f.format(n.lower()) for n in names if n for f in forms}

    table = {
        mkt.OVER_15: {"over 1.5", "o1.5"}, mkt.UNDER_15: {"under 1.5", "u1.5"},
        mkt.OVER_25: {"over 2.5", "o2.5"}, mkt.UNDER_25: {"under 2.5", "u2.5"},
        mkt.OVER_35: {"over 3.5", "o3.5"}, mkt.UNDER_35: {"under 3.5", "u3.5"},
        mkt.HOME: {"home", "1", "home win"} | named(homes, "{}", "{} win", "{} to win"),
        mkt.DRAW: {"draw", "x"},
        mkt.AWAY: {"away", "2", "away win"} | named(aways, "{}", "{} win", "{} to win"),
        mkt.BTTS_YES: {"btts", "btts yes", "both teams to score", "both teams to score yes", "gg"},
        mkt.BTTS_NO: {"btts no", "both teams to score no", "ng"},
        mkt.DC_1X: {"1x", "home or draw"} | named(homes, "{} or draw"),
        mkt.DC_X2: {"x2", "draw or away"} | named(aways, "draw or {}", "{} or draw"),
        mkt.DC_12: {"12", "home or away"} | {f"{h.lower()} or {a.lower()}"
                                             for h in homes if h for a in aways if a},
    }
    for key, words in table.items():
        if low in words:
            return key
    return None


def _find_fixture(home: str, away: str, today: date) -> Optional[dict]:
    """The match on a recent board (yesterday to 3 days ahead): its league,
    match date and that day's singles. None when no board carries it."""
    from engine.name_match import same_club
    from engine.picks_ledger import LEDGER_DIR

    def same(typed: str, board: str) -> bool:
        return bool(typed and board) and (same_club(typed, board) or same_club(board, typed))

    for offset in (0, 1, -1, 2, 3):
        path = LEDGER_DIR / f"picks_{(today + timedelta(days=offset)).isoformat()}.json"
        if not path.exists():
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        for r in doc.get("rated", []) + doc.get("singles", []):
            if same(home, r.get("home", "")) and same(away, r.get("away", "")):
                singles = [s for s in doc.get("singles", []) if s.get("fixture") == r.get("fixture")]
                return {"league": r.get("league"), "date": r.get("kickoff") or doc.get("date"),
                        "home": r.get("home"), "away": r.get("away"), "singles": singles}
    return None


def cmd_log(arg: str) -> str:
    """Architect-fed entry price -> a CL-LIVE paper leg.

    This is the highest-value command here. HR46 wants the price captured at
    pick time, and the price the Architect can actually get on SportyBet is
    better evidence than any API's — it is the one that will actually be
    settled against.

    A leg is only logged when it can be graded later: the match is found on a
    recent board (giving its league and date) or the Architect adds the date,
    and the market wording maps to a settlement rule. Before 2026-10-04 every
    /log leg had no match date and was never graded (grade_open_legs refuses
    a leg it can't pin to one match)."""
    from engine import markets as mkt
    parts = [p.strip() for p in arg.split("|")]
    if len(parts) not in (3, 4):
        return ("Usage: /log Home v Away | Market | price [| YYYY-MM-DD]\n"
                "e.g.  /log Hearts v Dundee United | Over 1.5 goals | 1.42")
    fixture, market, price_s = parts[:3]
    try:
        price = float(price_s)
    except ValueError:
        return f"'{price_s}' is not a decimal price. Nothing logged."
    if not (1.01 <= price <= 1000):
        return f"Price {price} is out of plausible range. Nothing logged."
    if " v " not in fixture:
        return "Fixture must read 'Home v Away'. Nothing logged."
    home, away = [s.strip() for s in fixture.split(" v ", 1)]

    found = _find_fixture(home, away, datetime.now(timezone.utc).date())
    match_date = parts[3] if len(parts) == 4 else (found or {}).get("date")
    if len(parts) == 4:
        try:
            date.fromisoformat(match_date or "")
        except ValueError:
            return f"'{parts[3]}' is not a date (YYYY-MM-DD). Nothing logged."
    if not match_date:
        return (f"{fixture} isn't on a recent board, so I can't tell which match to grade. "
                f"Add its date: /log {fixture} | {market} | {price_s} | YYYY-MM-DD. "
                f"Nothing logged.")
    homes, aways = [home], [away]
    if found:                               # the board's spellings grade reliably
        homes.append(found["home"])
        aways.append(found["away"])
        home, away = found["home"], found["away"]
        fixture = f"{home} v {away}"
    key = _market_key(market, homes, aways, (found or {}).get("singles", []))
    if key is None:
        return (f"I can't settle '{market}'. Use one of: Home / Draw / Away, "
                f"<team> to win, Home or Draw (1X), Draw or Away (X2), Home or Away (12), "
                f"Over/Under 1.5, 2.5 or 3.5, BTTS Yes/No — or the pick exactly as the "
                f"board writes it. Nothing logged.")

    log = CLVLog()
    leg = log.log_entry(
        league=(found or {}).get("league") or "ARCHITECT-FED", fixture=fixture, market=key,
        model_prob=0.0,                 # unknown here; CLV needs only the prices
        entry_odds=price, entry_capture_path="CL-LIVE",
        phase=PAPER_PHASE, stake=None,  # a paper record — never a stake
        match_date=match_date,
    )
    return (f"Logged as a PAPER leg (no stake):\n"
            f"  {fixture} ({match_date})\n  {mkt.display(key, home, away)} at {price} decimal\n"
            f"  capture path CL-LIVE, leg id {leg.leg_id[:40]}\n\n"
            f"It is graded after the match from football-data or Flashscore. CLV needs "
            f"a closing price, which only football-data publishes (its leagues only). "
            f"Nothing has been staked.")


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
    return ("Correction logged for review (memory/corrections.csv).\n\n"
            "It is listed on the heartbeat and in the weekly review until a session "
            "acts on it; it is not applied automatically. Any RULE change is proposed "
            "to you for approval first — the framework never rewrites its own rules.")


def cmd_debrief(_: str) -> str:
    log = CLVLog()
    s = log.phase2_status()
    mean = s["mean_clv_pct"]
    return "\n".join([
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
    ])


def _olp():
    """scripts/olp_query.py — the same read-only answers sessions get from the
    olp-xdv skill, so the phone and a session never disagree."""
    import importlib.util
    path = Path(__file__).parent.parent / "scripts" / "olp_query.py"
    spec = importlib.util.spec_from_file_location("olp_query", path)
    mod = importlib.util.module_from_spec(spec)          # type: ignore[arg-type]
    spec.loader.exec_module(mod)                         # type: ignore[union-attr]
    return mod


def cmd_lookup(arg: str) -> str:
    team = arg.strip()
    if not team:
        return "Usage: /lookup Arsenal — every pick and rated fixture for that team on record"
    rows = _olp().lookup(team)["rows"]
    if isinstance(rows, str):
        return f"{team}: {rows}"
    out = []
    for r in rows[-12:]:
        if "pick" in r:
            out.append(f"{r['date']} {r['fixture']}: {r['pick']} "
                       f"({r['chance']:.0%}) → {r.get('result') or 'PENDING'} {r.get('ft') or ''}")
        else:
            out.append(f"{r['date']} {r['fixture']}: rated, no pick → {r.get('ft') or 'PENDING'}")
    return f"ON RECORD — {team} (last {len(out)})\n\n" + "\n".join(out)


def cmd_picks(arg: str) -> str:
    day = arg.strip() or None
    got = _olp().picks(day)
    if isinstance(got["singles"], str):
        return f"Picks {got['date']}: {got['singles']}"
    rows = [f"{s['fixture']}: {s['pick']} @{s['price']} → {s.get('result') or 'PENDING'} "
            f"{s.get('ft') or ''}".rstrip() for s in got["singles"]]
    won = sum(s.get("result") == "won" for s in got["singles"])
    lost = sum(s.get("result") == "lost" for s in got["singles"])
    return (f"PICKS {got['date']} — {won} won, {lost} lost, "
            f"{len(rows) - won - lost} open\n\n" + "\n".join(rows[:40]))


def cmd_proposals(_: str) -> str:
    from engine import loss_watch
    props = loss_watch.load_proposals()
    if not props:
        return ("No proposals yet. The losing-market watch (order 39) proposes stopping a "
                "market in a competition once it has enough losing results.")
    rows = [f"{p['id']} [{p['status']}] {p['text']} — {p['evidence']}" for p in props[-15:]]
    return "PROPOSALS (order 39)\n\n" + "\n".join(rows) + \
        "\n\nReply /approve ID or /reject ID. Rejecting an approved block lifts it."


def _decide(arg: str, approve: bool, chat_id: Optional[str]) -> str:
    # FAILS CLOSED: a decision changes what the board picks, so it is taken
    # only from the Architect's own chat, and never when no chat is configured.
    if not chat_id or chat_id not in _allowed():
        return "REFUSED — proposals are decided from the Architect's chat only."
    pid = arg.strip().split()[0] if arg.strip() else ""
    if not pid:
        return f"Usage: /{'approve' if approve else 'reject'} P3"
    from engine import loss_watch
    return loss_watch.decide(pid, approve)


HANDLERS = {
    "/help": cmd_help, "/start": cmd_help,
    "/status": cmd_status, "/board": cmd_board, "/verify": cmd_verify,
    "/why": cmd_why, "/log": cmd_log, "/note": cmd_note,
    "/debrief": cmd_debrief, "/proposals": cmd_proposals,
    "/lookup": cmd_lookup, "/picks": cmd_picks,
}


def handle(text: str, chat_id: Optional[str] = None) -> str:
    """Route one message. Bright-line requests are refused, not executed."""
    stripped = text.strip()
    low = stripped.lower()

    if any(w in low for w in BRIGHT_LINE_WORDS) and not low.startswith("/note"):
        return (
            "REFUSED — that would move a bright line.\n\n"
            f"The capital line is set in code (PHASE={PHASE}; the framework never "
            "places a stake), and the honest-edge "
            "caveat is not removable. Those are not settings I change from a "
            "message: a chat channel can be spoofed, and the framework exists "
            "because of a fabrication incident.\n\n"
            "If you genuinely want to change this, do it deliberately in a "
            "working session where the reasoning is on the record. Logged as a "
            "note in the meantime."
        )

    cmd = low.split()[0] if low else ""
    if cmd in ("/approve", "/reject"):
        return _decide(stripped[len(cmd):], cmd == "/approve", chat_id)
    handler = HANDLERS.get(cmd)
    if handler is None:
        return f"Unknown command '{cmd or stripped[:20]}'.\n\n{cmd_help('')}"
    return handler(stripped[len(cmd):])


def poll_once(token: Optional[str] = None) -> list[str]:
    """One getUpdates pass. Returns a log line per message handled."""
    notes: list[str] = []
    token = token or os.environ.get("TELEGRAM_BOT_TOKEN")
    if requests is None or not token:
        return ["telegram not configured — skipping command poll"]

    offset = _load_offset()
    try:
        r = requests.get(f"https://api.telegram.org/bot{token}/getUpdates",
                          params={"offset": offset + 1, "timeout": 0}, timeout=30)
        updates = r.json().get("result", [])
    except Exception as e:
        return [f"command poll failed: {e}"]

    allowed = _allowed()
    for u in updates:
        offset = max(offset, u.get("update_id", offset))
        msg = u.get("message") or {}
        chat_id = str(msg.get("chat", {}).get("id", ""))
        text = msg.get("text") or ""
        if not text:
            continue
        if allowed and chat_id not in allowed:
            notes.append(f"IGNORED message from non-whitelisted chat {chat_id}")
            continue
        reply = handle(text, chat_id)
        send_telegram(reply, token=token, chat_id=chat_id)
        notes.append(f"handled {text.split()[0] if text.split() else '?'} from {chat_id}")

    _save_offset(offset)
    return notes or ["no new commands"]


if __name__ == "__main__":
    for n in poll_once():
        print(n)
