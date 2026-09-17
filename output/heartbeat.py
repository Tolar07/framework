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
from pathlib import Path
from typing import Optional

from .produce_bet import BoardFixture

# Repo-rooted heartbeat state. MUST be shared by the writer and the reader.
#
# save_heartbeat_record() used to build its own Path("data/heartbeat") — relative
# to the CURRENT WORKING DIRECTORY — while get_heartbeat_stats() resolved the
# same file from __file__. Whenever the pipeline was launched from anywhere other
# than the repo root the record was appended to a stray data/heartbeat/ beside
# the caller and the stats reader, looking in the repo, saw nothing. That is the
# same defect class as the vault-sync path bug: two halves of one feature
# disagreeing about where the state lives. One constant, both halves.
REPO_ROOT = Path(__file__).resolve().parent.parent
HEARTBEAT_DIR = REPO_ROOT / "data" / "heartbeat"
HISTORY_FILE = HEARTBEAT_DIR / "history.jsonl"


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
    # Lineage fields (Architect 2026-08-29 survival/reproduction model)
    lineage_id: Optional[str] = None  # owning heartbeat lineage
    generation: int = 0              # lineage generation (0 = genesis)


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
        # CONFLICT / NO-DATA disqualify the fixture. See is_excluded.
        if is_excluded(bf):
            continue

        # A heartbeat is a pre-match bet. See has_kicked_off.
        if has_kicked_off(bf):
            continue

        # Calculate edge/score for selection. Tuple key for the same reason as
        # select_top_heartbeats: an unpriced fixture's probability must not be
        # compared against a priced fixture's edge as if they were one scale.
        pick_info = _get_best_pick_info(bf, odds_index)
        if not pick_info:
            continue

        market_label, probability, edge_value = pick_info
        has_price = getattr(bf, 'best_price', None) is not None

        if has_price and edge_value > 0:
            scored_fixtures.append(((1, edge_value), bf, pick_info))
        elif not has_price and probability > 0:
            scored_fixtures.append(((0, probability), bf, pick_info))

    if not scored_fixtures:
        return None

    # Select fixture with highest edge score
    best_score, best_bf, best_pick_info = max(scored_fixtures, key=lambda x: x[0])

    # Build HeartbeatFixture from selected board fixture
    return _build_heartbeat_fixture(best_bf, best_pick_info, odds_index)


def select_top_heartbeats(
    board: list[BoardFixture],
    target_date: str = None,
    odds_index: Optional[dict] = None,
    top_n: int = 5,
    min_edge: float = 0.0,
    require_priced: bool = True,
    exclude_started: bool = True,
) -> list[HeartbeatFixture]:
    """
    Architect 2026-08-29 — lineage reproduction model.

    Return the N strongest, DISTINCT heartbeat candidates for the day, ranked by
    model edge. The heartbeat is modelled as a lifeform under selection pressure:
    a surviving lineage (WIN) spawns up to two offspring heartbeats the next day;
    a dead lineage (LOSS) goes extinct. To keep the species alive, the day's
    *living* lineages each reproduce — so we need the top-N highest-edge fixtures
    as reproduction candidates, not just one.

    Distinctness rule: one heartbeat per fixture (no duplicate fixture in the
    candidate pool) — each lineage seeds from a different match.

    Args:
        board: List of BoardFixture from the daily pipeline.
        target_date: Date string for filtering (defaults to today).
        odds_index: Optional odds index for market data lookup.
        top_n: Max number of candidate heartbeats to return (offspring pool size).
        min_edge: Minimum edge score to qualify (0.0 = any positive signal).

    Returns:
        List of HeartbeatFixture, highest-edge first, length <= top_n.
    """
    if target_date is None:
        target_date = date.today().isoformat()

    today_fixtures = [
        bf for bf in board
        if getattr(bf, 'kickoff_date', None) == target_date
    ]

    if not today_fixtures:
        return []

    # Rank key is a TUPLE (priced_rank, score), never a bare float.
    #
    # The previous key collapsed two incompatible scales into one number:
    # a priced fixture scored its EDGE (e.g. 0.08) while an unpriced fixture
    # fell back to its raw PROBABILITY (e.g. 0.92). Compared as plain floats,
    # ANY unpriced fixture outranked EVERY genuinely positive-edge one, so the
    # day's heartbeat was reliably the heaviest unpriced favourite — the exact
    # opposite of the selection pressure this model exists to apply, and it
    # cannot be seen in the output because both render as a percentage.
    #
    # Priced candidates (priced_rank=1) now sort strictly above unpriced ones
    # (priced_rank=0), and probability only breaks ties inside the unpriced
    # group. A heartbeat with no price also cannot be settled (see
    # heartbeat_lineage.record_heartbeat_result), so preferring priced
    # candidates keeps the lineage economically meaningful.
    scored: list[tuple[tuple[int, float], BoardFixture, Optional[tuple]]] = []
    seen_fixtures: set[str] = set()

    for bf in today_fixtures:
        fixture_str = getattr(bf, 'fixture', 'Unknown v Unknown')
        # Distinctness: one heart per fixture
        if fixture_str in seen_fixtures:
            continue

        # CONFLICT / NO-DATA disqualify the fixture. See is_excluded.
        if is_excluded(bf):
            continue

        # A heartbeat is a pre-match bet. See has_kicked_off.
        if exclude_started and has_kicked_off(bf):
            continue

        pick_info = _get_best_pick_info(bf, odds_index)
        if not pick_info:
            continue

        _, probability, edge_value = pick_info
        has_price = getattr(bf, 'best_price', None) is not None

        if has_price and edge_value > min_edge:
            key = (1, edge_value)
        elif not has_price and probability > 0 and not require_priced:
            # No price -> no edge can exist, and the result cannot be settled.
            #
            # require_priced defaults True so this fallback is OPT-IN. On
            # 2026-09-17 the board carried 23 fixtures, 8 of them priced, and
            # every priced one was NEGATIVE edge (e.g. Crystal Palace at 1.41
            # implies 70.9% against a model 33.3%), so no capital leg existed.
            # The old scorer answered that by promoting an unpriced 80%
            # favourite to "the day's heartbeat" — presenting a pick with no
            # measured edge as though it had won a selection contest, and
            # feeding the lineage something it could never settle.
            #
            # A day with no qualifying candidate is a real result: the species
            # skips a generation. Reporting the absence is HR35; filling it is
            # not.
            key = (0, probability)
        else:
            continue

        scored.append((key, bf, pick_info))
        seen_fixtures.add(fixture_str)

    if not scored:
        return []

    scored.sort(key=lambda x: x[0], reverse=True)
    return [
        _build_heartbeat_fixture(bf, pick_info, odds_index)
        for _, bf, pick_info in scored[:top_n]
    ]


