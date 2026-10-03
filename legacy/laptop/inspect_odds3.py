import json

d = json.load(open('data/cache/api_football_odds/odds_1622620.json'))
for i, item in enumerate(d['payload']):
    print(f"--- item {i} (type {type(item).__name__}) ---")
    if isinstance(item, str):
        print(item[:500])
    elif isinstance(item, dict):
        print(json.dumps(item, indent=2)[:500])
