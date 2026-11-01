"""
BOT BET GRADER — every bet the three bots placed, graded leg by leg, and one
daily report to the Architect's own chat.

Architect 2026-11-01 (improvement plan point 4): "grade EVERY bet all three bots
placed, and send one daily report". Grading is by GAME + MARKET + SIDE, never by
booking code: a SportyBet code is only opened (SportyBet's public share API) to
read its legs, and each leg is settled on the framework's own graded results in
data/universe with engine/full_markets (football), engine/half (first half) or
engine/nba_markets (basketball). So live-trimmed codes, MEGAs, the EDGE/VALUE
rule bets, steam and in-play bets and the BTTS-day singles all grade the same
way. Accas are graded leg by leg, then the slip.

When data/universe has no result for a leg, SportyBet's own final score of that
event is settled with the same rules ("sportybet score"), then SportyBet's own
settlement of the leg ("sportybet"), then, for an exchange single, the
exchange's settlement. Each leg records which source graded it.

Money:
  - SportyBet (naira, per account): stake from the bot's ledger; payout = stake x
    the odds taken when every leg won (a void leg divides its price out).
  - Matchbook / Betfair (pounds): the bot's own settled profit is the money
    truth (it includes cash-out and lock exits); the grader adds the side's
    full-time result for the market + side tables.

Where it writes (grading and reporting only — never a stake, threshold or rule):
  - each bot repo: one file per bet day beside the bot's ledger
      sportybet-agent  ledger/sportybet/graded/<date>.json, ledger/sportybet2/graded/<date>.json
      matchbook-agent  ledger/graded/<date>.json
      betfair-agent    ledger/graded/<date>.json
    The bots never write these files, so the grader never races them.
  - the Architect's own Telegram chat (TELEGRAM_OWNER_CHAT_ID, else
    TELEGRAM_CHAT_ID; never a subscriber chat): the daily report on the first
    run at/after 23:00 UK, and on Sundays the weekly switch-on/off summary.

THIS REPO IS PUBLIC and so are its Actions logs: nothing here prints a stake, a
naira or pound figure, a code or a bet id. Bot checkouts live in .bots/ (git-
ignored), the decoded-code cache in data/cache/bot_grader/ (Actions cache).

    python monitor/bot_grader.py              grade + write back (+ report when due)
    python monitor/bot_grader.py --report     also send the report now
    python monitor/bot_grader.py --dry-run    grade and print counts; write nothing
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
import urllib.request
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import full_markets as fm  # noqa: E402
from engine import half  # noqa: E402

UK = ZoneInfo("Europe/London")
BOTS = Path(os.environ.get("BOT_LEDGERS_DIR") or ROOT / ".bots")
GRADED_DIR = ROOT / "data" / "universe"
PICKS_DIR = ROOT / "output" / "picks"
CACHE = ROOT / "data" / "cache" / "bot_grader" / "codes.json"
NOTE_DIR = ROOT / "data" / "universe" / "notes"
STUDY = ROOT / "backtest" / "MODEL_SIDES_STUDY.md"
WINDOW = 30                       # days graded and reported
REPORT_HOUR = 23                  # UK: the daily report on the first run at/after this
# The pound total converts naira at this stated rate (Architect 2026-11-01: both currencies plus a
# pound total). A repo variable NGN_PER_GBP overrides it; the report always says which rate it used.
NGN_PER_GBP = float(os.environ.get("NGN_PER_GBP") or 2000)
SPORTYBET_ACCOUNTS = ("sportybet", "sportybet2")

_SHARE = "https://www.sportybet.com/api/ng/orders/share/{code}"
_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
       "Accept": "application/json", "Referer": "https://www.sportybet.com/ng/"}


# ── names and games ──────────────────────────────────────────────────────────
def _n(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return " ".join(w for w in s.split() if w not in {"fc", "cf", "sc", "afc", "the", "club"})


def _alike(a: str, b: str) -> float:
    a, b = _n(a), _n(b)
    if not a or not b:
        return 0.0
    if a == b or (len(a) >= 4 and a in b) or (len(b) >= 4 and b in a):
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


class Games:
    """data/universe's graded games of the window, by SportyBet event id and by kick-off day."""

    def __init__(self, since: str, folder: Path | None = None):
        folder = folder or GRADED_DIR
        self.by_id: dict[str, dict] = {}
        self.by_day: dict[str, list[dict]] = defaultdict(list)
        for p in sorted(folder.glob("graded_*.jsonl*")):
            m = re.search(r"graded_(\d{4}-\d{2}(?:-\d{2})?)", p.name)
            if m and m.group(1)[:10] < since[: len(m.group(1)[:10])]:
                continue
            if p.suffix == ".gz":
                with gzip.open(p, "rt", encoding="utf-8") as f:
                    text = f.read()
            else:
                text = p.read_text(encoding="utf-8")
            for line in text.splitlines():
                if not line.strip():
                    continue
                g = json.loads(line)
                if not g.get("result"):
                    continue
                self.by_id[g["id"]] = g
                self.by_day[(g.get("ko") or "")[:10]].append(g)

    def find(self, leg: dict) -> dict | None:
        g = self.by_id.get(leg.get("event_id") or "")
        if g or not (leg.get("home") and leg.get("away") and leg.get("ko")):
            return g
        d0 = date.fromisoformat(leg["ko"][:10])
        best, score = None, 0.0
        for off in (0, -1, 1):
            for c in self.by_day.get((d0 + timedelta(days=off)).isoformat(), []):
                if leg.get("sport") and c.get("sport") != leg["sport"]:
                    continue
                s = _alike(leg["home"], c["home"]) + _alike(leg["away"], c["away"])
                if s > score:
                    best, score = c, s
        return best if score >= 1.5 else None


