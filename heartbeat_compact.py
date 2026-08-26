#!/usr/bin/env python3
"""Generate compact heartbeat format for Telegram."""

import json
from datetime import date
from collections import defaultdict

bd = json.load(open('output/boards/board_2026-08-25.json'))

_WEEKDAYS = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun']
_MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
d = date(2026,8,25)
date_label = f'{_WEEKDAYS[d.weekday()]} {d.day:02d} {_MONTHS[d.month-1]} {d.year}'

# Group by league
leagues = defaultdict(list)
for entry in bd.get('board', []):
    fx = entry.get('fixture','')
    if '(' not in fx: continue
    league = fx.rsplit('(',1)[-1].rstrip(')')
    leagues[league].append(entry)

lines = []
lines.append("##########OLP XDV#########")
lines.append("==================================")
lines.append(f"")
lines.append(f"📅  {date_label}   (PICK · win %  ·  alt markets)")
lines.append(f"")

for league in sorted(leagues.keys()):
    entries = leagues[league]
    lines.append(f"⚽  {league}")

    for e in entries:
        fx = e.get('fixture','')
        if '(' not in fx: continue
        match = fx.rsplit('(',1)[0].strip()

        p = e.get('probs')
        if p:
            # Find best 1X2 pick
            probs = [(p['p_home'], 'home'), (p['p_draw'], 'draw'), (p['p_away'], 'away')]
            prob, side = max(probs, key=lambda x: x[0])
            label = {'home': 'home', 'draw': 'Draw', 'away': 'away'}[side]
            arrow = "➡" if label == 'home' else ("⚪" if label == 'Draw' else "🔁")

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
            lines.append(f"       {arrow} {label} {prob:.0%}")
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

print('\n'.join(lines))