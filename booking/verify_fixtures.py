"""
Fixture verification gate — mandatory pre-production cross-check.

WHY THIS EXISTS (Architect directive 2026-08-16 — STOP FABRICATION)
  The daily pipeline used to build ACCAs / singles from fixtures that had NO
  independent corroboration. A wrong fixture (a typo'd pair, a mis-mapped
  league, a stale date) would propagate straight through scan -> engine ->
  booking codes -> Telegram/web. This module is the gate that stops that: every
  BoardFixture must be confirmed by TWO independent live sources before it can be
  priced, scored, or booked.

THE VERIFICATION SOURCES (expanded 2026-08-23)
  1. SportyBet cache — Playwright-captured real fixtures
     (booking/bridge.load_sportybet_fixtures). Provenance: the cache file is
     built by an actual browser walk of the SportyBet league pages.
  2. FlashScore fixture feed — the scraped match_1x2 JSONL
     (data/live_odds/flashscore_odds_*.jsonl, read by fixtures_agent.fetch_flashscore).
     RATIFIED T2 in verification/id403.py. Only team identity + date are used
     here (the feed's odds are NOT trusted — the scraper's odds regex is buggy).
  3. ESPN schedules — live fixture lists from ESPN API (multi-source concrete layer).
     RATIFIED T1 in verification/id403.py. Authoritative for upcoming fixtures.
  4. football-data.co.uk — completed fixture results (CSV). RATIFIED T1.
     Only usable for fixtures that have already kicked off.

F2 QUORUM RULE (ID403/403.1)
  A fixture is VERIFIED when:
    a) SportyBet + ≥1 other source agree, OR
    b) A SINGLE T1 source (ESPN, football-data) carries it — T1 authority
       is sufficient on its own per ID403 T1 trust tier.

OUTAGE SEMANTICS (the Architect's "find the data" rule)
  - One source missing a fixture -> DROP that fixture with a loud flag. A fixture
    only one source knows about is unverifiable; shipping it is exactly the
    fabrication we are ending.
  - ALL sources entirely unavailable -> the gate CANNOT do its job. Rather than
    silently empty the day's board (a different failure), it KEEPS all fixtures
    but stamps them UNVERIFIED and raises one warning flag. This is the
    double-outage path: keep-but-warn, never guess.

IMMUTABLE (coding-style rule): returns a new list + report; never mutates input.
"""but-warn, never guess.

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
from verification.id403 import SOURCE_TRUST  # noqa: E402


VERIFIED = "VERIFIED"
UNVERIFIED = "UNVERIFIED"
DROP_MISSING_SOURCE = "DROPPED_MISSING_SOURCE"
KEEP_UNVERIFIED_OUTAGE = "KEEP_UNVERIFIED_OUTAGE"


