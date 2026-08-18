import json

d = json.load(open('data/cache/api_football_odds/odds_1622620.json'))
for item in d['payload']:
    fx = item.get('fixture', {})
    teams = fx.get('teams', {})
    home = teams.get('home', {}).get('name', '?')
    away = teams.get('away', {}).get('name', '?')
    print(f"{home} v {away}")
