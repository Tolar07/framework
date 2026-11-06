"""
THE BETFAIR BOARD — every sport except football (Architect 2026-11-06: "all the new sports on November 12th
will be hosted on Betfair ... Betfair will stop anything football"; layout approved the same day).

One board, a section per sport: basketball (NBA + world + NCAA), ice hockey and every multi-sport board sport.
Built only from files the loops already wrote (HR59; a missing file reads PENDING, HR35):

  picks       output/picks/nba_<day>.json, output/world_basketball/wb_<day>.json,
              output/ice_hockey/ih_<day>.json, output/multisport/<sport>/ms_<day>.json
  Betfair     .bots/betfair-agent/ledger/paper_<UK day>.json (+ heartbeat.json): what the bot did per code
  scorecard   data/ice_hockey/scoreboard.json, data/multisport/<sport>/scoreboard.json

Per pick: chance, fair price, SportyBet's price and value, then Betfair's status (matched £x @ price /
on paper / skipped + why / not yet: Betfair backs up to 3 h before the start). A sport with no pick shows
its STUDY LINES: the sides closest to value, so an empty day is never a blank board. Phone-sized: the best
TOP picks per sport; the full list is /board <sport>. The framework never stakes; the Betfair bot does.
No steam (order 50).
"""
from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"
DATA = ROOT / "data"
BOTS = ROOT / ".bots"
BOARD_DIR = OUT / "boards"
UK = ZoneInfo("Europe/London")
PENDING = "NO DATA — PENDING"
TOP = 5
STUDY = 2
BAND = (1.20, 2.00)       # the price range a pick may have (engine/multisport.py BAND); study lines use it too
MAX_CHARS = 3900          # Telegram's limit is 4096
_RULE = "──────────────────────────────"

# (sport, label, emoji, files) — basketball first, then the rollout order (config/sport_rollout.json)
MS = ("american_football", "snooker", "darts", "volleyball", "table_tennis", "cricket", "rugby", "tennis",
      "baseball")
SECTIONS = [("basketball", "BASKETBALL (NBA + world + NCAA)", "🏀"), ("ice_hockey", "ICE HOCKEY", "🏒"),
            ("american_football", "AMERICAN FOOTBALL", "🏈"), ("snooker", "SNOOKER", "🎱"), ("darts", "DARTS", "🎯"),
            ("volleyball", "VOLLEYBALL", "🏐"), ("table_tennis", "TABLE TENNIS", "🏓"), ("cricket", "CRICKET", "🏏"),
            ("rugby", "RUGBY", "🏉"), ("tennis", "TENNIS", "🎾"), ("baseball", "BASEBALL", "⚾")]
NOT_ON_BETFAIR = {"table_tennis": "Betfair lists no table tennis"}
LIVE_FROM = date(2026, 11, 12)     # every rollout sport live (order 50); Betfair = non-football from the same day


