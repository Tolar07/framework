import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from output.notify import deliver

board = Path("output/boards/board_2026-08-25.txt")
text = board.read_text(encoding="utf-8")
tag = "\n\n=== SURVIVAL RUN — booking paused, SportyBet nav fix pending ===\n\n"
body = text + tag

ok, notes = deliver(body, save_to=board)
for n in notes:
    print(n)
print("STATUS:", "DELIVERED" if ok else "FAILED")