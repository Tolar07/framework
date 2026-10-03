'''Render both board views against the latest board JSON.'''
import json
import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path('.')).replace('\\', '/'))

# Force UTF-8 encoding for Windows console
os.environ['PYTHONIOENCODING'] = 'utf-8'

from output.produce_bet import BoardFixture, render_compact_heartbeat
from output.render_fixture_list import render_fixture_list
from engine.dixon_coles import FixtureProbabilities

bd = Path('output/boards')
boards = sorted(bd.glob('board_*.json'))
raw = json.loads(boards[-1].read_text(encoding='utf-8'))

objs = []
for e in raw.get('board', []):
    pd = e.get('probs')
    probs = (
        FixtureProbabilities(
            home_team=pd.get('home_team', ''),
            away_team=pd.get('away_team', ''),
            lambda_home=0.0,
            lambda_away=0.0,
            p_home=pd.get('p_home', 0.0),
            p_draw=pd.get('p_draw', 0.0),
            p_away=pd.get('p_away', 0.0),
            modal_scoreline=tuple(pd.get('modal_scoreline', [0, 0])),
            p_over_15=pd.get('p_over_15'),
            p_over_25=pd.get('p_over_25'),
            p_over_35=pd.get('p_over_35'),
            p_btts_yes=pd.get('p_btts_yes'),
        )
        if pd else None
    )
    objs.append(
        BoardFixture(
            fixture=e.get('fixture', ''),
            probs=probs,
            verification=None,
            kickoff_utc=e.get('kickoff_utc'),
            best_market=e.get('best_market'),
            best_price=e.get('best_price'),
            best_bookmaker=e.get('best_bookmaker'),
            best_mes_ev=e.get('best_mes_ev'),
            best_model_prob=e.get('best_model_prob'),
            best_market_key=e.get('best_market_key'),
            kickoff_date=e.get('kickoff_date'),
            on_deploy_shortlist=e.get('on_deploy_shortlist', False),
        )
    )

print('=== RENDER_COMPACT_HEARTBEAT (produce_bet.py) ===')
print(render_compact_heartbeat(objs))
print()
print('=== RENDER_FIXTURE_LIST (render_fixture_list.py) ===')
print(render_fixture_list(board=objs))