"""
SHARP LIST — the parallel selection the Architect ordered on 2026-10-14: "run the
sharp value list in parallel with the current board".

WHAT IT IS
  A second, independent list built from one rule only — take an outcome when
  SportyBet pays MORE than the Betfair Exchange's margin-free price for it
  (engine/sharp_value.py holds the rule and the thresholds). It is scored,
  booked and graded exactly like the board, on the same fixtures, the same day,
  from the same feeds. It never touches the board: not a pick, not an acca, not
  a code. Two lists, one grader, and in a few weeks the price question is
  settled by data instead of argument.

WHY
  332 graded board singles to 13 Oct: stated 78.0%, landed 78.0% (calibration
  error 0.0 points) at an average price of 1.242, which needs 80.5% to break
  even -> -3.4%. Over 272 legs measured against SportyBet's OWN closing price
  the mean CLV is -0.04% +/- 0.15%: the board bets the closing line. The
  prediction is sound; the price is not.

COVERAGE, HONESTLY
  The exchange prices 1X2, double chance and Over/Under 2.5, in the leagues
  football-data gives a division code (19 of SportyBet's 32 here — the cups,
  the UNL and the new-leagues countries have none, so nothing is ever produced
  for them). A fixture it does not price produces nothing — never a guess
  (HR35). Most days the list is short, and some days it is empty. That is the
  rule working, not a missing list.

    python monitor/sharp_list.py --target-date 2026-10-15      build + book
    python monitor/sharp_list.py --target-date 2026-10-15 --no-book
    python monitor/sharp_list.py --target-date 2026-10-15 --telegram
    python monitor/sharp_list.py --grade                        grade + record
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import sharp_value as sv  # noqa: E402
from pipeline import sharp  # noqa: E402
from pipeline.odds_sportybet import parse_markets  # noqa: E402

STORE = ROOT / "data" / "sharp"


def _utc(ms: int) -> dt.datetime:
    return dt.datetime.fromtimestamp(ms / 1000, dt.UTC)


def build(target: str, book: bool = True) -> dict:
    """Scan every fixture of `target` the exchange prices and keep the outcomes
    that beat its fair price. Returns the saved document."""
    from pipeline.sportybet_booking import _event_index, code_for_legs

    run_id = "SHARP-" + uuid.uuid4().hex[:8]
    fetched = dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    flags: list[str] = []

    index = _event_index()
    if not index:
        flags.append("NO DATA — PENDING: SportyBet feed unavailable")
        index = {}
    fair, fair_flags = sharp.fair_book()
    flags += fair_flags
    if not fair:
        flags.append("NO DATA — PENDING: no Betfair Exchange prices in fixtures.csv")

    picks: list[dict] = []
    suspect: list[dict] = []
    scanned = priced = 0
    for (league, home, away), ev in sorted(index.items()):
        ms = ev.get("estimateStartTime")
        if not ms or _utc(ms).strftime("%Y-%m-%d") != target:
            continue
        scanned += 1
        f = sv.fair_row(fair, league, home, away)
        if not f:
            continue                      # exchange does not price it — no guess
        rows = sv.scan(parse_markets(ev), f)
        if not rows:
            continue
        priced += 1
        base = {"league": league, "home": home, "away": away,
                "fixture": f"{home} v {away} ({league})",
                "kickoff": _utc(ms).strftime("%Y-%m-%dT%H:%M:%SZ")}
        for r in sv.suspect(rows):
            suspect.append({**base, **r})
        best = sv.pick(rows)
        if not best:
            continue
        code = url = None
        if book:
            code, url = code_for_legs(index, [(league, home, away, best["key"])])
        picks.append({**base, **best, "code": code, "url": url,
                      "result": None, "ft": None, "run_id": run_id})

    doc = {"date": target, "run_id": run_id, "fetched_utc": fetched,
           "rule": {"min_ev": sv.MIN_EV, "band": list(sv.BAND), "max_ev": sv.MAX_EV},
           "source": "SportyBet live prices vs Betfair Exchange fair odds "
                     "(football-data fixtures.csv, proportional de-vig)",
           "fixtures_on_day": scanned, "fixtures_priced_by_exchange": priced,
           "picks": picks, "suspect": suspect, "flags": flags}
    STORE.mkdir(parents=True, exist_ok=True)
    (STORE / f"sharp_{target}.json").write_text(json.dumps(doc, indent=1), encoding="utf-8")
    return doc


def render(doc: dict) -> str:
    """The list as the Architect reads it. No pick is ever invented: an empty
    list says so (HR35)."""
    out = [f"SHARP VALUE LIST — {doc['date']} (parallel test, not the board)",
           f"Run {doc['run_id']} · fetched {doc['fetched_utc']}",
           f"Rule: SportyBet price must beat the Betfair Exchange's fair price by "
           f"{doc['rule']['min_ev']*100:.0f}%+, price {doc['rule']['band'][0]:.2f}-"
           f"{doc['rule']['band'][1]:.2f}. No 'most likely outcome' floor.",
           f"{doc['fixtures_on_day']} fixture(s) on the day · "
           f"{doc['fixtures_priced_by_exchange']} priced by the exchange · "
           f"{len(doc['picks'])} clear the bar", ""]
    if not doc["picks"]:
        out.append("NO PICK — PENDING: nothing on this day beats the sharp price. "
                   "That is the rule working, not a missing list.")
    for p in doc["picks"]:
        out.append(f"{p['kickoff'][11:16]}  {p['fixture']}")
        out.append(f"   {p['outcome']}  @ {p['price']:.2f}   fair {p['fair_price']:.2f} "
                   f"(exchange {p['sharp_p']*100:.1f}%)   value +{p['sharp_ev']*100:.1f}%")
        out.append(f"   code: {p['code'] or 'PENDING'}")
    if doc["suspect"]:
        out += ["", f"NOT PICKED — {len(doc['suspect'])} price(s) too good to be true "
                    f"(> {doc['rule']['max_ev']*100:.0f}% over fair: a stale line or a "
                    f"mismatched fixture):"]
        for s in doc["suspect"][:10]:
            out.append(f"   {s['fixture']} · {s['outcome']} @ {s['price']:.2f} "
                       f"vs fair {s['fair_price']:.2f}")
    for f in doc["flags"]:
        out.append(f"   flag: {f}")
    return "\n".join(out)


def grade(today: str | None = None) -> str:
    """Grade every saved list from Flashscore and report the running record
    beside what the sharp edge predicted."""
    from data.flashscore_results import find_result, results_since
    from engine.picks_ledger import _settle, _settle_90_bounds

    today = today or dt.date.today().isoformat()
    events = results_since(7)
    graded: list[dict] = []
    for path in sorted(STORE.glob("sharp_*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        if doc["date"] > today:
            continue
        changed = 0
        for p in doc["picks"]:
            if p["result"] in (None, "no-90min-result"):
                ev = find_result(events, p["home"], p["away"], p["kickoff"] or doc["date"])
                if ev and ev["finished_regular"]:
                    p["ft"] = f'{ev["fthg"]}-{ev["ftag"]}'
                    p["result"] = _settle(p["key"], ev["fthg"], ev["ftag"])
                    changed += 1
                elif ev and ev["finished_other"]:
                    res = _settle_90_bounds(p["key"], ev) or "no-90min-result"
                    if res != p["result"]:
                        p["result"] = res
                        changed += 1
            graded.append(p)
        if changed:
            path.write_text(json.dumps(doc, indent=1), encoding="utf-8")

    done = [p for p in graded if p["result"] in ("won", "lost", "void")]
    if not done:
        return (f"SHARP LIST record: {len(graded)} pick(s) saved, 0 graded — PENDING. "
                f"Nothing to report yet.")
    won = sum(p["result"] == "won" for p in done)
    void = sum(p["result"] == "void" for p in done)
    staked = len(done) - void
    ret = sum((p["price"] - 1) if p["result"] == "won" else 0 if p["result"] == "void" else -1
              for p in done)
    exp = sum(p["sharp_ev"] for p in done) / len(done)
    price = sum(p["price"] for p in done) / len(done)
    return (f"SHARP LIST record: {len(done)} graded of {len(graded)} · {won} won, "
            f"{len(done)-won-void} lost, {void} void · average price {price:.2f} · "
            f"return {ret:+.2f}u on {staked}u staked ({(ret/staked*100 if staked else 0):+.1f}%) · "
            f"the sharp edge taken averaged {exp*100:+.1f}%")


def _send(body: str) -> None:
    """To the Architect's own chat only (order 33) — never a subscriber. A
    failed send is said out loud and never fails the run."""
    from output.notify import send_architect
    ok, notes = send_architect(body)
    print(f"telegram: {'sent' if ok else 'NOT SENT'}" + (f" ({'; '.join(notes)})" if notes else ""))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="the parallel sharp-value list")
    ap.add_argument("--target-date", default=None, help="YYYY-MM-DD (default: tomorrow UTC)")
    ap.add_argument("--no-book", action="store_true", help="skip SportyBet booking codes")
    ap.add_argument("--grade", action="store_true", help="grade saved lists and report")
    ap.add_argument("--telegram", action="store_true",
                    help="also send the list to the Architect's own chat (order 33)")
    a = ap.parse_args(argv)
    if a.grade:
        report = grade()
        print(report)
        if a.telegram:
            _send(report)
        return 0
    target = a.target_date or (dt.datetime.now(dt.UTC) + dt.timedelta(days=1)).strftime("%Y-%m-%d")
    doc = build(target, book=not a.no_book)
    text = render(doc)
    print(text)
    # A day with nothing to show is recorded in data/sharp/ and printed here,
    # but not sent: a daily "NO PICK" message would train the Architect to
    # ignore the one that matters. A pick, or a suspect price, is sent.
    if a.telegram and (doc["picks"] or doc["suspect"]):
        _send(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
