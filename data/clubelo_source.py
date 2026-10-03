"""
ClubElo current-season strength ratings (keyless, free) — the STRETCH fallback.

ClubElo (http://api.clubelo.com) publishes a single daily all-clubs CSV of
European club Elo ratings, updated from real match results. It is the only
key-free source that covers the continental qualifiers with zero fitted
history (Celje, Ararat-Armenia, Larne, Sabah, Apollon, CSKA 1948, Slovan,
Dinamo, Sparta, Olympiakos, Bodo/Glimt, ...). Verified live 2026-08-12: the
2026-08-11 snapshot has 594 clubs.

VERIFIED LIMITATION — newly-added clubs get a PROVISIONAL PLACEHOLDER, not a
rating: ClubElo parks clubs with no recent match data on a shared league/default
value (Beveren/Lommel/Kortrijk all = 1350.29, Cambuur/Den Haag/Willem II =
1317.29, Lyngby/Horsens = 1347.07, the whole Ukrainian league = 1241.8). Those
are dropped by ratings() (HR35 — a fabricated strength is worse than NO DATA),
so the promoted clubs (Cambuur, Beveren, Lommel, Horsens) and anything with no
real match history stay NO DATA until they accrue matches or the paid
api-football current-season fit covers them.

This is deliberately a STRETCH rating source. The fitted DC pool (or the paid
api-football current-season fit) is the PRIMARY rating; ClubElo only backfills
fixtures whose teams the primary fit cannot rate — the paid plan structurally
cannot rate a club with zero current-season matches, ClubElo can. A team absent
from the snapshot returns None (HR35), never a guessed strength.

Consumed by orchestrator.py: when `probs is None` after the carry-over
fallback, a 1X2 FixtureProbabilities is built from the ClubElo Elo gap via the
engine/elo probabilities math, and the board stamps rating_source="clubelo" so
a stretch rating is never mistaken for a fitted one (Architect 2026-08-12:
bookable + labeled).
"""
from __future__ import annotations

import csv
import io
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from data.retry import get

CACHE_DIR = Path(__file__).parent.parent / "data" / "cache" / "clubelo"
# A daily snapshot is cheap to refetch and the steward warms it each pass, so a
# 24h window matches the SportyBet loader: today's ratings stay readable all
# day without hammering the endpoint.
SNAPSHOT_MAX_AGE_HOURS = 24
BASE_URL = "http://api.clubelo.com"

try:
    import requests
except ImportError:
    requests = None  # type: ignore[assignment]

# ClubElo spellings that differ from the OLP model keys after normalization
# (see _normalize below). Every entry was VERIFIED against the live snapshot on
# 2026-08-12 — a guess would attach one club's strength to another (HR35), so
# only confirmed spellings belong here. Keys are the football-data model keys.
CLUBELO_ALIASES: dict[str, str] = {
    # Only entries where the model key's normalized form does NOT match the
    # ClubElo name directly (verified against the 2026-08-11 snapshot). Targets
    # are the RAW ClubElo spellings.
    "Bodo/Glimt": "Bodoe Glimt",
    "Bodoe/Glimt": "Bodoe Glimt",           # legacy alias
    "FC CSKA 1948": "CSKA 1948 Sofia",
    "Apollon Limassol": "Apollon Lemesos",
    "Sabah Baku": "Sabah",
    "Ararat-Armenia": "Ararat",
    "Olympiakos Piraeus": "Olympiakos",
    "AZ Alkmaar": "Alkmaar",
    "AGF Aarhus": "Aarhus",
}


def _normalize(name: str) -> str:
    """Lowercase, strip diacritics + common club prefixes/suffixes, drop
    punctuation. The ClubElo spelling differs from model keys in exactly these
    ways ("Bodo/Glimt" vs "Bodoe Glimt", "FK Crvena Zvezda" vs "Crvena
    Zvezda"). A local normalizer (not team_map's) keeps this module
    self-contained — each name layer owns its own spelling rules."""
    name = name.lower().strip()
    for prefix in ("fc ", "sc ", "ac ", "cd ", "cf ", "rk ", "ss ", "sk ", "fk "):
        if name.startswith(prefix):
            name = name[len(prefix):]
    for suffix in (" fc", " sc", " ac", " cf", " if", " bk", " fk", " sk"):
        if name.endswith(suffix):
            name = name[:-len(suffix)]
    replacements = {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u",
                    "ä": "a", "ö": "o", "ü": "u", "ñ": "n", "ø": "o",
                    "æ": "ae", "ß": "ss", "ç": "c"}
    for old, new in replacements.items():
        name = name.replace(old, new)
    for ch in "()/.'-":
        name = name.replace(ch, " ")
    return " ".join(name.split())


