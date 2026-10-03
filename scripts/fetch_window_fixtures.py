"""
Fetch fixtures for all whitelisted leagues across a date window (today → N days ahead).
Usage: python scripts/fetch_window_fixtures.py [days_ahead]
Default days_ahead=5 (today Tuesday → Sunday).
"""
import os
import sys
from pathlib import Path
from datetime import date, timedelta

# Load .env
env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, val = line.split('=', 1)
            os.environ[key.strip()] = val.strip()

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.multi_source_concrete import get_fixtures
from engine.league_registry import registry

def main():
    days_ahead = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    today = date.today()
    end = today + timedelta(days=days_ahead)

    print(f"Today: {today} ({today.strftime('%A')})")
    print(f"Window: {today} to {end} ({days_ahead} days ahead)")
    print(f"Whitelisted leagues: {len(registry._leagues)}")
    print("=" * 60)

    total = 0
    leagues_with_fixtures = 0
    for lg in sorted(registry._leagues.keys()):
        try:
            fx = get_fixtures(lg, '2627', days_ahead=days_ahead)
            fixtures_list = fx.get('fixtures', fx) if isinstance(fx, dict) else fx
            count = len(fixtures_list)
            if count > 0:
                total += count
                leagues_with_fixtures += 1
                print(f"{lg}: {count} fixtures")
        except Exception as e:
            print(f"{lg}: ERROR {str(e)[:80]}")

    print("=" * 60)
    print(f"Total: {total} fixtures across {leagues_with_fixtures} leagues "
          f"(out of {len(registry._leagues)} whitelisted)")

if __name__ == "__main__":
    main()
