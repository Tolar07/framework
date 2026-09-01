#!/usr/bin/env python3
"""
Generate compact heartbeat format for Telegram.
FIXED: Use edge_value (model edge with actual bookmaker price) instead of probability
for selection, to align with heartbeat.py's highest EV selection logic.
"""

import json
from datetime import date
from collections import defaultdict
import sys
import glob
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from output.heartbeat import _get_best_pick_info, _categorize_market_type


def _get_heartbeat_arrow_ascii(market_type: str, pick_label: str) -> str:
    """Get appropriate ASCII arrow for heartbeat pick display (Windows console friendly)."""
    pick_lower = pick_label.lower()

    if market_type == "1X2":
        if 'home' in pick_lower:
            return "->"
        elif 'draw' in pick_lower:
            return "="
        elif 'away' in pick_lower:
            return "<-"
        else:
            return "?"
    elif market_type == "O/U":
        if 'over' in pick_lower:
            return "+"
        else:  # under
            return "-"
    elif market_type == "BTTS":
        if 'yes' in pick_lower or 'btts' in pick_lower:
            return "H"
        else:  # no
            return "A"
    elif market_type == "DC":
        return "DC"
    else:
        return "?"


def generate_compact_heartbeat(board_data: dict = None, target_date: str = None) -> str:
    """
    Generate compact heartbeat format showing highest EV picks per league.

    Args:
        board_data: Board data dictionary (loads latest if None)
        target_date: Date string for filtering (defaults to today)

    Returns:
        Formatted compact heartbeat string for Telegram
    """
    # Load board data if not provided
    if board_data is None:
        board_files = glob.glob('output/boards/board_*.json')
        if not board_files:
            return "No board files found"
        latest_board = max(board_files, key=lambda f: f.split('_')[-1].split('.')[0])
        with open(latest_board, 'r') as f:
            board_data = json.load(f)

    if target_date is None:
        target_date = date.today().isoformat()

    _WEEKDAYS = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun']
    _MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
    d = date.fromisoformat(target_date)
    date_label = f'{_WEEKDAYS[d.weekday()]} {d.day:02d} {_MONTHS[d.month-1]} {d.year}'

    # Group by league
    leagues = defaultdict(list)
    for entry in board_data.get('board', []):
        fx = entry.get('fixture','')
        if '(' not in fx: continue
        # Filter by kickoff_date if available
        if entry.get('kickoff_date') != target_date:
            continue
        league = fx.rsplit('(',1)[-1].rstrip(')')
        leagues[league].append(entry)

    lines = []
    lines.append("##########OLP XDV#########")
    lines.append("==================================")
    lines.append(f"")
    lines.append(f"[Date]  {date_label}   (PICK · win %  ·  alt markets)")
    lines.append(f"")

    for league in sorted(leagues.keys()):
        entries = leagues[league]
        lines.append(f"[League]  {league}")

        for e in entries:
            fx = e.get('fixture','')
            if '(' not in fx: continue
            match = fx.rsplit('(',1)[0].strip()

            p = e.get('probs')
            if p:
                # Get best pick info with edge_value (not probability)
                # Extract directly from JSON entry since _get_best_pick_info expects BoardFixture object
                best_market = e.get('best_market')
                best_mes_ev = e.get('best_mes_ev')
                best_model_prob = e.get('best_model_prob')

                if best_market and best_mes_ev is not None and best_model_prob is not None:
                    market_label = best_market
                    probability = best_model_prob
                    edge_value = best_mes_ev
                    # Use edge_value for selection, not probability
                    market_type = _categorize_market_type(market_label)
                    arrow = _get_heartbeat_arrow_ascii(market_type, market_label)
                else:
                    # Fallback: use highest probability 1X2 pick if no edge available
                    probs = [(p['p_home'], 'home'), (p['p_draw'], 'draw'), (p['p_away'], 'away')]
                    prob, side = max(probs, key=lambda x: x[0])
                    label = {'home': 'home', 'draw': 'Draw', 'away': 'away'}[side]
                    arrow = "->" if label == 'home' else ("=" if label == 'Draw' else "<-")
                    market_label = label.capitalize()
                    probability = prob
                    edge_value = 0.0  # Unknown EV

                # Build alt markets line
                alt = []
                if p.get('p_over_15'): alt.append(f"O1.5 {p['p_over_15']:.0%}")
                if p.get('p_over_25'): alt.append(f"O2.5 {p['p_over_25']:.0%}")
                if p.get('p_over_35'): alt.append(f"O3.5 {p['p_over_35']:.0%}")
                if p.get('p_btts_yes'): alt.append(f"BTTS {p['p_btts_yes']:.0%}")
                alt_str = "  ·  ".join(alt) if alt else ""

                kickoff = e.get('kickoff_utc', '??:??')
                if 'T' in str(kickoff):
                    import re
                    m = re.match(r'\d{4}-\d{2}-\d{2}T(\d{2}:\d{2})', kickoff)
                    ko = m.group(1) if m else '??:??'
                else:
                    ko = '??:??'

                lines.append(f"   {ko}   {match}")
                if alt_str:
                    lines.append(f"       {alt_str}")
                lines.append(f"       {arrow} {market_label} {probability:.0%} (EV: {edge_value:.1%})")

            else:
                # NO DATA - just show kickoff time and match
                kickoff = e.get('kickoff_utc', '??:??')
                if 'T' in str(kickoff):
                    import re
                    m = re.match(r'\d{4}-\d{2}-\d{2}T(\d{2}:\d{2})', kickoff)
                    ko = m.group(1) if m else '??:??'
                else:
                    ko = '??:??'
                lines.append(f"   {ko}   {match}")

    lines.append(f"")
    lines.append(f"==================================")

    return '\n'.join(lines)


if __name__ == "__main__":
    # CLI usage: python heartbeat_compact.py [board_file] [date]
    import argparse
    parser = argparse.ArgumentParser(description="Generate compact heartbeat for Telegram")
    parser.add_argument("board_file", nargs="?", help="Path to board JSON file (default: latest)")
    parser.add_argument("--date", help="Target date YYYY-MM-DD (default: today)")
    args = parser.parse_args()

    board_data = None
    if args.board_file:
        with open(args.board_file, 'r') as f:
            board_data = json.load(f)

    print(generate_compact_heartbeat(board_data, args.date))