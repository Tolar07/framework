"""
FIXTURE FEATURE STORE (autonomy plan item 5, 2026-10-20).

capture_news(now)  — called every pre-kickoff round (monitor/news_loop.py):
    for every fixture the board RATED today (not only the picks), FotMob's
    team news — injuries/suspensions and the lineup, predicted then confirmed —
    once when it first comes inside NEWS_FIRST_H of kick-off and again inside
    NEWS_CONFIRM_MIN until the lineup is confirmed. Saved to
    data/features/news_<date>.json, one snapshot per fixture (the latest).

build_day(day)     — called by the universe sweep (monitor/universe_sweep.py):
    data/features/features_<date>.json — engine/features.build for every rated
    fixture: xG form, team news, the closing prices (Matchbook sharp +
    SportyBet) from the graded universe archive, the Betfair Exchange close
    from football-data.co.uk (main leagues, published days later), the result.

Strict matching only (data/fotmob.find_match — both names, unambiguous).
Missing data reads PENDING (HR35). Nothing here selects or stakes.
"""
from __future__ import annotations

import json
import time
from collections.abc import Callable
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FEAT_DIR = ROOT / "data" / "features"
LEDGER_DIR = ROOT / "output" / "picks"
NEWS_FIRST_H = 6          # first snapshot (injuries, predicted XI) inside 6 h of kick-off
NEWS_CONFIRM_MIN = 90     # re-read until confirmed inside 90 min (FotMob confirms ~60 min before)


def _key(home: str, away: str) -> str:
    return f"{home} v {away}"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _save(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=1, sort_keys=True), encoding="utf-8")


def rated(day: str, ledger_dir: Path = LEDGER_DIR) -> list[dict]:
    p = ledger_dir / f"picks_{day}.json"
    if not p.exists():
        return []
    return [r for r in json.loads(p.read_text(encoding="utf-8")).get("rated", [])
            if r.get("home") and r.get("away")]


def _when(s: str) -> datetime | None:
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return None


def snapshot(news: dict, now: datetime) -> dict:
    """The compact record of data/fotmob.team_news kept per fixture."""
    absent = []
    for side in ("home", "away"):
        for m in (news.get(side) or {}).get("missing", [])[:3]:
            absent.append({"side": side, "name": m.get("name"), "type": m.get("type")})
    return {"at": now.strftime("%Y-%m-%dT%H:%MZ"), "lineup_type": news.get("lineup_type"),
            "home_missing_share": (news.get("home") or {}).get("missing_share"),
            "away_missing_share": (news.get("away") or {}).get("missing_share"),
            "home_unavailable": len((news.get("home") or {}).get("missing", [])),
            "away_unavailable": len((news.get("away") or {}).get("missing", [])),
            "absent": absent}


def due(snap: dict | None, ko: datetime, now: datetime) -> bool:
    mins = (ko - now).total_seconds() / 60
    if mins <= 0 or mins > NEWS_FIRST_H * 60:
        return False
    if snap is None:
        return True
    return snap.get("lineup_type") != "confirmed" and mins <= NEWS_CONFIRM_MIN


def capture_news(now: datetime, day: str | None = None, fm=None, folder: Path = FEAT_DIR,
                 ledger_dir: Path = LEDGER_DIR, pause: float = 0.3) -> str:
    """One round of team-news capture for the day's rated fixtures."""
    if fm is None:
        from data import fotmob as fm
    day = day or now.date().isoformat()
    fixtures = rated(day, ledger_dir)
    if not fixtures:
        return "team news: no rated fixtures today"
    path = folder / f"news_{day}.json"
    store = _load(path)
    lists: dict[str, list] = {}
    got = unmatched = failed = 0
    for fx in fixtures:
        k = _key(fx["home"], fx["away"])
        m = None
        for off in (0, -1, 1):                         # FotMob's day list is local-time
            d = (date.fromisoformat(day) + timedelta(days=off)).isoformat()
            if d not in lists:
                try:
                    lists[d] = fm.matches_on(d)
                except Exception:  # noqa: BLE001 — FotMob down: next round retries
                    lists[d] = []
            m = fm.find_match(lists[d], fx["home"], fx["away"])
            if m is not None:
                break
        if m is None:
            unmatched += 1
            continue
        ko = _when(m.get("kickoff_utc") or "")
        if ko is None or not due(store.get(k), ko, now):
            continue
        try:
            news = fm.team_news(m["id"])
        except Exception:  # noqa: BLE001 — counted; next round retries
            failed += 1
            continue
        if news is None:
            continue
        snap = snapshot(news, now)
        snap.update({"fotmob_id": m["id"], "kickoff_utc": m.get("kickoff_utc")})
        store[k] = snap
        got += 1
        time.sleep(pause)
    if got:
        _save(path, store)
    return (f"team news: {got} captured, {len(store)} of {len(fixtures)} rated fixtures held"
            + (f", {unmatched} not on FotMob" if unmatched else "")
            + (f", {failed} unavailable" if failed else ""))