# ── settling one leg ─────────────────────────────────────────────────────────
def settle_on(key: str, h: int, a: int, ht: list | None = None) -> str | None:
    """'won' / 'lost' / 'void' for a ladder key on a final score, None if no rule knows it."""
    if key.startswith("NBA:"):
        from engine import nba_markets as nm
        parts = key[4:].rsplit("|", 1)
        mid, spec = (parts[0].split("|", 1) + [""])[:2]
        r = nm.settle_any(mid, spec, parts[1] if len(parts) > 1 else "", h, a, None, None)
        return None if r is None else ("won" if r else "lost")
    pk = fm.parse_key(key)
    if not pk:
        return None
    if half.is_first_half(key):
        return half.settle(key, *(ht or [None, None])[:2])
    rule = fm.rule_for(*pk)
    if rule is None:
        return None
    res = rule(h, a)
    return "void" if res == "push" else ("won" if res == "win" else "lost")


def _sb_settled(sb: dict | None) -> str | None:
    """SportyBet's own settlement of a decoded leg (its market status 3 = settled; the
    event status is not needed: cup games end as 'AP' / 'AET', abandoned ones are refunded)."""
    if not sb or sb.get("mstatus") not in (3, "3"):
        return None
    if float(sb.get("refund") or 0) >= 1:
        return "void"
    return "won" if int(sb.get("win") or 0) == 1 else "lost"


def _sb_score(sb: dict | None) -> tuple[int, int] | None:
    if not sb or not sb.get("ended") or not re.fullmatch(r"\d+:\d+", sb.get("score") or ""):
        return None
    h, a = sb["score"].split(":")
    return int(h), int(a)


def grade_leg(leg: dict, games: Games, tally: dict) -> dict:
    """The leg with result ('won' / 'lost' / 'void' / None) and source filled in."""
    out = dict(leg)
    key = leg.get("key") or ""
    g = games.find(leg) if key else None
    if g is not None:
        out["game"] = g["id"]               # one id per match across the bots (point 6 exposure line)
    res = None
    if g is not None:
        r = g["result"]
        if not r.get("after_90"):          # extra-time games: SportyBet settles regular time
            res = settle_on(key, r["h"], r["a"], r.get("ht"))
    sb_res = _sb_settled(leg.get("sb"))
    if res is not None:
        if sb_res is not None and sb_res != res:
            # SportyBet's settlement is what it paid: it decides the money, and the
            # report counts every such leg so a wrong rule or a wrong game is seen
            tally["disagree"] += 1
            out.update(result=sb_res, source="sportybet (universe said " + res + ")")
            return out
        out.update(result=res, source="universe")
        return out
    if sb_res is not None:
        out.update(result=sb_res, source="sportybet")
        return out
    sc = _sb_score(leg.get("sb"))
    if key and sc and not half.is_first_half(key):
        res = settle_on(key, *sc)
        if res is not None:
            out.update(result=res, source="sportybet score")
            return out
    if leg.get("own"):
        out.update(result=leg["own"], source="exchange")
        return out
    out.update(result=None, source=("no market" if not key else "no game found" if g is None
                                    else "rule unknown"))
    return out


def grade_slip(bet: dict, games: Games, tally: dict, now: datetime | None = None) -> dict:
    """Legs graded, then the slip: result, payout, profit (None while any leg is open)."""
    legs = [grade_leg(x, games, tally) for x in bet.get("legs") or []]
    bet = {**bet, "legs": legs}
    rs = [x["result"] for x in legs]
    if not legs:
        bet.update(result=None, why="legs unknown")
    elif "lost" in rs:
        bet.update(result="lost")
    elif None in rs:
        bet.update(result=None, why=_why_open([x for x in legs if x["result"] is None], now))
    elif all(r == "void" for r in rs):
        bet.update(result="void")
    else:
        bet.update(result="won")
    if bet.get("own_pnl") is not None and bet.get("own_settled"):
        # exchanges: the bot's own settled money (cash-outs and locks included)
        bet["profit"] = round(float(bet["own_pnl"]), 2)
        bet["payout"] = round(bet["stake"] + bet["profit"], 2)
    elif bet["result"] in ("won", "lost", "void"):
        odds = float(bet.get("odds") or 0)
        for x in legs:
            if x["result"] == "void" and x.get("price"):
                odds /= float(x["price"])
        pay = 0.0 if bet["result"] == "lost" else (bet["stake"] if bet["result"] == "void"
                                                    else bet["stake"] * max(odds, 1.0))
        bet["payout"] = round(pay, 2)
        bet["profit"] = round(pay - bet["stake"], 2)
    else:
        bet["payout"] = bet["profit"] = None
    return bet


def _why_open(legs: list[dict], now: datetime | None) -> str:
    """'not played yet' while a leg's game is under 4 hours past kick-off (results land
    ~3 h after), else the first open leg's reason."""
    now = now or datetime.now(UTC)
    for x in legs:
        try:
            ko = datetime.fromisoformat(str(x.get("ko") or "").replace("Z", "+00:00"))
        except ValueError:
            continue
        if ko.tzinfo and ko > now - timedelta(hours=4):
            return "not played yet"
    return legs[0]["source"]


# ── SportyBet codes -> legs (share API, cached) ──────────────────────────────
def load_cache(path: Path | None = None) -> dict:
    path = path or CACHE
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_cache(cache: dict, path: Path | None = None) -> None:
    path = path or CACHE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, separators=(",", ":")), encoding="utf-8")


