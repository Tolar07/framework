"""
PDC World Championship results from Wikipedia's bracket wikitext (framework#341; record-only data feed).

Wikipedia's CC-licensed bracket templates list every match as player names + sets won, so a dated multi-season
darts results history exists after all. Idea only: this parses the public wikitext, nothing is copied from any
GPL code. Nothing here touches a pick, stake or bar. A failed fetch gives an empty list, never an invented game
(HR59); missing fields are skipped, never filled (HR35).

kickoff_utc is an ORDERING key only ("<year>-RR-MMM"): round, then bracket position. Real match dates are not in
the bracket, so no date is claimed.

  python data/darts_results.py     fetch 2020-2026 and write data/darts/wc_results.json
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "darts" / "wc_results.json"
YEARS = range(2020, 2027)
API = ("https://en.wikipedia.org/w/api.php?action=parse&page={year}_PDC_World_Darts_Championship"
       "&prop=wikitext&format=json&formatversion=2")
UA = "olp-research/1.0 (framework darts study)"

_TEAM = re.compile(r"^\|\s*RD(\d+)-team(\d+)\s*=\s*(.*)$")
_SCORE = re.compile(r"^\|\s*RD(\d+)-score(\d+)\s*=\s*'*(\d+)'*\s*(?:<.*)?$")
_NAME = re.compile(r"PDCFlag\|([^|}]+)")
_LINK = re.compile(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]")


def player_name(cell: str) -> str | None:
    m = _NAME.search(cell)
    if m:
        return m.group(1).strip() or None
    m = _LINK.search(cell)
    s = (m.group(1) if m else re.sub(r"\{\{[^}]*\}\}|<[^>]+>", "", cell)).strip()
    return s or None


_HEAD = re.compile(r"^\|\s*RD(\d+)\s*=(.*)$")
_ROUNDS = (("first", 1), ("second", 2), ("third", 3), ("fourth", 4), ("quarter", 5), ("semi", 6), ("final", 7))


def round_order(header: str, rd: int) -> int:
    """Chronological round (1 first round .. 7 final) from the bracket header text; falls back to the column number."""
    m = re.search(r"'''([^']+)'''", header)
    h = (m.group(1) if m else "").lower()
    for key, n in _ROUNDS:
        if key in h:
            return n
    return rd


def parse_bracket(wikitext: str, year: int) -> list[dict]:
    """Every match with both player names and both scores, oldest round first. A page holds several brackets (four
    quarters of the draw, then the knockout stage); a new `RD1` header starts the next one. Incomplete pairs are
    skipped and a match listed in two brackets is kept once."""
    names: dict[tuple[int, int, int], str] = {}
    scores: dict[tuple[int, int, int], int] = {}
    heads: dict[tuple[int, int], str] = {}
    block = 0
    for line in wikitext.splitlines():
        m = _HEAD.match(line)
        if m:
            if int(m.group(1)) == 1:
                block += 1
            heads[(block, int(m.group(1)))] = m.group(2)
            continue
        m = _TEAM.match(line)
        if m:
            n = player_name(m.group(3))
            if n:
                names[(block, int(m.group(1)), int(m.group(2)))] = n
            continue
        m = _SCORE.match(line)
        if m:
            scores[(block, int(m.group(1)), int(m.group(2)))] = int(m.group(3))
    out, seen = [], set()
    for (bl, rd, i), home in sorted(names.items()):
        if i % 2 == 0:
            continue
        away = names.get((bl, rd, i + 1))
        sh, sa = scores.get((bl, rd, i)), scores.get((bl, rd, i + 1))
        if away is None or sh is None or sa is None or sh == sa:
            continue
        key = (frozenset((home, away)), round_order(heads.get((bl, rd), ""), rd))
        if key in seen:
            continue
        seen.add(key)
        out.append({"home": home, "away": away, "home_sets": sh, "away_sets": sa,
                    "winner": 1 if sh > sa else 2,
                    "kickoff_utc": f"{year}-{key[1]:02d}-{bl:02d}-{i:03d}",
                    "tournament": f"{year} PDC World Championship"})
    out.sort(key=lambda g: g["kickoff_utc"])
    return out


def _wiki(year: int) -> str:
    """Wikitext of one year's page; waits and retries when Wikipedia says 429 (rate limit)."""
    for wait in (0, 20, 60, 120):
        time.sleep(wait)
        req = urllib.request.Request(API.format(year=year), headers={"User-Agent": UA})  # noqa: S310 fixed https URL
        try:
            with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310
                return json.load(r)["parse"]["wikitext"]
        except urllib.error.HTTPError as e:
            if e.code != 429:
                raise
    raise RuntimeError("rate limited")


def fetch_year(year: int, get=None) -> list[dict]:
    try:
        text = _wiki(year) if get is None else get(year)
    except Exception:
        return []
    return parse_bracket(text, year)


def fetch_all(years=YEARS, get=None) -> list[dict]:
    games: list[dict] = []
    for y in years:
        games += fetch_year(y, get)
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
