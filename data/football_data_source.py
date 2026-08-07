"""
Football-Data.co.uk source module.
ID404 tier: T1 (structured/official).
Provides historical results + closing odds for Dixon-Coles fitting and CLV backtest.

HR35: if a fetch fails or a fixture is malformed, it is dropped and logged to
`skipped`, never silently interpolated or guessed.

Live network access: this module uses `requests` and needs outbound internet.
It will NOT work in a sandboxed environment with no egress (test it locally,
in Claude Code, or on a scheduled runner).
"""
from __future__ import annotations
import csv
import io
import json
import time
from dataclasses import dataclass, asdict, field
from datetime import date, datetime
from pathlib import Path
from typing import Optional

try:
    import requests
except ImportError:
    requests = None

BASE_URL = "https://www.football-data.co.uk/mmz4281/{season}/{code}.csv"

# The daily run settles paper legs against the LIVE season's results (HR46
# closing lines come from the same file). football-data.co.uk adds new results
# to the current-season file every morning, so a stale cache means a played
# match never settles and its CLV never reaches the Phase 3 gate — the bug this
# TTL fixes. Completed-season files never change, so they keep a long TTL and
# the run stays fast (the brain's content_hash reuse still holds).
LIVE_SEASON_MAX_AGE_SECONDS = 6 * 3600        # refresh every run
COMPLETED_SEASON_MAX_AGE_SECONDS = 30 * 24 * 3600

# ID401 whitelist -> football-data.co.uk league codes.
# Verified against football-data.co.uk's actual country/code list — codes below
# are real, not guessed. Three whitelisted leagues have NO mapping here because
# this source simply doesn't carry them (continental competitions aren't
# covered at all; Croatia isn't in their country list) — HR35: better to raise
# a clear "not available from this source" than invent a plausible-looking code.
LEAGUE_CODES = {
    # GREEN — tool-fed, structured
    "Premier League": "E0",
    "La Liga": "SP1",
    "Serie A": "I1",
    "Bundesliga": "D1",
    "Ligue 1": "F1",
    "Champions League": None,   # NOT COVERED — football-data.co.uk has no continental competitions
    "Europa League": None,      # NOT COVERED — same reason
    # AMBER — FootyStats + F2 verified
    "Scottish Premiership": "SC0",
    "Belgian Pro League": "B1",
    "Eredivisie": "N1",
    "Championship": "E1",
    "Primeira Liga": "P1",
    "Danish Superliga": None,   # 'Extra' league, different endpoint (see EXTRA_URL)
    "Ekstraklasa": None,        # 'Extra' league, different endpoint
    "HNL": None,                # NOT COVERED — Croatia isn't in football-data.co.uk's country list
}

UNCOVERED_LEAGUES = {"Champions League", "Europa League", "HNL"}

# Second-division feeds for the PREVIOUS completed season, used to give
# promoted clubs a rating they otherwise lack (Architect 2026-08-07). The
# mechanism is wired and tested; the DATA is what's blocked:
#   - football-data publishes NONE of the needed second divisions: D2 is the
#     GERMAN 2. Bundesliga (verified 2026-08-07 — must never be fed to a
#     Danish fit), N2 (Eerste Divisie) and B2 (Challenger Pro League) are dead
#     links, and the DNK Extra file is the Danish Superliga only.
#   - TheSportsDB has the leagues but the free test key truncates league
#     discovery to 5 (the framework's own comment: a personal key resolves
#     these), and API-Football's free tier stops before the 2425 season.
# So no code is mapped yet: promoted clubs stay honest NO DATA until a source
# is reachable (a personal TheSportsDB key is the documented path). Adding one
# league here + its ID in thesportsdb_fixtures.LEAGUE_IDS wires it.
SECOND_DIVISION_CODES: dict[str, str] = {}

EXTRA_URL = "https://www.football-data.co.uk/new/{code}.csv"
EXTRA_CODES = {
    "Danish Superliga": "DNK",
    "Ekstraklasa": "POL",
}

# The 'Extra' endpoint uses a DIFFERENT schema from the main per-season CSVs,
# and bundles every season into one file. Mapping the core fields here (rather
# than assuming one schema) is what stops Denmark/Poland silently parsing to
# zero rows. Closing-odds column names (PSCH/PSCD/PSCA, AvgCH/AvgCD/AvgCA) are
# identical across both schemas, so only these five differ.
STANDARD_COLUMNS = {"home": "HomeTeam", "away": "AwayTeam",
                    "hg": "FTHG", "ag": "FTAG", "res": "FTR"}
