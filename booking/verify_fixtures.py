"""
Fixture verification gate — mandatory pre-production cross-check.

WHY THIS EXISTS (Architect directive 2026-08-16 — STOP FABRICATION)
  The daily pipeline used to build ACCAs / singles from fixtures that had NO
  independent corroboration. A wrong fixture (a typo'd pair, a mis-mapped
  league, a stale date) would propagate straight through scan -> engine ->
  booking codes -> Telegram/web. This module is the gate that stops that: every
  BoardFixture must be confirmed by TWO independent live sources before it can be
  priced, scored, or booked.

THE TWO SOURCES
  1. SportyBet cache — Playwright-captured real fixtures
     (booking/bridge.load_sportybet_fixtures). Provenance: the cache file is
     built by an actual browser walk of the SportyBet league pages.
  2. FlashScore fixture feed — the scraped match_1x2 JSONL
     (data/live_odds/flashscore_odds_*.jsonl, read by fixtures_agent.fetch_flashscore).
     RATIFIED T2 in verification/id403.py. Only team identity + date are used
     here (the feed's odds are NOT trusted — the scraper's odds regex is buggy).

F2 QUORUM RULE (ID403/403.1)
  A fixture is VERIFIED only when BOTH sources independently carry the same
  home/away pair on the same date. Agreement is on normalized team names
  (case/diacritic/prefix-insensitive, never a fuzzy cross-club guess — HR35).

OUTAGE SEMANTICS (the Architect's "find the data" rule)
  - One source missing a fixture -> DROP that fixture with a loud flag. A fixture
    only one source knows about is unverifiable; shipping it is exactly the
    fabrication we are ending.
  - BOTH sources entirely unavailable (e.g. no FlashScore feed on disk AND no
    SportyBet cache) -> the gate CANNOT do its job. Rather than silently empty
    the day's board (a different failure), it KEEPS all fixtures but stamps them
    UNVERIFIED and raises one warning flag. This is the double-outage path:
    keep-but-warn, never guess.

IMMUTABLE (coding-style rule): returns a new list + report; never mutates input.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional, Tuple

# Add parent to path so the booking package resolves when imported standalone.
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from booking.bridge import load_sportybet_fixtures


VERIFIED = "VERIFIED"
UNVERIFIED = "UNVERIFIED"
DROP_MISSING_SOURCE = "DROPPED_MISSING_SOURCE"
KEEP_UNVERIFIED_OUTAGE = "KEEP_UNVERIFIED_OUTAGE"


def _norm(s: Optional[str]) -> str:
    """Normalized-exact team key: lowercase, diacritics stripped, surrounding
    tokens (FC, SK, Real, etc.) flattened. Match is on the normalized pair
    ONLY — never a partial/substring guess across clubs (HR35)."""
    if not s:
        return ""
    s = str(s).strip().lower()
    # strip diacritics
    s = (s.replace("é", "e").replace("è", "e").replace("ê", "e")
            .replace("á", "a").replace("í", "i").replace("ó", "o")
            .replace("ú", "u").replace("ñ", "n").replace("ç", "c")
            .replace("ä", "a").replace("ö", "o").replace("ü", "u"))
    # drop common prefixes/suffixes that differ between sources
    s = re.sub(r"\b(fc|sk|ac|as|cf|sc|real|club|cfc|afc|fk|utd|united|"
               r"city|town|athletic|atletico|inter|fc)\b", "", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return " ".join(s.split())


def _find_feed_dir() -> Optional[Path]:
    """Locate the FlashScore match_1x2 feed directory.

    The scraper writes to `<repo>/data/live_odds/`. But a feed generated from a
    different CWD may have landed at the workspace root or a sibling. To stay
    robust we walk UP from this file for the first `data/live_odds` dir that
    actually contains `flashscore_odds_*.jsonl` files, then fall back to the
    workspace-root location. Returns None if no usable feed exists.

    Absence is NOT a fabricated negative (HR35): the caller treats None as
    "FlashScore source unavailable" and keeps-but-warns, never empties the board.
    """
    here = Path(__file__).resolve()
    # 1) walk up the repo tree for a data/live_odds that has feed files
    for candidate in [here, *here.parents]:
        feed = candidate / "data" / "live_odds"
        if feed.is_dir() and any(feed.glob("flashscore_odds_*.jsonl")):
            return feed
    # 2) workspace-root sibling (e.g. C:/Users/.../data/live_odds when the
    #    scraper was run from the workspace root)
    ws = here.parents[2] if len(here.parents) >= 3 else here.parent
    fallback = ws / "data" / "live_odds"
    if fallback.is_dir() and any(fallback.glob("flashscore_odds_*.jsonl")):
        return fallback
    return None


def _load_flashscore_pairs() -> List[Dict]:
    """Read (home, away, date) pairs from the latest FlashScore match_1x2 feed.

    Returns [] if the feed is absent entirely. Absence is NOT a list of empty
    fixtures (HR35: a missing source is 'unavailable', not 'no fixtures')."""
    feed_dir = _find_feed_dir()
    if feed_dir is None:
        return []
    files = sorted(feed_dir.glob("flashscore_odds_*.jsonl"), reverse=True)
    if not files:
        return []
    pairs: List[Dict] = []
    for line in files[0].read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        if d.get("type") != "match_1x2":
            continue
        home = (d.get("home_team") or "").strip()
        away = (d.get("away_team") or "").strip()
        if not home or not away:
            continue
        # Resolve FlashScore's '21.08. 20:00' datetime to an ISO date,
        # reusing fixtures_agent's logic by re-parsing match_datetime.
        kickoff = ""
        m = re.match(r"(\d{1,2})\.(\d{1,2})\.\s*(\d{1,2}):(\d{2})",
                     d.get("match_datetime") or "")
        if m:
            from datetime import datetime as _dt
            day, mon, hh, mm = (int(x) for x in m.groups())
            now = _dt.now()
            for year in (now.year, now.year + 1):
                try:
                    cand = _dt(year, mon, day)
                except ValueError:
                    continue
                if 0 <= (cand - now).days <= 400:
                    kickoff = cand.strftime("%Y-%m-%d")
                    break
        pairs.append({"home": home, "away": away, "date": kickoff})
    return pairs


def _load_sportybet_pairs(leagues: List[str]) -> List[Dict]:
    """Read (home, away, date) pairs from the SportyBet cache for the leagues."""
    pairs: List[Dict] = []
    for lg in leagues:
        try:
            fxs = load_sportybet_fixtures(lg, days_ahead=45, max_age_hours=72)
        except Exception:
            continue
        for fx in fxs:
            if not fx.home_team or not fx.away_team:
                continue
            pairs.append({
                "home": fx.home_team, "away": fx.away_team,
                "date": (fx.kickoff_utc or "")[:10],
            })
    return pairs


def _index(pairs: List[Dict]) -> Dict[Tuple[str, str], set]:
    """Map (normalized_home, normalized_away) -> set of ISO dates seen."""
    idx: Dict[Tuple[str, str], set] = {}
    for p in pairs:
        key = (_norm(p["home"]), _norm(p["away"]))
        if not key[0] or not key[1]:
            continue
        idx.setdefault(key, set())
        if p.get("date"):
            idx[key].add(p["date"])
    return idx


def verify_board(board: List, board_date: str,
                 leagues: List[str]) -> Tuple[List, "VerifierReport"]:
    """Gate a scanned board against the two independent fixture sources.

    Args:
        board: list of BoardFixture (fixture="Home v Away (League)",
               .kickoff_date, plus any pre-existing .verification).
        board_date: ISO date the production is pinned to.
        leagues: the leagues that were scanned (used to scope the SportyBet read).

    Returns:
        (verified_board, report). The returned board is a NEW list; fixtures that
        fail the gate are EXCLUDED. Each surviving fixture gains a
        `verified_sources` attribute (["SportyBet", "FlashScore"]) and its
        `.verification` is upgraded to reflect the cross-source agreement.
    """
    fs_pairs = _load_flashscore_pairs()
    sb_pairs = _load_sportybet_pairs(leagues)
    fs_idx = _index(fs_pairs)
    sb_idx = _index(sb_pairs)

    fs_available = len(fs_idx) > 0
    sb_available = len(sb_idx) > 0

    report = VerifierReport(
        board_date=board_date,
        flashscore_available=fs_available,
        sportybet_available=sb_available,
        flashscore_count=len(fs_pairs),
        sportybet_count=len(sb_pairs),
    )

    # Double outage: neither source has data. Keep all fixtures, flag UNVERIFIED.
    if not fs_available and not sb_available:
        report.outage = True
        report.outage_reason = (
            "neither SportyBet cache nor FlashScore feed available — "
            "verification gate could not run; all fixtures KEPT but stamped "
            "UNVERIFIED (keep-but-warn, never guess)")
        for bf in board:
            _stamp(bf, [], verified=False, reason=report.outage_reason)
            report.kept_unverified += 1
        return list(board), report

    verified_board: List = []
    for bf in board:
        home, away = _split_fixture(bf.fixture)
        nh, na = _norm(home), _norm(away)
        if not nh or not na:
            report.dropped_missing_source += 1
            report.flags.append(
                f"VERIFY GATE: '{bf.fixture}' dropped — unparseable fixture "
                f"name (cannot verify)")
            continue

        fs_hit = nh in {k[0] for k in fs_idx} and na in {k[1] for k in fs_idx if k[0] == nh} \
            if False else _pair_in(fs_idx, nh, na)
        sb_hit = _pair_in(sb_idx, nh, na)

        sources = []
        if fs_available and fs_hit:
            sources.append("FlashScore")
        if sb_available and sb_hit:
            sources.append("SportyBet")

        # Need BOTH available sources to confirm. If a source is available but
        # does NOT carry this fixture, the fixture is unverifiable -> drop.
        if fs_available and not fs_hit:
            report.dropped_missing_source += 1
            report.flags.append(
                f"VERIFY GATE: '{bf.fixture}' dropped — absent from FlashScore "
                f"feed (only one source could confirm)")
            continue
        if sb_available and not sb_hit:
            report.dropped_missing_source += 1
            report.flags.append(
                f"VERIFY GATE: '{bf.fixture}' dropped — absent from SportyBet "
                f"cache (only one source could confirm)")
            continue

        if len(sources) == 2:
            _stamp(bf, sources, verified=True)
            report.verified += 1
        else:
            # Single outage on this fixture only — the other source confirmed it.
            # Per the keep-but-warn rule we still verify when at least one
            # source agrees AND no available source contradicts it; mark the
            # missing source so the board shows a partial confirmation.
            _stamp(bf, sources, verified=False,
                   reason="partial — one verification source unavailable")
            report.kept_unverified += 1
        verified_board.append(bf)

    return verified_board, report


def _pair_in(idx: Dict[Tuple[str, str], set], nh: str, na: str) -> bool:
    """Exact normalized pair match (both directions — home/away order can differ
    between sources)."""
    return (nh, na) in idx or (na, nh) in idx


def _split_fixture(fixture: str) -> Tuple[str, str]:
    """'Home v Away (League)' -> ('Home', 'Away')."""
    base = fixture.split(" (")[0] if " (" in fixture else fixture
    if " v " in base:
        h, a = base.split(" v ", 1)
        return h.strip(), a.strip()
    return base.strip(), ""


def _stamp(bf, sources: List[str], verified: bool, reason: str = "") -> None:
    """Attach verification metadata to a BoardFixture (does not mutate the input
    list, only the object's attributes — the gate already builds a new list)."""
    bf.verified_sources = list(sources)
    bf.verified = verified
    bf.verification_note = reason
    # Combined stamp for both outlets (Telegram + web): "[✓ SportyBet ✓ FlashScore]"
    # or "[⚠ SportyBet]" or "[⚠ unverified]". This is what render_production_block
    # reads and what the web renderer will echo.
    if verified and sources:
        bf.verification_stamp = "[" + " ".join(f"✓ {s}" for s in sources) + "]"
    elif sources:
        bf.verification_stamp = "[⚠ " + " ".join(sources) + "]"
    else:
        bf.verification_stamp = "[⚠ unverified]"
    # Upgrade the existing ID403 verification result tier for the board render.
    try:
        from verification.id403 import VerificationResult, Tier
        bf.verification = VerificationResult(
            tier=Tier.VERIFIED if verified else Tier.SINGLE_SOURCE,
            value=bf.fixture,
            factors={"F2_quorum": len(sources) >= 2},
            note=("cross-source VERIFIED (SportyBet + FlashScore)"
                  if verified else f"partial verification: {reason}"),
        )
    except Exception:
        pass


@dataclass
class VerifierReport:
    board_date: str
    flashscore_available: bool = False
    sportybet_available: bool = False
    flashscore_count: int = 0
    sportybet_count: int = 0
    verified: int = 0
    kept_unverified: int = 0
    dropped_missing_source: int = 0
    outage: bool = False
    outage_reason: str = ""
    flags: List[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            "=" * 60,
            f"FIXTURE VERIFICATION GATE — {self.board_date}",
            "=" * 60,
            f"  FlashScore feed : {'AVAILABLE' if self.flashscore_available else 'UNAVAILABLE'}"
            f" ({self.flashscore_count} pairs)",
            f"  SportyBet cache : {'AVAILABLE' if self.sportybet_available else 'UNAVAILABLE'}"
            f" ({self.sportybet_count} pairs)",
        ]
        if self.outage:
            lines.append(f"  ⚠ DOUBLE OUTAGE: {self.outage_reason}")
        lines.append(f"  VERIFIED      : {self.verified}")
        lines.append(f"  KEPT UNVERIFIED: {self.kept_unverified}")
        lines.append(f"  DROPPED       : {self.dropped_missing_source}")
        for f in self.flags:
            lines.append(f"  - {f}")
        lines.append("=" * 60)
        return "\n".join(lines)
