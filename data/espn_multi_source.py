"""
ESPN Multi-Source Integration — registers ESPN data sources with the multi-source fabric.

This module creates DataSource wrappers for the ESPN modules and registers them
with the global SourceRegistry for health monitoring and automatic failover.

Priority ordering (lower = higher priority):
- Priority 0: ESPN (free, fast, primary for many leagues)
- Priority 10: TheSportsDB (existing fixtures source)
- Priority 20: football-data.co.uk (existing results/odds source)
- Priority 30: The Odds API (paid, odds primary)
"""

from __future__ import annotations

from typing import List, Optional

from data.multi_source import (
    DataSource,
    MultiSource,
    SourceNoData,
    build_multi_source,
    registry,
)

# Import ESPN modules
from data.espn_results import fetch_results_for_date, MatchResult
from data.espn_lineups import fetch_lineups_for_date, MatchLineup
from data.espn_winprob import fetch_winprob_for_date, WinProbability


# --- Results Sources ---

class ESPNResultsSource(DataSource[List[MatchResult]]):
    """ESPN results source - completed matches with closing odds."""

    def __init__(self, league: str):
        super().__init__(name=f"espn_results_{league}", priority=0)
        self.league = league

    def fetch(self, target_date: str, **kwargs) -> List[MatchResult]:
        results = fetch_results_for_date(target_date, self.league)
        if not results:
            raise SourceNoData(f"No ESPN results for {self.league} on {target_date}")
        return results


class ESPNLineupsSource(DataSource[List[MatchLineup]]):
    """ESPN lineups source - confirmed starting XIs with formations."""

    def __init__(self, league: str):
        super().__init__(name=f"espn_lineups_{league}", priority=0)
        self.league = league

    def fetch(self, target_date: str, **kwargs) -> List[MatchLineup]:
        results = fetch_lineups_for_date(target_date, self.league)
        if not results:
            raise SourceNoData(f"No ESPN lineups for {self.league} on {target_date}")
        return results


class ESPNWinProbSource(DataSource[List[WinProbability]]):
    """ESPN win probability source - live/in-match win probabilities."""

    def __init__(self, league: str):
        super().__init__(name=f"espn_winprob_{league}", priority=0)
        self.league = league

    def fetch(self, target_date: str, **kwargs) -> List[WinProbability]:
        results = fetch_winprob_for_date(target_date, self.league)
        if not results:
            raise SourceNoData(f"No ESPN winprob for {self.league} on {target_date}")
        return results


# --- Multi-Source Factories ---

def create_results_multi_source(league: str) -> MultiSource[List[MatchResult]]:
    """Create a multi-source for match results with ESPN as primary."""
    sources = [
        (lambda td, lg=league: fetch_results_for_date(td, lg), f"espn_results_{league}", 0),
    ]
    return build_multi_source(f"results_{league}", sources)


def create_lineups_multi_source(league: str) -> MultiSource[List[MatchLineup]]:
    """Create a multi-source for lineups with ESPN as primary."""
    sources = [
        (lambda td, lg=league: fetch_lineups_for_date(td, lg), f"espn_lineups_{league}", 0),
    ]
    return build_multi_source(f"lineups_{league}", sources)


def create_winprob_multi_source(league: str) -> MultiSource[List[WinProbability]]:
    """Create a multi-source for win probabilities with ESPN as primary."""
    sources = [
        (lambda td, lg=league: fetch_winprob_for_date(td, lg), f"espn_winprob_{league}", 0),
    ]
    return build_multi_source(f"winprob_{league}", sources)


# --- Registration Functions ---

def register_espn_sources_for_league(league: str) -> dict:
    """
    Register all ESPN multi-sources for a league with the global registry.

    Returns dict of created multi-sources.
    """
    results_ms = create_results_multi_source(league)
    lineups_ms = create_lineups_multi_source(league)
    winprob_ms = create_winprob_multi_source(league)

    registry.register(results_ms)
    registry.register(lineups_ms)
    registry.register(winprob_ms)

    return {
        "results": results_ms,
        "lineups": lineups_ms,
        "winprob": winprob_ms,
    }


