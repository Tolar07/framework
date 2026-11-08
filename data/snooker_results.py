"""
World Snooker Tour results WITH TOURNAMENT DATES (framework#352; record-only data feed).

Wikipedia's CC-licensed season pages ("2023-24 snooker season") list every World Snooker Tour event of the season,
and each event page carries its draw as bracket templates (`{{#invoke:RoundN ...}}` or `{{16TeamBracket ...}}`)
with both players and frames won, plus the event's start date in the infobox (`{{Start and end dates|...}}`).

A match gets the START date of its event, never a finer date the page does not give (HR35); inside an event the
rounds are put in order (last 128 before last 64 ... before the final). Single-frame Shoot Out, round-robin
Championship League groups, team, seniors' and women's events are left out. Public wikitext is parsed, nothing is
copied from any code. A failed fetch or a missing page gives nothing, never an invented match (HR59); a match with a
walkover, a missing score or a tie is skipped. No price is in this source.

  python data/snooker_results.py     fetch the 2019-20 .. 2025-26 seasons and write data/snooker/results.json
"""
from __future__ import annotations

import json
import math
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "snooker" / "results.json"
SEASONS = range(2019, 2026)                 # season starting year: 2019 = 2019-20
API = "https://en.wikipedia.org/w/api.php?action=parse&page={page}&prop=wikitext&format=json&formatversion=2"
UA = "olp-research/1.0 (framework snooker study)"
SKIP = ("shoot out", "shoot-out", "championship league", "world cup", "seniors", "women", "q tour", "six-red",
        "mixed doubles", "nations", "team")

_START = re.compile(r"\{\{\s*Start and end dates\s*\|\s*(\d{4})\s*\|\s*(\d{1,2})\s*\|\s*(\d{1,2})", re.I)
_LINK = re.compile(r"\[\[([^|\]]+)(?:\|[^\]]*)?\]\]")
_NAME_LINK = re.compile(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]")
_SIZE_WORDS = (("quarter", 8), ("semi", 4), ("final", 2))


def season_page(start_year: int) -> str:
    return f"{start_year}–{(start_year + 1) % 100:02d}_snooker_season"


def split_params(body: str) -> list[str]:
    """Top-level `|` split of a template body (pipes inside {{...}} and [[...]] are kept)."""
    out, cur, depth_t, depth_l, i = [], [], 0, 0, 0
    while i < len(body):
        two = body[i:i + 2]
        if two == "{{":
            depth_t += 1
            cur.append(two)
            i += 2
            continue
        if two == "}}" and depth_t:
            depth_t -= 1
            cur.append(two)
            i += 2
            continue
        if two == "[[":
            depth_l += 1
            cur.append(two)
            i += 2
            continue
        if two == "]]" and depth_l:
            depth_l -= 1
            cur.append(two)
            i += 2
            continue
        if body[i] == "|" and not depth_t and not depth_l:
            out.append("".join(cur))
            cur = []
        else:
            cur.append(body[i])
        i += 1
    out.append("".join(cur))
    return out


def templates(text: str) -> list[str]:
    """Bodies of every RoundN / NTeamBracket template in a page (balanced braces)."""
    out = []
    for m in re.finditer(r"\{\{\s*(#invoke:RoundN|[0-9A-Za-z-]*TeamBracket)", text):
        depth, i = 0, m.start()
        while i < len(text):
            if text.startswith("{{", i):
                depth += 1
                i += 2
            elif text.startswith("}}", i):
                depth -= 1
                i += 2
                if depth == 0:
                    out.append(text[m.start() + 2:i - 2])
                    break
            else:
                i += 1
    return out


def player(cell: str) -> str | None:
    cell = re.sub(r"\{\{\s*tooltip\|[^}]*\}\}|<[^>]+>|'''|''", "", cell or "")
    m = _NAME_LINK.search(cell)
    s = (m.group(1) if m else re.sub(r"\{\{[^}]*\}\}", "", cell)).strip()
    s = re.sub(r"\s*\((?:\d+|a|A|WC|wc)\)\s*$", "", s).strip()
    return s if s and not re.fullmatch(r"(bye|w/o|tbd|\W*)", s, re.I) else None


def frames(cell: str) -> int | None:
    s = re.sub(r"<[^>]+>|'''|''|\{\{[^}]*\}\}", "", cell or "").strip()
    return int(s) if s.isdigit() else None


def round_size(header: str, rd: int, columns: int) -> int:
    """Players in the round: 'Last 32' -> 32, quarter-finals 8, semi-finals 4, final 2; else from the column."""
    h = re.sub(r"<[^>]+>|'''", " ", header or "").lower()
    m = re.search(r"last\s*(\d+)", h)
    if m:
        return int(m.group(1))
    for word, n in _SIZE_WORDS:
        if word in h:
            return n
    return 2 ** (columns - rd + 1)