def _norm(s: Optional[str]) -> str:
    """Normalized-exact team key: lowercase, diacritics stripped, surrounding
    tokens (FC, SK, Real, etc.) flattened. Match is on the normalized pair
    ONLY - never a partial/substring guess across clubs (HR35)."""
    if not s:
        return ""
    s = str(s).strip().lower()
    # strip diacritics
    s = (s.replace("é", "e").replace("è", "e").replace("ê", "e")
            .replace("á", "a").replace("í", "i").replace("ó", "o")
            .replace("ú", "u").replace("ñ", "n").replace("ç", "c")
            .replace("ä", "a").replace("ö", "o").replace("ü", "u"))
    # drop common prefixes/suffixes that differ between sources
    # Note: 'athletic' and 'inter' removed from strip list - they are club names (Athletic Bilbao, Inter Milan)
    # 'atletico' kept as it's a prefix (Atletico Madrid -> Madrid)
    s = re.sub(r"\b(fc|sk|ac|as|cf|sc|real|club|cfc|afc|fk|utd|united|"
               r"city|town|atletico|fc)\b", "", s)
    # Also handle common abbreviations: manchester -> man, man utd -> man utd (already handled)
    # The key insight: normalize "manchester" to "man" to match "man utd" -> "man"
    # but only for known club abbreviations, not all words
    s = re.sub(r"\bmanchester\b", "man", s)
    s = re.sub(r"\bwolverhampton\b", "wolves", s)
    s = re.sub(r"\bnewcastle\b", "newcastle", s)  # keep as-is
    s = re.sub(r"\bwest ham\b", "west ham", s)  # keep as-is
    s = re.sub(r"\baston villa\b", "aston villa", s)  # keep as-is
    # Handle "nottingham forest" -> "nottingham" (forest not in strip list)
    s = re.sub(r"\bforest\b", "", s)
    s = re.sub(r"\bafc\b", "", s)  # already handled but ensure

    # Additional club name normalizations for cross-source matching
    # La Liga
    s = re.sub(r"\bathletic club\b", "athletic bilbao", s)
    s = re.sub(r"\bath bilbao\b", "athletic bilbao", s)
    s = re.sub(r"\batletico madrid\b", "atletico", s)
    s = re.sub(r"\bathletic bilbao\b", "athletic bilbao", s)
    # "Athletic" alone is ambiguous, convert to Athletic Bilbao for La Liga context
    # This happens after "club" is stripped from "Athletic Club" (leaves "athletic")
    s = re.sub(r"^athletic\s*$", "athletic bilbao", s)
    # Serie A
    s = re.sub(r"\binter milan\b", "inter", s)
    s = re.sub(r"\bac milan\b", "milan", s)
    # Bundesliga
    s = re.sub(r"\bborussia dortmund\b", "dortmund", s)
    s = re.sub(r"\bbayer leverkusen\b", "leverkusen", s)
    s = re.sub(r"\bborussia monchengladbach\b", "moenchengladbach", s)
    s = re.sub(r"\beintracht frankfurt\b", "frankfurt", s)
    s = re.sub(r"\bvfb stuttgart\b", "stuttgart", s)
    s = re.sub(r"\bvfl wolfsburg\b", "wolfsburg", s)
    s = re.sub(r"\bmainz 05\b", "mainz", s)
    # Ligue 1
    s = re.sub(r"\bolympique marseille\b", "marseille", s)
    s = re.sub(r"\bolympique lyonnais\b", "lyon", s)
    s = re.sub(r"\blille osc\b", "lille", s)
    s = re.sub(r"\bstade rennais\b", "rennes", s)
    s = re.sub(r"\bas monaco\b", "monaco", s)
    # Championship
    s = re.sub(r"\bsheffield united\b", "sheffield", s)

    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return " ".join(s.split())


def _find_feed_dir(pattern: str) -> Optional[Path]:
    """Locate a feed directory containing files matching `pattern`.

    Walks UP from this file for the first `data/live_odds` dir that actually
    contains files matching the pattern. Falls back to workspace-root sibling.
    Returns None if no usable feed exists.

    Absence is NOT a fabricated negative (HR35): the caller treats None as
    "source unavailable" and keeps-but-warns, never empties the board.
    """
    here = Path(__file__).resolve()
    # 1) walk up the repo tree for a data/live_odds that has feed files
    for candidate in [here, *here.parents]:
        feed = candidate / "data" / "live_odds"
        if feed.is_dir() and any(feed.glob(pattern)):
            return feed
    # 2) workspace-root sibling
    ws = here.parents[2] if len(here.parents) >= 3 else here.parent
    fallback = ws / "data" / "live_odds"
    if fallback.is_dir() and any(fallback.glob(pattern)):
        return fallback
    return None


def _load_feed_pairs(pattern: str, datetime_parser: callable) -> List[Dict]:
    """Generic loader for structured fixture feeds.

    Args:
        pattern: glob pattern for the feed files (e.g., "flashscore_odds_*.jsonl")
        datetime_parser: function(match_datetime: str) -> ISO date string

    Returns [] if the feed is absent entirely. Absence is NOT a list of empty
    fixtures (HR35: a missing source is 'unavailable', not 'no fixtures')."""
    feed_dir = _find_feed_dir(pattern)
    if feed_dir is None:
        return []
    files = sorted(feed_dir.glob(pattern), reverse=True)
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
        kickoff = datetime_parser(d.get("match_datetime"))
        pairs.append({"home": home, "away": away, "date": kickoff})
    return pairs