def _fetch_code(code: str) -> dict | None:
    req = urllib.request.Request(_SHARE.format(code=code), headers=_UA)  # noqa: S310 (fixed https host)
    with urllib.request.urlopen(req, timeout=20) as r:  # noqa: S310
        d = json.loads(r.read().decode("utf-8"))
    return d.get("data") if d.get("bizCode") == 10000 else None


def legs_from_share(data: dict) -> list[dict]:
    legs = []
    for o in data.get("outcomes") or []:
        nba = (o.get("sport") or {}).get("id") == "sr:sport:2"
        ko = datetime.fromtimestamp(int(o.get("estimateStartTime") or 0) / 1000, UTC)
        for m in o.get("markets") or []:
            for oc in m.get("outcomes") or []:
                legs.append({
                    "event_id": o.get("eventId"), "home": o.get("homeTeamName"),
                    "away": o.get("awayTeamName"), "ko": ko.strftime("%Y-%m-%dT%H:%MZ"),
                    "sport": "basketball" if nba else "football",
                    "key": f"{'NBA' if nba else 'SB'}:{m.get('id')}|{m.get('specifier') or ''}|{oc.get('desc')}",
                    "price": float(oc.get("odds") or 0) or None,
                    "sb": {"ended": o.get("matchStatus") == "Ended", "mstatus": m.get("status"),
                           "win": oc.get("isWinning"), "refund": oc.get("refundFactor"),
                           "score": o.get("setScore")},
                })
    return legs


def code_legs(code: str, cache: dict, fetch=None) -> list[dict] | None:
    """A code's legs. Cached once SportyBet has settled every leg (nothing left to change)."""
    fetch = fetch or _fetch_code
    c = cache.get(code)
    if c and c.get("final"):
        return c["legs"]
    try:
        data = fetch(code)
    except Exception:  # noqa: BLE001 — SportyBet down: use what the cache has
        data = None
    if not data:
        return c["legs"] if c else None
    legs = legs_from_share(data)
    cache[code] = {"legs": legs, "final": bool(legs) and all(x["sb"]["mstatus"] in (3, "3") for x in legs),
                   "at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%MZ")}
    return legs