EXTRA_COLUMNS = {"home": "Home", "away": "Away",
                 "hg": "HG", "ag": "AG", "res": "Res"}


def _season_to_extra_label(season: str) -> str:
    """'2526' -> '2025/2026', the value in the Extra CSVs' own Season column.
    Raises on a malformed code rather than guessing a season."""
    if len(season) != 4 or not season.isdigit():
        raise ValueError(f"Season code must be 4 digits like '2526', got {season!r}")
    return f"20{season[:2]}/20{season[2:]}"


def _clean_row(row: dict) -> dict:
    """Strip the UTF-8 BOM off the first header and trim stray whitespace.
    The Extra files carry both ('\\ufeffCountry', 'Superliga ' with a trailing
    space), which would otherwise break exact-match lookups."""
    cleaned = {}
    for k, v in row.items():
        if k is None:
            continue
        key = k.lstrip("﻿").strip()
        cleaned[key] = v.strip() if isinstance(v, str) else v
    return cleaned


# --- Opening + closing price capture (for the CLV backtest) ------------------
#
# The standard per-season CSVs carry BOTH an opening and a closing price for
# 1X2 and Over/Under 2.5. The Extra schema (Denmark, Poland) carries CLOSING
# ONLY — every one of its odds columns has a 'C' in the name — so entry-vs-close
# is undefined there and those leagues cannot be CLV-backtested from this
# source at all. That is recorded in MatchOdds.notes rather than papered over.
#
# No Over/Under 1.5, Over/Under 3.5, or BTTS prices exist in EITHER schema at
# any point. Those markets are permanently unmeasurable here (HR35: reported,
# not estimated).

BOOK_PREFERENCE_1X2 = [
    ("market_avg", {"home": ("AvgH", "AvgCH"), "draw": ("AvgD", "AvgCD"), "away": ("AvgA", "AvgCA")}),
    ("pinnacle",   {"home": ("PSH", "PSCH"),   "draw": ("PSD", "PSCD"),   "away": ("PSA", "PSCA")}),
    ("b365",       {"home": ("B365H", "B365CH"), "draw": ("B365D", "B365CD"), "away": ("B365A", "B365CA")}),
]

BOOK_PREFERENCE_OU25 = [
    ("market_avg", {"over25": ("Avg>2.5", "AvgC>2.5"), "under25": ("Avg<2.5", "AvgC<2.5")}),
    ("pinnacle",   {"over25": ("P>2.5", "PC>2.5"),     "under25": ("P<2.5", "PC<2.5")}),
    ("b365",       {"over25": ("B365>2.5", "B365C>2.5"), "under25": ("B365<2.5", "B365C<2.5")}),
]

# Deliberately NOT in the preference lists: Max/MaxC. Those are order
# statistics across books, so their open->close movement tracks which book
# happened to be extreme rather than consensus line movement — it would look
# like CLV without being it.
DEFAULT_BOOK_PREFERENCE = ("market_avg", "pinnacle", "b365")


@dataclass
class MarketPrice:
    """One market's opening and closing price, with the provenance attached to
    the price it describes rather than kept in a parallel structure."""
    open: Optional[float] = None
    close: Optional[float] = None
    book: Optional[str] = None
    open_column: Optional[str] = None   # exact CSV column, per ID400
    close_column: Optional[str] = None

    @property
    def complete(self) -> bool:
        return self.open is not None and self.close is not None


@dataclass
class MatchOdds:
    home: MarketPrice
    draw: MarketPrice
    away: MarketPrice
    over25: MarketPrice
    under25: MarketPrice
    schema: str = "standard"          # "standard" | "extra"
    notes: list[str] = field(default_factory=list)


@dataclass
class MatchResult:
    league: str
    date: str  # ISO yyyy-mm-dd
    home_team: str
    away_team: str
    fthg: int  # full-time home goals
    ftag: int  # full-time away goals
    ftr: str   # H/D/A
    # Closing odds (Pinnacle preferred per HR46 CL-ARCHIVE path), may be None.
    # Kept EXACTLY as-is — published contract consumed by existing callers.
    # `odds` below is purely additive and carries the richer open/close pairs.
    closing_home_odds: Optional[float] = None
    closing_draw_odds: Optional[float] = None
    closing_away_odds: Optional[float] = None
    source: str = "football-data.co.uk"
    source_tier: str = "T1"  # ID404
    odds: Optional[MatchOdds] = None
    kickoff_time: Optional[str] = None