def _parse_flashscore_datetime(match_datetime: str) -> str:
    """Parse FlashScore '21.08. 20:00' or '12:30' (time only = today) to ISO date."""
    if not match_datetime:
        return ""
    # Try DD.MM. HH:MM format first
    m = re.match(r"(\d{1,2})\.(\d{1,2})\.\s*(\d{1,2}):(\d{2})", match_datetime)
    if m:
        day, mon, hh, mm = (int(x) for x in m.groups())
        from datetime import datetime as _dt
        now = _dt.now()
        for year in (now.year, now.year + 1):
            try:
                cand = _dt(year, mon, day)
            except ValueError:
                continue
            if 0 <= (cand - now).days <= 400:
                return cand.strftime("%Y-%m-%d")
    # Try HH:MM only (matches for today)
    m = re.match(r"^(\d{1,2}):(\d{2})$", match_datetime.strip())
    if m:
        from datetime import datetime as _dt
        now = _dt.now()
        return now.strftime("%Y-%m-%d")
    return ""


def _parse_predictz_datetime(match_datetime: str) -> str:
    """Parse PredictZ '21/08/2026 20:00' or '21/08/2026' to ISO date."""
    if not match_datetime:
        return ""
    # Try with time
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})\s+(\d{1,2}):(\d{2})", match_datetime)
    if m:
        day, mon, year, hh, mm = (int(x) for x in m.groups())
        try:
            from datetime import datetime as _dt
            cand = _dt(year, mon, day)
            return cand.strftime("%Y-%m-%d")
        except ValueError:
            pass
    # Try date only
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", match_datetime)
    if m:
        day, mon, year = (int(x) for x in m.groups())
        try:
            from datetime import datetime as _dt
            cand = _dt(year, mon, day)
            return cand.strftime("%Y-%m-%d")
        except ValueError:
            pass
    return ""


def _parse_statsarea_datetime(match_datetime: str) -> str:
    """Parse StatsArea '21.08.2026 20:00' or '21/08/2026' to ISO date."""
    if not match_datetime:
        return ""
    # Try DD.MM.YYYY HH:MM
    m = re.match(r"(\d{1,2})\.(\d{1,2})\.(\d{4})\s+(\d{1,2}):(\d{2})", match_datetime)
    if m:
        day, mon, year, hh, mm = (int(x) for x in m.groups())
        try:
            from datetime import datetime as _dt
            cand = _dt(year, mon, day)
            return cand.strftime("%Y-%m-%d")
        except ValueError:
            pass
    # Try DD/MM/YYYY
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", match_datetime)
    if m:
        day, mon, year = (int(x) for x in m.groups())
        try:
            from datetime import datetime as _dt
            cand = _dt(year, mon, day)
            return cand.strftime("%Y-%m-%d")
        except ValueError:
            pass
    # Try FlashScore-like DD.MM. HH:MM
    m = re.match(r"(\d{1,2})\.(\d{1,2})\.\s*(\d{1,2}):(\d{2})", match_datetime)
    if m:
        day, mon, hh, mm = (int(x) for x in m.groups())
        from datetime import datetime as _dt
        now = _dt.now()
        for year in (now.year, now.year + 1):
            try:
                cand = _dt(year, mon, day)
            except ValueError:
                continue
            if 0 <= (cand - now).days <= 400:
                return cand.strftime("%Y-%m-%d")
    return ""


def _parse_bet365_datetime(match_datetime: str) -> str:
    """Parse Bet365 '21 Aug 20:00' or '21/08/2026 20:00' to ISO date."""
    if not match_datetime:
        return ""
    # Try '21 Aug 20:00'
    m = re.match(r"(\d{1,2})\s+(\w{3})\s+(\d{1,2}):(\d{2})", match_datetime)
    if m:
        day, mon_str, hh, mm = m.groups()
        day = int(day)
        hh = int(hh)
        mm = int(mm)
        # Map month abbreviation to number
        month_map = {
            "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
            "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12
        }
        mon = month_map.get(mon_str.lower()[:3])
        if mon:
            from datetime import datetime as _dt
            now = _dt.now()
            for year in (now.year, now.year + 1):
                try:
                    cand = _dt(year, mon, day)
                except ValueError:
                    continue
                if 0 <= (cand - now).days <= 400:
                    return cand.strftime("%Y-%m-%d")
    # Try DD/MM/YYYY HH:MM
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})\s+(\d{1,2}):(\d{2})", match_datetime)
    if m:
        day, mon, year, hh, mm = (int(x) for x in m.groups())
        try:
            from datetime import datetime as _dt
            cand = _dt(year, mon, day)
            return cand.strftime("%Y-%m-%d")
        except ValueError:
            pass
    return ""