def universe_index(rows: list[dict]) -> dict[str, list[dict]]:
    """Graded universe football rows by kick-off date, as find_match wants them."""
    idx: dict[str, list[dict]] = {}
    for r in rows:
        # rated fixtures are in covered leagues only: a smaller, safer pool
        if r.get("sport") == "football" and r.get("ko") and r.get("covered"):
            idx.setdefault(r["ko"][:10], []).append(r)
    return idx


def find_universe(fx: dict, day: str, idx: dict[str, list[dict]],
                  find: Callable | None = None) -> dict | None:
    if find is None:
        from data.fotmob import find_match
        find = find_match
    cands = []
    for off in (0, -1, 1):
        cands += idx.get((date.fromisoformat(day) + timedelta(days=off)).isoformat(), [])
    return find(cands, fx["home"], fx["away"]) if cands else None


def season_of(day: str) -> str:
    """football-data's season code: '2627' for 2026/27 (from August)."""
    y, m = int(day[:4]), int(day[5:7])
    a = y if m >= 7 else y - 1
    return f"{a % 100:02d}{(a + 1) % 100:02d}"


def betfair_index(leagues: set[str], season: str, fetch: Callable | None = None) -> dict[tuple, dict]:
    """(date, home, away) -> football-data row with the Betfair Exchange close,
    for the main leagues football-data publishes it in (its extra-league files
    carry no exchange prices). A league that fails to fetch is just absent."""
    import csv
    import io

    from data import football_data_source as fds
    if fetch is None:
        fetch = fds.fetch_csv_text
    out: dict[tuple, dict] = {}
    for lg in sorted(leagues):
        if not fds.LEAGUE_CODES.get(lg) or lg in fds.EXTRA_CODES:
            continue
        try:
            text = fetch(lg, season)
        except Exception:  # noqa: BLE001,S112 — absent league = PENDING closes
            continue
        for raw in csv.DictReader(io.StringIO(text)):
            row = fds._clean_row(raw)
            if not row.get("BFECH"):
                continue
            try:
                out[(fds._parse_date(row["Date"]), row["HomeTeam"].strip(), row["AwayTeam"].strip())] = row
            except (KeyError, ValueError, AttributeError):
                continue
    return out


def find_betfair(fx: dict, day: str, bidx: dict[tuple, dict]) -> dict | None:
    """Exact names — the rated ledger spells teams as football-data does (the model's history)."""
    for off in (0, -1, 1):
        d = (date.fromisoformat(day) + timedelta(days=off)).isoformat()
        r = bidx.get((d, fx["home"], fx["away"]))
        if r is not None:
            return r
    return None


def build_day(day: str, stats_rows: list[dict], uidx: dict[str, list[dict]],
              folder: Path = FEAT_DIR, ledger_dir: Path = LEDGER_DIR,
              bidx: dict[tuple, dict] | None = None) -> int:
    from engine import features
    fixtures = rated(day, ledger_dir)
    if not fixtures:
        return 0
    news = _load(folder / f"news_{day}.json")
    out = {}
    for fx in fixtures:
        k = _key(fx["home"], fx["away"])
        out[k] = features.build(fx, day, stats_rows, news.get(k), find_universe(fx, day, uidx),
                                find_betfair(fx, day, bidx or {}))
    _save(folder / f"features_{day}.json", out)
    return len(out)


def build_recent(days: int = 10, today: date | None = None, folder: Path = FEAT_DIR,
                 ledger_dir: Path = LEDGER_DIR) -> str:
    """Rebuild the feature files of the last `days` days and today."""
    import importlib
    match_stats = importlib.import_module("data.match_stats")   # a module beside its data folder
    from engine import universe as uv
    today = today or date.today()
    stats_rows = match_stats.load()
    uidx = universe_index(uv.load_graded())
    span = [(today - timedelta(days=b)).isoformat() for b in range(days + 1)]
    leagues = {fx.get("league") or "" for d in span for fx in rated(d, ledger_dir)}
    bidx: dict[tuple, dict] = {}
    for season in sorted({season_of(d) for d in span}):
        bidx.update(betfair_index(leagues, season))
    n = sum(build_day(d, stats_rows, uidx, folder, ledger_dir, bidx) for d in span)
    return f"features: {n} rated fixtures written"
