"""
BOT BET GRADER — every bet the three bots placed, graded leg by leg, and one
daily report to the Architect's own chat.

Architect 2026-11-01 (improvement plan point 4): "grade EVERY bet all three bots
placed, and send one daily report". Grading is by GAME + MARKET + SIDE, never by
booking code: a SportyBet code is only opened (SportyBet's public share API) to
read its legs, and each leg is settled on the framework's own graded results in
data/universe with engine/full_markets (football), engine/half (first half) or
engine/nba_markets (basketball), and every rollout sport (ice hockey and the
multisport boards, framework#357: see "rollout sports" below) on the framework's
own graded board of that sport. So live-trimmed codes, MEGAs, the EDGE/VALUE
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
from engine import multisport as ms  # noqa: E402

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

    def __init__(self, since: str, folder: Path | None = None, rollout: RolloutGames | None = None):
        folder = folder or GRADED_DIR
        self.rollout = rollout if rollout is not None else RolloutGames(since)
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


# ── rollout sports (order 50; framework#357) ─────────────────────────────────
# Ice hockey and the nine multisport-board sports, graded on the framework's OWN graded boards
# (output/ice_hockey/ih_<day>.json via engine/ice_hockey.py, output/multisport/<sport>/ms_<day>.json via
# engine/multisport.py, both graded by run_multisport.py from Flashscore). A bot leg on one of them carries
# the key the bots use, "MS:<sport>:<SportyBet market id>|<specifier>|<outcome>" (Matchbook fw_key, Betfair
# sb_market); a SportyBet code decoded from the share API gets the same key from its sport id.
ROLLOUT_SPORTS: tuple[str, ...] = ("ice_hockey", *ms.SPORTS)
SB_SPORT_IDS = {"sr:sport:4": "ice_hockey", **{f"sr:sport:{v['sb']}": k for k, v in ms.SPORTS.items()}}
IH_DIR = ROOT / "output" / "ice_hockey"
MS_DIR = ROOT / "output" / "multisport"
IH_MARKETS = ("1", "406", "410", "18", "16", "14", "29")
SPORT_NAMES = {"football": "Football", "basketball": "Basketball", "ice_hockey": "Ice hockey",
               "american_football": "American football", "snooker": "Snooker", "darts": "Darts",
               "volleyball": "Volleyball", "table_tennis": "Table tennis", "cricket": "Cricket",
               "rugby": "Rugby", "tennis": "Tennis", "baseball": "Baseball"}
MS_MARKET_NAMES = {"186": "Winner", "219": "Winner", "251": "Winner", "340": "Winner", "406": "Winner",
                   "1": "1X2", "60": "1st half 1X2", "10": "Double chance", "11": "Draw no bet",
                   "16": "Handicap", "223": "Handicap", "256": "Handicap", "187": "Game handicap",
                   "188": "Set handicap", "493": "Frame handicap", "237": "Point handicap", "14": "3-way handicap",
                   "18": "Total", "225": "Total", "258": "Total", "189": "Total games", "494": "Total frames",
                   "238": "Total points", "202": "Set winner"}
IH_MARKET_NAMES = {"1": "1X2 (60 min)", "406": "Winner incl. OT", "410": "Handicap incl. OT",
                   "18": "Total (60 min)", "16": "Handicap (60 min)", "14": "3-way handicap", "29": "Both teams score"}


def rollout_key(key: str | None) -> tuple[str, str, str, str] | None:
    """'MS:tennis:186||Home' (or 'tennis:186||Home') -> ('tennis', '186', '', 'Home'); None for any other sport."""
    k = (key or "").removeprefix("MS:")
    sport, sep, rest = k.partition(":")
    if not sep or sport not in ROLLOUT_SPORTS:
        return None
    mid, spec, out = (rest.split("|") + ["", ""])[:3]
    return sport, mid, spec, out


def ms_key(sport: str, mid: str, spec: str, out: str) -> str:
    return f"MS:{sport}:{mid}|{spec or ''}|{out or ''}"


def _board_side(sport: str, mid: str, spec: str, out: str) -> str:
    """The side's key on the sport's own board: 'H:406||Home' (ice hockey), 'tennis:186||Home' (multisport)."""
    return f"{'H' if sport == 'ice_hockey' else sport}:{mid}|{spec}|{out}"


def _player(name: str) -> str:
    """'Monteiro, Thiago' (SportyBet) and 'Thiago Monteiro' (the exchanges) compare alike."""
    return ms.match_name(name or "")


def _read_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


class RolloutGames:
    """Every game of the rollout sports' boards (graded or not), by (sport, SportyBet event id) and by day."""

    def __init__(self, since: str, ih_dir: Path | None = None, ms_dir: Path | None = None):
        ih_dir, ms_dir = ih_dir or IH_DIR, ms_dir or MS_DIR
        self.by_id: dict[tuple[str, str], dict] = {}
        self.by_day: dict[tuple[str, str], list[dict]] = defaultdict(list)
        self.picks: list[tuple[str, str, dict]] = []
        files = [("ice_hockey", f) for f in sorted(ih_dir.glob("ih_20??-??-??.json"))]
        files += [(sp, f) for sp in ms.SPORTS for f in sorted((ms_dir / sp).glob("ms_20??-??-??.json"))]
        for sport, f in files:
            day = f.stem[3:]
            if day < since[:10]:
                continue
            doc = _read_json(f) or {}
            for gid, g in (doc.get("games") or {}).items():
                g = {**g, "id": gid, "sport": sport}
                self.by_id[(sport, gid)] = g
                self.by_day[(sport, (g.get("ko") or day)[:10])].append(g)
            self.picks += [(sport, day, x) for x in doc.get("picks") or [] if isinstance(x, dict)]

    def find(self, leg: dict, sport: str) -> dict | None:
        g = self.by_id.get((sport, leg.get("event_id") or ""))
        if g or not (leg.get("home") and leg.get("away") and leg.get("ko")):
            return g
        try:
            d0 = date.fromisoformat(str(leg["ko"])[:10])
        except ValueError:
            return None
        best, score = None, 0.0
        for off in (0, -1, 1):
            for c in self.by_day.get((sport, (d0 + timedelta(days=off)).isoformat()), []):
                s = (_alike(_player(leg["home"]), _player(c.get("home") or ""))
                     + _alike(_player(leg["away"]), _player(c.get("away") or "")))
                if s > score:
                    best, score = c, s
        return best if score >= 1.5 else None


