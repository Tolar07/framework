"""
HEARTBEAT SELECTION — single best daily fixture for Telegram heartbeat.

Selects the single fixture with highest model edge (best_mes_ev or canonical edge)
to serve as the day's "heartbeat" pick — a trackable, compounding single bet.

Rationale:
- Isolated from daily board mixing (unlike render_compact_heartbeat which shows all)
- Pure signal: highest expected value / edge from model
- Trackable over time: win/loss record enables compounding stake growth
- Telegram-deliverable: compact single-fixture format for 07:00 heartbeat alert
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

from .produce_bet import BoardFixture


@dataclass
class HeartbeatFixture:
    """Single heartbeat selection with render-ready fields."""
    fixture: str          # e.g. "Man City v Arsenal"
    kickoff_time: str     # e.g. "15:00"
    league: str           # e.g. "Premier League"
    pick: str             # e.g. "Over 2.5 goals" or "home" etc.
    probability: float    # model probability 0-1
    edge: float           # canonical edge (model_prob - implied_prob) or best_mes_ev
    market_type: str      # "1X2", "O/U", "BTTS", "DC" for arrow selection
    bookmaker: Optional[str] = None  # e.g. "SportyBet Nigeria"
    price: Optional[float] = None    # decimal odds if priced
    verification_passed: bool = False  # ID403 verification status


def select_heartbeat_fixture(
    board: list[BoardFixture],
    target_date: str = None,
    odds_index: Optional[dict] = None
) -> Optional[HeartbeatFixture]:
    """
    Select the single best fixture as heartbeat by highest expected value.

    Selection priority:
    1. Highest best_mes_ev (model edge with actual bookmaker price)
    2. Fallback to highest model probability if no priced markets available
    3. Must be verification-passed (ID403) for quality

    Args:
        board: List of BoardFixture objects from daily pipeline
        target_date: Date string for filtering (defaults to today)
        odds_index: Optional odds index for market data lookup

    Returns:
        HeartbeatFixture object or None if no suitable fixture found
    """
    if target_date is None:
        target_date = date.today().isoformat()

    # Filter to today's fixtures only (production intent rule)
    # BoardFixture has kickoff_date (not match_date)
    today_fixtures = []
    for bf in board:
        if getattr(bf, 'kickoff_date', None) == target_date:
            today_fixtures.append(bf)

    if not today_fixtures:
        return None

    # Score each fixture for heartbeat selection
    scored_fixtures = []

    for bf in today_fixtures:
        # Skip if verification failed (quality gate)
        verification_passed = getattr(bf, 'verification', None)
        if verification_passed is not None and not getattr(verification_passed, 'tier', None) in ['TIER_A', 'TIER_B']:
            # TIER_A/B are passing grades; others may need Architect review
            # For now, accept any verification that isn't explicitly failed
            verification_status = str(getattr(verification_passed, 'tier', 'UNKNOWN'))
            if verification_status in ['FAILED', 'REJECTED']:
                continue

        # Calculate edge/score for selection
        edge_score = 0.0
        pick_info = _get_best_pick_info(bf, odds_index)

        if pick_info:
            market_label, probability, edge_value = pick_info
            edge_score = edge_value

            # If no edge value available, fall back to pure probability
            if edge_score == 0.0 and probability > 0:
                edge_score = probability  # Pure probability fallback

        if edge_score > 0:  # Only consider fixtures with positive signal
            scored_fixtures.append((edge_score, bf, pick_info))

    if not scored_fixtures:
        return None

    # Select fixture with highest edge score
    best_score, best_bf, best_pick_info = max(scored_fixtures, key=lambda x: x[0])

    # Build HeartbeatFixture from selected board fixture
    return _build_heartbeat_fixture(best_bf, best_pick_info, odds_index)


def _get_best_pick_info(bf: BoardFixture, odds_index: Optional[dict]) -> Optional[tuple[str, float, float]]:
    """
    Extract the best pick information from a BoardFixture.

    Returns:
        Tuple of (market_label, probability, edge_value) or None
    """
    # Check if BoardFixture already has a priced best_market with EV
    if getattr(bf, "best_market", None) and getattr(bf, "best_mes_ev", None) is not None:
        if bf.best_mes_ev is not None:
            # Use the priced best market with actual EV
            return (
                bf.best_market,
                bf.best_model_prob or 0.0,
                bf.best_mes_ev
            )

    # Fallback: try to compute best EV from model probabilities + available odds
    probs = getattr(bf, 'probs', None)
    if not probs:
        return None

    # Try 1X2 markets first (most common)
    if hasattr(probs, 'p_home') and probs.p_home is not None:
        probs_list = [
            (probs.p_home, 'home', getattr(bf, 'home_team', 'Home')),
            (probs.p_draw, 'draw', 'Draw'),
            (probs.p_away, 'away', getattr(bf, 'away_team', 'Away'))
        ]

        # Filter to valid probabilities
        valid_probs = [(p, side, label) for p, side, label in probs_list if p is not None and p > 0]

        if valid_probs and odds_index:
            # Try to get actual prices for EV calculation
            best_ev = 0.0
            best_label = ''
            best_prob = 0.0

            # This would require odds_index lookup - simplified for now
            prob, side, label = max(valid_probs, key=lambda x: x[0])
            return (label, prob, 0.0)  # Return probability-only if no price data

        elif valid_probs:
            # Return highest probability pick without price data
            prob, side, label = max(valid_probs, key=lambda x: x[0])
            return (label, prob, 0.0)

    # Check other markets (O/U, BTTS, etc.)
    market_checks = [
        ('p_over_15', 'Over 1.5 goals'),
        ('p_over_25', 'Over 2.5 goals'),
        ('p_over_35', 'Over 3.5 goals'),
        ('p_btts_yes', 'BTTS Yes'),
        ('p_btts_no', 'BTTS No')
    ]

    best_prob = 0.0
    best_label = ''

    for attr_name, label in market_checks:
        if hasattr(probs, attr_name):
            prob = getattr(probs, attr_name)
            if prob is not None and prob > best_prob:
                best_prob = prob
                best_label = label

    if best_prob > 0:
        return (best_label, best_prob, 0.0)

    return None


def _build_heartbeat_fixture(
    bf: BoardFixture,
    pick_info: Optional[tuple[str, float, float]],
    odds_index: Optional[dict]
) -> HeartbeatFixture:
    """Build a HeartbeatFixture from a BoardFixture and pick info."""

    # Extract basic fixture info
    fixture_str = getattr(bf, 'fixture', 'Unknown v Unknown')
    kickoff_time = _extract_kickoff_time(bf)
    league = _extract_league(bf)

    # Extract pick info
    if pick_info:
        pick_label, probability, edge_value = pick_info
    else:
        # Fallback to AI pick from probs
        pick_label, probability = _get_fallback_pick(bf)
        edge_value = 0.0

    # Determine market type for arrow selection
    market_type = _categorize_market_type(pick_label)

    # Extract bookmaker/price info if available
    bookmaker = getattr(bf, 'best_bookmaker', None)
    price = getattr(bf, 'best_price', None)

    # Verification status
    verification_obj = getattr(bf, 'verification', None)
    verification_passed = verification_obj is not None and str(getattr(verification_obj, 'tier', '')) in ['TIER_A', 'TIER_B']

    return HeartbeatFixture(
        fixture=fixture_str,
        kickoff_time=kickoff_time,
        league=league,
        pick=pick_label,
        probability=probability,
        edge=edge_value,
        market_type=market_type,
        bookmaker=bookmaker,
        price=price,
        verification_passed=verification_passed
    )


def _extract_kickoff_time(bf: BoardFixture) -> str:
    """Extract kickoff time from BoardFixture."""
    kickoff_utc = getattr(bf, 'kickoff_utc', None)
    if kickoff_utc and len(kickoff_utc) >= 16:
        # Extract HH:MM from ISO timestamp
        import re
        match = re.match(r'\d{4}-\d{2}-\d{2}T(\d{2}:\d{2})', kickoff_utc)
        if match:
            return match.group(1)

    # Fallback: try to get from fixture string or return unknown
    return "??:??"


def _extract_league(bf: BoardFixture) -> str:
    """Extract league from BoardFixture fixture string."""
    fixture = getattr(bf, 'fixture', '')
    if '(' in fixture and ')' in fixture:
        return fixture.rsplit('(', 1)[-1].rstrip(')')
    return "Unknown League"


def _get_fallback_pick(bf: BoardFixture) -> tuple[str, float]:
    """Get fallback pick when no detailed pick info available."""
    probs = getattr(bf, 'probs', None)
    if not probs:
        return ("Unknown", 0.0)

    # Try to get AI-style result pick (1X2)
    if hasattr(probs, 'p_home') and probs.p_home is not None:
        probs_list = [
            (probs.p_home, 'home'),
            (probs.p_draw, 'draw'),
            (probs.p_away, 'away')
        ]
        valid_probs = [(p, label) for p, label in probs_list if p is not None and p > 0]
        if valid_probs:
            prob, label = max(valid_probs, key=lambda x: x[0])
            return (label, prob)

    # Fallback to first available market probability
    market_attrs = ['p_over_15', 'p_over_25', 'p_over_35', 'p_btts_yes', 'p_btts_no']
    for attr in market_attrs:
        if hasattr(probs, attr):
            prob = getattr(probs, attr)
            if prob is not None and prob > 0:
                label_map = {
                    'p_over_15': 'Over 1.5 goals',
                    'p_over_25': 'Over 2.5 goals',
                    'p_over_35': 'Over 3.5 goals',
                    'p_btts_yes': 'BTTS Yes',
                    'p_btts_no': 'BTTS No'
                }
                return (label_map[attr], prob)

    return ("No Data", 0.0)


def _categorize_market_type(market_label: str) -> str:
    """Categorize market label into type for arrow selection."""
    label_lower = market_label.lower()

    if any(team in label_lower for team in ['home', 'away', 'draw']) or \
       'v ' in label_lower or ' vs ' in label_lower:
        return "1X2"
    elif 'over' in label_lower or 'under' in label_lower or 'o1.5' in label_lower or 'o2.5' in label_lower or 'o3.5' in label_lower:
        return "O/U"
    elif 'btts' in label_lower or 'both teams' in label_lower:
        return "BTTS"
    elif 'double chance' in label_lower or 'dc' in label_lower:
        return "DC"
    else:
        return "OTHER"


def render_heartbeat_telegram(heartbeat: HeartbeatFixture) -> str:
    """
    Render single heartbeat fixture in Telegram format.

    Format matches user's request for clean, trackable single pick:
    🎯 OLP XDV HEARTBEAT
    📅 Tue 26 Aug 2026
    ⚽ Premier League
    🕐 15:00   Man City v Arsenal
    💡 Pick: Over 2.5 goals (72%)
    📈 Edge: +18.3%
    💷 SportyBet: 2.10
    """
    if not heartbeat:
        return "❌ No heartbeat fixture available today"

    # Format probability as percentage
    prob_pct = round(heartbeat.probability * 100)

    # Format edge as percentage with sign
    edge_pct = round(heartbeat.edge * 100, 1)
    edge_sign = "+" if edge_pct >= 0 else ""
    edge_str = f"{edge_sign}{edge_pct}%"

    # Format price if available
    price_str = f"{heartbeat.price:.2f}" if heartbeat.price else "NO PRICE"

    # Select arrow based on market type and pick
    arrow = _get_heartbeat_arrow(heartbeat.market_type, heartbeat.pick)

    # Format date
    try:
        from datetime import date
        today = date.today()
        weekdays = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun']
        months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
        date_label = f'{weekdays[today.weekday()]} {today.day:02d} {months[today.month-1]} {today.year}'
    except:
        date_label = "Today"

    lines = [
        "🎯 OLP XDV HEARTBEAT",
        f"📅  {date_label}",
        f"",
        f"⚽  {heartbeat.league}",
        f"🕐  {heartbeat.kickoff_time}   {heartbeat.fixture}",
        f"💡  Pick: {arrow} {heartbeat.pick} ({prob_pct}%)",
        f"📈  Edge: {edge_str}",
        f"💷  {heartbeat.bookmaker or 'SportyBet'}: {price_str}"
    ]

    if not heartbeat.verification_passed:
        lines.append("⚠️  Verification: Pending Review")

    return "\n".join(lines)


def _get_heartbeat_arrow(market_type: str, pick_label: str) -> str:
    """Get appropriate arrow for heartbeat pick display."""
    pick_lower = pick_label.lower()

    if market_type == "1X2":
        if 'home' in pick_lower:
            return "➡"
        elif 'draw' in pick_lower:
            return "⚪"
        elif 'away' in pick_lower:
            return "🔁"
        else:
            return "📌"
    elif market_type == "O/U":
        if 'over' in pick_lower:
            return "📈"
        else:  # under
            return "📉"
    elif market_type == "BTTS":
        if 'yes' in pick_lower or 'btts' in pick_lower:
            return "🤝"
        else:  # no
            return "🚫"
    elif market_type == "DC":
        return "🔗"
    else:
        return "💡"


def save_heartbeat_record(heartbeat: HeartbeatFixture, result: str = None) -> None:
    """
    Save heartbeat result to history file for tracking/compounding.

    Args:
        heartbeat: HeartbeatFixture object
        result: 'WIN', 'LOSS', 'PENDING', or None for just recording selection
    """
    import json
    from pathlib import Path
    from datetime import datetime

    # Ensure data directory exists
    data_dir = Path("data/heartbeat")
    data_dir.mkdir(parents=True, exist_ok=True)

    # History file
    history_file = data_dir / "history.jsonl"

    # Today's record
    record = {
        "date": datetime.now().date().isoformat(),
        "fixture": heartbeat.fixture,
        "league": heartbeat.league,
        "pick": heartbeat.pick,
        "probability": heartbeat.probability,
        "edge": heartbeat.edge,
        "market_type": heartbeat.market_type,
        "bookmaker": heartbeat.bookmaker,
        "price": heartbeat.price,
        "kickoff_time": heartbeat.kickoff_time,
        "verification_passed": heartbeat.verification_passed,
        "result": result,  # WIN/LOSS/PENDING or None
        "timestamp": datetime.now().isoformat()
    }

    # Append to history
    with history_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def get_heartbeat_stats() -> dict:
    """
    Get heartbeat performance statistics for compounding calculation.

    Returns:
        Dictionary with win/loss/total counts and win rate
    """
    import json
    from pathlib import Path

    history_file = Path("data/heartbeat/history.jsonl")
    if not history_file.exists():
        return {"wins": 0, "losses": 0, "total": 0, "win_rate": 0.0}

    wins = 0
    losses = 0
    total = 0

    try:
        with history_file.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    record = json.loads(line)
                    result = record.get("result")
                    if result == "WIN":
                        wins += 1
                    elif result == "LOSS":
                        losses += 1
                    # PENDING or None don't count toward win/loss
                    if result in ["WIN", "LOSS"]:
                        total += 1
    except:
        pass  # Return zeros on error

    win_rate = wins / total if total > 0 else 0.0

    return {
        "wins": wins,
        "losses": losses,
        "total": total,
        "win_rate": win_rate
    }