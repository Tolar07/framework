import sys
from pathlib import Path

# This script lives at the repo root, so the repo root is simply its own
# directory. It previously hardcoded
# 'c:/Users/Motunrayo/omniroute test/olp_xdv_agent/olp_xdv', which resolves on
# exactly one machine and nowhere else.
sys.path.insert(0, str(Path(__file__).resolve().parent))

# ARCHITECT: this imported `orchestrator`, which does not exist -- orchestrator.py
# was deleted in 41ddf9d ("Fix SportyBet nav + Telegram dotenv") and renamed to
# orchestrator_DEPRECATED.py, but this consumer was never updated. run_scan.py
# has raised ModuleNotFoundError on line 3 ever since, so it has not run at all.
#
# scan_one_league, FULL_WHITELIST and next_season_code exist ONLY in
# orchestrator_DEPRECATED.py -- there is no replacement anywhere in the repo --
# so pointing at it is what restores this script. But the file is named
# DEPRECATED, which says the intent was to retire it. Decide which you want:
# either this script should move to whatever superseded the orchestrator, or
# orchestrator_DEPRECATED.py should lose the suffix because it is still load-bearing.
from orchestrator_DEPRECATED import scan_one_league, FULL_WHITELIST, next_season_code
import io
from contextlib import redirect_stdout

# Aggregate all leagues directly
season = '2526'
fixtures_season = next_season_code(season)
combined_board = []
all_flags = []

buf = io.StringIO()
with redirect_stdout(buf):
    for league in FULL_WHITELIST:
        print(f"Scanning {league}...")
        board_slice, flags = scan_one_league(league, season, fixtures_season=fixtures_season)
        combined_board.extend(board_slice)
        all_flags.extend(flags)

with open('scan_output.txt', 'w', encoding='utf-8') as f:
    f.write(f'Board size: {len(combined_board)} fixtures\n')
    rated = sum(1 for b in combined_board if b.probs is not None)
    unrated = sum(1 for b in combined_board if b.probs is None)
    f.write(f'Rated: {rated}\n')
    f.write(f'Unrated (NO DATA): {unrated}\n')
    f.write('\n--- UNRATED FIXTURES ---\n')
    for b in combined_board:
        if b.probs is None:
            f.write(f'  NO DATA: {b.fixture} - {b.rejection_reason}\n')
    f.write('\n--- FULL BOARD OUTPUT ---\n')
    f.write(buf.getvalue())

print('Done - output written to scan_output.txt')