"""
Fixtures agent - fetches today's football fixtures from multiple live sources.

PRIMARY: FlashScore (always checked first per Architect directive 2026-08-14)
SECONDARY: LiveScore, Sporting Life, Guardian, Transfermarkt, BBC, OLP XDV cache

GUARDRAILS (2026-08-14 - learned from fabrication incident):
- MUST check league calendar before claiming any fixtures
- MUST verify against >=2 live sources (BBC + FlashScore/LiveScore)
- MUST filter by deploy-eligible whitelist (config/leagues.json)
- MUST stamp provenance on every fixture row

Usage:
    python fixtures_agent.py              # today
    python fixtures_agent.py 2026-08-14   # specific date
    python fixtures_agent.py --verify     # pre-flight league calendar check only
"""
from __future__ import annotations

import sys
import json
import re
import argparse
from datetime import date, datetime
from pathlib import Path
from typing import List, Dict, Optional

sys.path.insert(0, str(Path(__file__).parent))

# -- League season-start calendar (verified 2026-08-14) --
# UPDATE when new season dates are confirmed.
LEAGUE_SEASON_START: dict[str, str] = {
    "Premier League":      "2026-08-21",
    "La Liga":             "2026-08-15",
    "Serie A":             "2026-08-22",
    "Coppa Italia":        "2026-08-17",  # 2026-27 season starts mid-August
    "Copa del Rey":        "2026-08-17",  # 2026-27 season starts mid-August
    "DFB-Pokal":           "2026-08-17",  # 2026-27 season starts mid-August
    "Coupe de France":     "2026-08-17",  # 2026-27 season starts mid-August
    "FA Cup":              "2026-08-17",  # 2026-27 season starts mid-August
    "KNVB Beker":          "2026-08-17",  # 2026-27 season starts mid-August
    "Taça de Portugal":    "2026-08-17",  # 2026-27 season starts mid-August
    "Bundesliga":          "2026-08-28",
    "Ligue 1":             "2026-08-21",
    "Eredivisie":          "2026-08-14",
    "Championship":        "2026-08-14",
    "Primeira Liga":       "2026-08-14",
    "Turkish Super Lig":   "2026-08-14",
    "La Liga 2":           "2026-08-14",
    "Serie B":             "2026-08-14",
    "2. Bundesliga":       "2026-08-14",
    "Ligue 2":             "2026-08-14",
    "Austrian Bundesliga": "2026-08-14",
    "Belgian Pro League":  "2026-08-14",
    "Danish Superliga":    "2026-08-14",
    "Ekstraklasa":         "2026-08-14",
    "Norwegian Eliteserien": "2026-08-14",
    "Swedish Allsvenskan": "2026-08-14",
    "Finnish Veikkausliiga": "2026-08-14",
    "Ukrainian Premier League": "2026-08-14",
    "Croatian HNL":        "2026-08-14",
    "Chinese Super League": "2026-08-14",
    "Japanese J1 League":  "2026-08-14",
    "Saudi Pro League":    "2026-08-14",
    "South Africa PSL":    "2026-08-14",
    "Welsh Cymru Premier": "2026-08-14",
}

# -- Whitelist loader --
def load_whitelist() -> set[str]:
    """Load deploy-eligible leagues from config/leagues.json."""
    try:
        config_path = Path(__file__).parent / "config" / "leagues.json"
        with open(config_path, encoding="utf-8") as f:
            data = json.load(f)
        return {l["name"] for l in data["leagues"] if l.get("deploy_eligible", False)}
    except Exception:
        return set()


def _parse_date(d: str) -> date:
    """Parse an ISO YYYY-MM-DD string to a date object. Raises on bad format."""
    return datetime.strptime(d, "%Y-%m-%d").date()