# ── reading the bots' ledgers ────────────────────────────────────────────────
def _read(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _rows(d) -> list[dict]:
    b = (d or {}).get("bets") if isinstance(d, dict) else d
    return list(b.values()) if isinstance(b, dict) else list(b or [])


def sportybet_bets(repo: Path, since: str, cache: dict, board: dict | None = None) -> list[dict]:
    """Every placed SportyBet bet of both accounts. Day files before 29 Oct carry no
    section: it comes from the placer's placed_<day>.json, else the board's slip."""
    out: dict[tuple, dict] = {}
    board = board or {}
    for acct in SPORTYBET_ACCOUNTS:
        folder = repo / "ledger" / acct
        for p in sorted(folder.glob("20??-??-??.json")):
            day = p.stem
            if day < since:
                continue
            placed = {(x.get("code") or "").upper(): x.get("section")
                      for x in _rows(_read(folder / f"placed_{day}.json"))}
            day_led = _read(p) or {}
            for b in list(_rows(day_led)) + [dict(t, section="survivor top-up")
                                             for t in (day_led.get("topups") or {}).values()]:
                if b.get("status") != "placed" or not b.get("code"):
                    continue
                code = b["code"].upper()
                sec = next((x for x in (b.get("section"), placed.get(code), board.get(code))
                            if x and x != "?"), "unlabelled")
                out.setdefault((acct, b.get("bet_id") or b["code"]), {
                    "bot": acct, "cur": "NGN", "date": day, "id": b.get("bet_id") or b["code"],
                    "code": b["code"], "kind": sec, "stake": float(b.get("stake") or 0),
                    "odds": float(b.get("odds") or 0), "paper": False})
        for sub, label in (("steam", "steam"), ("rules", None), ("inplay", "inplay")):
            for b in _rows(_read(folder / sub / "ledger.json")):
                if b.get("status") != "placed" or not b.get("code"):
                    continue
                day = (b.get("at") or "")[:10]
                if day < since:
                    continue
                kind = label or f"rule {b.get('rule') or '?'}"
                out.setdefault((acct, b.get("bet_id") or b["code"]), {
                    "bot": acct, "cur": "NGN", "date": day, "id": b.get("bet_id") or b["code"],
                    "code": b["code"], "kind": kind, "stake": float(b.get("stake") or 0),
                    "odds": float(b.get("odds") or 0), "paper": False})
            # ON PAPER since 2026-11-01 (sportybet-agent #60): the rule's pick with the stake it would have had
            for n, b in enumerate((_read(folder / sub / "ledger.json") or {}).get("paper") or []):
                day = (b.get("at") or "")[:10]
                if day < since:
                    continue
                name = label or f"rule {b.get('rule') or '?'}"
                row = {"bot": acct, "cur": "NGN", "date": day, "id": f"paper-{sub}-{n}", "kind": f"{name} (paper)",
                       "stake": float(b.get("stake") or 0), "odds": float(b.get("odds") or 0), "paper": True}
                if b.get("code"):
                    row["code"] = b["code"]
                else:                               # steam: SEL:<event>|<market>|<specifier>|<outcome id>
                    sel = (b.get("key") or "").removeprefix("SEL:").split("|")
                    key = f"SB:{sel[1]}|{sel[2]}|{b.get('outcome')}" if len(sel) == 4 and b.get("outcome") else None
                    row["legs"] = [{"event_id": b.get("sb_event") or sel[0], "ko": b.get("start"), "key": key}]
                out[(acct, row["id"])] = row
    bets = list(out.values())
    for b in bets:
        if "legs" not in b:
            b["legs"] = code_legs(b["code"], cache) or []
    return bets


def _mb_key(r: dict) -> tuple[str | None, str, str, str]:
    """(ladder key, home, away, sport) for one Matchbook position."""
    ev = r.get("event_name") or ""
    nba = " at " in ev and " vs " not in ev
    if nba:
        away, _, home = ev.partition(" at ")
    else:
        home, _, away = ev.partition(" vs ")
    sport = "basketball" if nba else "football"
    fk = r.get("fw_key") or ""
    for tag in ("|SB:", "|NBA:"):
        if tag in fk:
            return fk[fk.index(tag) + 1:], home, away, sport
    if (r.get("vt_market") or "").startswith(("SB:", "NBA:")):
        return r["vt_market"], home, away, sport
    mk, run = r.get("market_name") or "", (r.get("runner_name") or "").strip()
    pre = "NBA" if nba else "SB"
    if mk in ("Match Odds", "Moneyline"):
        if run.lower() == "draw":
            return f"{pre}:1||Draw", home, away, sport
        side = "Home" if _alike(run, home) >= _alike(run, away) else "Away"
        return (f"NBA:219||{side}" if nba else f"SB:1||{side}"), home, away, sport
    m = re.fullmatch(r"(OVER|UNDER)\s+([\d.]+)", run.upper())
    if mk == "Total" and m:
        word, line = m.group(1).title(), m.group(2)
        return f"{'NBA:225' if nba else 'SB:18'}|total={line}|{word} {line}", home, away, sport
    m = re.fullmatch(r"(.+?)\s+([+-][\d.]+)", run)
    if mk == "Handicap" and m and not nba:
        line = float(m.group(2))
        if _alike(m.group(1), home) >= _alike(m.group(1), away):
            return f"SB:16|hcp={line:g}|Home ({m.group(2)})", home, away, sport
        return f"SB:16|hcp={-line:g}|Away ({m.group(2)})", home, away, sport
    return None, home, away, sport


def matchbook_bets(repo: Path, since: str) -> list[dict]:
    out = []
    path = repo / "ledger" / "ledger.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    for line in lines:
        try:
            r = json.loads(line)
        except ValueError:
            continue
        ko = r.get("start") or r.get("opened_at") or ""
        day = _uk_day(ko)
        if day < since or not r.get("pos_id"):
            continue
        key, home, away, sport = _mb_key(r)
        st = (r.get("status") or "").upper()
        own = {"WON": "won", "LOST": "lost", "PUSH": "void", "VOID": "void"}.get(st)
        out.append({
            "bot": "matchbook", "cur": "GBP", "date": day, "id": r["pos_id"],
            "kind": r.get("source") or "?", "stake": float(r.get("cost_gbp") or r.get("stake_asked_gbp") or 0),
            "odds": float(r.get("avg_odds") or r.get("odds_asked") or 0), "paper": False,
            "own_pnl": r.get("pnl_gbp"), "own_settled": own is not None and r.get("pnl_gbp") is not None,
            "legs": [{"home": home.strip(), "away": away.strip(), "ko": ko, "sport": sport,
                      "key": key, "own": own}],
        })
    # ON PAPER since 2026-11-01 (matchbook-agent #135): steam and in-play picks never placed
    for name in ("steam_paper.jsonl", "inplay_paper.jsonl"):
        path = repo / "ledger" / name
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines() if path.exists() else []):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            ko = r.get("start") or r.get("at") or ""
            day = _uk_day(ko)
            if day < since:
                continue
            key, home, away, sport = _mb_key(r)
            out.append({"bot": "matchbook", "cur": "GBP", "date": day, "id": f"{name}-{n}",
                        "kind": f"{r.get('source') or name.split('_')[0]} (paper)",
                        "stake": float(r.get("stake_gbp") or 1), "odds": float(r.get("odds") or 0), "paper": True,
                        "legs": [{"home": home.strip(), "away": away.strip(), "ko": ko, "sport": sport, "key": key}]})
    return out


def betfair_bets(repo: Path, since: str, cache: dict) -> list[dict]:
    out = []
    for p in sorted((repo / "ledger").glob("paper_20??-??-??.json")):
        d = _read(p) or {}
        for b in d.get("paper_rules") or []:     # ON PAPER since 2026-11-01 (betfair-agent #2): R4 value
            ko = b.get("kickoff_utc") or ""
            day = _uk_day(ko) if ko else p.stem[6:]
            if day < since:
                continue
            legs = (code_legs(b["code"].split("/")[0], cache) if b.get("code") else None) or []
            if len(legs) != 1:
                home, _, away = (b.get("fixture") or "").partition(" v ")
                legs = [{"home": home, "away": away, "ko": ko, "key": b.get("sb_market"),
                         "sport": "basketball" if b.get("sport") == "nba" else "football"}]
            out.append({"bot": "betfair", "cur": "GBP", "date": day, "id": f"paper-{b.get('code')}",
                        "kind": f"{b.get('section') or '?'} {b.get('rule') or ''} (paper)".strip(),
                        "stake": float(b.get("stake") or 0), "odds": float(b.get("price") or 0),
                        "paper": True, "legs": legs})
        for b in _rows(d):
            if b.get("mode") != "live" or not b.get("bet_id"):   # paper rows are the bot's own study
                continue
            ko = b.get("kickoff_utc") or ""
            day = _uk_day(ko) if ko else p.stem[6:]
            if day < since:
                continue
            st = (b.get("result") or "").upper()
            own = {"WON": "won", "LOST": "lost", "VOIDED": "void", "VOID": "void"}.get(st)
            legs = (code_legs(b["code"].split("/")[0], cache) if b.get("code") else None) or []
            if len(legs) != 1:
                home, _, away = (b.get("fixture") or "").partition(" v ")
                legs = [{"home": home, "away": away, "ko": ko, "key": b.get("sb_market"),
                         "sport": "basketball" if b.get("sport") == "nba" else "football"}]
            legs[0] = {**legs[0], "own": own}
            out.append({
                "bot": "betfair", "cur": "GBP", "date": day, "id": str(b["bet_id"]),
                "kind": f"{b.get('section') or '?'} {b.get('rule') or ''}".strip(),
                "stake": float(b.get("size_matched") or b.get("stake") or 0),
                "odds": float(b.get("avg_price") or b.get("price") or 0), "paper": False,
                "own_pnl": b.get("pnl"), "own_settled": st in ("WON", "LOST", "GREEN", "VOIDED", "VOID")
                and b.get("pnl") is not None, "legs": legs})
    return out


