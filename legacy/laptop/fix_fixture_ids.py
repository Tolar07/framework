"""Fix sportybet_fixture_id in board by patching cache with model_name fallback.
This runs before booking_codes.py so the cache has matching entries.
"""
import json, sys, unicodedata, time, re
from pathlib import Path
from difflib import SequenceMatcher

def norm(s):
    # Unicode normalize then lower, strip extra spaces
    s = unicodedata.normalize('NFKD', str(s)).lower().strip()
    # Strip diacritics
    s = re.sub(r'[^\x00-\x7f]', '', s) if False else s  # keep chars
    return ' '.join(s.split())

def sim(a, b):
    return SequenceMatcher(None, norm(a), norm(b)).ratio()

sys.path.insert(0, 'booking')
from team_map import resolve_team

def match_team(name, candidates, threshold=0.7):
    """Return best matching team from candidates or None."""
    # 1. exact match (case-insensitive)
    for c in candidates:
        if norm(c) == norm(name):
            return c
    key2name = {norm(c): c for c in candidates}
    # 2. substring
    n = norm(name)
    for c in candidates:
        cn = norm(c)
        if n in cn or cn in n:
            return c
    # 3. fuzzy
    best, score = max(((c, sim(name, c)) for c in candidates), key=lambda x: x[1], default=(None, 0))
    return best if score >= threshold else None

def fix_board():
    cache_dir = Path('data/cache/sportybet/fixtures')
    # 1. Build (league, readable_name) -> list of fixtures for each sportybet team
    league_sb_teams = {}  # league -> list of sb names in cache
    league_fixtures = {}  # league -> list of fixtures
    for f in sorted(cache_dir.glob('*.json')):
        data = json.loads(f.read_text())
        league = data.get('league', '')
        fixtures = data.get('fixtures', [])
        league_fixtures[league] = fixtures
        league_sb_teams[league] = list(set(
            [fx['home_team'] for fx in fixtures] + [fx['away_team'] for fx in fixtures]
        ))

    print("Leagues in cache:")
    for l in sorted(league_fixtures.keys()):
        print(f"  {l}: {len(league_fixtures[l])} fixtures")

    # 2. Load board
    board = json.load(open('output/boards/acca_2026-08-23.json'))
    total = sum(len(a['legs']) for a in board['accas'])
    has_id = sum(1 for a in board['accas'] for l in a['legs'] if l.get('sportybet_fixture_id'))
    print(f"\nBoard: {len(board['accas'])} accas, {total} legs, {has_id} have IDs")

    # 3. Fix each leg
    matched = 0
    unmatched = []
    missing_leagues = {}
    for acca in board['accas']:
        for leg in acca['legs']:
            if leg.get('sportybet_fixture_id'):
                continue
            parts = leg['fixture'].split(' v ')
            model_home = parts[0].strip()
            model_away = parts[1].split(' (')[0].strip()
            league = leg['league']

            # Get sportybet names
            sb_home_raw = resolve_team(model_home, 'sportybet')
            sb_away_raw = resolve_team(model_away, 'sportybet')

            # Look up the cache by league
            if league not in league_sb_teams or not league_sb_teams[league]:
                missing_leagues[league] = True
                continue

            teams_in_league = league_sb_teams[league]
            sb_home = match_team(sb_home_raw, teams_in_league)
            sb_away = match_team(sb_away_raw, teams_in_league)

            if not sb_home or not sb_away:
                unmatched.append(f"{leg['fixture']} ({league}) -> sb: {sb_home_raw}, {sb_away_raw}")
                continue

            # Find fixture in cache
            for fx in league_fixtures[league]:
                fx_h, fx_a = fx['home_team'], fx['away_team']
                # Match in any order
                if (fx_h == sb_home and fx_a == sb_away) or (fx_h == sb_away and fx_a == sb_home):
                    leg['sportybet_fixture_id'] = fx['fixture_id']
                    leg['sportybet_home'] = fx_h
                    leg['sportybet_away'] = fx_a
                    matched += 1
                    break
            else:
                unmatched.append(f"{leg['fixture']} ({league}) -> no fixture match for {sb_home} and {sb_away}")

    # 4. Save board
    with open('output/boards/acca_2026-08-23.json', 'w') as f:
        json.dump(board, f, indent=2)

    has_id2 = sum(1 for a in board['accas'] for l in a['legs'] if l.get('sportybet_fixture_id'))
    print(f"\nMatched {matched} new IDs")
    print(f"Total with ID: {has_id2}/{total}")
    if missing_leagues:
        print(f"Missing leagues: {', '.join(sorted(missing_leagues.keys()))}")
    if unmatched:
        print(f"Still unmatched ({len(unmatched)}):")
    for u in unmatched[:30]:
        print(f'  NOT FOUND')

if __name__ == '__main__':
    fix_board()