def _parse_date(raw: str) -> str:
    """football-data.co.uk uses dd/mm/yy or dd/mm/yyyy — normalise to ISO."""
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f"Unparseable date: {raw!r}")


def _price(row: dict, key: str) -> Optional[float]:
    """One numeric cell, or None. Tests `is None` rather than truthiness so a
    legitimate 0.0 can never silently fall through to a fallback."""
    v = row.get(key)
    if v is None or v == "" or v == "NA":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _resolve_line(row: dict, preferences: list, wanted_books: tuple[str, ...]
                   ) -> dict[str, MarketPrice]:
    """Resolve a whole betting line from ONE book, or not at all.

    A book is accepted only if it supplies EVERY value in the line — both
    sides/outcomes, both open and close. This is the rule that keeps the
    backtest honest: resolving per-outcome (as the old
    `_odds("PSCH") or _odds("AvgCH")` did) can pair a Pinnacle opening price
    with a market-average close, which manufactures CLV out of a book-to-book
    spread that no bettor ever experienced.

    Returns empty MarketPrices (all None) when no single book is complete —
    never a mixed line, never an imputed value.
    """
    outcomes = [k for k in preferences[0][1].keys()]
    for book, columns in preferences:
        if book not in wanted_books:
            continue
        resolved: dict[str, MarketPrice] = {}
        for outcome, (open_col, close_col) in columns.items():
            o, c = _price(row, open_col), _price(row, close_col)
            if o is None or c is None:
                resolved = {}
                break  # this book is incomplete for this line — try the next
            resolved[outcome] = MarketPrice(open=o, close=c, book=book,
                                             open_column=open_col, close_column=close_col)
        if resolved:
            return resolved
    return {k: MarketPrice() for k in outcomes}


def _resolve_closing_only(row: dict, preferences: list, wanted_books: tuple[str, ...]
                           ) -> dict[str, MarketPrice]:
    """Extra-schema variant: closing prices exist, opening prices do not.
    Same all-or-nothing rule applied to the closing side alone."""
    outcomes = [k for k in preferences[0][1].keys()]
    for book, columns in preferences:
        if book not in wanted_books:
            continue
        resolved: dict[str, MarketPrice] = {}
        for outcome, (_open_col, close_col) in columns.items():
            c = _price(row, close_col)
            if c is None:
                resolved = {}
                break
            resolved[outcome] = MarketPrice(open=None, close=c, book=book,
                                             open_column=None, close_column=close_col)
        if resolved:
            return resolved
    return {k: MarketPrice() for k in outcomes}


def build_match_odds(row: dict, is_extra: bool,
                      book_preference: tuple[str, ...] = DEFAULT_BOOK_PREFERENCE) -> MatchOdds:
    """Assemble the open/close price set for one match."""
    notes: list[str] = []
    if is_extra:
        one_x_two = _resolve_closing_only(row, BOOK_PREFERENCE_1X2, book_preference)
        ou = {k: MarketPrice() for k in ("over25", "under25")}
        notes.append("Extra schema: CLOSING prices only — no opening price exists in "
                     "this source, so CLV (entry vs close) cannot be measured for "
                     "this league. NO DATA — PENDING, not estimated.")
        notes.append("Extra schema carries no Over/Under prices at all.")
    else:
        one_x_two = _resolve_line(row, BOOK_PREFERENCE_1X2, book_preference)
        ou = _resolve_line(row, BOOK_PREFERENCE_OU25, book_preference)
        if not one_x_two["home"].complete:
            notes.append("no single book supplied a complete 1X2 open+close line")
        if not ou["over25"].complete:
            notes.append("no single book supplied a complete Over/Under 2.5 open+close line")

    return MatchOdds(
        home=one_x_two["home"], draw=one_x_two["draw"], away=one_x_two["away"],
        over25=ou["over25"], under25=ou["under25"],
        schema="extra" if is_extra else "standard",
        notes=notes,
    )


