"""
MULTI-SPORT TEAM NEWS RUN (framework#354): engine/ms_team_news.py over every rollout sport's board (ice hockey
and the multisport boards) for today and tomorrow, then the record of every flag against its result.

    python monitor/ms_team_news_run.py [--date YYYY-MM-DD] [--record]

Started by .github/workflows/multisport.yml after each look (and with --record after each grade).
RECORDED ONLY: it writes output/ms_team_news/ and memory/ms_team_news_record.json, never a board file.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from engine import ms_team_news as T  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="multi-sport team news (recorded only)")
    ap.add_argument("--date", action="append", help="board date(s); default today and tomorrow (UTC)")
    ap.add_argument("--record", action="store_true", help="grade every past flag against its result")
    a = ap.parse_args(argv)
    now = datetime.now(UTC)
    dates = a.date or [(now + timedelta(days=k)).date().isoformat() for k in (0, 1)]
    if not a.record:
        for line in T.run(dates, now=now):
            print(line)
    rec = T.record()
    T.RECORD.parent.mkdir(parents=True, exist_ok=True)
    T.RECORD.write_text(json.dumps(rec, indent=1), encoding="utf-8")
    print(T.summary_line(rec))
    return 0


if __name__ == "__main__":
    sys.exit(main())