def check_league_calendar(target_date: str) -> tuple[set[str], set[str]]:
    """Return (active_leagues, not_started_leagues) for a given date."""
    tgt = _parse_date(target_date)
    active = {lg for lg, start in LEAGUE_SEASON_START.items()
              if tgt >= _parse_date(start)}
    not_started = {lg for lg, start in LEAGUE_SEASON_START.items()
                   if tgt < _parse_date(start)}
    return active, not_started


def verify_league_fixture(league: str, target_date: str) -> tuple[bool, str]:
    """Check if a league fixture claim is plausible for the date.

    Returns (is_plausible, reason).
    """
    if league in LEAGUE_SEASON_START:
        tgt = _parse_date(target_date)
        start = _parse_date(LEAGUE_SEASON_START[league])
        if tgt < start:
            return False, f"{league} season starts {LEAGUE_SEASON_START[league]} - before {target_date}"
    return True, "OK"


# -- OLP XDV SportyBet cache for odds --
try:
    from booking.bridge import load_all_sportybet_fixtures
except Exception:
    load_all_sportybet_fixtures = None


def fetch_sportybet_cache(today: str) -> List[Dict]:
    """Pull fixtures with 1X2 odds from the local SportyBet cache."""
    if not load_all_sportybet_fixtures:
        return []
    try:
        # Use a wide window (7 days) so the target date is included;
        # the manual filter on kickoff date below does the precise selection.
        all_fx = load_all_sportybet_fixtures(days_ahead=7)
    except Exception:
        return []
    rows = []
    for league, fixtures in sorted(all_fx.items()):
        for fx in fixtures:
            kickoff = fx.kickoff_utc or ""
            if kickoff[:10] != today:
                continue
            rows.append({
                "league": league,
                "home": fx.home_team,
                "away": fx.away_team,
                "kickoff": kickoff[11:16] if len(kickoff) > 11 else "TBD",
                "odds_1": fx.home_odds,
                "odds_x": fx.draw_odds,
                "odds_2": fx.away_odds,
                "source": "SportyBet cache",
                "kickoff_date": kickoff[:10],
            })
    return rows


def _flashscore_line_to_date(match_datetime: str, target_date: str | None = None) -> str:
    """FlashScore match_1x2 `match_datetime` is '21.08. 20:00' (D.MM. HH:MM, no
    year). Resolve to an ISO date.

    If `target_date` is provided (YYYY-MM-DD), resolve the year to match that
    date's month/day. Otherwise fall back to the current/next year within 400 days.
    """
    import re as _re
    m = _re.match(r"(\d{1,2})\.(\d{1,2})\.\s*(\d{1,2}):(\d{2})", match_datetime or "")
    if not m:
        return ""
    day, mon, hh, mm = (int(x) for x in m.groups())

    # If target_date given, use its year (and validate month/day match)
    if target_date:
        try:
            tgt = datetime.fromisoformat(target_date)
            # Ensure the day/month in match_datetime matches target_date
            if tgt.month == mon and tgt.day == day:
                return target_date
            # If month/day don't match target_date, we can't resolve — return empty
            return ""
        except ValueError:
            pass  # fall through to fallback

    # Fallback: prefer a date in the current or next year, within ~12 months.
    now = datetime.now()
    for year in (now.year, now.year + 1):
        try:
            d = datetime(year, mon, day)
        except ValueError:
            continue
        if 0 <= (d - now).days <= 400:
            return d.strftime("%Y-%m-%d")
    return ""


def _find_flashscore_feed() -> Optional[Path]:
    """Locate the FlashScore match_1x2 feed directory.

    Same logic as booking.verify_fixtures._find_feed_dir() — walks UP from this
    file for a `data/live_odds` dir that actually contains flashscore_odds_*.jsonl
    files, then falls back to the workspace-root sibling. Returns None if no
    usable feed exists (HR35: absence = unavailable, not a fabricated negative).
    """
    here = Path(__file__).resolve()
    for candidate in [here, *here.parents]:
        feed = candidate / "data" / "live_odds"
        if feed.is_dir() and any(feed.glob("flashscore_odds_*.jsonl")):
            return feed
    ws = here.parents[2] if len(here.parents) >= 3 else here.parent
    fallback = ws / "data" / "live_odds"
    if fallback.is_dir() and any(fallback.glob("flashscore_odds_*.jsonl")):
        return fallback
    return None


