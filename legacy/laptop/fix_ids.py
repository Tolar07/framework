"""Quick script to fix fixture IDs in today's acca board."""
import json, sys, unicodedata
from pathlib import Path

sys.path.insert(0, 'booking')
from team_map import resolve_team, _normalize

def norm(s):
    return unicodedata.normalize('NFKD', str(s).lower()).encode('ASCII','ignore').decode().strip()

cache_dir = Path('data/cache/sportybet/fixtures')
sb_fixtures = []
for f in sorted(cache_dir.glob('*.json')):
    data = json.loads(f.read_text())
    for fx in data.get('fixtures', []):
        sb_fixtures.append(fx)

# Build lookup: (norm(home), norm(away)) -> fixture_id
norm_lookup = {}
for fx in sb_fixtures:
    nh = norm(fx['home_team'])
    na = norm(fx['away_team'])
    norm_lookup[(nh, na)] = fx['fixture_id']
    norm_lookup[(na, nh)] = fx['fixture_id']

# Load board
board = json.load(open('output/boards/acca_2026-08-23.json'))

matched = 0
unmatched = []
for acca in board['accas']:
    for leg in acca['legs']:
        if leg.get('sportybet_fixture_id'):
            continue
        parts = leg['fixture'].split(' v ')
        model_home = parts[0].strip()
        model_away = parts[1].split(' (')[0].strip()
        league = leg['league']

        sb_home = resolve_team(model_home, 'sportybet')
        sb_away = resolve_team(model_away, 'sportybet')

        nh = norm(sb_home)
        na = norm(sb_away)

        if (nh, na) in norm_lookup:
            leg['sportybet_fixture_id'] = norm_lookup[(nh, na)]
            leg['sportybet_home'] = sb_home
            leg['sportybet_away'] = sb_away
            matched += 1
            continue

        if (na, nh) in norm_lookup:
            leg['sportybet_fixture_id'] = norm_lookup[(na, nh)]
            leg['sportybet_home'] = sb_away
            leg['sportybet_away'] = sb_home
            matched += 1
            continue

        unmatched.append(f'{model_home} v {model_away} ({league})')

with open('output/boards/acca_2026-08-23.json', 'w') as f:
    json.dump(board, f, indent=2)

total = sum(len(a['legs']) for a in board['accas'])
has_id = sum(1 for a in board['accas'] for l in a['legs'] if l.get('sportybet_fixture_id'))
print(f'Matched new: {matched}')
print(f'Total with ID: {has_id}/{total}')
if unmatched:
    print(f'Still unmatched: {len(unmatched)}')
    for u in unmatched:
        print(f'  {u}')