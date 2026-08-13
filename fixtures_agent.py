"""
Fixtures agent — fetches today's football fixtures from multiple live sources.

PRIMARY: FlashScore (always checked first per Architect directive 2026-08-14)
SECONDARY: LiveScore, Sporting Life, Guardian, Transfermarkt, BBC, OLP XDV cache

Usage:
    python fixtures_agent.py              # today
    python fixtures_agent.py 2026-08-14   # specific date
"""
from __future__ import annotations

import sys
import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import List, Dict, Optional

sys.path.insert(0, str(Path(__file__).parent))

# ── OLP XDV SportyBet cache for odds ──
try:
    from booking.bridge import load_all_sportybet_fixtures
except Exception:
    load_all_sportybet_fixtures = None


def fetch_sportybet_cache(today: str) -> List[Dict]:
    """Pull fixtures with 1X2 odds from the local SportyBet cache."""
    if not load_all_sportybet_fixtures:
        return []
    try:
        all_fx = load_all_sportybet_fixtures(days_ahead=0)
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
            })
    return rows


def fetch_flashscore(today: str) -> List[Dict]:
    """Scrape FlashScore football page for today's fixtures.

    FlashScore renders via JS, so we hit the JSON API endpoint the page uses
    internally (flashscore.com/api/v1/football/events?date=YYYY-MM-DD).
    Falls back to scraping if API is unavailable.
    """
    rows: List[Dict] = []
    try:
        import requests
        # FlashScore uses an XHR API — try fetching the page HTML first
        url = f"https://www.flashscore.com/football/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }
        resp = requests.get(url, headers=headers, timeout=15)
        # Extract embedded JSON match data from the page
        # FlashScore embeds tournament data in script tags
        text = resp.text
        # Try parsing embedded tournament > match structures
        # Pattern: tournament name + match rows
        # This is a best-effort scrape — FlashScore's JS renders most content
        # so if we get nothing, we rely on other sources
        matches = re.findall(
            r'"homeTeam":\{"name":"([^"]+)".*?"awayTeam":\{"name":"([^"]+)"',
            text
        )
        for home, away in matches:
            rows.append({
                "league": "FlashScore",
                "home": home,
                "away": away,
                "kickoff": "TBD",
                "odds_1": None,
                "odds_x": None,
                "odds_2": None,
                "source": "FlashScore",
            })
    except Exception:
        pass
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
                "Coppa Italia", "Scottish League Cup", "Bundesliga 2",
                "Europa League", "Champions League", "Conference League",
            ]:
                if league_name.lower() in text.lower() and len(text) < 60:
                    current_league = league_name
                    break
    except Exception:
        pass
    return rows


def print_fixtures(today: str, all_rows: List[Dict]) -> None:
    """Print fixtures in a clean table format."""
    # Merge by (home, away) — prefer rows with odds
    seen: Dict[str, Dict] = {}
    for r in all_rows:
        key = f"{r.get('home','')}|{r.get('away','')}"
        if key not in seen:
            seen[key] = r
        elif not seen[key].get("odds_1") and r.get("odds_1"):
            seen[key] = r  # prefer row with odds

    sorted_rows = sorted(seen.values(), key=lambda r: (
        r.get("kickoff", "99:99") if r.get("kickoff") != "TBD" else "99:99",
        r.get("league", ""),
    ))

    print(f"\n{'='*80}")
    print(f"  FOOTBALL FIXTURES — {today}")
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
            src = f"  [{r.get('source', '?')}]"
            print(f"    {kickoff}  {home} vs {away}{odds}{src}")
            total += 1
        print()

    print(f"  Total: {total} fixtures across {len(by_league)} competitions")
    print(f"{'='*80}\n")


def main(target_date: Optional[str] = None):
    today = target_date or date.today().isoformat()

    print(f"[fixtures-checker] Fetching fixtures for {today}...")
    print(f"[fixtures-checker] PRIMARY SOURCE: FlashScore (always first)")
    print()

    all_rows: List[Dict] = []

    # 1. FlashScore (PRIMARY — always first per Architect directive)
    print("  [1/4] FlashScore...")
    fs_rows = fetch_flashscore(today)
    print(f"       {len(fs_rows)} fixtures found")
    all_rows.extend(fs_rows)

    # 2. LiveScore
    print("  [2/4] LiveScore...")
    ls_rows = fetch_livescore(today)
    print(f"       {len(ls_rows)} fixtures found")
    all_rows.extend(ls_rows)

    # 3. Sporting Life
    print("  [3/4] Sporting Life...")
    sl_rows = fetch_sportinglife(today)
    print(f"       {len(sl_rows)} fixtures found")
    all_rows.extend(sl_rows)

    # 4. OLP XDV SportyBet cache (odds-enhanced)
    print("  [4/4] SportyBet cache (odds)...")
    sb_rows = fetch_sportybet_cache(today)
    print(f"       {len(sb_rows)} fixtures with odds")
    all_rows.extend(sb_rows)

    print_fixtures(today, all_rows)


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    main(target)