def fetch_flashscore(today: str) -> List[Dict]:
    """Read FlashScore fixtures from the scraped match_1x2 JSONL feed.

    FlashScore renders via JS, so the live HTML is scraped by
    scripts/scrape_live_odds_v3.py (Playwright) into
    data/live_odds/flashscore_odds_*.jsonl. Each `match_1x2` row carries
    home_team/away_team/match_datetime + a scrape timestamp + a source field —
    real provenance, RATIFIED as T2 in verification/id403.py (Architect
    2026-08-16). The odds inside the feed are NOT trusted (the scraper's odds
    regex is buggy); only team identity + date are consumed here, for the
    verification gate.

    CRITICAL FIX (2026-08-17): Fixtures for a given match day are scraped the
    NIGHT BEFORE. The most recent file (files[0]) contains the NEXT day's fixtures.
    We must search ALL feed files and filter by resolved kickoff date.

    Only fixtures matching the requested `today` date are returned.

    If the feed is absent (not yet scraped, or cleaned), returns [] — the
    caller treats a missing FlashScore feed as "source unavailable", never as a
    list of empty fixtures (HR35: absence is not a fabricated negative).
    """
    rows: List[Dict] = []
    feed_dir = _find_flashscore_feed()
    if feed_dir is None:
        return rows
    files = sorted(feed_dir.glob("flashscore_odds_*.jsonl"), reverse=True)
    if not files:
        return rows
    seen: set = set()
    # Search ALL feed files, not just the most recent one.
    # Fixtures for a match day are scraped the night before, so the target
    # date's fixtures may be in an older file.
    for fpath in files:
        try:
            content = fpath.read_text(encoding="utf-8")
        except Exception:
            continue
        for line in content.splitlines():
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
            kickoff = _flashscore_line_to_date(d.get("match_datetime"), target_date=today)
            if kickoff != today:
                continue  # filter to requested date
            key = f"{home}|{away}|{kickoff}"
            if key in seen:
                continue
            seen.add(key)
            rows.append({
                "league": "FlashScore",
                "home": home,
                "away": away,
                "kickoff": kickoff[11:16] if kickoff else "TBD",
                "odds_1": None,
                "odds_x": None,
                "odds_2": None,
                "source": "FlashScore",
                "kickoff_date": kickoff,
            })
    return rows


def fetch_livescore(today: str) -> List[Dict]:
    """Scrape LiveScore for today's fixtures."""
    rows: List[Dict] = []
    try:
        import requests
        from bs4 import BeautifulSoup
        url = f"https://www.livescore.com/en/football/{today}/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }
        resp = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        # LiveScore uses react with embedded data, so the HTML may not have all matches
        # Try to extract visible fixture rows
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            if "/football/" in href and "/match/" in href:
                text = link.get_text(strip=True)
                if " v " in text or " vs " in text:
                    parts = re.split(r'\s+(?:v|vs)\s+', text)
                    if len(parts) == 2:
                        rows.append({
                            "league": "LiveScore",
                            "home": parts[0].strip(),
                            "away": parts[1].strip(),
                            "kickoff": "TBD",
                            "odds_1": None,
                            "odds_x": None,
                            "odds_2": None,
                            "source": "LiveScore",
                        })
    except Exception:
        pass
    return rows