def board_bets(since: str, folder: Path | None = None) -> list[dict]:
    """The board's slips as paper (1 unit each): every section with codes, so new
    slip types (Short-3 and others) are counted the day they appear."""
    out = []
    for p in sorted((folder or PICKS_DIR).glob("picks_20??-??-??.json")):
        day = p.stem[6:]
        if day < since:
            continue
        picks = _read(p) or {}
        for sec, items in picks.items():
            if not isinstance(items, list) or sec.endswith("_dropped") or sec in ("rated", "replaced"):
                continue
            for x in items:
                if not isinstance(x, dict) or not x.get("code"):
                    continue
                src = x.get("leg_detail") or x.get("alt_legs") or ([x] if x.get("market") else [])
                legs = [{"event_id": y.get("sb_event_id"), "home": y.get("home"), "away": y.get("away"),
                         "ko": y.get("kickoff_utc") or y.get("kickoff") or day, "key": y.get("market"),
                         "price": y.get("price"),
                         "sport": "basketball" if str(y.get("market") or "").startswith("NBA") else None}
                        for y in src]
                odds = x.get("odds") or x.get("price") or 0
                out.append({"bot": "board", "cur": "unit", "date": day, "id": x["code"], "kind": sec,
                            "stake": 1.0, "odds": float(odds), "paper": True, "legs": legs})
    return out


def _uk_day(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(UK).date().isoformat()
    except ValueError:
        return iso[:10]


# ── writing back into each bot's ledger folder ───────────────────────────────
SIDECAR = {"sportybet": ("sportybet-agent", "ledger/sportybet/graded"),
           "sportybet2": ("sportybet-agent", "ledger/sportybet2/graded"),
           "matchbook": ("matchbook-agent", "ledger/graded"),
           "betfair": ("betfair-agent", "ledger/graded")}


def _slim(b: dict) -> dict:
    return {"kind": b["kind"], "stake": b["stake"], "odds": b["odds"], "result": b["result"],
            "payout": b.get("payout"), "profit": b.get("profit"), "why": b.get("why"),
            **({"code": b["code"]} if b.get("code") else {}),
            "legs": [{"event": f"{x.get('home')} v {x.get('away')}", "key": x.get("key"),
                      "result": x.get("result"), "source": x.get("source")} for x in b["legs"]]}


def write_back(graded: list[dict], now: datetime, root: Path | None = None) -> dict[str, int]:
    """One graded file per bot per bet day; rewritten only when a grade changed."""
    root = root or BOTS
    changed: dict[str, int] = defaultdict(int)
    groups: dict[tuple[str, str], dict] = defaultdict(dict)
    for b in graded:
        if b["bot"] in SIDECAR:
            groups[(b["bot"], b["date"])][b["id"]] = _slim(b)
    for (bot, day), bets in groups.items():
        repo, sub = SIDECAR[bot]
        path = root / repo / sub / f"{day}.json"
        old = _read(path) or {}
        if old.get("bets") == bets:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"date": day, "graded_at": now.strftime("%Y-%m-%dT%H:%MZ"),
                                    "by": "framework monitor/bot_grader.py", "bets": bets},
                                   indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        changed[repo] += 1
    return dict(changed)


def push_repos(changed: dict[str, int], now: datetime, root: Path | None = None) -> list[str]:
    """Commit and push ONLY the graded/ folders. The bots push their own ledger all day, so a
    rejected push re-bases by moving the index to the latest main (mixed reset: the bot's
    files are taken as they are on main, never from this older checkout) and re-adding the
    graded folders; nothing the bot wrote can be reverted."""
    root = root or BOTS
    notes = []
    for repo in changed:
        cwd = root / repo
        paths = [sub for r, sub in SIDECAR.values() if r == repo]

        def git(*a: str, cwd: Path = cwd) -> subprocess.CompletedProcess:
            return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True)  # noqa: S603,S607

        def commit(paths: list[str] = paths) -> bool:
            git("add", "--", *paths)
            if git("diff", "--staged", "--quiet").returncode == 0:
                return False
            git("-c", "user.name=olp-xdv-agent", "-c", "user.email=olp-xdv-agent@users.noreply.github.com",
                "commit", "-q", "-m", f"graded bets {now:%Y-%m-%d %H:%M} (framework bot_grader) [skip ci]")
            return True
        if not commit():
            continue
        ok = False
        for _ in range(5):
            if git("push", "-q", "origin", "HEAD:main").returncode == 0:
                ok = True
                break
            time.sleep(3)
            if git("fetch", "-q", "--depth=1", "origin", "main").returncode != 0:
                continue
            git("reset", "-q", "--mixed", "FETCH_HEAD")
            if not commit():          # main already holds these exact grades
                ok = True
                break
        notes.append(f"{repo} {'saved' if ok else 'NOT saved'}")
    return notes