def register_all_espn_sources(leagues: Optional[List[str]] = None) -> dict:
    """
    Register ESPN sources for all leagues (or specified subset).

    Returns dict mapping league -> {results, lineups, winprob} multi-sources.
    """
    from data.espn_source import LEAGUE_MAP

    target_leagues = leagues or list(LEAGUE_MAP.keys())
    registered = {}

    for league in target_leagues:
        registered[league] = register_espn_sources_for_league(league)

    return registered


# --- Convenience Fetch Functions ---

def fetch_results_multi(league: str, target_date: str) -> List[MatchResult]:
    """Fetch results using the multi-source fabric (with failover)."""
    ms = registry.get_source(f"results_{league}")
    if ms is None:
        ms = create_results_multi_source(league)
        registry.register(ms)
    result = ms.fetch(target_date=target_date)
    return result.data or []


def fetch_lineups_multi(league: str, target_date: str) -> List[MatchLineup]:
    """Fetch lineups using the multi-source fabric (with failover)."""
    ms = registry.get_source(f"lineups_{league}")
    if ms is None:
        ms = create_lineups_multi_source(league)
        registry.register(ms)
    result = ms.fetch(target_date=target_date)
    return result.data or []


def fetch_winprob_multi(league: str, target_date: str) -> List[WinProbability]:
    """Fetch win probabilities using the multi-source fabric (with failover)."""
    ms = registry.get_source(f"winprob_{league}")
    if ms is None:
        ms = create_winprob_multi_source(league)
        registry.register(ms)
    result = ms.fetch(target_date=target_date)
    return result.data or []


# --- Health Reporting ---

def get_espn_health_report() -> dict:
    """Get health report for all registered ESPN sources."""
    report = registry.get_health_report()
    # Filter to ESPN sources only
    espn_sources = {
        name: data for name, data in report.get("sources", {}).items()
        if name.startswith("espn_") or name.startswith("results_") or name.startswith("lineups_") or name.startswith("winprob_")
    }
    return {
        "timestamp": report["timestamp"],
        "espn_sources": espn_sources,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ESPN Multi-Source integration test")
    parser.add_argument("--league", default="La Liga", help="League to test")
    parser.add_argument("--date", help="Date (YYYY-MM-DD), defaults to yesterday")
    parser.add_argument("--register-all", action="store_true", help="Register all leagues")

    args = parser.parse_args()

    from datetime import date, timedelta

    target_date = args.date or (date.today() - timedelta(days=1)).isoformat()

    if args.register_all:
        registered = register_all_espn_sources()
        print(f"Registered ESPN sources for {len(registered)} leagues")
        for league in registered:
            print(f"  {league}: results, lineups, winprob")
    else:
        # Test fetch
        print(f"Testing ESPN multi-source for {args.league} on {target_date}...")
        print()

        print("--- Results ---")
        results = fetch_results_multi(args.league, target_date)
        print(f"  Found {len(results)} results")
        for r in results[:3]:
            print(f"    {r.home_team} {r.home_score}-{r.away_score} {r.away_team} | {r.odds_source}")

        print()
        print("--- Lineups ---")
        lineups = fetch_lineups_multi(args.league, target_date)
        print(f"  Found {len(lineups)} lineups")
        for l in lineups[:3]:
            hf = l.home_lineup.formation if l.home_lineup else "?"
            af = l.away_lineup.formation if l.away_lineup else "?"
            print(f"    {l.home_team} ({hf}) vs {l.away_team} ({af})")

        print()
        print("--- Win Probabilities ---")
        wps = fetch_winprob_multi(args.league, target_date)
        print(f"  Found {len(wps)} win probabilities")
        for wp in wps[:3]:
            live = " [LIVE]" if wp.is_live else ""
            print(f"    {wp.home_team} vs {wp.away_team}{live}")
            if wp.home_win_prob:
                print(f"      Implied: H{wp.home_win_prob:.0f}% D{wp.draw_prob:.0f}% A{wp.away_win_prob:.0f}%")

        print()
        print("--- Health Report ---")
        health = get_espn_health_report()
        for name, data in health.get("espn_sources", {}).items():
            print(f"  {name}: {data['health']} (success: {data['success_rate']:.0%}, calls: {data['total_calls']})")