# ID403 verification tiers as this framework actually defines them
# (verification.id403.Tier). NONE of the strings heartbeat.py previously
# checked -- "TIER_A", "TIER_B", "FAILED", "REJECTED" -- exist anywhere in the
# codebase. They appear to be from an earlier or imagined scheme.
#
# Two consequences, both silent:
#   * verification_passed compared against TIER_A/TIER_B and so was ALWAYS
#     False, which is why every heartbeat rendered "⚠ Verification: Pending
#     Review" regardless of how well the fixture was verified. A warning that
#     is always on carries no information.
#   * the exclusion gate skipped fixtures whose tier was "FAILED"/"REJECTED",
#     values that never occur — so it never excluded anything. CONFLICT
#     fixtures, where sources disagree on kickoff beyond tolerance, were
#     eligible to become the day's heartbeat.
#
# The enum compounds it: str(Tier.VERIFIED) is "Tier.VERIFIED", not "VERIFIED",
# so even the right vocabulary would not have matched without reading .value.
_TIER_PASSING = {"VERIFIED", "TIER_A", "TIER_B"}   # TIER_* kept for legacy data
_TIER_EXCLUDED = {"CONFLICT", "NO-DATA", "NO_DATA", "FAILED", "REJECTED"}


def tier_of(bf) -> str:
    """This fixture's ID403 tier as an UPPERCASE string, or '' when absent.

    Reads .value first because tier is a Tier enum; str() on an enum yields
    'Tier.VERIFIED' and matches nothing.
    """
    v = getattr(bf, "verification", None)
    raw = getattr(v, "tier", None)
    if raw is None:
        return ""
    return str(getattr(raw, "value", raw) or "").upper()


def is_verified(bf) -> bool:
    """True only when ID403 actually verified this fixture."""
    return tier_of(bf) in _TIER_PASSING


def is_excluded(bf) -> bool:
    """True when the tier disqualifies the fixture from being a heartbeat.

    CONFLICT means the sources disagree on kickoff beyond tolerance — the
    framework does not know when the match starts, so it cannot be a pre-match
    bet. NO-DATA means there is nothing to stand on at all.
    """
    return tier_of(bf) in _TIER_EXCLUDED


