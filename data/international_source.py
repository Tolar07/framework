"""
International (national-team) match history — for UEFA Nations League.

WHY
  football-data.co.uk is clubs only, so the framework could not rate a single
  national-team fixture. This reads the open, keyless international results
  dataset (github.com/martj42/international_results — every men's international
  since 1872, community-maintained) and returns it as MatchResult rows, so the
  SAME Dixon-Coles + Elo engines fit national teams exactly as they fit clubs,
  and the SAME grader settles logged legs against it.

WHAT IS IN THE FIT (and why)
  * UEFA teams only — a team is "UEFA" if it has played in a UEFA Nations League
    or UEFA Euro qualification match since 2018. Matches are kept only when BOTH
    sides are UEFA, so the rating graph is one connected European pool (every
    Nations League fixture is UEFA v UEFA).
  * Since HISTORY_SINCE (rolling ~4-5 years): recent enough to reflect current
    squads, long enough for ~40+ matches per team.
  * NEUTRAL-VENUE matches EXCLUDED. The goals model has a single home-advantage
    term; a neutral tournament game fed in as "home" would mis-attribute an
    advantage that didn't exist. Nations League fixtures are played at home
    venues, so home advantage is estimated from real home games only.

HONEST LIMITS (HR35)
  * No odds in this dataset -> a Nations League leg can be SETTLED (result) but
    its CLV stays NO DATA — it never counts toward the Phase 3 CLV gate.
  * The dataset is updated by volunteers; the newest results can lag days/weeks.
    The latest match date is surfaced as a flag, never hidden.
"""
from __future__ import annotations

import csv
import io
import time
import urllib.request
from pathlib import Path
from typing import Optional

from data.football_data_source import MatchResult

RESULTS_URL = ("https://raw.githubusercontent.com/martj42/"
               "international_results/master/results.csv")
HISTORY_SINCE = "2022-01-01"
UEFA_MARKER_SINCE = "2018-01-01"
UEFA_MARKER_TOURNAMENTS = {"UEFA Nations League", "UEFA Euro qualification"}
CACHE_MAX_AGE_SECONDS = 12 * 60 * 60

# Framework league name(s) served by this source.
INTERNATIONAL_LEAGUES = {"UEFA Nations League"}

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def _fetch_csv(cache_dir: Path) -> tuple[str, list[str]]:
    """The raw CSV text, from a <=12h cache or live. Falls back to a stale cache
    if the live fetch fails (flagged), rather than dropping the league."""
    flags: list[str] = []
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache = cache_dir / "international_results.csv"
    if cache.exists() and time.time() - cache.stat().st_mtime <= CACHE_MAX_AGE_SECONDS:
        return cache.read_text(encoding="utf-8"), flags
    try:
        req = urllib.request.Request(RESULTS_URL, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=60) as r:
            text = r.read().decode("utf-8", "replace")
        cache.write_text(text, encoding="utf-8")
        return text, flags
    except Exception as e:  # noqa: BLE001 — degrade to stale cache, flagged
        if cache.exists():
            flags.append(f"international results: live fetch failed ({e}) — "
                         f"using the cached copy")
            return cache.read_text(encoding="utf-8"), flags
        raise


def load_results(league: str, cache_dir: Optional[str | Path] = None
                 ) -> tuple[list[MatchResult], list[dict], list[str]]:
    """(results, skipped_rows, flags) for a national-team competition."""
    if league not in INTERNATIONAL_LEAGUES:
        raise ValueError(f"'{league}' is not an international league")
    cache_dir = Path(cache_dir) if cache_dir else Path(__file__).parent / "cache"
    text, flags = _fetch_csv(cache_dir)
    rows = list(csv.DictReader(io.StringIO(text)))

    uefa = set()
    for r in rows:
        if (r.get("tournament") in UEFA_MARKER_TOURNAMENTS
                and r.get("date", "") >= UEFA_MARKER_SINCE):
            uefa.add(r["home_team"])
            uefa.add(r["away_team"])

    results: list[MatchResult] = []
    skipped: list[dict] = []
    latest = ""
    for r in rows:
        d = r.get("date", "")
        if d < HISTORY_SINCE:
            continue
        if r["home_team"] not in uefa or r["away_team"] not in uefa:
            continue
        if (r.get("neutral") or "").strip().upper() == "TRUE":
            continue
        try:
            hg, ag = int(r["home_score"]), int(r["away_score"])
        except (TypeError, ValueError):
            skipped.append(r)  # unplayed / NA score — never guessed
            continue
        latest = max(latest, d)
        results.append(MatchResult(
            league=league, date=d, home_team=r["home_team"],
            away_team=r["away_team"], fthg=hg, ftag=ag,
            ftr="H" if hg > ag else ("A" if ag > hg else "D")))

    flags.append(f"{league}: national-team history via martj42/international_results "
                 f"— {len(results)} UEFA home-venue matches since {HISTORY_SINCE}, "
                 f"{len(uefa)} UEFA teams, latest result {latest or 'none'}; no odds "
                 f"in this source, so legs settle but CLV stays NO DATA")
    return results, skipped, flags
