"""
Second-source fixture check — ID403 F2 for every fixture on the board.

Each fixture reaches the board from one feed (TheSportsDB, or the odds feed),
so ID403 stamped it ○ SINGLE-SOURCE. This looks the same match up in two free
sources (Architect 2026-10-03: no paid APIs):

  ESPN scoreboard           espn.com              T2   data/espn_fixtures.py
  FotMob match list         fotmob.com            T2   data/fotmob.py (Architect
                                                       2026-10-08: every fixture verified)
  Flashscore day feed       flashscore.co.uk      T2   data/flashscore_results.py
                                                       (2026-10-09: covers Poland and
                                                       Croatia, which ESPN doesn't)
  football-data.co.uk       football-data.co.uk   T1   fixtures.csv and
                                                       new_league_fixtures.csv

and re-runs verification.id403.verify on all the claims, so two independent
T1/T2 sources agreeing gives ✓ VERIFIED.

WHAT COUNTS (HR35 — never resolved by picking a side, never guessed)
  - A source that lists the same match (both teams, same league, within a day)
    as scheduled AGREES.
  - A source that can't find it adds NOTHING. A spelling we can't pair, or a
    league a source doesn't cover, is not evidence against a fixture.
  - ESPN listing the match POSTPONED / CANCELLED / ABANDONED (on a STRONG name
    match, engine/fixture_match.py) DISAGREES -> ⚠ CONFLICT. ID403 keeps a
    CONFLICT off the deploy list, so a match that won't be played isn't bet;
    it stays on the board with the reason.
  - A source that is down is flagged and skipped; the run never fails here.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Callable, Optional

from data import espn_fixtures as espn
from data import flashscore_results as flashscore
from data import fotmob
from engine.fixture_match import find_match
from verification.id403 import SourcedDatum, Tier, verify

FD_URL = "https://www.football-data.co.uk/fixtures.csv"
FD_NEW_URL = "https://www.football-data.co.uk/new_league_fixtures.csv"
FD_DOMAIN = "football-data.co.uk"
FM_DOMAIN = "fotmob.com"
FS_DOMAIN = "flashscore.co.uk"
# Youth / women / reserve sides share the senior club's name ("Galatasaray U19")
# and would make the pairing ambiguous.
_NOT_SENIOR = re.compile(r"\b(U\d{2}|Women|W|II|B|Reserves?)$", re.I)


def _flashscore_day(day: str) -> list[dict]:
    """Flashscore's whole football feed for one date (scheduled matches too)."""
    offset = date.fromisoformat(day).toordinal() - date.today().toordinal()
    return flashscore.results_for_offset(offset)


def split_fixture(label: str) -> Optional[tuple[str, str, str]]:
    """'Home v Away (League)' -> (home, away, league), None if not that shape."""
    head, sep, tail = label.rpartition(" (")
    if not sep or not tail.endswith(")"):
        return None
    home, v, away = head.partition(" v ")
    if not v or not home.strip() or not away.strip():
        return None
    return home.strip(), away.strip(), tail[:-1].strip()


def _days_around(day: str) -> list[str]:
    d = date.fromisoformat(day[:10])
    return [(d + timedelta(days=k)).isoformat() for k in (-1, 0, 1)]


def _near(day_a: str, day_b: str) -> bool:
    try:
        return abs((date.fromisoformat(day_a[:10]) - date.fromisoformat(day_b[:10])).days) <= 1
    except ValueError:
        return False


def _espn_events(league: str, days: set[str], flags: list[str],
                 fetch: Callable) -> list:
    events, failed = [], []
    for d in sorted({x for day in days for x in _days_around(day)}):
        try:
            events += fetch(league, d)
        except ValueError:
            return []                      # league not covered by ESPN — nothing to add
        except Exception as e:  # noqa: BLE001 — a source down is flagged, not fatal
            failed.append(f"{d} ({str(e)[:50]})")
    if failed:
        flags.append(f"{league}: ESPN unavailable for " + ", ".join(failed))
    return events


def _fd_fixtures(league: str, flags: list[str], fetch_main: Callable,
                 fetch_extra: Callable) -> tuple[list, str]:
    from pipeline.odds_footballdata import EXTRA_COUNTRY
    try:
        if league in EXTRA_COUNTRY:
            rows, _ = fetch_extra(league)
            return rows, FD_NEW_URL
        rows, _ = fetch_main(league)
        return rows, FD_URL
    except Exception as e:  # noqa: BLE001
        flags.append(f"{league}: football-data fixtures unavailable ({str(e)[:60]})")
        return [], FD_URL


def _base_domain(bf) -> Optional[str]:
    domains = (bf.verification.factors or {}).get("independent_domains") or []
    return domains[0] if domains else None


def _fotmob_events(days: set[str], flags: list[str], fetch: Callable) -> list[dict]:
    """FotMob's whole match list for each board day (one call a day, every
    league). A day FotMob can't serve is flagged and adds nothing."""
    events: dict = {}
    for d in sorted({x for day in days for x in _days_around(day)}):
        try:
            for e in fetch(d):
                # One match once: a match listed on two days would otherwise
                # make the name match ambiguous and add nothing.
                events.setdefault(e.get("id") or (e.get("home"), e.get("away")), e)
        except Exception as e:  # noqa: BLE001 — a source down is flagged, not fatal
            flags.append(f"FotMob unavailable for {d} ({str(e)[:50]})")
    return list(events.values())