def _read(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _ko(p: dict) -> datetime | None:
    s = str(p.get("tip") or p.get("ko") or "")
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _name(n: str) -> str:
    """'Shelton, Ben' -> 'Ben Shelton' (SportyBet's player form)."""
    if n and n.count(",") == 1:
        last, first = (x.strip() for x in n.split(","))
        return f"{first} {last}"
    return n or "?"


# ── inputs ────────────────────────────────────────────────────────────────────────────────────
def sport_files(sport: str, day: str, out: Path = OUT) -> list[dict]:
    if sport == "basketball":
        return [d for d in (_read(out / "picks" / f"nba_{day}.json"), _read(out / "world_basketball" / f"wb_{day}.json"))
                if d]
    if sport == "ice_hockey":
        d = _read(out / "ice_hockey" / f"ih_{day}.json")
        return [d] if d else []
    d = _read(out / "multisport" / sport / f"ms_{day}.json")
    return [d] if d else []


def picks_of(docs: list[dict]) -> list[dict]:
    out = []
    for d in docs:
        for p in d.get("picks") or []:
            fair = p.get("fair") if p.get("fair") is not None else p.get("chance")
            value = p.get("value") if p.get("value") is not None else p.get("ev")
            if fair is None and p.get("fair_price"):
                fair = 1 / p["fair_price"]
            out.append(dict(p, _fair=fair, _value=value))
    return sorted(out, key=lambda p: (_ko(p) or datetime.max.replace(tzinfo=UTC)))


def study_lines(docs: list[dict], n: int = STUDY) -> list[dict]:
    """Sides closest to value (chance × price − 1) with a fair chance (exchange) or a model chance (Elo)."""
    rows = []
    for d in docs:
        for g in (d.get("games") or {}).values():
            for key, s in (g.get("sides") or {}).items():
                last = s.get("last") or {}
                p = last.get("fair") if last.get("fair") is not None else last.get("model")
                if p and last.get("price") and BAND[0] <= last["price"] <= BAND[1]:
                    rows.append({"home": g.get("home"), "away": g.get("away"), "ko": g.get("ko"), "key": key,
                                 "price": last["price"], "p": p, "value": last["price"] * p - 1,
                                 "src": "exchange" if last.get("fair") is not None else "Elo"})
    out, seen = [], set()
    for r in sorted(rows, key=lambda r: -r["value"]):
        k = (r["home"], r["away"], r["key"].split("|")[-1], r["price"])
        if k not in seen:
            seen.add(k)
            out.append(r)
    return out[:n]


def games_watched(docs: list[dict]) -> int:
    return sum(len(d.get("games") or {}) for d in docs)


def betfair_ledgers(days: list[str], bots: Path = BOTS) -> tuple[dict, dict]:
    """({code: {"bet": .., "paper": .., "skip": ..}}, heartbeat) from the Betfair bot's published ledger."""
    by: dict[str, dict] = {}
    root = bots / "betfair-agent" / "ledger"
    for day in days:
        d = _read(root / f"paper_{day}.json") or {}
        for b in d.get("bets") or []:
            by.setdefault(str(b.get("code")), {})["bet"] = b
        for b in d.get("paper_rules") or []:
            by.setdefault(str(b.get("code")), {})["paper"] = b
        for code, why in (d.get("skipped") or {}).items():
            by.setdefault(str(code), {}).setdefault("skip", why)
    return by, (_read(root / "heartbeat.json") or {})


def betfair_line(p: dict, sport: str, bf: dict, now: datetime) -> str:
    if sport in NOT_ON_BETFAIR:
        return f"Betfair: — ({NOT_ON_BETFAIR[sport]})"
    rec = bf.get(str(p.get("code"))) or {}
    b = rec.get("bet")
    if b:
        res = f" · {b['result'].lower()} £{b.get('pnl', 0):+.2f}" if b.get("result") else ""
        if b.get("mode") == "live":
            got = b.get("size_matched") or 0
            px = b.get("avg_price") or b.get("price")
            return f"Betfair: matched £{got:.2f} @{px}{res}" if got else f"Betfair: offered £{b.get('stake')} @{b.get('price')}, not matched yet"
        return f"Betfair (paper): £{b.get('stake')} @{b.get('price')}{res}"
    if rec.get("paper"):
        q = rec["paper"]
        why = " (football on paper)" if (q.get("sport") or "football") == "football" else ""
        return f"Betfair: on paper @{q.get('price')}{why}"
    if rec.get("skip"):
        return f"Betfair: skipped — {str(rec['skip'])[:70]}"
    ko = _ko(p)
    if ko and ko > now + timedelta(hours=3):
        return f"Betfair: waits (bets from {(ko - timedelta(hours=3)).astimezone(UK):%H:%M}, 3 h before)"
    if ko and ko <= now:
        return "Betfair: not bet (no record in its ledger)"
    return "Betfair: no record yet — PENDING"


def scorecard(sport: str, data: Path = DATA) -> str | None:
    p = data / "ice_hockey" / "scoreboard.json" if sport == "ice_hockey" else data / "multisport" / sport / "scoreboard.json"
    sb = _read(p)
    if not sb:
        return None
    sides = sum(b.get("sides", 0) for b in (sb.get("all_sides_by_market") or {}).values())
    clv = f" · value vs close {sb['clv_fair_avg']:+.1%}" if sb.get("clv_fair_avg") is not None else ""
    return f"{sport.replace('_', ' ')}: picks {sb.get('picks', 0)} (won {sb.get('won', 0)}), {sb.get('pnl', 0):+.2f}u{clv}; {sides} sides graded"


# ── render ────────────────────────────────────────────────────────────────────────────────────
def pick_lines(p: dict, sport: str, bf: dict, now: datetime) -> list[str]:
    ko = _ko(p)
    t = f"{ko.astimezone(UK):%H:%M}" if ko else "--:--"
    fair, val, price = p.get("_fair"), p.get("_value"), p.get("price")
    bits = [p.get("pick") or "PENDING"]
    if isinstance(fair, (int, float)) and fair > 0:
        bits += [f"chance {fair:.0%}", f"fair {1 / fair:.2f}"]
    if isinstance(price, (int, float)):
        bits.append(f"SportyBet {price:.2f}")
    if isinstance(val, (int, float)):
        bits.append(f"value {val:+.1%}")
    paper = " · PAPER" if p.get("paper") else ""
    return [f"{t}  {_name(p.get('home'))} v {_name(p.get('away'))}" + (f"  ({p['comp']})" if p.get("comp") else "") + paper,
            "   " + " · ".join(bits), "   " + betfair_line(p, sport, bf, now)]


def section(sport: str, label: str, emoji: str, day: str, bf: dict, now: datetime, top: int | None = TOP,
            out: Path = OUT) -> list[str]:
    docs = sport_files(sport, day, out)
    if not docs:
        return [f"{emoji} {label}: {PENDING} (no board file for {day})"]
    picks = picks_of(docs)
    watched = games_watched(docs)
    head = f"{emoji} {label} — {len(picks)} pick{'s' if len(picks) != 1 else ''}" + (f" · {watched} game{'s' if watched != 1 else ''} watched" if watched else "")
    L = [head]
    shown = picks if top is None else picks[:top]
    for p in shown:
        L += pick_lines(p, sport, bf, now)
    if top is not None and len(picks) > top:
        L.append(f"   … {len(picks) - top} more: /board {sport}")
    if not picks:
        st = study_lines(docs)
        if st:
            L.append("   No side beat the fair price. Closest (study lines, not bets):")
            for r in st:
                L.append(f"   {_name(r['home'])} v {_name(r['away'])}: {r['key'].split('|')[-1]} @{r['price']:.2f} "
                         f"· chance {r['p']:.0%} ({r['src']}) · {r['value']:+.1%}")
        else:
            L.append("   No side at 1.20-2.00 priced by the exchange or the sport's Elo yet.")
    return L


def render(day: str, now: datetime | None = None, run_id: str = "local", out: Path = OUT, bots: Path = BOTS,
           data: Path = DATA, only: str | None = None) -> str:
    now = now or datetime.now(UTC)
    uk_days = sorted({day, (date.fromisoformat(day) - timedelta(days=1)).isoformat()})
    bf, hb = betfair_ledgers(uk_days, bots)
    live = date.fromisoformat(day) >= LIVE_FROM
    L = ["##### OLP XDV · BETFAIR — EVERY SPORT EXCEPT FOOTBALL #####",
         f"📅 {date.fromisoformat(day):%a %d %b %Y} · UK time · Run ID: {run_id}",
         ("LIVE: Betfair places these (the framework never stakes)" if live else
          "SHADOW until 12 Nov: every pick is paper; Betfair goes live on them from 12 Nov")]
    non_fb = [r["bet"] for r in bf.values() if r.get("bet") and (r["bet"].get("sport") or "football") != "football"
              and r["bet"].get("mode") == "live"]
    matched = [b for b in non_fb if (b.get("size_matched") or 0) > 0]
    settled = [b for b in non_fb if b.get("result")]
    pnl = sum(b.get("pnl") or 0 for b in settled)
    wallet = f" · wallet £{hb['wallet']:.2f}" if isinstance(hb.get("wallet"), (int, float)) else " · wallet PENDING"
    L.append(f"Betfair today: {len(non_fb)} placed · {len(matched)} matched · {len(settled)} settled £{pnl:+.2f}{wallet}")
    L += ["", _RULE]
    for sport, label, emoji in SECTIONS:
        if only and sport != only:
            continue
        L += section(sport, label, emoji, day, bf, now, None if only else TOP, out) + [""]
    if not only:
        cards = [c for c in (scorecard(s, data) for s, _l, _e in SECTIONS if s != "basketball") if c]
        L += [_RULE, "SCORECARD (paper + live, since 5 Nov)"] + (cards or [PENDING])
        L += ["", "Not on Betfair: " + "; ".join(f"{s.replace('_', ' ')} ({w})" for s, w in NOT_ON_BETFAIR.items()),
              "Football is on the football board (Matchbook + SportyBet)."]
    return "\n".join(L)


def split(text: str, limit: int = MAX_CHARS) -> list[str]:
    """Telegram-sized parts, cut between sport sections (blank lines), never mid-pick."""
    parts, cur = [], ""
    for block in text.split("\n\n"):
        add = (("\n\n" if cur else "") + block)
        if len(cur) + len(add) > limit and cur:
            parts.append(cur)
            cur = block
        else:
            cur += add
    if cur:
        parts.append(cur)
    return [p[:limit] for p in parts]


def path_for(day: str, folder: Path = BOARD_DIR) -> Path:
    return folder / f"allsports_{day}.txt"


def latest(folder: Path = BOARD_DIR) -> str:
    files = sorted(folder.glob("allsports_*.txt")) if folder.exists() else []
    if not files:
        return f"No Betfair all-sports board has been produced yet. {PENDING}."
    return files[-1].read_text(encoding="utf-8")


SPORT_NAMES = {s for s, _l, _e in SECTIONS} | {"hockey", "nfl", "af"}


def sport_alias(arg: str) -> str | None:
    a = (arg or "").strip().lower().replace(" ", "_")
    return {"hockey": "ice_hockey", "nfl": "american_football", "af": "american_football",
            "tt": "table_tennis"}.get(a, a if a in {s for s, _l, _e in SECTIONS} else None)
