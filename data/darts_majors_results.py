"""
PDC major-event results WITH ROUND DATES (framework#341; record-only data feed).

Wikipedia's CC-licensed pages for the PDC majors (World Matchplay, World Grand Prix, Grand Slam knockout, UK Open,
Players Championship Finals, European Championship, Masters) carry bracket templates whose round headers state the
dates ("First round (best of 19 legs)<br>19-21 July"). Every match gets the START date of its round, never a
finer date it does not have (HR35), so within a round the order is only a tie-break. This widens the dated sample
beyond the closed Premier League field (data/darts_pl_results.py). Idea only: public wikitext is parsed, nothing is
copied from any GPL code. A failed fetch or a page that does not exist gives nothing, never an invented game (HR59);
a round whose header has no readable date is skipped. No price is in this source.

  python data/darts_majors_results.py     fetch 2023-2026 and write data/darts/majors_results.json
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

OUT = ROOT / "data" / "darts" / "majors_results.json"
YEARS = range(2023, 2027)
EVENTS = {"World Matchplay": "World_Matchplay", "World Grand Prix": "World_Grand_Prix_(darts)",
          "Grand Slam of Darts": "Grand_Slam_of_Darts", "UK Open": "UK_Open",
          "Players Championship Finals": "Players_Championship_Finals",
          "European Championship": "European_Championship_(darts)", "Masters": "Masters_(darts)"}
API = "https://en.wikipedia.org/w/api.php?action=parse&page={year}_{page}&prop=wikitext&format=json&formatversion=2"
_MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
           "november", "december"]
_RD = re.compile(r"^\|\s*RD(\d+)\s*=(.*)$")
_MON = "|".join(m.capitalize() for m in _MONTHS)
_DAY_MONTH = re.compile(rf"(\d{{1,2}})\s*({_MON})\b")
_DAY_RANGE = re.compile(rf"(\d{{1,2}})\s*[-–—]\s*\d{{1,2}}\s*({_MON})\b")


def header_start(header: str, year: int) -> date | None:
    """Start date of a round from its header text ('...<br>19-21 July' or '30 June - 2 July'); None if unreadable."""
    tail = re.sub(r"\{\{[^}]*\}\}|'''|''", " ", header.split("<br>")[-1]) if "<br" in header else header
    tail = re.sub(r"\(best of[^)]*\)", " ", tail)
    for rx in (_DAY_RANGE, _DAY_MONTH):
        m = rx.search(tail)
        if m:
            try:
                return date(year, _MONTHS.index(m.group(2).lower()) + 1, int(m.group(1)))
            except ValueError:
                return None
    return None


def parse_event(wikitext: str, year: int, event: str) -> list[dict]:
    """Dated matches of one event page. Each bracket template is parsed on its own so a round header's date reaches
    the matches of that round; matches in a round with no readable date are dropped."""
    chunks = re.split(r"(?m)^(?=\{\{[^\n{|]*Bracket)", wikitext)
    out: list[dict] = []
    seen: set[tuple[frozenset, str]] = set()
    for ch in chunks:
        dates: dict[int, date] = {}
        for line in ch.splitlines():
            m = _RD.match(line)
            if m:
                d = header_start(m.group(2), year)
                if d:
                    dates[wc.round_order(m.group(2), int(m.group(1)))] = d
        if not dates:
            continue
        for g in wc.parse_bracket(ch, year):
            rnd = int(g["kickoff_utc"].split("-")[1])
            d = dates.get(rnd)
            key = (frozenset((g["home"], g["away"])), d.isoformat() if d else "")
            if d is None or key in seen:
                continue
            seen.add(key)
            g = dict(g)
            g["date"] = d.isoformat()
            g["tournament"] = f"{year} {event}"
            out.append(g)
    out.sort(key=lambda g: (g["date"], g["kickoff_utc"]))
    for i, g in enumerate(out):
        g["kickoff_utc"] = f"{g['date']}-{i:04d}"
    return out


def _wiki(year: int, page: str) -> str | None:
    for wait in (0, 20, 60, 120):
        time.sleep(wait)
        req = urllib.request.Request(API.format(year=year, page=page), headers={"User-Agent": wc.UA})  # noqa: S310 fixed https URL
        try:
            with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310
                return json.load(r).get("parse", {}).get("wikitext")  # None when the page does not exist
        except urllib.error.HTTPError as e:
            if e.code != 429:
                return None
        except (OSError, ValueError):
            return None
    return None


def fetch_all(years=YEARS, get=None) -> list[dict]:
    games: list[dict] = []
    for y in years:
        for event, page in EVENTS.items():
            text = _wiki(y, page) if get is None else get(y, page)
            if text:
                games += parse_event(text, y, event)
            if get is None:
                time.sleep(3)
    games.sort(key=lambda g: (g["date"], g["tournament"], g["kickoff_utc"]))
    for i, g in enumerate(games):
        g["kickoff_utc"] = f"{g['date']}-{i:04d}"
    return games


if __name__ == "__main__":
    g = fetch_all()
    if g:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(g, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"{len(g)} matches" if g else "NO DATA - PENDING")
    sys.exit(0)
