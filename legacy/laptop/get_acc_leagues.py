import json

# Extract all unique leagues from acca_2026-08-29.json
with open('output/boards/acca_2026-08-29.json', 'r') as f:
    data = json.load(f)

leagues = set()
for acca in data['accas']:
    for leg in acca['legs']:
        leagues.add(leg['league'])

print('All leagues in acca_2026-08-29.json:')
for league in sorted(leagues):
    print(f'  - {league}')
print(f'Total: {len(leagues)} unique leagues')