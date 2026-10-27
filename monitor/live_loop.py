"""
LIVE LOOP — the matchday tracker as a GitHub Actions job, reporting to the
Architect on Telegram (Architect 2026-10-14: "can it be a GitHub action? I
don't want it taking too much token ... Let GitHub give me the update").

WHY THIS REPLACES RUNNING IT FROM A SESSION
  `monitor/live_tracker.py` was written to be run from a Claude session on
  matchdays, and its own docstring gave the reason: "an all-day Actions job
  would use about three times the free Actions minutes". That was WRONG for
  this repo. Tolar07/framework is PUBLIC, and GitHub-hosted minutes are
  unmetered on public repositories — the all-day job costs nothing. Running it
  from a session costs the Architect tokens for every goal, every half time and
  every poll that fails, all day, and stops the moment the session does.

WHAT IT DOES
  Exactly what the session script does — `live_tracker.round_once` is shared,
  so the same snapshots are written and the same events are detected — plus:
    * Telegram to the Architect's own chat (order 33, never a subscriber),
      paced by `Outbox` (Architect 2026-10-25: a message every goal on every
      tracked match was too much):
        - INSTANT only for an event that changes an open bet: a goal, a red
          card or full time in a match carrying a board pick;
        - HALF TIME / FULL TIME of everything else goes out as one round-up,
          held ROUNDUP_HOLD so matches that kicked off together share it;
        - the rest (study and no-call goals, feed failures) waits for one
          digest every DIGEST_EVERY. A quiet half hour says nothing;
    * the live snapshots committed to main every PERSIST_EVERY rounds and once
      at the end, so a dropped job loses minutes, not a matchday;
    * one FULL TIME message listing every tracked match's final score beside
      the call we made on it;
    * the same single-loop and hand-off discipline as the pre-kickoff loop
      (`monitor/news_loop.py`): a run that finds an older one going exits, and
      a job nearing GitHub's 6-hour limit starts a fresh run and ends.

  Nothing here bets, prices or changes a board. It records and it reports.

    python monitor/live_loop.py                 today
    python monitor/live_loop.py --day 2026-10-14
    python monitor/live_loop.py --handoff       (internal: started by the previous run)
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from monitor import live_tracker as lt  # noqa: E402
from monitor import loop_util as lu  # noqa: E402

EARLIEST = timedelta(hours=3)        # don't sit idle longer than this before the first kickoff
PERSIST_EVERY = 10                   # rounds between commits (POLL=120s -> ~20 min)
WORKFLOW = "live.yml"
DIGEST_EVERY = timedelta(minutes=30)  # the slow lane: everything that changes no open bet
ROUNDUP_HOLD = timedelta(minutes=6)   # three polls: matches that kicked off together share one HT/FT round-up


def persist(day: str, now: datetime) -> str:
    """Save the live snapshots so far. They are append-only files under
    data/study/<day>/live/, so a rebase never conflicts over them."""
    return lu.save([f"data/study/{day}/live"], f"live tracker {day} {now:%H:%M} [skip ci]")


def first_kickoff(matches: list[dict]) -> datetime | None:
    kos = [datetime.fromisoformat(m["kickoff_utc"].replace("Z", "+00:00")) for m in matches
           if m.get("kickoff_utc")]
    return min(kos) if kos else None


def should_hand_off(started: datetime, now: datetime) -> bool:
    return now - started >= lu.HANDOFF_AFTER


def worth_telling(lines: list[str], said: set[str]) -> list[str]:
    """The lines to send. A match event (a goal, a red card, half time, full
    time) always goes. A FAILURE goes ONCE and then stays quiet: a feed that
    breaks for a whole match would otherwise send the Architect the same line
    every two minutes for ninety minutes — which is the noise this job exists
    to avoid. The failure is still printed to the run log every round, so the
    run history keeps the full picture.
    """
    out = []
    for line in lines:
        if "failed" not in line:
            out.append(line)
            continue
        key = line.split("] ", 1)[-1]          # drop the timestamp: same fault, same key
        if key not in said:
            said.add(key)
            out.append(line + "  (said once; see the run log for the rest)")
    return out


def lane(line: str) -> str:
    """'instant', 'roundup' or 'digest' for one line from round_once.

    round_once ends every CHANGE / HALF TIME / FULL TIME line with the match's
    calls, so a line naming a "board:" call belongs to a match we hold an open
    bet on. Study legs are not bets, and half time changes no bet."""
    if "NO FULL TIME" in line:
        return "digest"
    if (" CHANGE " in line or " FULL TIME " in line) and "board:" in line:
        return "instant"
    if " HALF TIME " in line or " FULL TIME " in line:
        return "roundup"
    return "digest"


class Outbox:
    """Holds the lines that need not go at once and says when a batch is due.

    add() returns the lines to send now; due() returns a message body, or None,
    each round. A round-up carries the waiting digest lines with it, so the
    Architect never gets a round-up and a digest minutes apart."""

    def __init__(self, now: datetime):
        self.roundup: list[str] = []
        self.digest: list[str] = []
        self.roundup_since: datetime | None = None
        self.last_digest = now

    def add(self, lines: list[str], now: datetime) -> list[str]:
        instant = []
        for line in lines:
            where = lane(line)
            if where == "instant":
                instant.append(line)
            elif where == "roundup":
                self.roundup.append(line)
                self.roundup_since = self.roundup_since or now
            else:
                self.digest.append(line)
        return instant

    def due(self, now: datetime, flush: bool = False) -> str | None:
        """flush=True empties everything (end of day, hand-off) so nothing held is lost."""
        if self.roundup and (flush or now - self.roundup_since >= ROUNDUP_HOLD):
            body = "HT/FT ROUND-UP\n\n" + "\n\n".join(self.roundup)
            if self.digest:
                body += "\n\nALSO SINCE THE LAST DIGEST\n\n" + "\n\n".join(self.digest)
            self.roundup, self.digest, self.roundup_since = [], [], None
            self.last_digest = now
            return body
        if now - self.last_digest >= DIGEST_EVERY or flush:
            self.last_digest = now
            if self.digest:
                body = f"DIGEST (last {DIGEST_EVERY.seconds // 60} min)\n\n" + "\n\n".join(self.digest)
                self.digest = []
                return body
        return None


def tell(body: str) -> None:
    """To the Architect's own chat only (order 33). A failed send is said out
    loud and never stops the loop — the snapshots are the record, not Telegram."""
    try:
        from output.notify import send_architect
        ok, notes = send_architect(body)
        if not ok:
            print(f"  telegram NOT SENT ({'; '.join(notes) or 'no reason given'})", flush=True)
    except Exception as e:  # noqa: BLE001 — a missed message is not a stopped matchday
        print(f"  telegram failed ({str(e)[:60]})", flush=True)


def summary(day: str, matches: list[dict], seen: dict) -> str:
    """The full-time message: every tracked match, its final score as the
    tracker last saw it, and the call we made on it. A match whose score never
    arrived reads PENDING, never a guess (HR35)."""
    out = [f"LIVE TRACKER — {day}: all matches finished", ""]
    for m in matches:
        key = seen.get(m["id"])
        score = key[0] if key else None
        out.append(f"{m['kickoff_utc'][11:16]}Z {m['home']} {score or 'PENDING'} {m['away']}")
        out.append(f"   {' | '.join(m['calls']) or 'no call'}")
    out += ["", "Snapshots in data/study/" + day + "/live/ — graded and reviewed separately.",
            "Nothing here was bet; the Architect deploys."]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="the matchday live tracker, as an Actions job")
    ap.add_argument("--day", default=None, help="YYYY-MM-DD (default: today UTC)")
    ap.add_argument("--handoff", action="store_true",
                    help="started by the previous loop run — don't wait for it to end")
    a = ap.parse_args(argv)
    day = a.day or datetime.now(UTC).strftime("%Y-%m-%d")
    repo, token = os.environ.get("GITHUB_REPOSITORY", ""), os.environ.get("GITHUB_TOKEN", "")
    run_id = int(os.environ.get("GITHUB_RUN_ID", "0") or 0)
    started = datetime.now(UTC)

    # A day older than yesterday is over: never track it, never hand it on.
    # (2026-10-18: a hand-off chain carried --day 2026-10-17 for a whole day.)
    if datetime.fromisoformat(day).date() < started.date() - timedelta(days=1):
        print(f"{day} is over — nothing to track")
        return 0

    if not a.handoff and repo and token and lu.other_loop_running(WORKFLOW, repo, token, run_id):
        print("a live loop is already running — nothing to do")
        return 0

    out_dir = ROOT / "data" / "study" / day / "live"
    out_dir.mkdir(parents=True, exist_ok=True)
    matches = lt.tracked(day, lt.our_calls(day))
    if not matches:
        print(f"no tracked match on {day} — no board, no study board, no Champions League")
        return 0
    ko = first_kickoff(matches)
    if ko and ko - started > EARLIEST:
        print(f"too early — first kickoff {ko:%H:%M}Z, more than {EARLIEST} away")
        return 0

    print(f"tracking {len(matches)} matches on {day}", flush=True)
    for m in matches:
        print(f"  {m['kickoff_utc'][11:16]}Z {m['home']} v {m['away']} — "
              + (" | ".join(m["calls"]) or "no call"), flush=True)

    seen: dict = {}
    said: set[str] = set()
    box = Outbox(started)
    rounds = 0
    while True:
        lines, still = lt.round_once(matches, seen, out_dir)
        rounds += 1
        for line in lines:
            print(line, flush=True)
        now = datetime.now(UTC)
        send = box.add(worth_telling(lines, said), now)
        if send:
            tell(f"LIVE — {day} · open bet\n\n" + "\n\n".join(send))
        batch = box.due(now, flush=not still or should_hand_off(started, now))
        if batch:
            tell(f"LIVE — {day} · {batch}")
        if not still:
            print("ALL MATCHES FINISHED", flush=True)
            print(f"  {persist(day, datetime.now(UTC))}", flush=True)
            tell(summary(day, matches, seen))
            return 0
        if rounds % PERSIST_EVERY == 0:
            print(f"[{datetime.now(UTC):%H:%M}Z] {persist(day, datetime.now(UTC))}", flush=True)
        if should_hand_off(started, now):
            print(f"[{datetime.now(UTC):%H:%M}Z] {persist(day, datetime.now(UTC))}", flush=True)
            if repo and token:
                lu.hand_off(WORKFLOW, repo, token, {"day": day})
                print("handed off to a fresh run (job time limit)", flush=True)
            else:
                print("job time limit reached and no token to hand off with — "
                      "the rest of the day is NOT tracked", flush=True)
            return 0
        time.sleep(lt.POLL)


if __name__ == "__main__":
    raise SystemExit(main())