def has_kicked_off(bf, now=None) -> bool:
    """True when this fixture has already started, or we cannot prove it has not.

    A heartbeat is a PRE-MATCH bet. The selector previously applied no time
    filter at all, so on 2026-09-17 at 17:43 UTC it ranked
    "Gazovik Orenburg v FC Krasnodar" first -- a match that kicked off at 13:15,
    four and a half hours earlier -- along with two others already in play.
    Handing a lineage a match it could never have backed is bad on its own; it
    became serious the moment one LOSS meant extinction, because a bloodline
    could be ended on a fixture nobody could have staked.

    FAILS SAFE, and deliberately differs from
    pipeline.fixture_extraction._has_kicked_off. That helper returns False
    ("not started") when the timestamp cannot be parsed OR when it is NAIVE:
    comparing a naive datetime against an aware now() raises TypeError, which
    its except clause swallows into False. Naive timestamps are not exotic here
    -- collaborative_fixtures._kickoff_iso emits "2026-09-17T18:00" with no zone
    for FlashScore and SportyBet -- so that default would wave through exactly
    the fixtures this filter exists to catch.

    Here, a naive stamp is read as UTC (which is what the pipeline stores), and
    anything genuinely unreadable counts as STARTED, because a heartbeat we
    cannot confirm is pre-match is not one worth risking a lineage on.
    """
    from datetime import datetime, timezone

    now = now or datetime.now(timezone.utc)
    raw = getattr(bf, "kickoff_utc", None) or getattr(bf, "kickoff_time", None)
    if not raw:
        return True  # no kickoff -> cannot confirm pre-match -> treat as gone

    try:
        ko = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return True

    if ko.tzinfo is None:
        ko = ko.replace(tzinfo=timezone.utc)
    return now >= ko


def _get_best_pick_info(bf: BoardFixture, odds_index: Optional[dict]) -> Optional[tuple[str, float, float]]:
    """
    Extract the best pick information from a BoardFixture.

    Returns:
        Tuple of (market_label, probability, edge_value) or None
    """
    # Priced best market. Rank on CANONICAL EDGE (model_prob - implied_prob),
    # which is this framework's selection metric; best_mes_ev is EV and is
    # reserved for Kelly/staking. Where Stage B supplied an edge, use it; fall
    # back to deriving it from the price rather than substituting EV, because
    # EV and edge order fixtures differently at long prices.
    if getattr(bf, "best_market", None):
        edge = getattr(bf, "best_edge", None)
        prob = getattr(bf, "best_model_prob", None)
        price = getattr(bf, "best_price", None)
        if edge is None and prob is not None and price:
            edge = prob - (1.0 / price)
        if edge is not None:
            return (bf.best_market, prob or 0.0, edge)

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
    # The board's fixture string carries a "(League)" suffix, and _extract_league
    # reads the league back out of it. The renderer then prints the league on its
    # own line AND again inside the fixture:
    #   ⚽  La Liga
    #   🕐  19:45   Real Sociedad v Getafe (La Liga)
    # Drop the suffix now that the league has been extracted from it.
    if league != "Unknown League" and fixture_str.endswith(f"({league})"):
        fixture_str = fixture_str[: -len(f"({league})")].strip()

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

    # Verification status (ID403). See is_verified / _TIER_PASSING.
    verification_passed = is_verified(bf)

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

    # Double chance must be tested BEFORE 1X2: its labels ("Home or Draw",
    # "Draw or Away") contain the 1X2 tokens and would otherwise be
    # misclassified as a straight result pick and drawn with the wrong arrow.
    if 'double chance' in label_lower or ' or ' in label_lower:
        return "DC"
    # "<Club> to win" is the HR53 long-form of a 1X2 result pick. It carries no
    # home/away/draw token, so it used to fall through to OTHER and render as
    # "💡  Pick: 💡 Real Sociedad to win" — the generic arrow duplicating the
    # line's own prefix glyph.
    if any(team in label_lower for team in ['home', 'away', 'draw']) or \
       'to win' in label_lower or 'v ' in label_lower or ' vs ' in label_lower:
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
        # Draw is checked first: "Home or Draw"-style labels are routed to DC
        # before they reach here, so a remaining 'draw' token means the pick
        # really is the draw.
        if 'draw' in pick_lower:
            return "⚪"
        elif 'home' in pick_lower:
            return "➡"
        elif 'away' in pick_lower:
            return "🔁"
        else:
            # Named club, e.g. "Real Sociedad to win" (HR53 long form).
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
    from datetime import datetime

    HEARTBEAT_DIR.mkdir(parents=True, exist_ok=True)
    history_file = HISTORY_FILE

    # Today's record
    record = {
        "date": datetime.now().date().isoformat(),
        "lineage_id": heartbeat.lineage_id,
        "generation": heartbeat.generation,
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

    history_file = HISTORY_FILE
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