def settle_rollout(sport: str, mid: str, spec: str, out: str, g: dict) -> str | None:
    """'won' / 'lost' / 'void' for one side of a graded rollout game, None while ungraded or the rule is unknown.
    The board's own settlement of the side first (run_multisport.py wrote it), else the sport's rule on the result."""
    r = g.get("result")
    if not r:
        return None
    s = (g.get("sides") or {}).get(_board_side(sport, mid, spec, out))
    if s is not None and "won" in s:
        w = s["won"]
    elif sport == "ice_hockey":
        from engine import hockey_model as hm
        if not r.get("reg") or not r.get("final"):
            return None
        w = hm.settle(mid, spec, out, tuple(r["reg"]), tuple(r["final"]))
    else:
        if not r.get("final"):
            return None
        w = ms.settle(sport, mid, spec, out, r)
    if w is None:
        known = IH_MARKETS if sport == "ice_hockey" else tuple(ms.SPORTS[sport]["markets"].split(","))
        return "void" if mid in known else None
    return "won" if w else "lost"


def rollout_board_bets(rg: RolloutGames, since: str) -> list[dict]:
    """The rollout boards' own picks as paper (1 unit each, like the football board's slips): SportyBet's paper
    for these sports IS the framework's graded record (sportybet-agent #88), so the report shows it per sport."""
    out = []
    for sport, day, p in rg.picks:
        if day < since or not p.get("market_id"):
            continue
        key = ms_key(sport, str(p["market_id"]), p.get("specifier") or "", p.get("outcome") or "")
        out.append({"bot": "board", "cur": "unit", "date": day, "kind": f"{sport} board", "stake": 1.0,
                    "id": p.get("code") or f"{sport}:{p.get('sb_event_id')}", "odds": float(p.get("price") or 0),
                    "paper": True, "rollout": True,
                    "legs": [{"event_id": p.get("sb_event_id"), "home": p.get("home"), "away": p.get("away"),
                              "ko": p.get("ko"), "sport": sport, "price": p.get("price"), "key": key}]})
    return out


