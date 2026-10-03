import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from output.notify import deliver

board = Path("telegram_2026-08-25.txt")
text = board.read_text(encoding="utf-8")
# No survival tag — this is the standard new-format board resend
ok, notes = deliver(text, save_to=board)
for n in notes:
    print(n)
print("STATUS:", "DELIVERED" if ok else "FAILED")
