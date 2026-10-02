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


def _when(s: str):
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00").replace(".000", ""))
    except (ValueError, AttributeError):
        return None


def run(now: datetime | None = None, send: bool = True) -> str:
    now = now or datetime.now(timezone.utc)
    path = LEDGER_DIR / f"picks_{now.date().isoformat()}.json"
    if not path.exists():
        return "no picks ledger for today"
    doc = json.loads(path.read_text(encoding="utf-8"))
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
        return f"lineups: {ok} pick(s) confirmed OK, {waiting} awaiting XI, none flagged"
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