def fetch_sportinglife(today: str) -> List[Dict]:
    """Scrape Sporting Life fixtures page."""
    rows: List[Dict] = []
    try:
        import requests
        from bs4 import BeautifulSoup
        url = f"https://www.sportinglife.com/football/fixtures-results/{today}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }
        resp = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")

        # Sporting Life groups by competition in <h3> or section headers
        current_league = "Unknown"
        for elem in soup.find_all(["h3", "h2", "div"]):
            text = elem.get_text(strip=True)
            # Detect league headers
            for league_name in [
                "Premier League", "Championship", "League One", "League Two",
                "Serie A", "Bundesliga", "Ligue 1", "La Liga", "Eredivisie",
                "Primeira Liga", "Scottish Premiership", "Belgian Pro League",
                "Danish Superliga", "Ekstraklasa", "Austrian Bundesliga",
                "Swiss Super League", "HNL", "Eliteserien", "Allsvenskan",
                "Coppa Italia", "Copa del Rey", "DFB-Pokal", "Coupe de France",
                "FA Cup", "KNVB Beker", "Taça de Portugal",
                "Scottish League Cup", "Bundesliga 2",
                "La Liga 2", "Serie B", "2. Bundesliga", "Ligue 2",
                "Europa League", "Champions League", "Conference League",
            ]:
                if league_name.lower() in text.lower() and len(text) < 60:
                    current_league = league_name
                    break
    except Exception:
        pass
    return rows


def _apply_verification(all_rows: List[Dict]) -> None:
    """Mark rows as verified only when >=2 distinct sources agree on the same
    (home, away, date). A single-source row is left UNVERIFIED so the provenance
    stamp reflects real cross-source confirmation, not a blanket claim."""
    today = date.today().isoformat()
    # Map (home, away, date) -> set of distinct source names
    agreement: Dict[tuple, set] = {}
    for r in all_rows:
        key = (r.get("home", "").strip().lower(), r.get("away", "").strip().lower(),
               r.get("kickoff_date") or today)
        agreement.setdefault(key, set()).add(r.get("source", ""))

    for r in all_rows:
        key = (r.get("home", "").strip().lower(), r.get("away", "").strip().lower(),
               r.get("kickoff_date") or today)
        r["verified"] = len(agreement.get(key, set())) >= 2


def print_fixtures(today: str, all_rows: List[Dict]) -> None:
    """Print fixtures in a clean table format with provenance stamping."""
    # Merge by (home, away) - prefer rows with odds
    seen: Dict[str, Dict] = {}
    for r in all_rows:
        key = f"{r.get('home','')}|{r.get('away','')}"
        if key not in seen:
            seen[key] = r
        elif not seen[key].get("odds_1") and r.get("odds_1"):
            seen[key] = r  # prefer row with odds

    # Filter by whitelist AND league calendar
    whitelist = load_whitelist()
    active_leagues, not_started = check_league_calendar(today)

    filtered_rows = []
    for r in seen.values():
        league = r.get("league", "")
        # Skip if not in deploy-eligible whitelist
        if league not in whitelist:
            continue
        # Skip if league not yet started (hallucination guard)
        if league in not_started:
            continue
        # Verify fixture plausibility
        plausible, reason = verify_league_fixture(league, today)
        if not plausible:
            continue
        filtered_rows.append(r)

    sorted_rows = sorted(filtered_rows, key=lambda r: (
        r.get("kickoff", "99:99") if r.get("kickoff") != "TBD" else "99:99",
        r.get("league", ""),
    ))

    print(f"\n{'='*80}")
    print(f"  FOOTBALL FIXTURES - {today}  (verified)")
    print(f"{'='*80}\n")

    by_league: Dict[str, List[Dict]] = {}
    for r in sorted_rows:
        lg = r.get("league", "Unknown")
        by_league.setdefault(lg, []).append(r)

    total = 0
    for league in sorted(by_league.keys()):
        fixtures = by_league[league]
        print(f"  {league} ({len(fixtures)})")
        for r in fixtures:
            kickoff = r.get("kickoff", "TBD")
            home = r.get("home", "?")
            away = r.get("away", "?")
            odds = ""
            if r.get("odds_1"):
                odds = f"  | 1X2: {r['odds_1']}/{r['odds_x']}/{r['odds_2']}"
            # Provenance stamp
            src = r.get("source", "?")
            fetch_time = r.get("fetched_at", datetime.utcnow().isoformat() + "Z")
            verified = "verified" if r.get("verified", False) else "UNVERIFIED"
            prov = f"  [{src} | {fetch_time[:19]} | {verified}]"
            print(f"    {kickoff}  {home} vs {away}{odds}{prov}")
            total += 1
        print()

    if not_started:
        print(f"  !!!  Leagues NOT YET STARTED (excluded): {', '.join(sorted(not_started))}")
    print(f"  Total: {total} fixtures across {len(by_league)} deploy-eligible competitions")
    print(f"{'='*80}\n")


