"""Wrapper: test Ligue 2 booking for Reims v Annecy single."""
import sys, json
sys.path.insert(0, '.')

with open('output/boards/acca_2026-08-24.json', 'r', encoding='utf-8') as f:
    board = json.load(f)

leg = None
for acca in board['accas']:
    for l in acca['legs']:
        if l['fixture'] == 'Reims v Annecy':
            leg = l
            break
    if leg:
        break

if not leg:
    print('Leg not found')
    sys.exit(1)

payload = {
    "date": board["date"],
    "accas": [{
        "label": "SINGLE - Reims v Annecy",
        "combined_odds": leg['price'],
        "combined_prob": leg['prob'],
        "n_legs": 1,
        "legs": [leg]
    }]
}

from booking.booking_codes import book_accas
r = book_accas(payload, headless=True)
print(json.dumps(r, indent=2, ensure_ascii=False))
