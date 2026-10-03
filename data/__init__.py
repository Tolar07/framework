"""
OLP XDV Data Package — multi-source data redundancy and ingestion.

This package provides:
- Multi-source redundancy fabric (multi_source.py)
- ESPN API integration (espn_source.py, espn_results.py, espn_lineups.py, espn_winprob.py)
- xG data from Understat (xg_source.py)
- TheSportsDB fixtures (thesportsdb_fixtures.py)
- football-data.co.uk results/odds (football_data_source.py)
"""

from .multi_source import (
    DataSource,
    MultiSource,
    SourceNoData,
    MultiSourceExhausted,
    SourceHealth,
    SourceMetrics,
    build_multi_source,
    registry,
    as_source,
    SourceRegistry,
)

from .espn_source import (
    fetch_upcoming as fetch_fixtures,
    as_pairs,
    SLUGS as LEAGUE_MAP,
    UPCOMING_STATUSES,
)

from .espn_results import (
    fetch_results_for_date,
    fetch_results_range,
    fetch_results_for_league_season,
    MatchResult,
    get_results_source_name,
    create_results_fetcher,
)

from .espn_lineups import (
    fetch_lineups_for_date,
    fetch_lineup_for_event,
    MatchLineup,
    TeamLineup,
    LineupPlayer,
    get_lineups_source_name,
    create_lineups_fetcher,
)

from .espn_winprob import (
    fetch_winprob_for_date,
    fetch_winprob_for_event,
    WinProbability,
    get_winprob_source_name,
    create_winprob_fetcher,
)

from .espn_multi_source import (
    create_results_multi_source,
    create_lineups_multi_source,
    create_winprob_multi_source,
    register_espn_sources_for_league,
    register_all_espn_sources,
    fetch_results_multi,
    fetch_lineups_multi,
    fetch_winprob_multi,
    get_espn_health_report,
)

from .xg_source import (
    fit_xg,
    predict_xg,
    TeamXG,
    XGProbabilities,
    is_covered,
)

from .thesportsdb_fixtures import (
    fetch_upcoming as fetch_thesportsdb_fixtures,
    fetch_today as fetch_league_fixtures,
    load_results as fetch_thesportsdb_results,
    map_team,
)

from .api_football_team_state import (
    TeamStateSnapshot,
    fetch_manager,
    fetch_squad_hash,
    fetch_derived_formation,
    fetch_team_state,
    fetch_league_team_states,
)

from .football_data_source import (
    load_league as fetch_football_data_results,
    load_second_division as fetch_football_data_odds,
)

__all__ = [
    # Multi-source
    "DataSource",
    "MultiSource",
    "SourceNoData",
    "MultiSourceExhausted",
    "SourceHealth",
    "SourceMetrics",
    "build_multi_source",
    "registry",
    "as_source",
    "SourceRegistry",
    # ESPN
    "fetch_fixtures",
    "as_pairs",
    "LEAGUE_MAP",
    "UPCOMING_STATUSES",
    "fetch_results_for_date",
    "fetch_results_range",
    "fetch_results_for_league_season",
    "MatchResult",
    "get_results_source_name",
    "create_results_fetcher",
    "fetch_lineups_for_date",
    "fetch_lineup_for_event",
    "MatchLineup",
    "TeamLineup",
    "LineupPlayer",
    "get_lineups_source_name",
    "create_lineups_fetcher",
    "fetch_winprob_for_date",
    "fetch_winprob_for_event",
    "WinProbability",
    "get_winprob_source_name",
    "create_winprob_fetcher",
    "create_results_multi_source",
    "create_lineups_multi_source",
    "create_winprob_multi_source",
    "register_espn_sources_for_league",
    "register_all_espn_sources",
    "fetch_results_multi",
    "fetch_lineups_multi",
    "fetch_winprob_multi",
    "get_espn_health_report",
    # xG
    "fit_xg",
    "predict_xg",
    "TeamXG",
    "XGProbabilities",
    "is_covered",
    # TheSportsDB
    "fetch_thesportsdb_fixtures",
    "fetch_league_fixtures",
    "fetch_thesportsdb_results",
    "map_team",
    # API-Football team-state (ID417)
    "TeamStateSnapshot",
    "fetch_manager",
    "fetch_squad_hash",
    "fetch_derived_formation",
    "fetch_team_state",
    "fetch_league_team_states",
    # football-data.co.uk
    "fetch_football_data_results",
    "fetch_football_data_odds",
]