# ── the report ───────────────────────────────────────────────────────────────
BOT_NAMES = {"matchbook": "Matchbook", "betfair": "Betfair",
             "sportybet": "SportyBet acct 1", "sportybet2": "SportyBet acct 2"}


def _money(x: float, cur: str) -> str:
    sign = "+" if x > 0 else "-" if x < 0 else ""
    return f"{sign}£{abs(x):,.2f}" if cur == "GBP" else f"{sign}NGN {abs(x):,.0f}"


def _gbp(b: dict, field: str) -> float:
    v = float(b.get(field) or 0)
    return v / NGN_PER_GBP if b["cur"] == "NGN" else v


def _days(today: str, n: int) -> str:
    return (date.fromisoformat(today) - timedelta(days=n - 1)).isoformat()


def _bot_lines(bets: list[dict], since: str, today: str) -> list[str]:
    lines, total = [], 0.0
    for bot in ("matchbook", "betfair", "sportybet", "sportybet2"):
        bs = [b for b in bets if b["bot"] == bot and not b["paper"] and since <= b["date"] <= today
              and b.get("profit") is not None]
        if not bs:
            continue
        cur = bs[0]["cur"]
        st = sum(b["stake"] for b in bs)
        back = sum(b["payout"] for b in bs)
        won = sum(1 for b in bs if b["result"] == "won")
        lines.append(f"{BOT_NAMES[bot]}: {len(bs)} bets ({won} won), staked {_money(st, cur).lstrip('+')}, "
                     f"back {_money(back, cur).lstrip('+')}, {_money(back - st, cur)}")
        total += sum(_gbp(b, "profit") for b in bs)
    lines.append(f"Total: {_money(total, 'GBP')} (naira at {NGN_PER_GBP:,.0f} per £)")
    return lines


def _label(key: str | None) -> tuple[str, str]:
    if not key:
        return "?", "?"
    if key.startswith("NBA:"):
        mid, _, rest = key[4:].partition("|")
        side = rest.rsplit("|", 1)[-1]
        return f"NBA {({'219': 'Winner', '223': 'Handicap', '225': 'Total', '68': '1st half total'}).get(mid, mid)}", \
            re.sub(r"[\d.+-]+", "N", side).strip()
    pk = fm.parse_key(key)
    if not pk:
        return "?", "?"
    names = {**fm._NAMES, 19: "Home Team Goals", 20: "Away Team Goals", 60: "1st half 1X2",
             63: "1st half DC", 64: "1st half DNB"}
    return names.get(pk[0], f"market {pk[0]}"), re.sub(r"\d+(\.\d+)?", "N", pk[2])


def _table(groups: dict, min_n: int = 3, top: int = 8) -> list[str]:
    rows = []
    for name, bs in groups.items():
        st = sum(_gbp(b, "stake") for b in bs)
        pr = sum(_gbp(b, "profit") for b in bs)
        if len(bs) >= min_n and st > 0:
            rows.append((pr / st, name, len(bs), sum(b["result"] == "won" for b in bs), pr))
    rows.sort(reverse=True)
    pick = rows if len(rows) <= 2 * top else rows[:top] + rows[-top:]
    return [f"{n}: {k} bets, {w} won, {_money(p, 'GBP')} ({r:+.0%})" for r, n, k, w, p in pick]


def market_side(bets: list[dict]) -> dict:
    g: dict[str, list[dict]] = defaultdict(list)
    for b in bets:
        if not b["paper"] and len(b["legs"]) == 1 and b.get("profit") is not None:
            m, s = _label(b["legs"][0].get("key"))
            g[f"{m} {s}"].append(b)
    return g


def slip_types(bets: list[dict]) -> dict:
    g: dict[str, list[dict]] = defaultdict(list)
    for b in bets:
        if b.get("profit") is not None:
            g[("paper " if b["paper"] else "") + (b["kind"] if b["bot"] == "board" else f"{b['bot']} {b['kind']}")].append(b)
    return g


def _paper_lines(groups: dict, board: bool = True) -> list[str]:
    """Board slips in units (1 each); the bots' papered rules in £ at the stakes they would have had."""
    out = []
    for name, bs in sorted(groups.items()):
        if not name.startswith("paper ") or (bs[0]["bot"] == "board") != board:
            continue
        won = sum(b["result"] == "won" for b in bs)
        if board:
            pr = sum(b["profit"] for b in bs)
            out.append(f"{name[6:]}: {len(bs)} slips, {won} won, {pr:+.2f} units ({pr / len(bs):+.0%})")
        else:
            st, pr = sum(_gbp(b, "stake") for b in bs), sum(_gbp(b, "profit") for b in bs)
            out.append(f"{name[6:]}: {len(bs)} bets, {won} won, {_money(pr, 'GBP')} ({pr / st if st else 0:+.0%})")
    return out


def study_lines(path: Path | None = None, min_n: int = 30) -> list[str]:
    """Best and worst 3 market sides of the model sides study (bar 50%)."""
    path = path or STUDY
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    part = text.split("## Bar 50%: by market and side", 1)[-1].split("\n## ", 1)[0] if text else ""
    rows = []
    for line in part.splitlines():
        c = [x.strip() for x in line.strip("|").split("|")]
        if len(c) >= 9 and c[2].isdigit() and int(c[2]) >= min_n and c[-1].endswith("%"):
            rows.append((float(c[-1].rstrip("%")), f"{c[0]} {c[1]}", int(c[2])))
    if not rows:
        return []
    rows.sort(reverse=True)
    best = ", ".join(f"{n} {r:+.1f}% ({k})" for r, n, k in rows[:3])
    worst = ", ".join(f"{n} {r:+.1f}% ({k})" for r, n, k in rows[-3:][::-1])
    return [f"Best: {best}", f"Worst: {worst}"]


