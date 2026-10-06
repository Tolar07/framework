"""
NBA PAPER BOARD (standing order 41, Architect 2026-10-06) — run once a day
from the evening run, after the football board.

  1. grade every earlier NBA pick whose game has finished (ESPN final score,
     overtime included) and record its CLOSING value — the pick's price
     against the sharp closing line — the honest test of a price edge;
  2. read SportyBet's NBA games (regular season + preseason) and ESPN's
     sharp lines for every game tipping off in the next HOURS hours;
  3. list only prices ABOVE the fair price (engine/nba_value.py), one per
     game, each with its own SportyBet booking code, + one code for them all;
  4. send it to the Architect's own chat only, as a PAPER board: no stake,
     no capital, until the graded record says otherwise.

Preseason games are shown and graded as a pipeline test but kept OUT of the
record (starters are rested — not a fair test of anything).

  python run_nba.py              build, grade, send
  python run_nba.py --no-send    build + grade, print, don't send
  python run_nba.py --rebuild    replace an already-built board for the day

A day's board is built ONCE (like the 10pm freeze): a re-run resends it.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from data import nba_source as ns  # noqa: E402
from engine import nba_value as nv  # noqa: E402

LEDGER_DIR = ROOT / "output" / "picks"
BOARD_DIR = ROOT / "output" / "boards"
LAGOS = timezone(timedelta(hours=1))
HOURS = 26
TOURNAMENTS = {"sr:tournament:132": "regular", "sr:tournament:2382": "preseason"}
_FEED = ("https://www.sportybet.com/api/ng/factsCenter/pcUpcomingEvents"
         "?sportId=sr:sport:2&marketId=219,223,225&pageSize=100&pageNum={page}")
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
_RULE = "──────────────────────────────────"


def _run_id(now: datetime) -> str:
    return f"OLPXDV-{now:%Y%m%d-%H%M}-{secrets.token_hex(3)}"


def nickname(name: str) -> str:
    """'Los Angeles Clippers' / 'LA Clippers' -> 'clippers'; 'Portland Trail Blazers' -> 'blazers'."""
    return (name or "").strip().lower().split()[-1] if name else ""


def sportybet_events() -> list[tuple[str, dict]]:
    """[(stage, event)] for SportyBet's NBA + NBA Preseason games."""
    out = []
    for page in range(1, 6):
        req = urllib.request.Request(_FEED.format(page=page),
                                     headers={"User-Agent": _UA, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            blob = json.loads(r.read())
        ts = (blob.get("data") or {}).get("tournaments") or []
        for t in ts:
            stage = TOURNAMENTS.get(t.get("id"))
            if stage:
                out += [(stage, e) for e in t.get("events", [])]
        if len(ts) == 0 or sum(len(t.get("events", [])) for t in ts) < 100:
            break
    return out


def _tip_utc(ms) -> datetime:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


def build(now: datetime, hours: int = HOURS) -> tuple[list[dict], list[str], int]:
    """(picks, notes, games scanned) for games tipping off in (now, now + hours]."""
    notes: list[str] = []
    try:
        evs = sportybet_events()
    except Exception as e:  # noqa: BLE001
        return [], [f"SportyBet NBA feed unavailable ({str(e)[:80]}) — no board"], 0
    evs = [(st, e) for st, e in evs if e.get("estimateStartTime")
           and now < _tip_utc(e["estimateStartTime"]) <= now + timedelta(hours=hours)]
    days = sorted({(_tip_utc(e["estimateStartTime"]) + d).date()
                   for _s, e in evs for d in (timedelta(hours=-6), timedelta(0))})
    espn = [g for d in days for g in ns.scoreboard(d, use_cache=False)]
    picks, scanned = [], 0
    for stage, e in evs:
        tip = _tip_utc(e["estimateStartTime"])
        hn, an = nickname(e.get("homeTeamName")), nickname(e.get("awayTeamName"))
        g = next((g for g in espn if nickname(g.home_name) == hn and nickname(g.away_name) == an
                  and abs((datetime.fromisoformat(g.tip.replace("Z", "+00:00")) - tip).total_seconds()) < 6 * 3600),
                 None)
        label = f"{e.get('homeTeamName')} v {e.get('awayTeamName')}"
        if g is None:
            notes.append(f"{label}: no ESPN game matched — skipped")
            continue
        ns.attach_odds(g, use_cache=False)
        if not (g.ml_home and g.ml_away):
            notes.append(f"{label}: no sharp line yet — skipped")
            continue
        scanned += 1
        sb_p = nv.sportybet_winner_chance(e)
        sharp_p = nv.devig(g.ml_home, g.ml_away)
        if sb_p is not None and abs(sb_p - sharp_p) > nv.MAX_ML_GAP:
            notes.append(f"{label}: SportyBet and the sharp line disagree by "
                         f"{abs(sb_p - sharp_p):.0%} on the winner — stale or mismatched, skipped")
            continue
        found, suspect = nv.candidates(e, g)
        for s in suspect:
            notes.append(f"{label}: {s['outcome']} @{s['price']:.2f} looks {s['ev']:+.0%} — "
                         f"too good to be true (stale line?), not picked")
        if not found:
            continue
        best = max(found, key=lambda r: (r["ev"], r["chance"]))
        picks.append({**best, "stage": stage, "event_id": e.get("eventId"),
                      "espn_id": g.id, "espn_date": g.tip[:10], "tip": tip.isoformat(),
                      "home": e.get("homeTeamName"), "away": e.get("awayTeamName"),
                      "pick": nv.display(best, e.get("homeTeamName"), e.get("awayTeamName")),
                      "sharp": {"ml_home": g.ml_home, "ml_away": g.ml_away,
                                "spread": g.spread, "total": g.total},
                      "code": None, "result": None, "score": None, "close_value": None})
    picks.sort(key=lambda p: p["tip"])
    return picks, notes, scanned


def book(picks: list[dict]) -> Optional[str]:
    """Own code per pick; returns one code for all picks (2+), or None."""
    from pipeline.sportybet_booking import create_booking_code
    sels = []
    for p in picks:
        sel = {"eventId": p["event_id"], "marketId": p["market_id"],
               "specifier": p["specifier"], "outcomeId": p["outcome_id"]}
        code, _url, _ = create_booking_code([sel])
        p["code"] = code
        sels.append(sel)
    if len(sels) > 1:
        code, _url, _ = create_booking_code(sels)
        return code
    return None


def grade(now: datetime) -> list[str]:
    """Grade every pending pick whose game tipped off 3+ hours ago."""
    notes = []
    for path in sorted(LEDGER_DIR.glob("nba_*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        changed = False
        for p in doc.get("picks", []):
            if p.get("result") or datetime.fromisoformat(p["tip"]) > now - timedelta(hours=3):
                continue
            day = datetime.fromisoformat(p["espn_date"]).date()
            g = next((x for x in ns.scoreboard(day, use_cache=False) if x.id == p["espn_id"]), None)
            if g is None or not g.completed:
                continue
            p["result"] = nv.settle(p, g.hs, g.as_)
            p["score"] = f"{g.hs}-{g.as_}"
            ns.attach_odds(g, use_cache=False)          # the closing line
            pc = nv.fair_chance(p["market_id"], p["specifier"], p["outcome"], g)
            p["close_value"] = round(pc * p["price"] - 1, 4) if pc else None
            changed = True
        if changed:
            path.write_text(json.dumps(doc, indent=1), encoding="utf-8")
            notes.append(f"graded {path.name}")
    return notes


def scorecard() -> str:
    """The paper record: regular-season picks only (preseason is a pipeline test)."""
    rows = []
    for path in sorted(LEDGER_DIR.glob("nba_*.json")):
        rows += [p for p in json.loads(path.read_text(encoding="utf-8")).get("picks", [])
                 if p.get("stage") == "regular" and p.get("result") in ("won", "lost")]
    if not rows:
        return "Paper record: no graded regular-season pick yet (the season opens 20 Oct)."
    w = sum(p["result"] == "won" for p in rows)
    ret = sum(p["price"] for p in rows if p["result"] == "won") - len(rows)
    cv = [p["close_value"] for p in rows if p.get("close_value") is not None]
    cvs = f" · beat the closing line on average by {100 * sum(cv) / len(cv):+.1f}%" if cv else ""
    return (f"Paper record (regular season): {len(rows)} picks · won {w} ({100 * w / len(rows):.0f}%) · "
            f"£1 each returned {ret:+.2f} ({100 * ret / len(rows):+.1f}%){cvs}")


def render(picks: list[dict], board_date: str, run_id: str, scanned: int,
           mega: Optional[str], notes: list[str]) -> str:
    L = ["##########OLP XDV · NBA #########", "🏀 PAPER BOARD — no real money (order 41)",
         "==================================", "",
         f"📅  {datetime.fromisoformat(board_date):%a %d %b %Y}   ·   tip-off = Lagos time (WAT)",
         f"Run ID: {run_id}", f"Games checked against the sharp line: {scanned}", "",
         "Only prices where SportyBet pays MORE than the fair price (the sharp line, margin",
         "removed). One pick per game. Value = chance × price − 1.", "", _RULE, "PICKS", _RULE, ""]
    if not picks:
        L.append("No SportyBet NBA price above the fair price today.")
    for p in picks:
        tip = datetime.fromisoformat(p["tip"]).astimezone(LAGOS)
        tag = " · PRESEASON (test only)" if p["stage"] == "preseason" else ""
        L += [f"{tip:%H:%M}  {p['home']} v {p['away']}{tag}",
              f"   {p['pick']} @{p['price']:.2f} · chance {p['chance']:.0%} · fair {p['fair_price']:.2f} "
              f"· value {p['ev']:+.1%}",
              f"   code {p['code'] or 'PENDING'}", ""]
    if mega:
        L += [f"All {len(picks)} picks on one slip: {mega}", ""]
    L += [_RULE, scorecard(), "",
          "Honest edge: the backtest found NO edge in picking NBA favourites (−7.8%). This board",
          "tests the one route left — SportyBet paying above the sharp price — on paper only."]
    flagged = [n for n in notes if "too good" in n or "disagree" in n]
    if flagged:
        L += ["", "Checked and left out:"] + [f" • {n}" for n in flagged[:8]]
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-send", action="store_true")
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--hours", type=int, default=HOURS)
    ap.add_argument("--resend", action="store_true", help="send again even if already sent")
    a = ap.parse_args()
    now = datetime.now(timezone.utc)
    for n in grade(now):
        print(f"  {n}")
    picks, notes, scanned = build(now, a.hours)
    for n in notes:
        print(f"  ⚠ {n}")
    first_tip = picks[0]["tip"] if picks else (now + timedelta(hours=6)).isoformat()
    board_date = datetime.fromisoformat(first_tip).astimezone(LAGOS).date().isoformat()
    ledger = LEDGER_DIR / f"nba_{board_date}.json"
    text_path = BOARD_DIR / f"nba_{board_date}.txt"
    if ledger.exists() and text_path.exists() and not a.rebuild:
        text = text_path.read_text(encoding="utf-8")
        print(f"  NBA board for {board_date} already built — resending it (use --rebuild to replace)")
    else:
        run_id = _run_id(now)
        mega = book(picks) if picks else None
        text = render(picks, board_date, run_id, scanned, mega, notes)
        LEDGER_DIR.mkdir(parents=True, exist_ok=True)
        BOARD_DIR.mkdir(parents=True, exist_ok=True)
        ledger.write_text(json.dumps({"date": board_date, "run_id": run_id,
                                      "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                      "mega_code": mega, "picks": picks}, indent=1), encoding="utf-8")
        text_path.write_text(text, encoding="utf-8")
    print(text)
    if a.no_send:
        return 0
    from output import notify
    gate = notify.board_gate(text)
    owner = (os.environ.get("TELEGRAM_OWNER_CHAT_ID", "").strip()
             or os.environ.get("TELEGRAM_CHAT_ID", "").strip())
    if gate or not owner:
        print(f"  NBA board NOT sent: {gate or 'no Architect chat configured'}")
        return 0
    doc = json.loads(ledger.read_text(encoding="utf-8")) if ledger.exists() else {}
    if doc.get("sent_at") and not (a.resend or a.rebuild):
        print(f"  NBA board for {board_date} already sent at {doc['sent_at']} — not sent twice")
        return 0
    ok, sent = notify.send_telegram(text, chat_id=owner)     # the Architect only
    for n in sent:
        print(f"  NBA board: {n}")
    if ok and doc:
        doc["sent_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        ledger.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
