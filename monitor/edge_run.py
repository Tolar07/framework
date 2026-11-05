"""
EDGE RUN — about every 30 minutes (the Oracle VM clock starts edge.yml): SportyBet's whole
football + basketball list beside Matchbook's exchange, folded into the edge book
(engine/edge_book.py: fair exchange chance per side, first and last look, the gap board),
then the edge scoreboard and the residual model rewritten (monitor/edge_scoreboard.py).
RECORDED ONLY — nothing here picks, stakes or blocks.

    python monitor/edge_run.py              look + scoreboard (+ save inside Actions)
    python monitor/edge_run.py --score      scoreboard only
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from engine import edge_book as eb  # noqa: E402
from engine import exchange as ex  # noqa: E402
from engine import universe as uv  # noqa: E402

BASKETBALL_MARKETS = ("219", "223", "225", "68")     # winner, handicap, total, 1st-half total
SAVE_PATHS = ("data/edge", "output/world_basketball", "memory/edge_scoreboard.json", "memory/residual_model.json",
              "backtest/EDGE_SCOREBOARD.md")


def basketball_sides(event: dict) -> dict[str, float]:
    out: dict[str, float] = {}
    for m in event.get("markets") or []:
        mid = str(m.get("id"))
        if mid not in BASKETBALL_MARKETS or m.get("status") not in (None, 0, "0"):
            continue
        spec = m.get("specifier") or ""
        for o in m.get("outcomes") or []:
            x = ex._f(o.get("odds"))
            if x and x > 1.0:
                out[f"B:{mid}|{spec}|{(o.get('desc') or '').strip()}"] = x
    return out


def sb_rows(now: datetime, get=None) -> tuple[list[dict], list[str]]:
    """Every listed SportyBet game with its side prices, both sports."""
    from monitor import universe_sweep as us
    get = get or us._get
    cov = us.covered_ids()
    rows, notes = [], []
    for sport in ("football", "basketball"):
        sid = uv.SPORTS[sport][0]
        markets = uv.SPORTS["football"][1] if sport == "football" else ",".join(BASKETBALL_MARKETS)
        n = 0
        try:
            for page in range(1, 60):
                blob = get(us._FEED.format(sport=sid, markets=markets, page=page))
                ts = (blob.get("data") or {}).get("tournaments") or []
                k = 0
                for t in ts:
                    for e in t.get("events", []):
                        k += 1
                        if not (e.get("estimateStartTime") and e.get("eventId")):
                            continue
                        ko = datetime.fromtimestamp(e["estimateStartTime"] / 1000, tz=UTC)
                        sides = (uv.prices("football", e).get("ladder") or {}) if sport == "football" \
                            else basketball_sides(e)
                        if not sides:
                            continue
                        cat = (e.get("sport") or {}).get("category") or {}
                        rows.append({"sport": sport, "id": e["eventId"], "home": e.get("homeTeamName"),
                                     "away": e.get("awayTeamName"), "ko": ko.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                     "comp": t.get("name"), "country": cat.get("name"),
                                     "covered": t.get("id") in cov[sport], "sides": sides})
                        n += 1
                if not ts or k < 100:
                    break
            notes.append(f"SportyBet {sport} {n}")
        except Exception as e:  # noqa: BLE001 — one sport failing never stops the other
            notes.append(f"SportyBet {sport} unavailable ({str(e)[:60]})")
    return rows, notes


def look(now: datetime) -> str:
    rows, notes = sb_rows(now)
    try:
        events = ex.fetch_events()
    except Exception as e:  # noqa: BLE001
        return " · ".join([*notes, f"Matchbook unavailable ({str(e)[:60]}) — nothing recorded"])
    notes.append(f"Matchbook {len(events)} events")
    days = {(now + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(4)}
    days |= {r["ko"][:10] for r in rows}
    docs = {d: eb.load(d) for d in sorted(days)}
    stats = eb.update(docs, rows, events, now)
    for doc in docs.values():
        if doc["events"]:
            eb.save(doc)
    notes.append(f"matched {stats['matched']} games, {stats['sides']} sides, {stats['new_gaps']} new gaps")
    try:      # the paper world-basketball board (engine/world_basketball.py, Architect 2026-11-05)
        from engine import world_basketball as wb
        notes.append(f"world basketball: {wb.update(rows, events, now)} new picks")
    except Exception as e:  # noqa: BLE001 — the edge book is saved either way
        notes.append(f"world basketball skipped ({str(e)[:60]})")
    moved = eb.finalize(now)
    if moved:
        notes.append(f"finished days to git: {', '.join(moved)}")
    return " · ".join(notes)


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], capture_output=True, text=True)  # noqa: S603,S607 (fixed git args)


def persist(now: datetime) -> str:
    if os.environ.get("GITHUB_ACTIONS") != "true":
        return "not saved (outside GitHub Actions)"
    _git("add", *[p for p in SAVE_PATHS if (ROOT / p).exists()])
    if _git("diff", "--staged", "--quiet").returncode == 0:
        return "nothing to save"
    _git("commit", "-q", "-m", f"edge {now:%Y-%m-%d %H:%M} [skip ci]")
    for _ in range(3):
        if _git("push", "-q", "origin", "HEAD:main").returncode == 0:
            return "saved"
        if _git("pull", "-q", "--rebase", "origin", "main").returncode != 0:
            _git("rebase", "--abort")
            break
    return "NOT SAVED — main moved and a file conflicted; the next run looks again"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="OLP XDV edge run")
    ap.add_argument("--score", action="store_true", help="rewrite the scoreboard only")
    a = ap.parse_args(argv)
    now = datetime.now(UTC)
    if not a.score:
        print(f"[{now:%H:%M}Z] {look(now)}")
    from monitor import edge_scoreboard
    print(edge_scoreboard.build(now))
    print(persist(now))
    return 0


if __name__ == "__main__":
    sys.exit(main())
