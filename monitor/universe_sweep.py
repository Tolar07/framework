"""
UNIVERSE SWEEP — every 3 hours: read SportyBet's whole football and
basketball list, keep each game's first/last pre-kick-off prices, grade the
games that have finished from Flashscore, and archive them (engine/universe.py).
Once a day it rewrites backtest/UNIVERSE_STUDY.md and the paper book
(backtest/PAPER_BOOK.md: the system's own £1 paper bets), and collects FotMob's
post-match stats of the last 3 days' rated fixtures (data/match_stats.py) for
backtest/MATCH_STATS_STUDY.md.

The prices of games not yet played live in data/cache/universe/ (the
universe.yml Actions cache — not git: thousands of games a day would bloat
the repo); a game is written to git once, when graded, as one line in
data/universe/graded_<month>.jsonl. Losing the cache loses only the
ungraded games of the next day or two. Git is touched only inside Actions.

    python monitor/universe_sweep.py            sweep + grade (+ study once a day)
    python monitor/universe_sweep.py --study    rewrite the study only
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from engine import universe as uv  # noqa: E402

_FEED = ("https://www.sportybet.com/api/ng/factsCenter/pcUpcomingEvents"
         "?sportId={sport}&marketId={markets}&pageSize=100&pageNum={page}")
_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/124.0 Safari/537.36", "Accept": "application/json"}
STUDY_HOUR = 6          # UTC: studies + the paper-book note on the first sweep at/after this hour each day


def covered_ids() -> dict[str, set[str]]:
    """SportyBet tournament ids the framework prices, per sport."""
    import run_nba
    from pipeline.odds_sportybet import SPORTYBET_TOURNAMENT_ID
    return {"football": set(SPORTYBET_TOURNAMENT_ID.values()), "basketball": set(run_nba.TOURNAMENTS)}


def _get(url: str) -> dict:
    for i in range(3):
        try:
            req = urllib.request.Request(url, headers=_UA)  # noqa: S310 (fixed https URL)
            with urllib.request.urlopen(req, timeout=40) as r:  # noqa: S310 (fixed https URL)
                return json.loads(r.read())
        except Exception:  # noqa: BLE001 — retry, then report
            time.sleep(2 + 2 * i)
    raise RuntimeError("SportyBet feed unavailable")


def fetch(sport: str, now: datetime, covered: set[str]) -> list[dict]:
    sid, markets, _fs = uv.SPORTS[sport]
    rows = []
    for page in range(1, 60):
        blob = _get(_FEED.format(sport=sid, markets=markets, page=page))
        ts = (blob.get("data") or {}).get("tournaments") or []
        n = 0
        for t in ts:
            for e in t.get("events", []):
                n += 1
                if e.get("estimateStartTime") and e.get("eventId"):
                    rows.append(uv.event_row(sport, e, t, covered, now))
        if not ts or n < 100:
            break
    return rows


def sweep(now: datetime) -> str:
    from data import flashscore_results as fr
    pending = uv.load_pending()
    cov = covered_ids()
    notes = []
    for sport in uv.SPORTS:
        try:
            rows = fetch(sport, now, cov[sport])
            notes.append(f"{sport}: {len(rows)} listed, {uv.update(pending, rows)} new")
        except Exception as e:  # noqa: BLE001 — one sport failing never stops the other
            notes.append(f"{sport}: SportyBet unavailable ({str(e)[:60]})")
    index = {}
    for sport, (_sid, _m, fs_sport) in uv.SPORTS.items():
        try:
            index[sport] = uv.ResultIndex(fr.results_since(7, sport=fs_sport))
        except Exception as e:  # noqa: BLE001
            index[sport] = uv.ResultIndex([])
            notes.append(f"{sport}: Flashscore unavailable ({str(e)[:60]}) — grading waits")
    graded, gave_up = uv.grade(pending, index, now)
    uv.archive(graded, now=now)
    uv.save_pending(pending)
    notes.append(f"graded {len(graded) - gave_up}, no result found {gave_up}, waiting {len(pending)}")
    return " · ".join(notes)


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], capture_output=True, text=True)  # noqa: S603,S607 (fixed git args)


def persist(now: datetime) -> str:
    if os.environ.get("GITHUB_ACTIONS") != "true":
        return "not saved (outside GitHub Actions)"
    _git("add", "data/universe", "backtest/UNIVERSE_STUDY.md", "data/match_stats",
         "backtest/MATCH_STATS_STUDY.md", "backtest/PAPER_BOOK.md")
    if _git("diff", "--staged", "--quiet").returncode == 0:
        return "nothing to save"
    _git("commit", "-q", "-m", f"universe {now:%Y-%m-%d %H:%M} [skip ci]")
    for _ in range(3):
        if _git("push", "-q", "origin", "HEAD:main").returncode == 0:
            return "saved"
        if _git("pull", "-q", "--rebase", "origin", "main").returncode != 0:
            _git("rebase", "--abort")
            break
    return "NOT SAVED — main moved and a file conflicted; the next sweep re-grades"


NOTE_DIR = ROOT / "data" / "universe" / "notes"


def send_daily_note(now: datetime) -> str:
    """The morning paper-book note to the Architect's own chat, once a day
    (marker data/universe/notes/<UTC date>.sent). Never a subscriber chat."""
    marker = NOTE_DIR / f"{now:%Y-%m-%d}.sent"
    if marker.exists():
        return "paper-book note already sent today"
    owner = (os.environ.get("TELEGRAM_OWNER_CHAT_ID", "").strip()
             or os.environ.get("TELEGRAM_CHAT_ID", "").strip())
    if not owner or not os.environ.get("TELEGRAM_BOT_TOKEN"):
        return "paper-book note not sent (no Telegram settings here)"
    from engine import paper_book
    from output import notify
    text = paper_book.daily_note([r for r in uv.load_graded() if r.get("result")])
    ok, notes = notify.send_telegram(text, chat_id=owner)      # the Architect only
    if ok:
        NOTE_DIR.mkdir(parents=True, exist_ok=True)
        marker.write_text(now.strftime("%Y-%m-%dT%H:%MZ"), encoding="utf-8")
    return f"paper-book note {'sent' if ok else 'NOT sent'} {notes}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="OLP XDV universe sweep")
    ap.add_argument("--study", action="store_true", help="rewrite the study only")
    a = ap.parse_args(argv)
    now = datetime.now(UTC)
    if not a.study:
        print(f"[{now:%H:%M}Z] {sweep(now)}")
    morning_due = now.hour >= STUDY_HOUR and not (NOTE_DIR / f"{now:%Y-%m-%d}.sent").exists()
    if a.study or morning_due or not (ROOT / "backtest" / "UNIVERSE_STUDY.md").exists():
        import importlib
        sys.path.insert(0, str(ROOT / "backtest"))
        importlib.import_module("universe_study").main()
        importlib.import_module("paper_book_study").main()
        try:
            # data/match_stats.py sits beside its data folder data/match_stats/: load the module by name
            n, notes = importlib.import_module("data.match_stats").collect(days=3)
            print(f"[{now:%H:%M}Z] match stats: {n} new" + "".join(f" · {x}" for x in notes))
        except Exception as e:  # noqa: BLE001 — FotMob down never stops the sweep
            print(f"[{now:%H:%M}Z] match stats skipped ({str(e)[:60]})")
        importlib.import_module("match_stats_study").main()
        if morning_due:
            print(f"[{now:%H:%M}Z] {send_daily_note(now)}")
    print(f"[{now:%H:%M}Z] {persist(now)}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
