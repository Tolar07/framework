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


def test_cup_archive() -> None:
    ev = [{"league": "TURKEY: Turkish Cup - Qualification", "home": "Hatayspor", "away": "Karakopru",
           "fthg": 1, "ftag": 2, "fh_home": 0, "fh_away": 0, "finished_regular": True,
           "finished_other": False, "kickoff_utc": "2026-10-07T11:00:00Z"},
          {"league": "TURKEY: Turkish Cup - Qualification", "home": "Soke 1970", "away": "Ayvalikgucu",
           "fthg": 1, "ftag": 2, "finished_regular": False, "finished_other": True,
           "kickoff_utc": "2026-10-07T11:30:00Z"},
          {"league": "TURKEY: Turkish Cup - Qualification", "home": "Eskisehirspor", "away": "Aksehirspor",
           "fthg": None, "ftag": None, "finished_regular": False, "finished_other": False,
           "kickoff_utc": "2026-10-07T17:00:00Z"},
          {"league": "TURKEY: 2. Lig Red Group", "home": "Hatayspor", "away": "X", "fthg": 0, "ftag": 0,
           "finished_regular": True, "kickoff_utc": "2026-10-04T12:00:00Z"},
          {"league": "TURKEY: 3. Lig Group 1", "home": "Y", "away": "Karakopru", "fthg": 0, "ftag": 0,
           "finished_regular": True, "kickoff_utc": "2026-10-04T12:00:00Z"}]
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "c.json"
        assert eu.archive_cups(ev, p) == 2, "finished cup ties only"
        assert eu.archive_cups(ev, p) == 0, "no duplicates"
        assert eu.archive(ev, Path(d) / "e.json") == 0, "cup ties are not European results"
        rows = {r["home"]: r for r in json.loads(p.read_text())}
        h = rows["Hatayspor"]
        assert (h["home_tier"], h["away_tier"], h["went_to_et"]) == (3, 4, False), h
        assert rows["Soke 1970"]["went_to_et"] is True and rows["Soke 1970"]["home_tier"] is None


if __name__ == "__main__":
    test_archive()
    test_cup_archive()
    print("European + Turkish Cup archive: OK")
