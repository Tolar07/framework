"""BOARD CLOCK — starts the 10pm and 7am board runs on time, every day.

Architect 2026-10-15: "make sure the triggers [are] on time ... I don't want
it to fail again going forward." Until now the board was started by a Claude
Routine plus GitHub's own crons, with the watchdog as a backup — and all three
fire late: on 15 Oct the Routine reached its session 2 h 21 min late, and
neither GitHub's 20:47 cron nor the watchdog's 21:23 cron fired at all, so
Friday's board had not gone out by 00:08 Lagos.

This is a clock that does not depend on anyone's schedule. ONE GitHub Actions
job (clock.yml) loops all day: every minute it looks at the time, and when a
slot is due and that slot's board has not been sent (no output/boards/
sent_<date>_<slot> marker on main) and no board run is going, it starts
daily.yml for that slot itself.

  evening  due 20:47 UTC (21:47 Lagos) — TOMORROW's card (Lagos date)
  morning  due 05:47 UTC (06:47 Lagos) — today's card

A slot stays due for a few hours (a board at 01:00 still beats none); a run
that ends without the marker (failed) is retried after RETRY_AFTER, at most
MAX_TRIES times, then the Architect is told exactly what to start by hand.
daily.yml's duplicate guard means a late Routine / GitHub cron / watchdog
run for the same slot just skips — they all stay as backups.

A job may run 6 hours at most, so after HANDOFF_AFTER the clock starts a
fresh clock.yml run (handoff) and ends. clock.yml's own crons restart the
clock if the chain ever breaks; a run that finds a clock already going exits.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, date, datetime, timedelta

SLOTS = {"evening": (20, 47), "morning": (5, 47)}            # UTC
DUE_FOR = {"evening": timedelta(hours=7), "morning": timedelta(hours=4)}
RETRY_AFTER = timedelta(minutes=40)
MAX_TRIES = 3
TICK = 60                                                     # seconds
HANDOFF_AFTER = timedelta(hours=5, minutes=40)               # job limit is 6 h
LAGOS = timedelta(hours=1)
API = "https://api.github.com/repos/{repo}"


def due_slots(now: datetime) -> list[tuple[str, date]]:
    """[(slot, target card date)] whose start time has passed and that are
    still inside their due window at `now` (UTC)."""
    out = []
    for slot, (h, m) in SLOTS.items():
        for back in (0, 1):                       # today's slot, or yesterday's still due
            day = (now - timedelta(days=back)).date()
            start = datetime(day.year, day.month, day.day, h, m, tzinfo=UTC)
            if start <= now < start + DUE_FOR[slot]:
                lagos_day = (start + LAGOS).date()
                target = lagos_day + timedelta(days=1) if slot == "evening" else lagos_day
                out.append((slot, target))
    return out


def marker(slot: str, target: date) -> str:
    return f"output/boards/sent_{target.isoformat()}_{slot}"


class Clock:
    def __init__(self, repo: str, token: str, run_id: int):
        self.repo, self.token, self.run_id = repo, token, run_id
        self.tries: dict[tuple[str, date], list[datetime]] = {}
        self.alerted: set[tuple[str, date]] = set()

    # --- GitHub API -----------------------------------------------------
    def _req(self, path: str, body: dict | None = None) -> dict | None:
        req = urllib.request.Request(  # noqa: S310 (fixed https URL)
            API.format(repo=self.repo) + path, method="POST" if body is not None else "GET",
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Authorization": f"Bearer {self.token}",
                     "Accept": "application/vnd.github+json",
                     "X-GitHub-Api-Version": "2022-11-28"})
        with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310
            raw = r.read()
        return json.loads(raw) if raw else None

    def sent(self, slot: str, target: date) -> bool:
        try:
            self._req(f"/contents/{marker(slot, target)}?ref=main")
            return True
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return False
            raise

    def board_run_going(self) -> bool:
        for status in ("in_progress", "queued"):
            runs = self._req(f"/actions/workflows/daily.yml/runs?status={status}&per_page=10")
            if (runs or {}).get("workflow_runs"):
                return True
        return False

    def other_clock_running(self) -> bool:
        runs = self._req("/actions/workflows/clock.yml/runs?status=in_progress&per_page=20")
        return any(int(r["id"]) < self.run_id for r in (runs or {}).get("workflow_runs", []))

    def start_board(self, slot: str, target: date) -> None:
        self._req("/actions/workflows/daily.yml/dispatches",
                  {"ref": "main", "inputs": {"target_date": target.isoformat(), "slot": slot}})

    def hand_off(self) -> None:
        self._req("/actions/workflows/clock.yml/dispatches",
                  {"ref": "main", "inputs": {"handoff": "true"}})

    # --- one tick -------------------------------------------------------
    def tick(self, now: datetime) -> list[str]:
        notes = []
        for slot, target in due_slots(now):
            key = (slot, target)
            if self.sent(slot, target):
                continue
            if self.board_run_going():
                continue                          # it will send (or fail and alert)
            tries = self.tries.setdefault(key, [])
            if tries and now - tries[-1] < RETRY_AFTER:
                continue
            if len(tries) >= MAX_TRIES:
                if key not in self.alerted:
                    self.alerted.add(key)
                    _send(f"OLP XDV clock: the {slot} board for {target} was started {MAX_TRIES} "
                          f"times and is still not sent. Start it by hand: Actions -> daily.yml -> "
                          f"Run workflow, target_date={target}, slot={slot}.")
                    notes.append(f"{slot} {target}: gave up after {MAX_TRIES} tries — Architect told")
                continue
            self.start_board(slot, target)
            tries.append(now)
            notes.append(f"{slot} {target}: board run started (try {len(tries)})")
        return notes


def _send(msg: str) -> None:
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not (token and chat):
        print(f"(no Telegram) {msg}")
        return
    try:
        body = json.dumps({"chat_id": chat, "text": msg}).encode()
        req = urllib.request.Request(  # noqa: S310 (fixed https URL)
            f"https://api.telegram.org/bot{token}/sendMessage", data=body, method="POST",
            headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=30).close()  # noqa: S310
    except Exception as e:  # noqa: BLE001 — an alert that fails is printed, never fatal
        print(f"Telegram alert failed: {e}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="OLP XDV board clock")
    ap.add_argument("--handoff", action="store_true",
                    help="started by the previous clock run — don't wait for it to end")
    a = ap.parse_args(argv)
    repo, token = os.environ.get("GITHUB_REPOSITORY", ""), os.environ.get("GITHUB_TOKEN", "")
    run_id = int(os.environ.get("GITHUB_RUN_ID", "0") or 0)
    if not (repo and token):
        print("GITHUB_REPOSITORY / GITHUB_TOKEN not set — the clock runs in GitHub Actions")
        return 0
    clock = Clock(repo, token, run_id)
    try:
        if not a.handoff and clock.other_clock_running():
            print("a board clock is already running — nothing to do")
            return 0
    except Exception as e:  # noqa: BLE001
        print(f"could not check for another clock ({e}) — running anyway")
    started = datetime.now(UTC)
    print(f"board clock started {started:%Y-%m-%d %H:%M}Z")
    while True:
        now = datetime.now(UTC)
        try:
            for n in clock.tick(now):
                print(f"[{now:%H:%M}Z] {n}")
        except Exception as e:  # noqa: BLE001 — one bad tick never stops the clock
            print(f"[{now:%H:%M}Z] tick failed: {e}")
        if datetime.now(UTC) - started >= HANDOFF_AFTER:
            try:
                clock.hand_off()
                print("handed off to a fresh clock run (job time limit)")
            except Exception as e:  # noqa: BLE001
                print(f"hand-off failed ({e}) — clock.yml's crons will restart the clock")
            return 0
        time.sleep(TICK)


if __name__ == "__main__":
    sys.exit(main())