def leg_sport(leg: dict) -> str:
    rk = rollout_key(leg.get("key"))
    if rk:
        return rk[0]
    if leg.get("sport") in SPORT_NAMES:
        return leg["sport"]
    return "basketball" if str(leg.get("key") or "").startswith("NBA:") else "football"


def bet_sport(bet: dict) -> str:
    sports = {leg_sport(x) for x in bet.get("legs") or []}
    return sports.pop() if len(sports) == 1 else ("mixed" if sports else "unknown")


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
    rk = rollout_key(key)
    if rk:
        return _grade_rollout_leg(out, rk, games, tally)
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


def _grade_rollout_leg(out: dict, rk: tuple[str, str, str, str], games: Games, tally: dict) -> dict:
    """A rollout-sport leg: the sport's own graded board, then SportyBet's settlement, then the exchange's."""
    sport = rk[0]
    g = games.rollout.find(out, sport)
    if g is not None:
        out["game"] = f"{sport}:{g['id']}"
    res = settle_rollout(*rk, g) if g is not None else None
    sb_res = _sb_settled(out.get("sb"))
    if res is not None:
        if sb_res is not None and sb_res != res:
            tally["disagree"] += 1
            out.update(result=sb_res, source=f"sportybet ({sport} board said {res})")
        else:
            out.update(result=res, source=f"{sport} board")
        return out
    if sb_res is not None:
        out.update(result=sb_res, source="sportybet")
        return out
    if out.get("own"):
        out.update(result=out["own"], source="exchange")
        return out
    out.update(result=None, source=("no game found" if g is None else "not graded yet" if not g.get("result")
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
        sid = (o.get("sport") or {}).get("id")
        nba = sid == "sr:sport:2"
        roll = SB_SPORT_IDS.get(sid)             # a rollout sport (framework#357)
        ko = datetime.fromtimestamp(int(o.get("estimateStartTime") or 0) / 1000, UTC)
        for m in o.get("markets") or []:
            for oc in m.get("outcomes") or []:
                key = (ms_key(roll, str(m.get("id")), m.get("specifier") or "", oc.get("desc") or "") if roll else
                       f"{'NBA' if nba else 'SB'}:{m.get('id')}|{m.get('specifier') or ''}|{oc.get('desc')}")
                legs.append({
                    "event_id": o.get("eventId"), "home": o.get("homeTeamName"),
                    "away": o.get("awayTeamName"), "ko": ko.strftime("%Y-%m-%dT%H:%MZ"),
                    "sport": roll or ("basketball" if nba else "football"),
                    "key": key,
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


def _jsonl(path: Path) -> list[dict]:
    try:
        return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    except (OSError, ValueError):
        return []


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
        sp = bet_sport(b)
        if sp in ROLLOUT_SPORTS and b["kind"] == "nba":   # the placer files rollout singles under "nba"
            b["kind"] = sp
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
    if "|MS:" in fk:                          # a rollout sport: "<date>|<home> v <away>|MS:<sport>:<market>|.."
        key = fk[fk.index("|MS:") + 1:]
        fixture = fk.split("|")[1]
        if " v " in fixture:
            home, _, away = fixture.partition(" v ")
        rk = rollout_key(key)
        return key, home, away, rk[0] if rk else sport
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
            "clv": r.get("clv"), "placed_at": r.get("opened_at"), "own_pnl": r.get("pnl_gbp"), "own_settled": own is not None and r.get("pnl_gbp") is not None,
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
    out += matchbook_rollout_paper(repo, since)
    return out


def matchbook_rollout_paper(repo: Path, since: str) -> list[dict]:
    """Matchbook's £1 paper backs on the rollout sports (matchbook-agent hockey.py / multisport.py):
    'IH|<event>|H:<market>|..' and 'MS|<sport>|<event>|<sport>:<market>|..' records."""
    out = []
    for name in ("hockey_paper.jsonl", "multisport_paper.jsonl"):
        for n, r in enumerate(_jsonl(repo / "ledger" / name)):
            raw = str(r.get("key") or "")
            if raw.startswith("IH|"):
                sport, side = "ice_hockey", raw.split("|", 2)[-1].removeprefix("H:")
            elif raw.startswith("MS|"):
                sport = r.get("sport") or raw.split("|")[1]
                side = raw.split("|", 3)[-1].partition(":")[2]
            else:
                continue
            ko = r.get("ko") or ""
            day = _uk_day(ko) if ko else str(r.get("date") or "")
            if not day or day < since or sport not in ROLLOUT_SPORTS:
                continue
            own = r.get("result") if r.get("result") in ("won", "lost", "void") else None
            out.append({"bot": "matchbook", "cur": "GBP", "date": day, "id": f"{name}-{n}",
                        "kind": f"{sport} (paper)", "stake": 1.0, "odds": float(r.get("odds") or 0), "paper": True,
                        "legs": [{"event_id": r.get("sb_event_id"), "home": r.get("home"), "away": r.get("away"),
                                  "ko": ko, "sport": sport, "key": f"MS:{sport}:{side}", "own": own}]})
    return out


BF_OWN = {"WON": "won", "LOST": "lost", "VOIDED": "void", "VOID": "void"}


def _bf_sport(b: dict) -> str:
    sp = b.get("sport")
    return "basketball" if sp == "nba" else sp if sp in ROLLOUT_SPORTS else "football"


def _bf_own_code(code: str) -> bool:
    """Betfair's own id for a rollout pick with no SportyBet code ('TENNIS-sr:match:1'): nothing to decode."""
    return "-" in code


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
                legs = [{"home": home, "away": away, "ko": ko, "key": b.get("sb_market"), "sport": _bf_sport(b)}]
            out.append({"bot": "betfair", "cur": "GBP", "date": day, "id": f"paper-{b.get('code')}",
                        "kind": f"{b.get('section') or '?'} {b.get('rule') or ''} (paper)".strip(),
                        "stake": float(b.get("stake") or 0), "odds": float(b.get("price") or 0),
                        "paper": True, "legs": legs})
        for n, b in enumerate(_rows(d)):
            if b.get("mode") != "live" and b.get("sport") in ROLLOUT_SPORTS:
                # a rollout sport on paper (betfair-agent #21): graded and kept too (order 53)
                ko = b.get("kickoff_utc") or ""
                day = _uk_day(ko) if ko else p.stem[6:]
                if day < since:
                    continue
                st = (b.get("result") or "").upper()
                home, _, away = (b.get("fixture") or "").partition(" v ")
                out.append({"bot": "betfair", "cur": "GBP", "date": day, "id": f"paper-{p.stem[6:]}-{n}",
                            "kind": f"{b.get('section') or b['sport']} (paper)", "stake": float(b.get("stake") or 0),
                            "odds": float(b.get("price") or 0), "paper": True,
                            "legs": [{"home": home, "away": away, "ko": ko, "key": b.get("sb_market"),
                                      "sport": b["sport"], "own": BF_OWN.get(st)}]})
                continue
            if b.get("mode") != "live" or not b.get("bet_id"):   # paper rows are the bot's own study
                continue
            ko = b.get("kickoff_utc") or ""
            day = _uk_day(ko) if ko else p.stem[6:]
            if day < since:
                continue
            st = (b.get("result") or "").upper()
            own = {"WON": "won", "LOST": "lost", "VOIDED": "void", "VOID": "void"}.get(st)
            code = str(b.get("code") or "").split("/")[0]
            legs = (code_legs(code, cache) if code and not _bf_own_code(code) else None) or []
            if len(legs) != 1:
                home, _, away = (b.get("fixture") or "").partition(" v ")
                legs = [{"home": home, "away": away, "ko": ko, "key": b.get("sb_market"), "sport": _bf_sport(b)}]
            legs[0] = {**legs[0], "own": own}
            out.append({
                "bot": "betfair", "cur": "GBP", "date": day, "id": str(b["bet_id"]),
                "kind": f"{b.get('section') or '?'} {b.get('rule') or ''}".strip(),
                "stake": float(b.get("size_matched") or b.get("stake") or 0),
                "odds": float(b.get("avg_price") or b.get("price") or 0), "paper": False,
                "placed_at": b.get("placed_at"), "own_pnl": b.get("pnl"), "own_settled": st in ("WON", "LOST", "GREEN", "VOIDED", "VOID")
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
    """One graded file per bot per bet day; rewritten only when a grade changed.
    GRADE EVERYTHING, KEEP EVERYTHING (the Architect, 2026-11-07 17:43 UK: "Never leave anything ungraded ...
    the framework needs every information to make decisions without me"): a bot's paper picks are kept too, in
    graded/paper_<day>.json beside the real ones' graded/<day>.json. The bots' money readers (derisk) glob
    20??-??-??.json only, so a paper grade never moves a real stake."""
    root = root or BOTS
    changed: dict[str, int] = defaultdict(int)
    groups: dict[tuple[str, str, bool], dict] = defaultdict(dict)
    for b in graded:
        if b["bot"] in SIDECAR:
            groups[(b["bot"], b["date"], bool(b.get("paper")))][b["id"]] = _slim(b)
    for (bot, day, is_paper), bets in groups.items():
        repo, sub = SIDECAR[bot]
        path = root / repo / sub / (f"paper_{day}.json" if is_paper else f"{day}.json")
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
    rk = rollout_key(key)
    if rk:
        sport, mid, _spec, out = rk
        names = IH_MARKET_NAMES if sport == "ice_hockey" else MS_MARKET_NAMES
        return f"{SPORT_NAMES[sport]} {names.get(mid, 'market ' + mid)}", re.sub(r"[\d.:+-]+", "N", out).strip()
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


def sport_lines(bets: list[dict], since: str, today: str) -> list[str]:
    """THE 23:02 REPORT, ONE LINE PER SPORT (framework#357): football, basketball and every rollout sport (always
    listed, so a sport with nothing graded says so): the bots' real money, the bots' paper and the board's own
    picks (units), each graded on that sport's results, plus what is still open."""
    by: dict[str, list[dict]] = defaultdict(list)
    for b in bets:
        if since <= b["date"] <= today:
            by[bet_sport(b)].append(b)
    out = []
    for sport in ("football", "basketball", *ROLLOUT_SPORTS, "mixed"):
        bs = by.get(sport) or []
        done = [b for b in bs if b.get("profit") is not None]
        real = [b for b in done if not b["paper"]]
        paper = [b for b in done if b["paper"] and b["bot"] != "board"]
        board = [b for b in done if b["bot"] == "board"]
        parts = []
        if real:
            st, pr = sum(_gbp(b, "stake") for b in real), sum(_gbp(b, "profit") for b in real)
            parts.append(f"real {len(real)} bets, {sum(b['result'] == 'won' for b in real)} won, "
                         f"{_money(pr, 'GBP')} ({pr / st if st else 0:+.0%})")
        if paper:
            st, pr = sum(_gbp(b, "stake") for b in paper), sum(_gbp(b, "profit") for b in paper)
            parts.append(f"bots' paper {len(paper)}, {sum(b['result'] == 'won' for b in paper)} won, "
                         f"{_money(pr, 'GBP')} ({pr / st if st else 0:+.0%})")
        if board:
            pr = sum(b["profit"] for b in board)
            parts.append(f"board {len(board)} picks, {sum(b['result'] == 'won' for b in board)} won, "
                         f"{pr:+.2f} units")
        still = sum(1 for b in bs if b.get("profit") is None and b["bot"] != "board")
        if still:
            parts.append(f"{still} bot bets open")
        if parts or sport in ROLLOUT_SPORTS:
            out.append(f"{SPORT_NAMES.get(sport, sport.title())}: " + ("; ".join(parts) or "nothing graded yet"))
    return out


def value_watch_lines(today: str, ih_dir: Path = IH_DIR, ms_dir: Path = MS_DIR) -> list[str]:
    """NEW SPORTS VALUE WATCH (Architect 2026-11-08: keep the value rule, show what it sees). For each rollout
    sport, today's board: games watched, the best value any side reached against its fair price (Matchbook, else
    75% SportyBet + 25% model) inside the pick rule's price band and 50% chance, and the bar it had to clear.
    Read-only: it changes no pick, bar or stake."""
    from engine import ice_hockey as ih
    out = []
    for sport in ROLLOUT_SPORTS:
        hockey = sport == "ice_hockey"
        path = ih_dir / f"ih_{today}.json" if hockey else ms_dir / sport / f"ms_{today}.json"
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            out.append(f"{SPORT_NAMES.get(sport, sport)}: no board today")
            continue
        mod = ih if hockey else ms
        best = None
        for g in (doc.get("games") or {}).values():
            prices = {k: (s.get("last") or s.get("first") or {}).get("price") for k, s in (g.get("sides") or {}).items()}
            for key, s in (g.get("sides") or {}).items():
                look = s.get("last") or s.get("first") or {}
                price, p = look.get("price"), look.get("fair")
                if price is None:
                    continue
                if p is None and look.get("model") is not None:
                    q = mod.devig(key, prices)
                    p = None if q is None else mod.ANCHOR * q + (1 - mod.ANCHOR) * look["model"]
                if p is None or not (mod.BAND[0] <= price <= mod.BAND[1] and p >= 0.50):
                    continue
                mid = key[2:].split("|")[0] if hockey else ms.split_key(key)[1]
                winner = mid in (ih.RESULT_MARKETS if hockey else ms.WINNER_MARKETS)
                v = price * p - 1
                if best is None or v > best[0]:
                    bar = mod._decided_bar(f"{sport}|{mid}", mod.MIN_VALUE if winner else mod.LINE_VALUE)
                    best = (v, bar, g, key, price)
        games, picks = len(doc.get("games") or {}), len(doc.get("picks") or [])
        name = SPORT_NAMES.get(sport, sport)
        if best is None:
            out.append(f"{name}: {games} games, {picks} picks; no side in the price band with a fair price")
            continue
        v, bar, g, key, price = best
        side = ih.describe(key, g.get("home", ""), g.get("away", "")) if hockey else             ms.describe(key, g.get("home", ""), g.get("away", ""))
        out.append(f"{name}: {games} games, {picks} picks; best value {v:+.1%} vs bar {bar:.1%} "
                   f"({side} @ {price}, {g.get('home')} v {g.get('away')})")
    return out


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


def coming_up(today: str) -> list[str]:
    """COMING UP (next 14 days): one line per sport from the sport calendar (engine/sport_calendar.py:
    international breaks, Nations League, NBA Cup, NFL byes, tournaments, off-seasons). Never blocks the report."""
    try:
        from engine import sport_calendar as CAL
        lines = CAL.coming_up_lines(CAL.load_latest(today), today, 14)
    except Exception:  # noqa: BLE001
        return []
    return ["", "COMING UP (next 14 days, sport calendar)"] + lines if lines else []


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
    out += ["", "BY SPORT (30 days: real £, bots' paper £, board picks in units)"] + sport_lines(bets, d30, today)
    try:                    # recorded only: never blocks the report
        vw = value_watch_lines(today)
    except Exception:  # noqa: BLE001
        vw = []
    if vw:
        out += ["", "NEW SPORTS VALUE WATCH (today's boards: best value seen vs the bar)"] + vw
    out += coming_up(today)
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
    try:                    # the scout's own record (recorded only): one line, never blocks the report
        from engine import scout as _scout
        if _scout.enabled():
            out += ["", _scout.summary_line()]
    except Exception:  # noqa: BLE001
        pass
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


def decision_inputs(graded: list[dict]) -> tuple[list[dict], list[dict]]:
    """Graded singles for engine/decisions.py: real ones by bot | market side, the board's paper picks by
    market side (the evidence a paper group needs to come back)."""
    from engine import decisions as dec
    real, paper = [], []
    for b in graded:
        if len(b.get("legs") or []) != 1 or b.get("profit") is None:
            continue
        key = b["legs"][0].get("key")
        if b["paper"] and b["bot"] == "board":
            if b.get("rollout"):        # the rollout boards' own picks: reported and kept, not decision evidence
                continue
            paper.append({"group": dec.group_of(key), "stake_gbp": 1.0, "profit_gbp": float(b["profit"]),
                          "date": b["date"]})
        elif not b["paper"]:
            real.append({"group": dec.group_of(key, b["bot"]), "stake_gbp": _gbp(b, "stake"),
                         "profit_gbp": _gbp(b, "profit"), "date": b["date"]})
    return real, paper


def board_sides() -> tuple[dict, dict]:
    """Graded sides of the hockey / multi-sport boards for the value-bar decisions: {sport|market: [(value, won,
    price)]} and each market's default bar."""
    from engine import ice_hockey as ih
    from engine import multisport as ms
    sides: dict = defaultdict(list)
    defaults: dict = {}
    docs = [("ice_hockey", d) for _day, d in ih.load_all()]
    docs += [(sp, d) for sp in ms.SPORTS for _day, d in ms.load_all(sp)]
    for sport, doc in docs:
        for g in (doc.get("games") or {}).values():
            for key, s in (g.get("sides") or {}).items():
                first = s.get("first") or {}
                if s.get("won") is None or not first.get("fair") or not first.get("price"):
                    continue
                mid = key[2:].split("|")[0] if sport == "ice_hockey" else ms.split_key(key)[1]
                k = f"{sport}|{mid}"
                p, f = float(first["price"]), float(first["fair"])
                if not (1.20 <= p <= 2.00 and f >= 0.50):
                    continue
                sides[k].append((p * f - 1, int(s["won"]), p))
                win = mid in (ih.RESULT_MARKETS if sport == "ice_hockey" else ms.WINNER_MARKETS)
                defaults[k] = (ih.MIN_VALUE if win else ih.LINE_VALUE) if sport == "ice_hockey" else \
                    (ms.MIN_VALUE if win else ms.LINE_VALUE)
    return dict(sides), defaults


def run_decisions(graded: list[dict], now: datetime) -> dict:
    from engine import decisions as dec
    real, paper = decision_inputs(graded)
    sides, defaults = board_sides()
    res = dec.run(real, paper, sides, defaults, now)
    res["line"] = dec.report_line(res)
    return res


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
def collect(today: str, cache: dict, rollout: RolloutGames | None = None) -> list[dict]:
    since = _days(today, WINDOW + 2)
    bets: list[dict] = []
    paper = board_bets(since)
    paper += rollout_board_bets(rollout if rollout is not None else RolloutGames(since), since)
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
    rollout = RolloutGames(_days(today, WINDOW + 3))
    bets = collect(today, cache, rollout)
    games = Games(_days(today, WINDOW + 3), rollout=rollout)
    tally: dict[str, int] = defaultdict(int)
    graded = [grade_slip(b, games, tally, now) for b in bets]
    real = [b for b in graded if not b["paper"]]
    done = sum(1 for b in real if b.get("profit") is not None)
    notes = [f"bots: {len(real)} bets read, {done} graded, {len(real) - done} open; "
             f"board: {sum(b['paper'] for b in graded)} paper slips"]
    save_cache(cache)
    if dry:
        return " · ".join(notes)
    changed = write_back(graded, now)            # real AND paper (paper_<day>.json); board slips stay in the report
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
    scorecard_line = ""
    timing_line = ""
    try:      # Matchbook (early) v Betfair (3 h before) on the same picks, by CLV (#259): record-only
        from monitor import timing_experiment
        tx = timing_experiment.build(real, today)
        timing_experiment.save(tx)
        timing_line = tx["report_line"]
        notes.append(f"timing: {tx['pairs']} same-pick pairs")
    except Exception as e:  # noqa: BLE001 — never blocks grading or the report
        notes.append(f"timing experiment not built: {type(e).__name__}")
    try:      # per-rule CLV scorecard across all bots (#258): record-only, proposals never applied
        from monitor import rule_scorecard
        card = rule_scorecard.build(real, today, hypotheses=_jsonl(ROOT / "memory" / "hypotheses.jsonl"),
                                    lessons=(_read(ROOT / "memory" / "tactics_lessons.json") or {}).get("lessons"))
        rule_scorecard.save(card)
        scorecard_line = card["report_line"]
        notes.append(f"scorecard: {len(card['rows'])} rule/market rows, {len(card['proposals'])} proposals")
    except Exception as e:  # noqa: BLE001 — never blocks grading or the report
        notes.append(f"scorecard not built: {type(e).__name__}")
    decisions_line = ""
    try:      # the decision layer (standing order 51): stakes x0.5-1.5, real/paper, value bars; with undo
        res = run_decisions(graded, now)
        decisions_line = res["line"]
        notes.append(f"decisions: {len(res['made'])} made, {len(res['undone'])} undone")
        if res["undone"] and not dry:
            send("DECISION UNDONE (automatic)\n" + "\n".join(
                f"- {d['key']}: back to {d['to']} ({d['evidence'].get('roi_since', 0):+.0%} on "
                f"{d['evidence'].get('bets_since')} bets since)" for d in res["undone"]))
    except Exception as e:  # noqa: BLE001 — never blocks grading or the report
        notes.append(f"decisions not run: {type(e).__name__}: {str(e)[:80]}")
    due = today if force_report else report_day(now)
    if due:
        text = build_report(graded, due, tally)
        if decisions_line:
            text += "\n\n" + decisions_line
        if learning:
            text += "\n\n" + learning
        if scorecard_line:
            text += "\n\n" + scorecard_line
        if timing_line:
            text += "\n\n" + timing_line
        try:      # the edge scoreboard (monitor/edge_scoreboard.py): CLV vs the exchange close, promotion
            edge = _read(ROOT / "memory" / "edge_scoreboard.json") or {}
            if edge.get("summary"):
                text += "\n\n" + edge["summary"]
        except Exception:  # noqa: BLE001 — never blocks the report
            pass
        try:      # the prediction sites' paper tip board: the day's record and each site's stage
            from engine import tip_board
            tips = tip_board.report_lines(due)
            if tips:
                text += "\n\n" + "\n".join(tips)
        except Exception:  # noqa: BLE001 — never blocks the report
            pass
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
