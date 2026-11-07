"""
Premier League Darts nightly results WITH REAL DATES (framework#341; record-only data feed).

Wikipedia's CC-licensed season pages (2023-2026) carry one bracket per night under a heading such as
"6 February - Night 1", so these matches have true dates, unlike the World Championship brackets. Idea only: this
parses public wikitext, nothing is copied from any GPL code. A failed fetch gives an empty list, never an invented
game (HR59); a night whose heading has no readable date is skipped (HR35). No price is in this source.

  python data/darts_pl_results.py     fetch 2023-2026 and write data/darts/pl_results.json
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from data import darts_results as wc  # noqa: E402

OUT = ROOT / "data" / "darts" / "pl_results.json"
YEARS = range(2023, 2027)
API = ("https://en.wikipedia.org/w/api.php?action=parse&page={year}_Premier_League_Darts"
       "&prop=wikitext&format=json&formatversion=2")
_MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
           "november", "december"]
_NIGHT = re.compile(r"^===\s*(\d{1,2})\s+([A-Za-z]+)\s*[-–—]\s*(Night\s+\d+|Play-offs?|Playoffs?)[^=]*===\s*$",
                    re.M | re.I)


def parse_nights(wikitext: str, year: int) -> list[dict]:
    """Every night's matches with a real ISO date. Sections run from one night heading to the next."""
    heads = list(_NIGHT.finditer(wikitext))
    out: list[dict] = []
    for i, m in enumerate(heads):
        if m.group(2).lower() not in _MONTHS:
            continue
        try:
            day = date(year, _MONTHS.index(m.group(2).lower()) + 1, int(m.group(1)))
        except ValueError:
            continue
        end = heads[i + 1].start() if i + 1 < len(heads) else len(wikitext)
        for j, g in enumerate(wc.parse_bracket(wikitext[m.end():end], year)):
            g = dict(g)
            g["kickoff_utc"] = f"{day.isoformat()}-{j:03d}"
            g["date"] = day.isoformat()
            g["tournament"] = f"{year} Premier League Darts"
            out.append(g)
    out.sort(key=lambda g: g["kickoff_utc"])
    return out


def _wiki(year: int) -> str:
    for wait in (0, 20, 60, 120):
        time.sleep(wait)
        req = urllib.request.Request(API.format(year=year), headers={"User-Agent": wc.UA})  # noqa: S310 fixed https URL
        try:
            with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310
                return json.load(r)["parse"]["wikitext"]
        except urllib.error.HTTPError as e:
            if e.code != 429:
                raise
    raise RuntimeError("rate limited")


def fetch_all(years=YEARS, get=None) -> list[dict]:
    games: list[dict] = []
    for y in years:
        try:
            text = _wiki(y) if get is None else get(y)
        except Exception:
            continue
        games += parse_nights(text, y)
        if get is None:
            time.sleep(3)
    return games


if __name__ == "__main__":
    g = fetch_all()
    if g:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(g, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"{len(g)} matches" if g else "NO DATA - PENDING")
    sys.exit(0)