def _cache_path(day: str) -> Path:
    return CACHE_DIR / f"{day}.json"


def _read_cache(day: str) -> Optional[dict]:
    path = _cache_path(day)
    try:
        mtime = path.stat().st_mtime
        from time import time
        if time() - mtime > SNAPSHOT_MAX_AGE_HOURS * 3600:
            return None  # stale REJECTED (same policy as thesportsdb fixtures)
    except OSError:
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _write_cache(day: str, payload: dict) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path = _cache_path(day)
        path.write_text(json.dumps(payload), encoding="utf-8")
        # latest.json lets a consumer read "the freshest snapshot" without
        # knowing today's date.
        (CACHE_DIR / "latest.json").write_text(json.dumps(payload), encoding="utf-8")
    except OSError:
        pass  # a cache write failure must never fail the fetch


def fetch_snapshot(day: str | None = None) -> dict:
    """Fetch the ClubElo all-clubs CSV for `day` (default today) and return
    {"date": iso, "clubs": [{club, country, level, elo}...]}.

    Best-effort (HR35): on any failure returns the cached snapshot if present,
    else an empty dict — a caller reports NO DATA rather than guessing.
    """
    day = day or date.today().isoformat()
    cached = _read_cache(day)
    if cached is not None:
        return cached
    if requests is None:
        raise RuntimeError("clubelo_source: the 'requests' library is required")
    url = f"{BASE_URL}/{day}"
    try:
        resp = get(url, timeout=30)
        text = resp.text
        rows = list(csv.DictReader(io.StringIO(text)))
        payload = {
            "date": day,
            "clubs": [
                {
                    "club": r.get("Club", "").strip(),
                    "country": r.get("Country", "").strip(),
                    "level": r.get("Level", "").strip(),
                    "elo": float(r["Elo"]) if r.get("Elo", "").strip() else None,
                }
                for r in rows
                if r.get("Club")
            ],
        }
        _write_cache(day, payload)
        return payload
    except Exception:
        # Transient network/parse failure: serve the cache we already have for
        # another recent day if any, else honest empty (NO DATA).
        try:
            for f in sorted(CACHE_DIR.glob("*.json")):
                if f.name == "latest.json":
                    continue
                data = json.loads(f.read_text(encoding="utf-8"))
                if data.get("clubs"):
                    return data
        except (OSError, json.JSONDecodeError):
            pass
        return {"date": day, "clubs": []}


def ratings() -> dict[str, float]:
    """Normalized ClubElo name -> Elo from the freshest cached snapshot.

    PROVISIONAL-PLACEHOLDER DROP (verified live 2026-08-12): ClubElo assigns
    one identical Elo value to a cluster of unrelated clubs when it has no real
    match data for them — e.g. Beveren/Lommel/Kortrijk all = 1350.29, Cambuur/
    Den Haag/Willem II = 1317.29, Lyngby/Horsens = 1347.07, the whole Ukrainian
    league = 1241.8. Those are NOT ratings; a club with no recent matches is
    parked on a league/default value. Using one would be fabricating a strength
    (HR35). So any Elo value shared by two or more clubs is dropped entirely;
    only a club-unique value is a real rating. This is exactly why the promoted
    clubs (Cambuur, Beveren, Lommel, Horsens) stay NO DATA via ClubElo until
    they accrue real matches — while the continental qualifiers with genuine
    match history (Celje, Ararat-Armenia, Kauno Zalgiris, Larne, Sabah, ...)
    resolve to real ratings.
    """
    out: dict[str, float] = {}
    for day_file in reversed(sorted(CACHE_DIR.glob("*.json"))):
        if day_file.name == "latest.json":
            continue
        try:
            data = json.loads(day_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        clubs = data.get("clubs", [])
        # Value -> number of clubs carrying it. A value seen for 2+ clubs is a
        # placeholder cluster (see above), not a rating.
        from collections import Counter
        value_counts = Counter(c.get("elo") for c in clubs)
        for c in clubs:
            elo = c.get("elo")
            if elo is not None and value_counts.get(elo) == 1:
                out.setdefault(_normalize(c.get("club", "")), elo)
        if out:
            break
    return out


def elo_for(team_name: str) -> Optional[float]:
    """Resolve an OLP model key (or any team name) to a ClubElo Elo.

    Exact normalized match first, then the verified CLUBELO_ALIASES table.
    Returns None for a team with no ClubElo entry (HR35) — never a guessed
    strength.
    """
    if not team_name:
        return None
    table = ratings()
    if not table:
        return None
    target = _normalize(team_name)
    if target in table:
        return table[target]
    alias = CLUBELO_ALIASES.get(team_name) or CLUBELO_ALIASES.get(
        _normalize(team_name))
    if alias:
        return table.get(_normalize(alias))
    return None