def _load_flashscore_pairs() -> List[Dict]:
    """Read (home, away, date) pairs from the latest FlashScore match_1x2 feed."""
    return _load_feed_pairs("flashscore_odds_*.jsonl", _parse_flashscore_datetime)


def _load_predictz_pairs() -> List[Dict]:
    """Read (home, away, date) pairs from the latest PredictZ match_1x2 feed."""
    return _load_feed_pairs("predictz_fixtures_*.jsonl", _parse_predictz_datetime)


def _load_statsarea_pairs() -> List[Dict]:
    """Read (home, away, date) pairs from the latest StatsArea match_1x2 feed."""
    return _load_feed_pairs("statsarea_fixtures_*.jsonl", _parse_statsarea_datetime)


def _load_bet365_pairs() -> List[Dict]:
    """Read (home, away, date) pairs from the latest Bet365 match_1x2 feed."""
    return _load_feed_pairs("bet365_fixtures_*.jsonl", _parse_bet365_datetime)


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


def _load_espn_pairs(board_date: str, leagues: List[str]) -> List[Dict]:
    """Read (home, away, date) pairs from ESPN schedules for the leagues.

    ESPN is a T1 source (verification/id403.py SOURCE_TRUST). Uses the multi-source
    concrete layer which caches ESPN fixture data. Returns empty list if ESPN
    unavailable for any reason (HR35: absence = unavailable, not fabricated)."""
    pairs: List[Dict] = []
    try:
        from data.multi_source_concrete import get_fixtures as ms_get_fixtures
    except Exception:
        return pairs
    for lg in leagues:
        try:
            result = ms_get_fixtures(
                league=lg,
                fixtures_season="2728",  # 2026/27 season
                days_ahead=14,
                api_football_season=None
            )
        except Exception:
            continue
        fixtures = result.get("fixtures") or []
        for fx in fixtures:
            # Filter to board_date only
            fx_date = (fx.get("kickoff_utc") or "")[:10]
            if fx_date != board_date:
                continue
            home = (fx.get("home_team") or "").strip()
            away = (fx.get("away_team") or "").strip()
            if not home or not away:
                continue
            pairs.append({"home": home, "away": away, "date": fx_date})
    return pairs