def fetch_csv_text(league: str, season: str) -> str:
    """season like '2526' for 2025/26. Raises if requests unavailable or fetch fails —
    caller must catch and record NO DATA — PENDING rather than proceed silently."""
    if requests is None:
        raise RuntimeError("requests not installed — cannot fetch live data")

    if league in EXTRA_CODES:
        url = EXTRA_URL.format(code=EXTRA_CODES[league])
    elif league in UNCOVERED_LEAGUES:
        raise ValueError(
            f"'{league}' is not covered by football-data.co.uk — this source "
            f"has no continental competitions and doesn't include Croatia. "
            f"Needs a different T1 source before it can be scanned with real "
            f"historical data (NOT a guess — genuinely unavailable here)."
        )
    elif LEAGUE_CODES.get(league):
        url = BASE_URL.format(season=season, code=LEAGUE_CODES[league])
    else:
        raise ValueError(f"'{league}' is not in LEAGUE_CODES — add it or check spelling.")

    resp = requests.get(url, timeout=20, headers={"User-Agent": "OLP-XDV/1.0"})
    resp.raise_for_status()
    return resp.text


def parse_csv_text(league: str, csv_text: str, season: Optional[str] = None,
                    book_preference: tuple[str, ...] = DEFAULT_BOOK_PREFERENCE
                    ) -> tuple[list[MatchResult], list[dict]]:
    """Returns (results, skipped). `skipped` records rows dropped for missing/malformed
    core fields — HR35: never guess a score or date.

    Handles both football-data.co.uk schemas. For the Extra schema (one file,
    every season) `season` filters to the requested season; rows from OTHER
    seasons are not errors and are not recorded as skipped."""
    results: list[MatchResult] = []
    skipped: list[dict] = []

    reader = csv.DictReader(io.StringIO(csv_text))
    fieldnames = [f.lstrip("﻿").strip() for f in (reader.fieldnames or [])]
    is_extra = "HomeTeam" not in fieldnames and "Home" in fieldnames
    cols = EXTRA_COLUMNS if is_extra else STANDARD_COLUMNS

    season_label = None
    if is_extra and season is not None:
        season_label = _season_to_extra_label(season)

    for i, raw_row in enumerate(reader):
        row = _clean_row(raw_row)
        try:
            # Extra files bundle all seasons — keep only the one asked for.
            # A non-matching season is simply a different row, not a defect.
            if season_label is not None and row.get("Season") != season_label:
                continue

            if not row.get(cols["home"]) or not row.get(cols["away"]):
                skipped.append({"row": i, "reason": "missing team name", "raw": row})
                continue
            if row.get(cols["hg"]) in (None, "") or row.get(cols["ag"]) in (None, ""):
                # Fixture not yet played — not an error, just not a result yet.
                continue

            date_iso = _parse_date(row["Date"])
            _odds = lambda key: _price(row, key)  # noqa: E731 — kept for the legacy fields below
            match_odds = build_match_odds(row, is_extra, book_preference)

            results.append(MatchResult(
                league=league,
                date=date_iso,
                home_team=row[cols["home"]].strip(),
                away_team=row[cols["away"]].strip(),
                fthg=int(row[cols["hg"]]),
                ftag=int(row[cols["ag"]]),
                ftr=row.get(cols["res"], "").strip(),
                # PSCH/PSCD/PSCA = Pinnacle closing odds (preferred per HR46).
                # Falls back to AvgC (market average closing) if Pinnacle absent —
                # NOTE per the master doc, Pinnacle odds have been unreliable since
                # 23/07/2025; treat closing odds as SINGLE-SOURCE not VERIFIED
                # unless cross-checked (ID403).
                closing_home_odds=_odds("PSCH") if _odds("PSCH") is not None else _odds("AvgCH"),
                closing_draw_odds=_odds("PSCD") if _odds("PSCD") is not None else _odds("AvgCD"),
                closing_away_odds=_odds("PSCA") if _odds("PSCA") is not None else _odds("AvgCA"),
                odds=match_odds,
                kickoff_time=row.get("Time") or None,
            ))
        except Exception as e:
            skipped.append({"row": i, "reason": str(e), "raw": row})

    return results, skipped


DEFAULT_CACHE_DIR = Path(__file__).parent / "cache"