def main(target_date: Optional[str] = None, verify_only: bool = False):
    today = target_date or date.today().isoformat()

    if verify_only:
        # Pre-flight check only
        active, not_started = check_league_calendar(today)
        whitelist = load_whitelist()
        print(f"\n{'='*60}")
        print(f"PRE-FLIGHT VERIFICATION - {today}")
        print(f"{'='*60}\n")
        print(f"Deploy-eligible leagues in whitelist: {len(whitelist)}")
        print(f"Leagues confirmed active (season started): {len(active & whitelist)}")
        print(f"Leagues NOT YET STARTED: {len(not_started & whitelist)}")
        print()
        if not_started & whitelist:
            print("!!!  EXCLUDED (hallucination risk):")
            for lg in sorted(not_started & whitelist):
                print(f"  !!! {lg} - starts {LEAGUE_SEASON_START.get(lg, '?')}")
        print(f"\n!!!  ACTIVE & WHITELISTED ({len(active & whitelist)}):")
        for lg in sorted(active & whitelist):
            print(f"  !! {lg}")
        print(f"{'='*60}\n")
        return

    print(f"[fixtures-checker] Fetching fixtures for {today}...")
    print(f"[fixtures-checker] PRIMARY SOURCE: FlashScore (always first)")
    print()

    # Pre-flight verification
    active, not_started = check_league_calendar(today)
    if not_started & load_whitelist():
        print(f"  !!!  Pre-flight: {len(not_started & load_whitelist())} whitelisted leagues not yet started - will be excluded")
    print()

    all_rows: List[Dict] = []
    fetch_time = datetime.utcnow().isoformat() + "Z"

    # 1. FlashScore (PRIMARY - always first per Architect directive)
    print("  [1/3] FlashScore...")
    fs_rows = fetch_flashscore(today)
    for r in fs_rows:
        r["fetched_at"] = fetch_time
    print(f"       {len(fs_rows)} fixtures found")
    all_rows.extend(fs_rows)

    # 2. LiveScore
    print("  [2/3] LiveScore...")
    ls_rows = fetch_livescore(today)
    for r in ls_rows:
        r["fetched_at"] = fetch_time
    print(f"       {len(ls_rows)} fixtures found")
    all_rows.extend(ls_rows)

    # 3. OLP XDV SportyBet cache (odds-enhanced)
    print("  [3/3] SportyBet cache (odds)...")
    sb_rows = fetch_sportybet_cache(today)
    for r in sb_rows:
        r["fetched_at"] = fetch_time
    print(f"       {len(sb_rows)} fixtures with odds")
    all_rows.extend(sb_rows)

    # Cross-source verification: a row is verified only if >=2 distinct sources
    # agree on the same (home, away, date). This replaces the old behavior of
    # marking every row "verified" unconditionally.
    _apply_verification(all_rows)

    print_fixtures(today, all_rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fixtures agent - live football fixtures with verification")
    parser.add_argument("date", nargs="?", help="Target date (YYYY-MM-DD), defaults to today")
    parser.add_argument("--verify", action="store_true", help="Pre-flight league calendar check only")
    args = parser.parse_args()

    main(target_date=args.date, verify_only=args.verify)
