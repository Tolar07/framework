"""
monitor/bot_grader.value_watch_lines (Architect 2026-11-08: keep the new sports' value rule, and show in the
23:02 report what it sees). For each rollout sport, today's board: games, picks, the best value seen inside the
pick rule's price band and 50% chance, and the bar it had to clear. Read-only. Offline: boards in a temp folder.
"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from monitor import bot_grader as bg  # noqa: E402

tmp = Path(tempfile.mkdtemp())
ih_dir, ms_dir = tmp / "ice_hockey", tmp / "multisport"
ih_dir.mkdir(parents=True)
(ms_dir / "rugby").mkdir(parents=True)
(ms_dir / "darts").mkdir(parents=True)
day = "2026-11-12"


def look(price, fair=None, model=None):
    return {"last": {"price": price, "fair": fair, "model": model, "at": "x"}}


# ice hockey: a Matchbook-priced winner side (1.90 x 0.53 = +0.7%) and one outside the band (price 2.40)
(ih_dir / f"ih_{day}.json").write_text(json.dumps({"games": {"g1": {
    "home": "Toronto Maple Leafs", "away": "Boston Bruins",
    "sides": {"H:406||Home": look(1.90, 0.53), "H:406||Away": look(2.40, 0.47)}}}, "picks": []}),
    encoding="utf-8")
# rugby: best side +2.6% (1.40 x 0.733), the other below 50%
(ms_dir / "rugby" / f"ms_{day}.json").write_text(json.dumps({"games": {"r1": {
    "home": "England", "away": "Australia",
    "sides": {"rugby:406||Home": look(1.40, 0.733), "rugby:406||Away": look(3.10, 0.267)}}},
    "picks": [{"x": 1}]}), encoding="utf-8")
# darts: no fair price and no model -> nothing to measure
(ms_dir / "darts" / f"ms_{day}.json").write_text(json.dumps({"games": {"d1": {
    "home": "Littler, Luke", "away": "Price, Gerwyn", "sides": {"darts:186||Home": look(1.50)}}}, "picks": []}),
    encoding="utf-8")

lines = bg.value_watch_lines(day, ih_dir, ms_dir)
by = {ln.split(":")[0]: ln for ln in lines}
assert len(lines) == len(bg.ROLLOUT_SPORTS), lines
assert "+0.7%" in by["Ice hockey"] and "Toronto Maple Leafs to win" in by["Ice hockey"], by["Ice hockey"]
assert "1 games, 0 picks" in by["Ice hockey"]
assert "+2.6%" in by["Rugby"] and "1 picks" in by["Rugby"] and "England to win @ 1.4" in by["Rugby"], by["Rugby"]
assert "vs bar" in by["Rugby"]
assert "no side in the price band" in by["Darts"], by["Darts"]
assert by["Tennis"] == "Tennis: no board today", by["Tennis"]

# the report carries the section, and a broken board never breaks the report
(ms_dir / "rugby" / f"ms_{day}.json").write_text("{not json", encoding="utf-8")
assert bg.value_watch_lines(day, ih_dir, ms_dir)[bg.ROLLOUT_SPORTS.index("rugby")] == "Rugby: no board today"
src = (ROOT / "monitor" / "bot_grader.py").read_text(encoding="utf-8")
assert "NEW SPORTS VALUE WATCH" in src

print("value_watch_test OK")
