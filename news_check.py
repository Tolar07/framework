"""
PRE-KICKOFF TEAM-NEWS CHECK (improvement #2, Architect 2026-10-02).

Runs every ~20 minutes through the day (.github/workflows/news.yml). For every
pick in today's ledger kicking off within the next LOOKAHEAD_MIN minutes it
reads the CONFIRMED lineup from FotMob and re-assesses the pick:
  * key players missing from the side the pick depends on, or
  * a ROTATED XI (confirmed XI worth far less than the XI predicted when the
    board was built).
Flagged picks are sent to Telegram with every slip (acca / 50%+ / mega) they
sit in, so the Architect can swap or skip them before kickoff. Each pick is
checked once; results are written back into output/picks/picks_<date>.json.
Stdlib only (no numpy) so the job stays light.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from data import fotmob
from engine import team_news as tn
from engine.picks_ledger import LEDGER_DIR

LOOKAHEAD_MIN = 100
LAST_CALL_MIN = 20      # inside this, record 'no confirmed XI' rather than wait
CLOSE_WINDOW_MIN = 35   # closing price = SportyBet's price within 35 min of kickoff

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
_LADDER_IDS = ("1,10,11,12,13,14,16,18,19,20,21,23,24,25,26,29,30,31,32,33,34,"
               "36,37,546,547,548")
_TOURNAMENT = ("https://www.sportybet.com/api/ng/factsCenter/pcUpcomingEvents"
               "?sportId=sr:sport:1&marketId=" + _LADDER_IDS +
               "&pageSize=100&pageNum=1&tournamentId={tid}")


def _when(s: str):
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00").replace(".000", ""))
    except (ValueError, AttributeError):
        return None


def _price(event: dict, mk: dict):
    for m in event.get("markets", []):
        if mk.get("id") is not None and str(m.get("id")) != str(mk["id"]):
            continue
        if mk.get("id") is None and m.get("desc") != mk.get("desc"):
            continue
        if (m.get("specifier") or "") != (mk.get("spec") or ""):
            continue
        for o in m.get("outcomes", []):
            if o.get("desc") == mk.get("outcome") and o.get("odds"):
                try:
                    return float(o["odds"])
                except ValueError:
                    return None
    return None


def capture_closing(doc: dict, now: datetime) -> int:
    """CLOSING-LINE VALUE (improvement #5): for picks kicking off within
    CLOSE_WINDOW_MIN, record SportyBet's current price and the CLV vs the
    board's entry price — CLV% = (entry / closing - 1) x 100; positive means
    the market moved our way (the pick shortened after we took it)."""
    import urllib.request
    due = [s for s in doc["singles"]
           if s.get("closing_price") is None and s.get("sb_event_id") and s.get("sb_tid")
           and s.get("sb_market") and s.get("price") and s.get("kickoff_utc")
           and _when(s["kickoff_utc"])
           and now <= _when(s["kickoff_utc"]) <= now + timedelta(minutes=CLOSE_WINDOW_MIN)]
    done = 0
    for tid in sorted({s["sb_tid"] for s in due}):
        try:
            req = urllib.request.Request(_TOURNAMENT.format(tid=tid),
                                         headers={"User-Agent": _UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=25) as r:
                data = json.loads(r.read().decode("utf-8", "replace")).get("data") or {}
        except Exception:  # noqa: BLE001 — try again next run
            continue
        events = {e.get("eventId"): e for t in data.get("tournaments", []) for e in t.get("events", [])}
        for s in due:
            ev = events.get(s["sb_event_id"]) if s["sb_tid"] == tid else None
            close = _price(ev, s["sb_market"]) if ev else None
            if close:
                s["closing_price"] = close
                s["clv"] = round((s["price"] / close - 1) * 100, 2)
                done += 1
    return done


def run(now: datetime | None = None, send: bool = True) -> str:
    now = now or datetime.now(timezone.utc)
    path = LEDGER_DIR / f"picks_{now.date().isoformat()}.json"
    if not path.exists():
        return "no picks ledger for today"
    doc = json.loads(path.read_text(encoding="utf-8"))
    closed = capture_closing(doc, now)
    flagged, ok, waiting = [], 0, 0
    for s in doc["singles"]:
        if s.get("lineup_check") or not s.get("fotmob_id") or not s.get("kickoff_utc"):
            continue
        ko = _when(s["kickoff_utc"])
        if ko is None or not (now <= ko <= now + timedelta(minutes=LOOKAHEAD_MIN)):
            continue
        try:
            news = fotmob.team_news(s["fotmob_id"])
        except Exception:  # noqa: BLE001 — try again next run
            continue
        if not news or news.get("lineup_type") != "confirmed":
            if ko - now <= timedelta(minutes=LAST_CALL_MIN):
                s["lineup_check"] = {"level": "NO XI", "note": "no confirmed lineup published",
                                     "at": now.strftime("%H:%MZ")}
            else:
                waiting += 1
            continue
        res = tn.assess(s["market"], news, s.get("predicted_xi"))
        s["lineup_check"] = {"level": res["level"], "note": res["note"],
                             "at": now.strftime("%H:%MZ")}
        if res["level"] in ("CAUTION", "RISK"):
            flagged.append(s)
        else:
            ok += 1
    path.write_text(json.dumps(doc, indent=1), encoding="utf-8")

    if not flagged:
        return (f"lineups: {ok} pick(s) confirmed OK, {waiting} awaiting XI, none flagged; "
                f"closing prices captured: {closed}")
    slips = {}
    for kind in ("safe3", "accas", "megas"):
        for slip in doc.get(kind, []):
            for s in flagged:
                if s["fixture"] in slip["legs"]:
                    slips.setdefault(s["fixture"], []).append(
                        f"{slip['name']} ({slip.get('code') or 'no code'})")
    lines = [f"⚠ TEAM NEWS — confirmed lineups, {now.strftime('%H:%M')} UTC",
             f"{len(flagged)} pick(s) weakened · {ok} confirmed OK", ""]
    for s in flagged:
        lines.append(f"{s['lineup_check']['level']}: {s['fixture']} — {s['pick']} "
                     f"@{s.get('price') or '?'} (code {s.get('code') or '—'})")
        lines.append(f"   {s['lineup_check']['note']}")
        if slips.get(s["fixture"]):
            lines.append(f"   in: {', '.join(slips[s['fixture']])}")
    lines.append("")
    lines.append("Consider skipping these picks or the slips that carry them. "
                 "Nothing is changed automatically — you decide.")
    msg = "\n".join(lines)
    if send:
        from output import notify
        ok_sent, notes = notify.deliver(msg, save_to=None)
        print("\n".join(notes))
    return msg


if __name__ == "__main__":
    print(run(send="--no-send" not in sys.argv))