def parse_template(body: str) -> list[dict]:
    """(player, frames, player, frames, round size) of every complete match in one bracket template."""
    parts = split_params(body)[1:]
    named: dict[str, str] = {}
    positional: list[str] = []
    for p in parts:
        m = re.match(r"\s*([A-Za-z0-9_ -]+?)\s*=(.*)$", p, re.S)
        if m and not p.lstrip().startswith(("{{", "[[", "'")):
            named[m.group(1).strip()] = m.group(2).strip()
        else:
            positional.append(p.strip())
    heads = {int(k[2:]): v for k, v in named.items() if re.fullmatch(r"RD\d+", k)}
    out: list[dict] = []
    if body.lstrip().startswith("#invoke"):
        if positional and positional[0].lower() == "main":
            positional = positional[1:]
        cols = int(named.get("columns", max(heads) if heads else 0) or 0)
        if not cols:
            return []
        i = 0
        for rd in range(1, cols + 1):
            size = round_size(heads.get(rd, ""), rd, cols)
            for _ in range(2 ** (cols - rd)):
                grp = positional[i:i + 5]
                i += 5
                if len(grp) < 5:
                    return out
                a, fa, b, fb = player(grp[1]), frames(grp[2]), player(grp[3]), frames(grp[4])
                if a and b and fa is not None and fb is not None and fa != fb:
                    out.append({"a": a, "fa": fa, "b": b, "fb": fb, "size": size})
        return out
    cols = max(heads) if heads else 0
    for k, v in named.items():
        m = re.fullmatch(r"RD(\d+)-team(\d+)", k)
        if not m or int(m.group(2)) % 2 == 0:
            continue
        rd, i = int(m.group(1)), int(m.group(2))
        j = f"{i + 1:0{len(m.group(2))}d}"
        a, b = player(v), player(named.get(f"RD{rd}-team{j}", ""))
        fa, fb = frames(named.get(f"RD{rd}-score{m.group(2)}", "")), frames(named.get(f"RD{rd}-score{j}", ""))
        if a and b and fa is not None and fb is not None and fa != fb:
            out.append({"a": a, "fa": fa, "b": b, "fb": fb, "size": round_size(heads.get(rd, ""), rd, cols)})
    return out


def parse_event(text: str, event: str) -> list[dict]:
    """Every match of one event page, dated by the event's start; a page without a readable start gives nothing."""
    m = _START.search(text or "")
    if not m:
        return []
    start = f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    seen: set[frozenset] = set()
    rows = []
    for body in templates(text):
        for g in parse_template(body):
            key = frozenset((g["a"], g["b"]))
            if key in seen:
                continue
            seen.add(key)
            rows.append(g)
    rows.sort(key=lambda g: -g["size"])
    out = []
    for i, g in enumerate(rows):
        rank = 8 - int(math.log2(max(g["size"], 2)))
        out.append({"date": start, "kickoff_utc": f"{start}-{rank:02d}-{i:04d}", "tournament": event,
                    "home": g["a"], "away": g["b"], "home_frames": g["fa"], "away_frames": g["fb"],
                    "winner": 1 if g["fa"] > g["fb"] else 2, "round_players": g["size"]})
    return out


def season_events(text: str) -> list[str]:
    """Event page titles in the season's World Snooker Tour table (the first calendar table)."""
    m = re.search(r"(?m)^===\s*World Snooker Tour\s*===\s*$", text)
    if not m:
        return []
    j = text.find("\n==", m.end())
    section = text[m.end():j if j > 0 else None]
    pages = []
    for m in _LINK.finditer(section):
        t = m.group(1).strip()
        if re.match(r"\d{4} ", t) and not any(s in t.lower() for s in SKIP) and t not in pages:
            pages.append(t)
    return pages


def _wiki(page: str) -> str | None:
    url = API.format(page=urllib.parse.quote(page.replace(" ", "_")))
    for wait in (0, 20, 60):
        time.sleep(wait)
        req = urllib.request.Request(url, headers={"User-Agent": UA})  # noqa: S310 fixed https URL
        try:
            with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310
                return json.load(r).get("parse", {}).get("wikitext")
        except urllib.error.HTTPError as e:
            if e.code != 429:
                return None
        except (OSError, ValueError):
            return None
    return None


def fetch_all(seasons=SEASONS, get=None) -> list[dict]:
    get = get or _wiki
    games: list[dict] = []
    for s in seasons:
        for page in season_events(get(season_page(s)) or ""):
            games += parse_event(get(page) or "", page)
            if get is _wiki:
                time.sleep(1)
    games.sort(key=lambda g: g["kickoff_utc"])
    return games


if __name__ == "__main__":
    g = fetch_all()
    if g:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(g, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"{len(g)} matches, {len({x['tournament'] for x in g})} events" if g else "NO DATA - PENDING")
    sys.exit(0)
