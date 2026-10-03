import json

d = json.load(open('data/cache/api_football_odds/odds_1622620.json'))
print("fetched_at:", d['fetched_at'])
print("payload len:", len(d['payload']))

for item in d['payload']:
    # Print only fixture identifier fields
    if 'fixture' in item:
        fx = item['fixture']
        if isinstance(fx, dict) and 'teams' in fx:
            teams = fx.get('teams', {})
            home = teams.get('home', {}).get('name', '?')
            away = teams.get('away', {}).get('name', '?')
            if 'viking' in home.lower() or 'viking' in away.lower() or 'zagreb' in home.lower() or 'zagreb' in away.lower():
                print(f"\n=== FOUND: {home} v {away} ===")
                print(json.dumps(item, indent=2)[:2000])
