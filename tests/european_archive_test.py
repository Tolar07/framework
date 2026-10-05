"""European results archive (data/european_archive.py). Offline."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data import european_archive as eu  # noqa: E402


def test_archive() -> None:
    ev = [{"league": "EUROPE: UEFA Champions League - League phase", "home": "Arsenal",
           "away": "PSV", "fthg": 2, "ftag": 1, "fh_home": 1, "fh_away": 0,
           "finished_regular": True, "finished_other": False,
           "kickoff_utc": "2026-10-21T19:00:00Z"},
          {"league": "EUROPE: UEFA Champions League Women - League phase", "home": "A",
           "away": "B", "fthg": 1, "ftag": 0, "finished_regular": True,
           "kickoff_utc": "2026-10-21T19:00:00Z"},
          {"league": "EUROPE: UEFA Europa League - League phase", "home": "Roma", "away": "Lyon",
           "fthg": None, "ftag": None, "finished_regular": False, "finished_other": False,
           "kickoff_utc": "2026-10-22T19:00:00Z"},
          {"league": "ENGLAND: Premier League", "home": "X", "away": "Y", "fthg": 0, "ftag": 0,
           "finished_regular": True, "kickoff_utc": "2026-10-21T19:00:00Z"}]
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "r.json"
        assert eu.archive(ev, p) == 1, "men's European club results only, finished only"
        assert eu.archive(ev, p) == 0, "no duplicates"
        rows = json.loads(p.read_text())
        assert rows[0]["home"] == "Arsenal" and rows[0]["fh_home"] == 1


if __name__ == "__main__":
    test_archive()
    print("European archive: OK")
