"""
THE MULTI-SPORT BOARD runner (standing order 50; engine/multisport.py). Every rollout sport, ice hockey
included (Architect 2026-11-06: "all the boards should be multi-sport"): hockey keeps its own NHL model and
files (engine/ice_hockey.py via run_hockey.py, output/ice_hockey/ih_<date>.json), run, graded and reported
here with the rest.

  python run_multisport.py                 look: every sport, every side of every game in the next
                                           24 h recorded, new value picks frozen (paper until live)
  python run_multisport.py --grade         settle finished games, teach each sport's Elo from every
                                           finished game of the last 7 days, write the scoreboards
  python run_multisport.py --report        grade + print (and --telegram: send) the gate report
  python run_multisport.py --sport tennis  one sport only;  --dry  look without writing

Started by .github/workflows/multisport.yml (Oracle VM clock). No steam (order 50).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from engine import multisport as ms  # noqa: E402
from engine import home_edge_shadow as hes  # noqa: E402

import run_hockey as rh  # noqa: E402

HOCKEY = "ice_hockey"
ALL_SPORTS = [HOCKEY, *ms.SPORTS]


def look(sport: str, now: datetime, write: bool = True) -> str:
    if sport == HOCKEY:
        return rh.look(now, write)
    rows = ms.fetch_sportybet(sport)
    mb = ms.fetch_matchbook(sport)
    elo = ms.load_elo(sport)
    if write:
        seen, added = ms.update(sport, rows, mb, elo, now)
    else:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            seen, added = ms.update(sport, rows, mb, elo, now, folder=Path(td), book=lambda s: None)
            for f in Path(td).rglob("ms_*.json"):
                for p in json.loads(f.read_text(encoding="utf-8"))["picks"]:
                    print(f"  {p['comp']}: {p['home']} v {p['away']} | {p['pick']} @ {p['price']} "
                          f"chance {p['fair']:.0%} value {p['value']:+.1%} [{p['source']}]")
    return (f"{sport}: SportyBet {len(rows)} games, Matchbook {len(mb)}, in window {seen}, "
            f"new picks {added}, Elo rated {len(elo['ratings'])}")


def grade(sport: str, now: datetime) -> dict:
    if sport == HOCKEY:
        return rh.grade(now)
    today = now.date()
    days = [today - timedelta(days=k) for k in range(7, -1, -1)]
    events = ms.results_days(sport, days, today)
    elo = ms.load_elo(sport)
    shadow_st = hes.load(sport)
    if sport in hes.EDGE:                       # record-only candidate, scored before the live Elo learns
        hes.learn(sport, shadow_st, events, elo)
        hes.save(sport, shadow_st)
    learned = ms.learn(elo, events)
    ms.save_elo(sport, elo)
    n = 0
    for day, doc in ms.load_all(sport):
        if all(g.get("result") for g in (doc.get("games") or {}).values()):
            continue
        k = ms.grade_doc(sport, doc, events, now)
        if k:
            ms.path_for(sport, day).write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
            n += k
    sb = ms.scoreboard(ms.load_all(sport), elo)
    if sport in hes.EDGE:
        sb["home_edge_shadow"] = hes.summary(sport, shadow_st)
    sb.update({"updated": now.strftime("%Y-%m-%dT%H:%MZ"), "games_settled_now": n, "elo_learned_now": learned})
    p = ms.DATA_DIR / sport / "scoreboard.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(sb, indent=1), encoding="utf-8")
    return sb


def report_line(sport: str, sb: dict) -> str:
    clv = f", value vs exchange close {sb['clv_fair_avg']:+.1%}" if sb.get("clv_fair_avg") is not None else ""
    e = sb.get("elo") or {}
    brier = f", Elo Brier {e['walk_forward_brier']} on {e['scored']}" if e.get("walk_forward_brier") is not None else ""
    sides = sum(b["sides"] for b in (sb.get("all_sides_by_market") or {}).values())
    return (f"{sport}: picks {sb['picks']} (won {sb['won']}), return {sb['pnl']:+.2f}u{clv}; "
            f"{sides} sides graded{brier}")


def send(text: str) -> None:
    tok, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not tok or not chat:
        print("telegram: no token/chat, not sent")
        return
    data = urllib.parse.urlencode({"chat_id": chat, "text": text}).encode()
    urllib.request.urlopen(f"https://api.telegram.org/bot{tok}/sendMessage", data=data, timeout=20)  # noqa: S310


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sport", choices=sorted(ALL_SPORTS), default=None)
    ap.add_argument("--grade", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--telegram", action="store_true")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    now = datetime.now(UTC)
    sports = [a.sport] if a.sport else list(ALL_SPORTS)
    lines = []
    for s in sports:
        try:
            if a.grade or a.report:
                lines.append(report_line(s, grade(s, now)))
            else:
                lines.append(look(s, now, write=not a.dry))
        except Exception as e:  # noqa: BLE001 — one sport failing never stops the others
            lines.append(f"{s}: PENDING ({type(e).__name__}: {str(e)[:100]})")
        print(lines[-1], flush=True)
    if a.report and a.telegram:
        send("MULTI-SPORT BOARD, every sport incl. ice hockey (paper until each sport's live date)\n" + "\n".join(lines))


if __name__ == "__main__":
    main()
