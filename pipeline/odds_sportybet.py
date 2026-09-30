"""
PROTOTYPE — SportyBet as a live odds source (the book the Architect bets into).

WHY THIS IS THE RIGHT SOURCE
  the-odds-api is metered (500/mo, shared across all leagues) and quotes
  Bet365/Pinnacle — books the Architect may not use in Nigeria. SportyBet is the
  book he ACTUALLY bets into, so its price is the truest "price you can take"
  (the doctrine pipeline.odds._best_price already encodes). SportyBet publishes
  a free, keyless JSON API — verified reachable, returning the FULL market
  ladder (1X2, Over/Under at every line, Double Chance, GG/NG, DNB, Odd/Even…).

  It also covers leagues the free sources can't: Danish Superliga and (to verify)
  Ekstraklasa are on SportyBet but NOT in football-data's fixtures feed.

STATUS — PROTOTYPE, NOT WIRED INTO THE PIPELINE
  This module fetches and parses; it is NOT yet in fetch_odds_chained and does
  NOT feed the capital/MES path. Two things gate promotion, both by design:
    1. Team-alias verification (HR35): SportyBet team names must be mapped to the
       model's keys by a VERIFIED pair list (as pipeline.odds.TEAM_ALIASES does
       for the-odds-api), never fuzzy-matched. Until then unmapped names pass
       through and simply won't join the model's fixtures (fail-safe: NO DATA,
       never a wrong match).
    2. Architect review — SportyBet is a single book, so a price from here is
       SINGLE-SOURCE unless cross-checked (see pipeline.odds_verify).

  ToS note: this reads SportyBet's own public endpoint for the Architect's own
  betting decisions. It can be rate-limited or changed by SportyBet at any time.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.odds import FixtureOdds, MarketQuote

API = ("https://www.sportybet.com/api/ng/factsCenter/pcUpcomingEvents"
       "?sportId=sr:sport:1&marketId=1,18,10,29,11,26&pageSize=100&pageNum={page}")
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# Framework league -> SportyBet tournament name (verified live 2026-09-30 against
# the SportyBet upcoming-events feed). Matched on the tournament NAME the feed
# returns, so a Sportradar ID renumber doesn't silently break it.
SPORTYBET_TOURNAMENTS = {
    "Eredivisie": "Eredivisie",
    "Belgian Pro League": "Pro League",
    "Scottish Premiership": "Premiership",
    "Danish Superliga": "Superliga",
    "Ekstraklasa": "Ekstraklasa",          # to confirm has upcoming events
    "Premier League": "Premier League",
    "Championship": "Championship",
    "Serie A": "Serie A",
    "Bundesliga": "Bundesliga",
    "Ligue 1": "Ligue 1",
    "La Liga": "LaLiga",
}


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": _UA,
                                               "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def parse_markets(event: dict) -> list[dict]:
    """The FULL market ladder for one event, structured and source-agnostic.

    Each entry: {id, desc, specifier, outcomes:[{desc, odds}]}. Nothing is
    dropped — this is every market SportyBet returned, for display or future use;
    to_fixture_odds() maps the subset the model actually predicts."""
    out = []
    for m in event.get("markets", []):
        out.append({
            "id": m.get("id"),
            "desc": m.get("desc"),
            "specifier": m.get("specifier", ""),
            "outcomes": [{"desc": o.get("desc"), "odds": o.get("odds")}
                         for o in m.get("outcomes", [])],
        })
    return out


def _price(markets: list[dict], desc: str, outcome: str,
           specifier: str = "") -> Optional[float]:
    for m in markets:
        if m["desc"] != desc or (specifier and m["specifier"] != specifier):
            continue
        for o in m["outcomes"]:
            if o["desc"] == outcome and o["odds"] not in (None, ""):
                try:
                    return float(o["odds"])
                except (TypeError, ValueError):
                    return None
    return None


def to_fixture_odds(event: dict, league: str, markets: list[dict],
                    now: str) -> FixtureOdds:
    """Map SportyBet's markets to the model's FixtureOdds (1X2 + O/U 2.5).

    Team names pass through UNCHANGED for now — see the alias note in the module
    docstring. bookmaker is 'sportybet' because that is literally the book."""
    def mq(price):
        return MarketQuote(price=price, bookmaker="sportybet", n_books=1,
                           captured_at=now) if price else MarketQuote(captured_at=now)

    ko = event.get("estimateStartTime")
    kickoff = ""
    if ko:  # SportyBet gives epoch millis
        kickoff = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(ko) / 1000))

    return FixtureOdds(
        league=league,
        home_team=(event.get("homeTeamName") or "").strip(),
        away_team=(event.get("awayTeamName") or "").strip(),
        kickoff_utc=kickoff,
        home=mq(_price(markets, "1X2", "Home")),
        draw=mq(_price(markets, "1X2", "Draw")),
        away=mq(_price(markets, "1X2", "Away")),
        over25=mq(_price(markets, "Over/Under", "Over 2.5", specifier="total=2.5")),
        under25=mq(_price(markets, "Over/Under", "Under 2.5", specifier="total=2.5")),
        source="sportybet.com",
        source_tier="T1",
    )


def fetch_odds_sportybet(league: str, max_pages: int = 8
                         ) -> tuple[list[FixtureOdds], list[str]]:
    """Live SportyBet prices for one league. Returns (fixtures, flags).

    Prototype: paginates the upcoming-events feed and keeps the tournament whose
    name maps to `league`. Returns [] (with a flag) for a league SportyBet has no
    upcoming events for, rather than guessing."""
    flags: list[str] = []
    tname = SPORTYBET_TOURNAMENTS.get(league)
    if not tname:
        flags.append(f"{league}: no SportyBet tournament mapping — NO DATA — PENDING")
        return [], flags

    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    out: list[FixtureOdds] = []
    total = None
    for page in range(1, max_pages + 1):
        try:
            data = _get(API.format(page=page)).get("data", {})
        except Exception as e:  # noqa: BLE001 — honest degrade, caller reports
            flags.append(f"{league}: SportyBet fetch failed p{page} ({e})")
            break
        total = data.get("totalNum", total)
        for t in data.get("tournaments", []):
            if t.get("name") != tname:
                continue
            for ev in t.get("events", []):
                out.append(to_fixture_odds(ev, league, parse_markets(ev), now))
        if total is not None and page * 100 >= total:
            break

    flags.append(f"{league}: {len(out)} fixture(s) priced from SportyBet "
                 f"({tname})")
    return out, flags


if __name__ == "__main__":  # live smoke demo
    import sys
    lg = sys.argv[1] if len(sys.argv) > 1 else "Eredivisie"
    fx, fl = fetch_odds_sportybet(lg)
    for f in fl:
        print("FLAG:", f)
    for q in fx[:5]:
        print(f"\n{q.home_team} v {q.away_team}  ({q.kickoff_utc})")
        print(f"  1X2: {q.home.price}/{q.draw.price}/{q.away.price}  "
              f"O/U2.5: {q.over25.price}/{q.under25.price}  [{q.home.bookmaker}]")
