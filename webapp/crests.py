"""Club crest lookup for the dashboards — TheSportsDB badges, hotlinked.

The Architect approved hotlinking TheSportsDB badge URLs (the same way league
flags are hotlinked from flagcdn.com): `render._crest_html` emits
`<img src="https://r2.thesportsdb.com/...">` for clubs TheSportsDB knows, and
a labelled initials placeholder for the rest — never a fake crest.

Network discipline:
- `badge_url(team)` is CACHE-READ ONLY. Rendering must stay deterministic and
  offline-safe (the test suites render without the network).
- `prefetch(teams)` is the ONLY place that calls TheSportsDB. It fetches just
  the teams missing from the cache, respects the free key's rate limit with a
  small delay between calls, and is best-effort (never raises). It is invoked
  by `webapp/export.py` (so the static site carries real crests) and by the
  daily run (env-guarded `OLP_PREFETCH_CRESTS=0` disables it, keeping test
  suites offline).

The cache file (`webapp/crests_cache.json`) is gitignored runtime state —
teams are stable, so after one prefetch the cache absorbs the whole whitelist
and later runs make zero requests.
"""
from __future__ import annotations

import argparse
import json
import re
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

_THESPORTSDB = "https://www.thesportsdb.com/api/v1/json/3/searchteams.php"
_DELAY_SECONDS = 0.3  # free-key rate limit courtesy
_TIMEOUT_SECONDS = 8

CRESTS_CACHE = Path(__file__).parent / "crests_cache.json"


def _normalize(name: str) -> str:
    """Team name -> lowercase, accent-stripped key for cache + matching."""
    name = unicodedata.normalize("NFKD", name or "")
    name = "".join(c for c in name if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()


def _load_cache() -> dict:
    try:
        return json.loads(CRESTS_CACHE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_cache(cache: dict) -> None:
    """Write atomically (temp + rename) so an interrupted prefetch never
    corrupts the cache."""
    CRESTS_CACHE.parent.mkdir(parents=True, exist_ok=True)
    tmp = CRESTS_CACHE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(cache, indent=1, ensure_ascii=False), encoding="utf-8")
    tmp.replace(CRESTS_CACHE)


def badge_url(team: str) -> str | None:
    """Cached badge URL for a team, or None. NEVER hits the network."""
    return _load_cache().get(_normalize(team))


def missing(teams: list[str]) -> list[str]:
    """Teams that have no cached badge URL — the honest 'no crest' list."""
    cache = _load_cache()
    return sorted({t for t in teams if not cache.get(_normalize(t))})


def _fetch_badge(team: str) -> str | None:
    """One TheSportsDB lookup for a team; None if no badge is returned."""
    q = urllib.parse.urlencode({"t": team})
    req = urllib.request.Request(
        f"{_THESPORTSDB}?{q}",
        headers={"User-Agent": "olp-xdv/1.0 (dashboard crest prefetch)"},
    )
    with urllib.request.urlopen(req, timeout=_TIMEOUT_SECONDS) as r:
        data = json.loads(r.read().decode("utf-8"))
    teams = data.get("teams") or []
    if not teams:
        return None
    want = _normalize(team)
    # Prefer an exact normalized name match over the first result, so a
    # search for "Ajax" doesn't pick up "Ajax Cape Town".
    for cand in teams:
        cand_name = _normalize(cand.get("strTeam") or cand.get("strAlternate") or "")
        if cand_name == want:
            badge = cand.get("strBadge")
            if badge:
                return badge
    for cand in teams:
        badge = cand.get("strBadge")
        if badge:
            return badge
    return None


def prefetch(teams: list[str]) -> dict:
    """Fetch badge URLs for uncached teams. Best-effort: a failed lookup is a
    miss (the team keeps its initials placeholder), never a raise.

    Returns the new {normalized_team: url} entries written to the cache."""
    teams = [t for t in dict.fromkeys(teams) if t and t.strip()]
    if not teams:
        return {}
    cache = _load_cache()
    new_entries: dict = {}
    for team in teams:
        key = _normalize(team)
        if not key or key in cache:
            continue
        try:
            url = _fetch_badge(team)
        except Exception:
            url = None
        if url:
            cache[key] = url
            new_entries[key] = url
        time.sleep(_DELAY_SECONDS)
    if new_entries:
        _save_cache(cache)
    return new_entries


def teams_from_board(board_json_path: str) -> list[str]:
    """Collect every team name from a board JSON file (for --prefetch)."""
    payload = json.loads(Path(board_json_path).read_text(encoding="utf-8"))
    teams: list[str] = []
    for bf in payload.get("board", []):
        fixture = bf.get("fixture", "")
        parts = fixture.split(" v ", 1)
        if len(parts) == 2:
            home = parts[0].split(" (")[0]
            away = parts[1].split(" (")[0]
            teams.extend([home, away])
    return teams


def _main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="OLP XDV club crest prefetch")
    ap.add_argument("--prefetch", metavar="board.json", type=str,
                    help="prefetch badges for every team on a board JSON")
    ap.add_argument("--report", action="store_true",
                    help="print which teams still lack a badge after prefetch")
    args = ap.parse_args(argv)
    if args.prefetch:
        teams = teams_from_board(args.prefetch)
        got = prefetch(teams)
        print(f"prefetched {len(got)} badge(s) for {len(teams)} team(s)")
        if args.report:
            still = missing(teams)
            print(f"still missing ({len(still)}): " +
                  (", ".join(still) if still else "none"))
    else:
        ap.print_help()


if __name__ == "__main__":
    _main()
