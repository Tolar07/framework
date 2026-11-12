"""
STATS HISTORY - the match rows the statistics lists are built from (framework #581-#584, Architect 2026-11-12:
"Stats are key ... look for where you can get all the statistics"). RECORD ONLY: nothing here picks or stakes.

Two sources, both already used elsewhere in the framework:

  football-data.co.uk   the 22 divisions on the per-season endpoint (data/football_data_source.LEAGUE_CODES),
                        2018/19 on: full-time AND half-time score, corners (HC/AC), and the closing
                        over/under 2.5 price (market average, else Pinnacle, else bet365). The 'Extra' leagues
                        (Nordics, Austria, Switzerland, Denmark, Poland) carry neither half-time scores nor
                        corners, so they are not read here (HR35: absent, not guessed).
  SportyBet sweep       data/universe/graded_*.jsonl.gz (private data repo, monitor/universe_sweep.py): every
                        football game SportyBet listed since 2026-10-08 (500+ competitions), with SportyBet's own
                        prices (1x2, over/under 1.5/2.5/3.5, both teams to score) and the full-time and
                        half-time score.

A row is a plain dict: league, season, date, home, away, hg, ag, hthg, htag (None when absent), hc, ac (None when
absent), o25, u25 (closing price or None), source.
"""
from __future__ import annotations

import csv
import gzip
import io
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache"
UNIVERSE = ROOT / "data" / "universe"
SEASONS = ("1819", "1920", "2021", "2122", "2223", "2324", "2425", "2526", "2627")
CURRENT = "2627"
CACHE_MAX_AGE_S = 12 * 3600


def _num(v) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if x == x else None


def _int(v) -> int | None:
    x = _num(v)
    return int(x) if x is not None else None


def _first(row: dict, *keys) -> float | None:
    for k in keys:
        x = _num(row.get(k))
        if x is not None and x > 1.0:
            return x
    return None


def _iso(raw: str) -> str | None:
    raw = (raw or "").strip()
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return time.strftime("%Y-%m-%d", time.strptime(raw, fmt))
        except ValueError:
            continue
    return None


def parse_rows(league: str, season: str, text: str) -> list[dict]:
    """football-data.co.uk per-season CSV text -> rows (main schema only)."""
    out = []
    for raw in csv.DictReader(io.StringIO(text.lstrip("﻿").lstrip("ï»¿"))):
        r = {(k or "").lstrip("﻿").lstrip("ï»¿").strip(): (v or "").strip() for k, v in raw.items() if k}
        hg, ag, date = _int(r.get("FTHG")), _int(r.get("FTAG")), _iso(r.get("Date", ""))
        if hg is None or ag is None or not date or not r.get("HomeTeam"):
            continue
        out.append({
            "league": league, "season": season, "date": date,
            "home": r["HomeTeam"], "away": r.get("AwayTeam", ""),
            "hg": hg, "ag": ag, "hthg": _int(r.get("HTHG")), "htag": _int(r.get("HTAG")),
            "hc": _int(r.get("HC")), "ac": _int(r.get("AC")),
            "o25": _first(r, "AvgC>2.5", "PC>2.5", "B365C>2.5"),
            "u25": _first(r, "AvgC<2.5", "PC<2.5", "B365C<2.5"),
            "source": "football-data.co.uk",
        })
    return out


def _text(league: str, season: str, cache: Path, fetch: bool) -> str | None:
    f = cache / f"{league.replace(' ', '_')}_{season}.csv"
    fresh = f.exists() and (season != CURRENT or time.time() - f.stat().st_mtime < CACHE_MAX_AGE_S)
    if fresh or (f.exists() and not fetch):
        return f.read_text(encoding="utf-8", errors="replace")
    if not fetch:
        return None
    try:
        from data import football_data_source as fds
        text = fds.fetch_csv_text(league, season)
        cache.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")
        return text
    except Exception:  # noqa: BLE001 - one league failing never stops the rest; a stale file still counts
        return f.read_text(encoding="utf-8", errors="replace") if f.exists() else None


def leagues() -> list[str]:
    from data import football_data_source as fds
    return [lg for lg, code in fds.LEAGUE_CODES.items() if code]


def load_history(seasons=SEASONS, cache: Path = CACHE, fetch: bool = True, only: list[str] | None = None
                 ) -> tuple[list[dict], dict]:
    """Every row of every main-schema league and season. Returns (rows, coverage) where coverage[league][season]
    is the row count, or 'PENDING' when the file could not be read."""
    rows, cov = [], {}
    for lg in only or leagues():
        for s in seasons:
            text = _text(lg, s, Path(cache), fetch)
            got = parse_rows(lg, s, text) if text else None
            cov.setdefault(lg, {})[s] = len(got) if got is not None else "PENDING"
            rows.extend(got or [])
    rows.sort(key=lambda r: r["date"])
    return rows, cov


def load_sportybet(universe: Path = UNIVERSE) -> list[dict]:
    """The sweep's graded football games: SportyBet's last price before kick-off and the result."""
    out, seen = [], set()
    for f in sorted(Path(universe).glob("graded_*.jsonl.gz")):
        with gzip.open(f, "rt", encoding="utf-8") as fh:
            for line in fh:
                try:
                    g = json.loads(line)
                except ValueError:
                    continue
                res = g.get("result") or {}
                if g.get("sport") != "football" or res.get("h") is None or g.get("id") in seen:
                    continue
                if res.get("after_90"):
                    continue
                seen.add(g.get("id"))
                ht = res.get("ht") or [None, None]
                p = ((g.get("last") or g.get("first") or {}).get("p")) or {}
                out.append({
                    "id": g.get("id"), "league": f"{g.get('country', '')}: {g.get('comp', '')}",
                    "country": g.get("country", ""), "comp": g.get("comp", ""), "covered": bool(g.get("covered")),
                    "date": (g.get("ko") or "")[:10], "ko": g.get("ko"), "home": g.get("home"), "away": g.get("away"),
                    "hg": int(res["h"]), "ag": int(res["a"]),
                    "hthg": ht[0] if len(ht) > 0 else None, "htag": ht[1] if len(ht) > 1 else None,
                    "hc": None, "ac": None, "prices": p, "source": "sportybet",
                })
    out.sort(key=lambda r: r["ko"] or "")
    return out
