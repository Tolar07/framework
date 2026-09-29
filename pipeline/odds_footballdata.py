"""
Second free odds source: football-data.co.uk's fixtures.csv.

WHY THIS EXISTS
  the-odds-api (pipeline/odds.py) is the primary live-price source, but its
  free tier is a single metered pool — 500 requests/month across all leagues.
  Once it's exhausted the daily run logs ZERO entry prices, the Phase 2 paper
  log stops growing, and the Phase 3 gate can't advance. That is exactly what
  happened for most of September (every board: "Odds API quota down to 0").

  football-data.co.uk publishes fixtures.csv — upcoming matches for its MAIN
  divisions with pre-match 1X2 (Bet365, Pinnacle) and Over/Under 2.5 columns.
  It needs no key and has no quota, so it keeps a real entry price flowing when
  the metered source is blind. This module turns that CSV into the same
  FixtureOdds shape the rest of the pipeline already consumes.

HONEST LIMITS (HR35 — stated, never hidden)
  - MAIN-schema leagues only. The 'Extra' leagues (Danish Superliga, Ekstraklasa)
    are NOT in fixtures.csv, so this source returns nothing for them and says
    so — the-odds-api stays their only price source.
  - These are the prices football-data last published, refreshed a few times a
    week, not a to-the-second live quote. They are a real, reachable-book price
    (a genuine Bet365/Pinnacle number), so a legitimate entry — but a FALLBACK,
    not a replacement for a live pull. Provenance is stamped on every quote.
  - Team names in fixtures.csv are football-data's own, i.e. the model's keys,
    so no alias map is needed here (unlike the-odds-api, which needs one).
"""
from __future__ import annotations

import csv
import io
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from pipeline.odds import (
    FixtureOdds, MarketQuote, CACHE_DIR, ODDS_MAX_AGE_SECONDS, requests,
)
from data.football_data_source import LEAGUE_CODES

FIXTURES_URL = "https://www.football-data.co.uk/fixtures.csv"
# One file covers every division, so it's cached once (not per league) and
# reused within the same 60-minute recency cap the odds cache already enforces.
_FIXTURES_CACHE = CACHE_DIR / "footballdata_fixtures.json"

SOURCE = "football-data.co.uk (fixtures)"

# 1X2 price columns in reachable-book preference order (name shown, CSV column).
# Bet365 first (the book the Architect can reach), then Pinnacle, then the
# market average as a last resort — the average is not a single bettable book,
# so it is flagged when used, mirroring pipeline.odds._best_price.
_1X2_COLS = {
    "home": (("bet365", "B365H"), ("pinnacle", "PSH"), ("avg", "AvgH")),
    "draw": (("bet365", "B365D"), ("pinnacle", "PSD"), ("avg", "AvgD")),
    "away": (("bet365", "B365A"), ("pinnacle", "PSA"), ("avg", "AvgA")),
}
_OU_COLS = {
    "over25":  (("bet365", "B365>2.5"), ("pinnacle", "P>2.5"), ("avg", "Avg>2.5")),
    "under25": (("bet365", "B365<2.5"), ("pinnacle", "P<2.5"), ("avg", "Avg<2.5")),
}


def _to_float(v: Optional[str]) -> Optional[float]:
    if v is None:
        return None
    v = v.strip()
    if not v:
        return None
    try:
        return float(v)
    except ValueError:
        return None


def _parse_date(raw: str) -> Optional[str]:
    """football-data uses dd/mm/yy or dd/mm/yyyy — normalise to ISO, or None."""
    raw = (raw or "").strip()
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _quote(row: dict, cols: tuple[tuple[str, str], ...], now: str) -> MarketQuote:
    """First reachable book that quotes this outcome. HR35: a price that isn't
    there is None (NO DATA — PENDING), never invented or averaged into one."""
    n_books = sum(1 for _, col in cols if _to_float(row.get(col)) is not None)
    for book, col in cols:
        price = _to_float(row.get(col))
        if price is None:
            continue
        # The market average is not a single bettable book — flag it as such so
        # it stays visibly distinguishable from a real single-book quote.
        label = book if book != "avg" else "avg (not a single book)"
        return MarketQuote(price=price, bookmaker=label, n_books=n_books, captured_at=now)
    return MarketQuote(captured_at=now)


def _load_fixtures_rows() -> tuple[list[dict], list[str]]:
    """Fetch (or reuse cached) fixtures.csv as a list of cleaned rows.

    Cached once for all leagues under the same 60-minute recency cap the odds
    cache uses: a stale cache is refetched, not served."""
    flags: list[str] = []
    if requests is None:
        raise RuntimeError("requests not installed — cannot fetch fixtures.csv")

    text: Optional[str] = None
    if _FIXTURES_CACHE.exists():
        try:
            blob = json.loads(_FIXTURES_CACHE.read_text(encoding="utf-8"))
            if time.time() - blob.get("fetched_at", 0) <= ODDS_MAX_AGE_SECONDS:
                text = blob.get("csv")
        except (json.JSONDecodeError, OSError):
            text = None

    if text is None:
        r = requests.get(FIXTURES_URL, headers={"User-Agent": "OLP-XDV/1.0"}, timeout=30)
        r.raise_for_status()
        text = r.text
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _FIXTURES_CACHE.write_text(
            json.dumps({"fetched_at": time.time(), "csv": text}), encoding="utf-8")
        flags.append("football-data fixtures.csv pulled live")
    else:
        flags.append("football-data fixtures.csv served from cache (<=60min)")

    reader = csv.DictReader(io.StringIO(text))
    reader.fieldnames = [f.lstrip("﻿").strip() for f in (reader.fieldnames or [])]
    return list(reader), flags


def fetch_odds_footballdata(league: str) -> tuple[list[FixtureOdds], list[str]]:
    """Live prices for one league from fixtures.csv. Returns (fixtures, flags).

    Returns an empty list (with an honest flag) for a league fixtures.csv does
    not carry — the Extra leagues — rather than guessing."""
    flags: list[str] = []
    div = LEAGUE_CODES.get(league)
    if not div:
        flags.append(f"{league}: not in football-data fixtures.csv "
                     f"(Extra-schema or uncovered league) — NO DATA — PENDING")
        return [], flags

    rows, load_flags = _load_fixtures_rows()
    flags += load_flags
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    out: list[FixtureOdds] = []
    for row in rows:
        if row.get("Div") != div:
            continue
        home, away = (row.get("HomeTeam") or "").strip(), (row.get("AwayTeam") or "").strip()
        if not home or not away:
            continue  # HR35 — incomplete record, skipped not guessed
        iso = _parse_date(row.get("Date", ""))
        fx = FixtureOdds(
            league=league,
            home_team=home,       # football-data names ARE the model keys
            away_team=away,
            kickoff_utc=iso or "",
            home=_quote(row, _1X2_COLS["home"], now),
            draw=_quote(row, _1X2_COLS["draw"], now),
            away=_quote(row, _1X2_COLS["away"], now),
            over25=_quote(row, _OU_COLS["over25"], now),
            under25=_quote(row, _OU_COLS["under25"], now),
            source=SOURCE,
            source_tier="T1",
        )
        if not fx.over25.available:
            fx.notes.append("Over/Under 2.5 not quoted — NO DATA — PENDING")
        out.append(fx)

    flags.append(f"{league}: {len(out)} fixture(s) priced from football-data fixtures.csv")
    return out, flags
