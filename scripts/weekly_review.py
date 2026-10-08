"""
WEEKLY RESULTS REVIEW — the olp-xdv-10-ceo agent's report, run automatically
every Monday by .github/workflows/weekly.yml (Architect 2026-10-04: "put all
the agents to work").

From the picks ledger (graded from Flashscore), the last 7 days:
  * singles W-L, hit rate and profit at 1 unit — overall, by MARKET FAMILY
    and by LEAGUE (worst first, so what is losing is read first);
  * every slip kind landed: 50%+ accas, accas, alt-market accas, megas;
  * the learning corrections in force (engine/learning.py, order 22);
  * PROPOSALS for the Architect, from fixed rules — a family or league with
    10+ results over 3+ match days running 8+ pts below what we said is
    named for review; nothing is changed automatically (the Architect
    decides; learning already trims it within its ±10 pt cap).

Read-only. Never raises from the CLI.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

PICKS = ROOT / "output" / "picks"
REVIEW_GAP_PP = 0.08     # hit rate this far below the stated chance -> review
MIN_N, MIN_DAYS = 10, 3  # bar for PROPOSING a review; automatic learning needs more (order 22)


def _docs(days: int, today: str, picks: Path) -> list[dict]:
    since = (date.fromisoformat(today) - timedelta(days=days)).isoformat()
    out = []
    for path in sorted(picks.glob("picks_*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        if since <= doc["date"] < today:
            out.append(doc)
    return out


def _seg_line(name: str, rows: list[dict]) -> tuple[float, str]:
    w = sum(r["result"] == "won" for r in rows)
    n = len(rows)
    said = sum(float(r.get("chance") or 0) for r in rows) / n
    pl = sum(((r.get("price") or 1.0) - 1.0) if r["result"] == "won" else -1.0 for r in rows)
    gap = w / n - said
    return gap, f"{name}: {w}/{n} won ({w / n:.0%} vs {said:.0%} said) · {pl:+.2f}u"


def review(days: int = 7, today: str | None = None, picks: Path = PICKS) -> str:
    from engine import learning
    today = today or date.today().isoformat()
    docs = _docs(days, today, picks)
    singles = [dict(s, _day=(s.get("kickoff") or d["date"])[:10])
               for d in docs for s in d.get("singles", [])
               if s.get("result") in ("won", "lost") and s.get("chance") is not None]
    if not singles:
        return (f"📈 WEEKLY REVIEW · to {today}\nNo graded singles in the last {days} days "
                f"— nothing to review yet.")
    _gap, overall = _seg_line(f"All singles ({len(docs)} board day(s))", singles)
    L = [f"📈 WEEKLY REVIEW · {days} days to {today}", overall]
    proposals = []
    for title, keyf in (("By market family", lambda s: learning.family(s.get("market"))),
                        ("By league", lambda s: s.get("league") or "?")):
        segs: dict = defaultdict(list)
        for s in singles:
            segs[keyf(s)].append(s)
        lines = sorted((_seg_line(k, v) + (k, v) for k, v in segs.items()),
                       key=lambda t: t[0])
        L.append(f"{title} (worst first):")
        L += [f"  {line}" for _g, line, _k, _v in lines[:8]]
        for gap, _line, k, v in lines:
            if (len(v) >= MIN_N and len({s["_day"] for s in v}) >= MIN_DAYS
                    and gap <= -REVIEW_GAP_PP):
                proposals.append(f"{k}: won {gap * 100:+.0f} pts vs what we said over "
                                 f"{len(v)} picks — review it (learning is already trimming it)")
    sw = [s for s in singles if s.get("orig_result") in ("won", "lost")]
    if sw:
        L.append(f"Switched picks (order 32): {sum(s['result'] == 'won' for s in sw)}/{len(sw)} "
                 f"won; the original picks would have won "
                 f"{sum(s['orig_result'] == 'won' for s in sw)}/{len(sw)}")
    for kind, label in (("safe3", "50%+ accas"), ("accas", "Accas"),
                        ("alts", "Alt-market accas"), ("megas", "Megas")):
        slips = [x for d in docs for x in d.get(kind, []) if x.get("result") in ("won", "lost")]
        if slips:
            L.append(f"{label}: {sum(x['result'] == 'won' for x in slips)}/{len(slips)} landed")
    try:
        L.append(learning.summary(learning.learn(picks, today=today)))
    except Exception as e:  # noqa: BLE001
        L.append(f"Learning: unavailable ({e})")
    # The losing-market watch, its proposals and your /note corrections
    # (order 39, engine/loss_watch; memory/proposals.json, memory/corrections.csv)
    try:
        from engine import loss_watch
        L.append(loss_watch.summary(loss_watch.watch(picks, today=today)))
        L.append(loss_watch.notes_line(loss_watch.open_notes()) or
                 "Your /note corrections: none waiting.")
    except Exception as e:  # noqa: BLE001
        L.append(f"Losing-market watch: unavailable ({e})")
    L.append("PROPOSALS for the Architect (nothing is changed automatically):")
    L += [f"  • {p}" for p in proposals] or ["  • none — no family or league is running "
                                             f"{REVIEW_GAP_PP * 100:.0f}+ pts below what we said "
                                             f"on {MIN_N}+ results over {MIN_DAYS}+ days"]
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="OLP XDV weekly results review")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--no-send", action="store_true")
    a = ap.parse_args(argv)
    try:
        text = review(a.days)
    except Exception as e:  # noqa: BLE001
        text = f"📈 WEEKLY REVIEW — could not be built ({e})"
    print(text)
    if not a.no_send:
        from output import notify
        sent, notes = notify.send_architect(text)    # Architect only (order 33)
        print("review sent" if sent else "review NOT sent")
        print("\n".join(notes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
