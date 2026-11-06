"""
ICE HOCKEY BOARD runner (standing order 50, multi-sport rollout; engine/ice_hockey.py).

  python run_hockey.py              look: record every side of every game in the next 24 h,
                                    freeze new picks (paper until the live_from date)
  python run_hockey.py --grade      settle finished games (Flashscore) + write the scoreboard
  python run_hockey.py --report     print the scoreboard (and send it with --telegram)
  python run_hockey.py --dry        look without writing (prints what would be picked)

Since 2026-11-06 ice hockey is part of the ONE multi-sport board (Architect: "the hockey board ... should be
made a multi-sports board ... all the boards should be multi-sport"): run_multisport.py calls look() and
grade() here, started by .github/workflows/multisport.yml (Oracle VM clock). Files and format are unchanged
(output/ice_hockey/ih_<date>.json; the bots read them). This file still runs on its own. No steam (order 50).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from data import nhl_source as nhl  # noqa: E402
from engine import ice_hockey as ih  # noqa: E402

SCOREBOARD = ROOT / "data" / "ice_hockey" / "scoreboard.json"


def look(now: datetime, write: bool = True) -> str:
    rows = ih.fetch_sportybet()
    mb = ih.fetch_matchbook()
    try:
        model = ih.NHL(nhl.history(seasons=2), now.strftime("%Y-%m-%dT%H:%M:%SZ"))
    except Exception as e:  # noqa: BLE001 — no NHL history = exchange-priced picks only
        print(f"NHL model unavailable: {type(e).__name__}")
        model = None
    if not write:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            seen, added = ih.update(rows, mb, model, now, folder=Path(td), book=lambda s: None)
            for f in Path(td).glob("ih_*.json"):
                for p in json.loads(f.read_text(encoding="utf-8"))["picks"]:
                    print(f"  {p['comp']}: {p['home']} v {p['away']} | {p['pick']} @ {p['price']} "
                          f"chance {p['fair']:.0%} value {p['value']:+.1%} [{p['source']}]")
    else:
        seen, added = ih.update(rows, mb, model, now)
    line = (f"ice_hockey: SportyBet {len(rows)} games, Matchbook {len(mb)}, in window {seen}, new picks {added}, "
            f"NHL model {'on' if model else 'PENDING'}")
    return line


def grade(now: datetime) -> dict:
    n = 0
    for day, doc in ih.load_all():
        if all(g.get("result") for g in (doc.get("games") or {}).values()):
            continue
        events = ih.results(day, now.date())
        k = ih.grade_doc(doc, events, now)
        if k:
            ih.path_for(day).write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
            n += k
    sb = ih.scoreboard(ih.load_all())
    sb["updated"] = now.strftime("%Y-%m-%dT%H:%MZ")
    SCOREBOARD.parent.mkdir(parents=True, exist_ok=True)
    SCOREBOARD.write_text(json.dumps(sb, indent=1), encoding="utf-8")
    print(f"ice hockey grade: {n} games settled; picks {sb['picks']} (won {sb['won']}), pnl {sb['pnl']:+}")
    return sb


def report_text(sb: dict) -> str:
    lines = ["🏒 ICE HOCKEY (shadow week, paper)",
             f"Picks graded: {sb['picks']}, won {sb['won']}, return {sb['pnl']:+.2f} units",
             f"Value vs exchange close: {sb['clv_fair_avg']:+.1%}" if sb.get("clv_fair_avg") is not None
             else "Value vs exchange close: PENDING"]
    for mid, b in sorted((sb.get("all_sides_by_market") or {}).items()):
        lines.append(f"  market {mid}: {b['sides']} sides graded, return {b['pnl']:+.1f}"
                     + (f", model Brier {b['model_brier']}" if b.get("model_brier") is not None else ""))
    return "\n".join(lines)


def send(text: str) -> None:
    tok, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not tok or not chat:
        print("telegram: no token/chat, not sent")
        return
    data = urllib.parse.urlencode({"chat_id": chat, "text": text}).encode()
    urllib.request.urlopen(f"https://api.telegram.org/bot{tok}/sendMessage", data=data, timeout=20)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--grade", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--telegram", action="store_true")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    now = datetime.now(UTC)
    if a.grade or a.report:
        sb = grade(now)
        if a.report:
            text = report_text(sb)
            print(text)
            if a.telegram:
                send(text)
        return
    print(look(now, write=not a.dry))


if __name__ == "__main__":
    main()