def _flashscore_events(days: set[str], flags: list[str], fetch: Callable) -> list[dict]:
    """Flashscore's senior matches for each board day; a day it can't serve is
    flagged and adds nothing."""
    events: dict = {}
    for d in sorted({x for day in days for x in _days_around(day)}):
        try:
            for e in fetch(d):
                if _NOT_SENIOR.search(e.get("home", "")) or _NOT_SENIOR.search(e.get("away", "")):
                    continue
                events.setdefault((e.get("home"), e.get("away"), (e.get("kickoff_utc") or "")[:10]), e)
        except Exception as e:  # noqa: BLE001 — a source down is flagged, not fatal
            flags.append(f"Flashscore unavailable for {d} ({str(e)[:50]})")
    return list(events.values())


def check_board(board: list, fetch_espn: Callable = espn.fetch_day,
                fetch_fd: Optional[Callable] = None,
                fetch_fd_extra: Optional[Callable] = None,
                max_days: int = 3,
                fetch_fotmob: Callable = fotmob.matches_on,
                fetch_flashscore: Callable = _flashscore_day) -> list[str]:
    """Re-stamp every board fixture's ID403 verification with the second and
    third sources. Mutates `board` in place (verification, and for a CONFLICT
    on_deploy_shortlist + rejection_reason). Returns data flags.

    ESPN is asked about each league's first `max_days` board days only (the
    live runs carry one target day); later fixtures are checked against
    football-data alone, so a manual whole-window run stays quick."""
    if fetch_fd is None or fetch_fd_extra is None:
        from pipeline.odds_footballdata import fetch_extra_footballdata, fetch_odds_footballdata
        fetch_fd = fetch_fd or fetch_odds_footballdata
        fetch_fd_extra = fetch_fd_extra or fetch_extra_footballdata
    flags: list[str] = []
    by_league: dict[str, list] = {}
    for bf in board:
        parts = split_fixture(bf.fixture)
        if parts is None or not bf.kickoff_date or bf.verification.tier == Tier.NO_DATA:
            continue
        by_league.setdefault(parts[2], []).append(bf)

    counts = {Tier.VERIFIED: 0, Tier.SINGLE_SOURCE: 0, Tier.CONFLICT: 0}
    conflicts: list[str] = []
    all_days = {bf.kickoff_date[:10] for fx in by_league.values() for bf in fx}
    fm_events = _fotmob_events(set(sorted(all_days)[:max_days]), flags, fetch_fotmob)
    fs_events = _flashscore_events(set(sorted(all_days)[:max_days]), flags, fetch_flashscore)
    for league, fixtures in by_league.items():
        days = set(sorted({bf.kickoff_date[:10] for bf in fixtures})[:max_days])
        events = _espn_events(league, days, flags, fetch_espn)
        fd_rows, fd_url = _fd_fixtures(league, flags, fetch_fd, fetch_fd_extra)
        for bf in fixtures:
            home, away, _ = split_fixture(bf.fixture)  # type: ignore[misc]
            base = _base_domain(bf)
            if base is None:
                continue
            value = f"{home} v {away}"
            claims = [SourcedDatum(domain=base, value=value, url=f"https://www.{base}")]
            notes = []
            near = [e for e in events if _near(e.kickoff_utc, bf.kickoff_date)]
            m = find_match(home, away, near, lambda e: (e.home, e.away))
            if m is not None:
                off = m.item.off
                if off and m.strong:
                    claims.append(SourcedDatum(domain=espn.DOMAIN, url=m.item.url,
                                               value=f"{value} — {off} per ESPN"))
                    notes.append(f"ESPN lists it {off}")
                elif not off:
                    claims.append(SourcedDatum(domain=espn.DOMAIN, value=value, url=m.item.url))
            near_fd = [r for r in fd_rows if _near(r.kickoff_utc, bf.kickoff_date)]
            mf = find_match(home, away, near_fd, lambda r: (r.home_team, r.away_team))
            if mf is not None:
                claims.append(SourcedDatum(domain=FD_DOMAIN, value=value, url=fd_url))
            near_fm = [e for e in fm_events if _near(e.get("kickoff_utc") or "", bf.kickoff_date)]
            mm = find_match(home, away, near_fm, lambda e: (e["home"], e["away"]))
            if mm is not None:
                claims.append(SourcedDatum(domain=FM_DOMAIN, value=value,
                                           url=f"https://www.fotmob.com/match/{mm.item.get('id')}"))
            near_fs = [e for e in fs_events if _near(e.get("kickoff_utc") or "", bf.kickoff_date)]
            ms = find_match(home, away, near_fs, lambda e: (e["home"], e["away"]))
            if ms is not None:
                claims.append(SourcedDatum(domain=FS_DOMAIN, value=value,
                                           url="https://www.flashscore.co.uk/"))
            if len(claims) == 1:
                counts[Tier.SINGLE_SOURCE] += 1
                continue
            result = verify(claims)
            bf.verification = result
            counts[result.tier] = counts.get(result.tier, 0) + 1
            if result.tier == Tier.CONFLICT:
                why = "; ".join(notes) or "sources disagree"
                conflicts.append(f"{value} ({league}): {why}")
                bf.on_deploy_shortlist = False
                bf.rejection_reason = (f"CONFLICT — {why}, while {base} still lists it. "
                                       f"Not deployed until the sources agree.")
    total = sum(counts.values())
    flags.append(
        f"Fixture check (TheSportsDB · ESPN · football-data · FotMob · Flashscore): {counts[Tier.VERIFIED]}/"
        f"{total} confirmed by two independent sources, {counts[Tier.SINGLE_SOURCE]} "
        f"one source only, {counts[Tier.CONFLICT]} conflict(s)"
        + ("" if not conflicts else " — " + " | ".join(conflicts)))
    return flags