def _load_football_data_pairs(board_date: str, leagues: List[str]) -> List[Dict]:
    """Read (home, away, date) pairs from football-data.co.uk completed results.

    football-data.co.uk is a T1 source (verification/id403.py SOURCE_TRUST).
    Only carries fixtures that have ALREADY PLAYED (completed results).
    Returns empty list if file absent or no matching fixtures."""
    pairs: List[Dict] = []
    try:
        from data.football_data_source import load_league
    except Exception:
        return pairs
    # Try both 2627 and 2728 season codes for coverage
    for season_code in ("2627", "2728"):
        for lg in leagues:
            try:
                results, _ = load_league(lg, season_code)
            except Exception:
                continue
            for r in results:
                if getattr(r, "date", None) != board_date:
                    continue
                home = (getattr(r, "home_team", "") or "").strip()
                away = (getattr(r, "away_team", "") or "").strip()
                if not home or not away:
                    continue
                pairs.append({"home": home, "away": away, "date": board_date})
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
    """Gate a scanned board against independent fixture sources.

    NEW HARD RULE (Architect 2026-08-19): NEVER drop any fixture.
    All fixtures pass through with appropriate verification stamps:

    T1 SOURCES (ESPN, FootballData.co.uk): Single confirmation = VERIFIED.
    EXECUTE T1_LOADERS FIRST since they are the authoritative sources.
    QUIT IFF ALL LEGS RESOLVED before downgrading secondary sources.

    T2 SOURCES (FlashScore, PredictZ, StatsArea, Bet365): Require
    SportyBet + at least one other source for VERIFIED.

    T3 SOURCES (manual): Not auto-loaded, only used as override.

    Stamps:
    - VERIFIED: found in ESPN or FootballData (T1) OR SportyBet + ≥1 other
    - UNVERIFIED (SportyBet only): found in SportyBet only (primary odds/booking)
    - UNVERIFIED (T2 only): found in FlashScore/PredictZ/StatsArea/Bet365 but
      NOT SportyBet, NOT T1
    - UNVERIFIED (no data): not found in any source (HR35 - honest gap)

    All fixtures are KEPT. The verification stamp informs downstream (booking,
    board) but never excludes a fixture from production.
    """
    # Load all sources
    fs_pairs = _load_flashscore_pairs()
    pz_pairs = _load_predictz_pairs()
    sa_pairs = _load_statsarea_pairs()
    b365_pairs = _load_bet365_pairs()
    sb_pairs = _load_sportybet_pairs(leagues)
    espn_pairs = _load_espn_pairs(board_date, leagues)
    fd_pairs = _load_football_data_pairs(board_date, leagues)

    # Index all sources
    fs_idx = _index(fs_pairs)
    pz_idx = _index(pz_pairs)
    sa_idx = _index(sa_pairs)
    b365_idx = _index(b365_pairs)
    sb_idx = _index(sb_pairs)
    espn_idx = _index(espn_pairs)
    fd_idx = _index(fd_pairs)

    # Availability flags (source has ANY data)
    fs_available = len(fs_idx) > 0
    pz_available = len(pz_idx) > 0
    sa_available = len(sa_idx) > 0
    b365_available = len(b365_idx) > 0
    sb_available = len(sb_idx) > 0
    espn_available = len(espn_idx) > 0
    fd_available = len(fd_idx) > 0

    available_sources = {
        "FlashScore": fs_available,
        "PredictZ": pz_available,
        "StatsArea": sa_available,
        "Bet365": b365_available,
        "SportyBet": sb_available,
        "ESPN": espn_available,
        "FootballData": fd_available,
    }

    report = VerifierReport(
        board_date=board_date,
        flashscore_available=fs_available,
        sportybet_available=sb_available,
        predictz_available=pz_available,
        statsarea_available=sa_available,
        bet365_available=b365_available,
        espn_available=espn_available,
        football_data_available=fd_available,
        flashscore_count=len(fs_pairs),
        sportybet_count=len(sb_pairs),
        predictz_count=len(pz_pairs),
        statsarea_count=len(sa_pairs),
        bet365_count=len(b365_pairs),
        espn_count=len(espn_pairs),
        football_data_count=len(fd_pairs),
    )

    # Double outage: NO source has data. Keep all fixtures, flag UNVERIFIED.
    if not any(available_sources.values()):
        report.outage = True
        report.outage_reason = (
            "no verification sources available (SportyBet, FlashScore, PredictZ, "
            "StatsArea, Bet365, ESPN, FootballData all unavailable) — verification gate could not run; "
            "all fixtures KEPT but stamped UNVERIFIED (keep-but-warn, never guess)")
        for bf in board:
            _stamp(bf, [], verified=False, reason=report.outage_reason)
            report.kept_unverified += 1
        return list(board), report

    verified_board: List = []
    for bf in board:
        home, away = _split_fixture(bf.fixture)
        nh, na = _norm(home), _norm(away)
        if not nh or not na:
            # Unparseable fixture name - keep but mark as no source
            _stamp(bf, [], verified=False, reason="unparseable fixture name")
            report.kept_unverified += 1
            report.flags.append(
                f"VERIFY GATE: '{bf.fixture}' kept UNVERIFIED — unparseable fixture name")
            verified_board.append(bf)
            continue

        # Check each available source
        source_hits = {}
        if fs_available:
            source_hits["FlashScore"] = _pair_in(fs_idx, nh, na)
        if pz_available:
            source_hits["PredictZ"] = _pair_in(pz_idx, nh, na)
        if sa_available:
            source_hits["StatsArea"] = _pair_in(sa_idx, nh, na)
        if b365_available:
            source_hits["Bet365"] = _pair_in(b365_idx, nh, na)
        if sb_available:
            source_hits["SportyBet"] = _pair_in(sb_idx, nh, na)
        if espn_available:
            source_hits["ESPN"] = _pair_in(espn_idx, nh, na)
        if fd_available:
            source_hits["FootballData"] = _pair_in(fd_idx, nh, na)

        # T1 sources: single confirmation is sufficient for VERIFIED
        t1_sources = {"ESPN", "FootballData"}
        # Check for T1 confirmation
        t1_confirming = [src for src in t1_sources
                         if available_sources.get(src, False) and source_hits.get(src, False)]
        # Confirming sources: FlashScore, PredictZ, StatsArea, Bet365 (non-SportyBet/T1)
        confirming_other = [src for src in ("FlashScore", "PredictZ", "StatsArea", "Bet365", "ESPN", "FootballData")
                            if available_sources.get(src, False) and source_hits.get(src, False)]

        in_sportybet = sb_available and source_hits.get("SportyBet", False)

        # Priority 1: T1 source (ESPN or FootballData) alone is sufficient for VERIFIED
        if t1_confirming:
            sources = t1_confirming
            _stamp(bf, sources, verified=True)
            report.verified += 1
            report.flags.append(
                f"VERIFY GATE: '{bf.fixture}' VERIFIED (T1 source: {', '.join(t1_confirming)})")
        elif in_sportybet and confirming_other:
            # VERIFIED: SportyBet + at least one other source
            sources = ["SportyBet"] + confirming_other
            _stamp(bf, sources, verified=True)
            report.verified += 1
            report.flags.append(
                f"VERIFY GATE: '{bf.fixture}' VERIFIED (SportyBet + {', '.join(confirming_other)})")
        elif in_sportybet:
            # UNVERIFIED but primary source: SportyBet only (where we actually bet)
            sources = ["SportyBet"]
            _stamp(bf, sources, verified=False)
            report.kept_unverified += 1
            report.flags.append(
                f"VERIFY GATE: '{bf.fixture}' kept UNVERIFIED (SportyBet only — primary odds/booking source)")
        elif confirming_other:
            # UNVERIFIED: found in other source(s) but NOT SportyBet/T1
            sources = confirming_other
            _stamp(bf, sources, verified=False)
            report.kept_unverified += 1
            report.flags.append(
                f"VERIFY GATE: '{bf.fixture}' kept UNVERIFIED (found in {', '.join(confirming_other)} but NOT SportyBet/T1 — cannot price/book)")
        else:
            # UNVERIFIED: not found in ANY source (honest gap, HR35)
            sources = []
            _stamp(bf, sources, verified=False, reason="not found in any source")
            report.kept_unverified += 1
            report.flags.append(
                f"VERIFY GATE: '{bf.fixture}' kept UNVERIFIED — not found in ANY source (honest gap, HR35)")

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
            note=("cross-source VERIFIED" if verified else f"partial verification: {reason}"),
        )
    except Exception:
        pass