def game_exposure(bets: list[dict], today: str) -> list[str]:
    """POINT 6 (the Architect, 2026-11-01 14:07): each game's total money across all bots today, in £.
    A game is the universe's match id, else SportyBet's event id, else the names; an acca's stake counts
    in full on every game it carries (all of it is lost if that game goes wrong)."""
    per: dict[str, dict] = defaultdict(lambda: {"gbp": 0.0, "bots": set(), "tickets": 0, "name": ""})
    for b in bets:
        if b["paper"] or b["date"] != today:
            continue
        for x in {(leg.get("game") or leg.get("event_id") or f"{_n(leg.get('home') or '')}|{_n(leg.get('away') or '')}"):
                  leg for leg in b["legs"]}.items():
            g = per[x[0]]
            g["gbp"] += _gbp(b, "stake")
            g["bots"].add(BOT_NAMES.get(b["bot"], b["bot"]).split(" acct")[0])
            g["tickets"] += 1
            g["name"] = g["name"] or f"{x[1].get('home')} v {x[1].get('away')}"
    if not per:
        return []
    top = sorted(per.values(), key=lambda g: -g["gbp"])[:3]
    three = sum(1 for g in per.values() if len(g["bots"]) >= 3)
    return ([f"Games bet today: {len(per)}; on all three bots: {three}. Most money on one game:"]
            + [f"{g['name']}: £{g['gbp']:.2f} on {g['tickets']} tickets ({', '.join(sorted(g['bots']))})"
               for g in top])


def ungraded_line(bets: list[dict], today: str) -> str:
    real = [b for b in bets if not b["paper"] and b["date"] <= today and b.get("profit") is None]
    why: dict[str, int] = defaultdict(int)
    for b in real:
        why[b.get("why") or "open"] += 1
    detail = ", ".join(f"{v} {k}" for k, v in sorted(why.items(), key=lambda kv: -kv[1]))
    return f"Could not grade yet: {len(real)} bets" + (f" ({detail})" if detail else "")


MISS = (("cash", ("cash ",)), ("no Betfair market", ("no betfair twin", "no market")),
        ("not on Betfair", ("no event", "not on betfair", "no runner", "not found")),
        ("price/liquidity", ("price", "only £", "no back")))


def betfair_coverage(day: str, root: Path | None = None) -> str | None:
    """Betfair's 'singles covered' line (the Architect, 2026-11-01 morning: "let's see if it's gonna cater
    for all the singles"), moved here from Betfair's 22:41 report when that went quiet (point 8): the
    SportyBet singles Betfair backed that day, and why the rest were missed."""
    d = _read((root or BOTS) / "betfair-agent" / "ledger" / f"paper_{day}.json")
    if not d:
        return None
    live = {b.get("code") for b in d.get("bets") or [] if b.get("mode") == "live" and "/" not in str(b.get("code"))}
    missed: dict[str, int] = defaultdict(int)
    for code, why in (d.get("skipped") or {}).items():
        if code in live or "/" in code:
            continue
        w = str(why).lower()
        missed[next((name for name, keys in MISS if any(k in w for k in keys)), "other")] += 1
    total = len(live) + sum(missed.values())
    if not total:
        return None
    why = ", ".join(f"{k} {v}" for k, v in sorted(missed.items(), key=lambda kv: -kv[1]))
    return f"Betfair singles covered: {len(live)} of {total}" + (f"; missed - {why}" if why else "")


def build_report(bets: list[dict], today: str, tally: dict) -> str:
    d7, d30 = _days(today, 7), _days(today, WINDOW)
    last30 = [b for b in bets if d30 <= b["date"] <= today]
    pretty = datetime.fromisoformat(today).strftime("%a %d %b")
    out = [f"BOT RESULTS {pretty} (graded by game, market and side)", "", "TODAY"]
    out += _bot_lines(bets, today, today)
    cov = betfair_coverage(today)
    if cov:
        out.append(cov)
    out += ["", "LAST 7 DAYS"] + _bot_lines(bets, d7, today)
    out += ["", "LAST 30 DAYS"] + _bot_lines(bets, d30, today)
    out += ["", "BY MARKET AND SIDE (singles, all bots, 30 days, £)"] + (_table(market_side(last30)) or ["none yet"])
    types = slip_types(last30)
    out += ["", "BY RULE AND SLIP TYPE (real money, 30 days, £)"]
    out += _table({k: v for k, v in types.items() if not k.startswith("paper ")}, min_n=1, top=99) or ["none yet"]
    out += ["", "BOARD SLIPS AS PAPER (1 unit each, 30 days)"] + (_paper_lines(types) or ["none yet"])
    rules_paper = _paper_lines(types, board=False)
    if rules_paper:
        out += ["", "RULES ON PAPER (stakes they would have had, 30 days, £)"] + rules_paper
    sl = study_lines()
    if sl:
        out += ["", "MODEL SIDES STUDY (paper singles, bar 50%)"] + sl
    ge = game_exposure(bets, today)
    if ge:
        out += ["", "MONEY PER GAME TODAY (all bots, £)"] + ge
    out += ["", ungraded_line(bets, today)]
    over = [b for b in last30 if b["cur"] == "GBP" and b.get("profit") is not None
            and b["profit"] < -b["stake"] - 0.01]
    if over:
        worst = min(over, key=lambda b: b["profit"])
        out.append(f"Money check: {len(over)} exchange bets lost more than their stake, "
                   f"{_money(sum(b['profit'] + b['stake'] for b in over), 'GBP')} beyond the stakes "
                   f"(worst {BOT_NAMES[worst['bot']]} {worst['kind']} {worst['date']}: "
                   f"£{worst['stake']:.2f} staked, {_money(worst['profit'], 'GBP')})")
    if tally.get("disagree"):
        out.append(f"Legs where SportyBet's settlement differs from the universe result: {tally['disagree']}")
    return "\n".join(out)