def _season_is_live(season: str) -> bool:
    """'2627' spans Aug 2026 - May 2027. A season is LIVE while today sits in
    that window (including the pre-season before it kicks off), because its
    results are still being published. An unparseable code counts as live so we
    always refresh rather than settle a leg against a stale snapshot."""
    try:
        start_year = 2000 + int(season[:2])
        end_year = 2000 + int(season[2:])
    except ValueError:
        return True
    today = date.today()
    return date(start_year, 8, 1) <= today <= date(end_year, 7, 31)


def _cache_age_seconds(cache_file: Path) -> float:
    try:
        return time.time() - cache_file.stat().st_mtime
    except OSError:
        return float("inf")


def load_league(league: str, season: str, cache_dir: str | Path = DEFAULT_CACHE_DIR,
                 book_preference: tuple[str, ...] = DEFAULT_BOOK_PREFERENCE
                 ) -> tuple[list[MatchResult], list[dict]]:
    """Fetch (or use cache) + parse. Writes a cache file so repeated runs don't
    hammer the source, and so results survive a sandbox reset.

    FRESHNESS: the LIVE season's file is re-downloaded when the cache is over
    the (6h) TTL — that is what lets the daily run settle played legs and
    capture closing lines (HR46). Completed seasons are stable and keep a
    30-day TTL. If a refresh fails (e.g. football-data removes the file between
    seasons), the STALE cache is kept rather than the data being lost — stale
    beats nothing, and the next successful refresh supersedes it."""
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    # Extra-league files contain EVERY season in one download, so they're cached
    # once per league rather than once per league+season (and the season filter
    # is applied at parse time instead).
    stem = league.replace(" ", "_")
    cache_file = (Path(cache_dir) / f"{stem}_all.csv" if league in EXTRA_CODES
                  else Path(cache_dir) / f"{stem}_{season}.csv")

    max_age = (LIVE_SEASON_MAX_AGE_SECONDS if _season_is_live(season)
               else COMPLETED_SEASON_MAX_AGE_SECONDS)
    csv_text = None
    if cache_file.exists() and _cache_age_seconds(cache_file) <= max_age:
        csv_text = cache_file.read_text(encoding="utf-8")
    if csv_text is None:
        try:
            csv_text = fetch_csv_text(league, season)
            cache_file.write_text(csv_text, encoding="utf-8")
        except Exception:
            if cache_file.exists():
                # Fresh failed; keep the stale snapshot rather than lose data.
                csv_text = cache_file.read_text(encoding="utf-8")
            else:
                raise

    return parse_csv_text(league, csv_text, season=season,
                           book_preference=book_preference)


def load_second_division(league: str, season: str,
                         cache_dir: str | Path = DEFAULT_CACHE_DIR,
                         book_preference: tuple[str, ...] = DEFAULT_BOOK_PREFERENCE
                         ) -> tuple[list[MatchResult], list[dict]]:
    """The league's SECOND-division results for a completed season — the
    promoted-club feed. A club promoted to the top flight has no top-flight
    history in the carry window, but its second-division season is real data
    that rates it (with a level adjustment applied at predict time).

    Returns ([], []) for a league football-data no longer publishes a second
    division for (honest empty — NO DATA rather than a guess). Rows carry the
    TOP-flight league name because they only ever feed a model fit; no leg is
    settled against them."""
    code = SECOND_DIVISION_CODES.get(league)
    if not code:
        return [], []
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    stem = f"{league.replace(' ', '_')}_2nd"
    cache_file = Path(cache_dir) / f"{stem}_{season}.csv"
    # Second-division history is a completed-season feed: stable, 30-day TTL.
    max_age = COMPLETED_SEASON_MAX_AGE_SECONDS
    csv_text = None
    if cache_file.exists() and _cache_age_seconds(cache_file) <= max_age:
        csv_text = cache_file.read_text(encoding="utf-8")
    if csv_text is None:
        url = BASE_URL.format(season=season, code=code)
        try:
            resp = requests.get(url, timeout=20,
                                headers={"User-Agent": "OLP-XDV/1.0"})
            resp.raise_for_status()
            csv_text = resp.text
            cache_file.write_text(csv_text, encoding="utf-8")
        except Exception:
            if cache_file.exists():
                # Fresh failed; keep the stale snapshot rather than lose data.
                csv_text = cache_file.read_text(encoding="utf-8")
            else:
                return [], []
    return parse_csv_text(league, csv_text, season=season,
                          book_preference=book_preference)


def save_results_json(results: list[MatchResult], path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump([asdict(r) for r in results], f, indent=2)