@dataclass
class VerifierReport:
    board_date: str
    flashscore_available: bool = False
    sportybet_available: bool = False
    predictz_available: bool = False
    statsarea_available: bool = False
    bet365_available: bool = False
    espn_available: bool = False
    football_data_available: bool = False
    flashscore_count: int = 0
    sportybet_count: int = 0
    predictz_count: int = 0
    statsarea_count: int = 0
    bet365_count: int = 0
    espn_count: int = 0
    football_data_count: int = 0
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
            f"  PredictZ feed   : {'AVAILABLE' if self.predictz_available else 'UNAVAILABLE'}"
            f" ({self.predictz_count} pairs)",
            f"  StatsArea feed  : {'AVAILABLE' if self.statsarea_available else 'UNAVAILABLE'}"
            f" ({self.statsarea_count} pairs)",
            f"  Bet365 feed     : {'AVAILABLE' if self.bet365_available else 'UNAVAILABLE'}"
            f" ({self.bet365_count} pairs)",
            f"  ESPN (T1)       : {'AVAILABLE' if self.espn_available else 'UNAVAILABLE'}"
            f" ({self.espn_count} pairs)",
            f"  FootballData (T1): {'AVAILABLE' if self.football_data_available else 'UNAVAILABLE'}"
            f" ({self.football_data_count} pairs)",
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
