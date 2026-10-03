import json, sys
sys.path.insert(0, 'booking')
from team_map import resolve_team, _normalize

# Check what resolve_team returns for each missing team
teams = ['Trabzonspor', 'Başakşehir', 'Vitória SC', 'Nacional',
         'Alanyaspor', 'Beşiktaş', 'Tenerife', 'Almeria',
         'PSV Eindhoven', 'Groningen', 'Porto', 'Arouca',
         'Spartak Moscow', 'Zenit', 'Torino', 'AC Milan',
         'Venezia', 'Lecce', 'Akron', 'Krylia Sovetov',
         'Göztepe', 'Gençlerbirliği', 'BSC Young Boys', 'FC Vaduz']

for t in teams:
    sb = resolve_team(t, 'sportybet')
    print(f'{t} -> {sb} [norm={_normalize(sb)}]')