def weekly_summary(bets: list[dict], today: str) -> str:
    """Sunday: market sides and rules to switch on or off, from 30 days of grades.
    Suggestions only; nothing here changes what the bots stake."""
    last30 = [b for b in bets if _days(today, WINDOW) <= b["date"] <= today]
    off, on = [], []
    for name, bs in {**market_side(last30), **slip_types(last30)}.items():
        st = sum(_gbp(b, "stake") for b in bs)
        if len(bs) < 20 or st <= 0:
            continue
        roi = sum(_gbp(b, "profit") for b in bs) / st
        if name.startswith("paper "):
            if roi >= 0.05:
                on.append(f"{name[6:]} (paper): {len(bs)} slips, {roi:+.0%}")
        elif roi <= -0.10:
            off.append(f"{name}: {len(bs)} bets, {roi:+.0%}")
        elif roi >= 0.05:
            on.append(f"{name}: {len(bs)} bets, {roi:+.0%} (keep)")
    out = ["WEEKLY: WHAT THE DATA SAYS TO SWITCH (30 days, 20+ bets each; suggestions only)", "",
           "Switch off or cut:"] + (off or ["nothing at -10% or worse"])
    out += ["", "Switch on or keep:"] + (on or ["nothing at +5% or better"])
    return "\n".join(out)


def send(text: str) -> tuple[bool, list[str]]:
    owner = (os.environ.get("TELEGRAM_OWNER_CHAT_ID", "").strip()
             or os.environ.get("TELEGRAM_CHAT_ID", "").strip())
    if not owner or not os.environ.get("TELEGRAM_BOT_TOKEN"):
        return False, ["no Telegram settings here"]
    from output import notify
    return notify.send_telegram(text.replace("_", " ").replace("*", ""), chat_id=owner)  # the Architect only


def report_day(now: datetime) -> str | None:
    """The UK day the report is due for: today from 23:00 UK, or yesterday's if its
    23:00 run was missed (until 06:00 UK). None when not due or already sent."""
    uk = now.astimezone(UK)
    day = uk.date() if uk.hour >= REPORT_HOUR else (uk.date() - timedelta(days=1) if uk.hour < 6 else None)
    if day is None or (NOTE_DIR / f"bot-report-{day}.sent").exists():
        return None
    return day.isoformat()


# ── the run ──────────────────────────────────────────────────────────────────
def collect(today: str, cache: dict) -> list[dict]:
    since = _days(today, WINDOW + 2)
    bets: list[dict] = []
    paper = board_bets(since)
    if (BOTS / "sportybet-agent").exists():
        bets += sportybet_bets(BOTS / "sportybet-agent", since, cache,
                               {b["id"].upper(): b["kind"] for b in paper})
    if (BOTS / "matchbook-agent").exists():
        bets += matchbook_bets(BOTS / "matchbook-agent", since)
    if (BOTS / "betfair-agent").exists():
        bets += betfair_bets(BOTS / "betfair-agent", since, cache)
    return bets + paper


def run(now: datetime, force_report: bool = False, dry: bool = False) -> str:
    today = now.astimezone(UK).date().isoformat()
    cache = load_cache()
    bets = collect(today, cache)
    games = Games(_days(today, WINDOW + 3))
    tally: dict[str, int] = defaultdict(int)
    graded = [grade_slip(b, games, tally, now) for b in bets]
    real = [b for b in graded if not b["paper"]]
    done = sum(1 for b in real if b.get("profit") is not None)
    notes = [f"bots: {len(real)} bets read, {done} graded, {len(real) - done} open; "
             f"board: {sum(b['paper'] for b in graded)} paper slips"]
    save_cache(cache)
    if dry:
        return " · ".join(notes)
    changed = write_back(real, now)
    notes += push_repos(changed, now) if os.environ.get("GITHUB_ACTIONS") == "true" else \
        [f"graded files written for {', '.join(changed) or 'no repo'} (not pushed outside Actions)"]
    learning = ""
    try:      # the bots' paper challengers (bot-training step 5), for the report and self_improve
        from monitor import bot_learning
        rows = bot_learning.collect(BOTS)
        bot_learning.save(rows)
        learning = bot_learning.report_block(rows)
        notes.append(f"challengers read for {len(rows)} bot ledger(s)")
    except Exception as e:  # noqa: BLE001 — never blocks grading or the report
        notes.append(f"challengers not read: {type(e).__name__}")
    due = today if force_report else report_day(now)
    if due:
        text = build_report(graded, due, tally)
        if learning:
            text += "\n\n" + learning
        if datetime.fromisoformat(due).weekday() == 6:
            text += "\n\n" + weekly_summary(graded, due)
        ok, _ = send(text)
        if ok:
            NOTE_DIR.mkdir(parents=True, exist_ok=True)
            (NOTE_DIR / f"bot-report-{due}.sent").write_text(now.strftime("%Y-%m-%dT%H:%MZ"), encoding="utf-8")
        notes.append(f"daily bot report {'sent' if ok else 'NOT sent'}")
    return " · ".join(notes)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="grade every bot bet + the daily report")
    ap.add_argument("--report", action="store_true", help="send the report now")
    ap.add_argument("--dry-run", action="store_true", help="grade and print counts only")
    a = ap.parse_args(argv)
    print(f"[bot grader] {run(datetime.now(UTC), force_report=a.report, dry=a.dry_run)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
