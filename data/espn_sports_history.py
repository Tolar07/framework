"""
ESPN SPORTS HISTORY - every game of the big ESPN-covered competitions outside football, with the score by period
and the pre-game bookmaker prices ESPN keeps for it.

The Architect, 2026-11-12: "It should cover the entire betting market for all sports."

Per league, one scoreboard request per date (site.api.espn.com/apis/site/v2/sports/<sport>/<league>/scoreboard?
dates=YYYYMMDD) for the finished games and their period scores, then one odds request per game
(sports.core.api.espn.com/v2/sports/<sport>/leagues/<league>/events/<id>/competitions/<id>/odds): the pre-game
total with its over / under prices, the home spread with its prices, and both moneylines, taken as the median over
the pre-game bookmakers ESPN lists (live-odds lines left out). A game with no pre-game price keeps "prices": null
(HR35: never a made-up line).

One line per finished game in data/sports_history/<league>/<yyyy-mm>.jsonl:
  {"sport", "league", "id", "date", "season", "hid", "aid", "home", "away", "ft": [h, a],
   "periods": [[h, a], ...] (quarters / halves / periods / innings as ESPN lists them, overtime included),
   "regulation": n periods in regulation, "prices": {"total", "over", "under", "spread", "sp_home", "sp_away",
   "ml_home", "ml_away"} | null}   (decimal prices; spread = the home side's line, e.g. -5.5)
RECORD ONLY. engine/sport_atlas.py reads it.
"""
from __future__ import annotations

import json
import statistics
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "data" / "sports_history"
UA = {"User-Agent": "Mozilla/5.0 (OLP XDV research)", "Accept": "application/json"}
SB = "https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard?dates={d}&limit=500{extra}"
ODDS = "https://sports.core.api.espn.com/v2/sports/{sport}/leagues/{league}/events/{e}/competitions/{e}/odds"
# league -> (sport, periods in regulation, extra scoreboard query). groups=50: every Division I game, not the top 25.
LEAGUES = {
    "nba": ("basketball", 4, ""), "wnba": ("basketball", 4, ""),
    "mens-college-basketball": ("basketball", 2, "&groups=50"),
    "nhl": ("hockey", 3, ""), "mlb": ("baseball", 9, ""),
    "nfl": ("football", 4, ""), "college-football": ("football", 4, "&groups=80"),
}


class Blocked(RuntimeError):
    """ESPN answered 403 / 429: stop politely, keep what was read, carry on next run."""


def _get(url: str) -> dict:
    for i in range(4):
        try:
            req = urllib.request.Request(url, headers=UA)  # noqa: S310 (fixed https URL)
            with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310 (fixed https URL)
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code in (400, 404):
                return {}
            if e.code in (403, 429):
                raise Blocked(str(e.code)) from e
            time.sleep(2 * (i + 1))
        except Exception:  # noqa: BLE001 - retry, then report
            time.sleep(2 * (i + 1))
    raise RuntimeError("ESPN unavailable")


def american_to_decimal(a) -> float | None:
    try:
        a = float(a)
    except (TypeError, ValueError):
        return None
    if a >= 100:
        return 1 + a / 100
    if a <= -100:
        return 1 + 100 / -a
    return None


def parse_game(e: dict, league: str) -> dict | None:
    sport, reg, _ = LEAGUES[league]
    st = (e.get("status") or {}).get("type") or {}
    if not st.get("completed"):
        return None
    c = (e.get("competitions") or [{}])[0]
    comp = c.get("competitors") or []
    try:
        h = next(t for t in comp if t.get("homeAway") == "home")
        a = next(t for t in comp if t.get("homeAway") == "away")
        ft = [int(float(h.get("score"))), int(float(a.get("score")))]
    except (StopIteration, TypeError, ValueError):
        return None
    lh = [x.get("value") for x in h.get("linescores") or []]
    la = [x.get("value") for x in a.get("linescores") or []]
    periods = [[int(x), int(y)] for x, y in zip(lh, la, strict=False) if x is not None and y is not None] \
        if len(lh) == len(la) and lh else None
    if periods and [sum(p[0] for p in periods), sum(p[1] for p in periods)] != ft:
        periods = None                    # period scores that do not add up are not kept (HR35)
    season = (e.get("season") or {}).get("year")
    return {"sport": sport, "league": league, "id": e.get("id"), "date": (e.get("date") or "")[:16] + "Z",
            "season": season, "hid": str((h.get("team") or {}).get("id")), "aid": str((a.get("team") or {}).get("id")),
            "home": (h.get("team") or {}).get("displayName"), "away": (a.get("team") or {}).get("displayName"),
            "ft": ft, "periods": periods, "regulation": reg, "neutral": bool(c.get("neutralSite")), "prices": None}


def parse_odds(blob: dict) -> dict | None:
    """Median over the pre-game bookmakers ESPN lists; live-odds lines left out."""
    tot, ov, un, sp, sph, spa, mlh, mla = [], [], [], [], [], [], [], []
    for it in blob.get("items") or []:
        name = ((it.get("provider") or {}).get("name") or "").lower()
        if "live" in name or "projection" in name:
            continue
        if it.get("overUnder") is not None:
            tot.append(float(it["overUnder"]))
            o, u = american_to_decimal(it.get("overOdds")), american_to_decimal(it.get("underOdds"))
            if o and u:
                ov.append(o)
                un.append(u)
        hto, ato = it.get("homeTeamOdds") or {}, it.get("awayTeamOdds") or {}
        if it.get("spread") is not None:
            sp.append(float(it["spread"]))      # the home side's line (+10.5 = home gets 10.5; checked 2026-11-12)
            x, y = american_to_decimal(hto.get("spreadOdds")), american_to_decimal(ato.get("spreadOdds"))
            if x and y:
                sph.append(x)
                spa.append(y)
        x, y = american_to_decimal(hto.get("moneyLine")), american_to_decimal(ato.get("moneyLine"))
        if x and y:
            mlh.append(x)
            mla.append(y)
    med = (lambda v: statistics.median(v) if v else None)
    out = {"total": med(tot), "over": med(ov), "under": med(un), "spread": med(sp), "sp_home": med(sph),
           "sp_away": med(spa), "ml_home": med(mlh), "ml_away": med(mla)}
    return out if any(v is not None for v in out.values()) else None


def run(league: str, start: date, end: date, folder: Path = DIR, get=None, workers: int = 3,
        max_days: int | None = None, pause: float = 0.4) -> str:
    """One date at a time (scoreboard), then that date's games' prices with at most `workers` requests at once.
    On a 403 / 429 from ESPN it stops, keeps what it read, and the next run carries on (never hammers)."""
    sport, _, extra = LEAGUES[league]
    live = get is None
    get = get or _get
    d = folder / league
    d.mkdir(parents=True, exist_ok=True)
    df = d / "days_read.json"
    done = set(json.loads(df.read_text(encoding="utf-8"))) if df.exists() else set()
    today = datetime.now(UTC).date()
    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    todo = [x for x in days if x.isoformat() not in done][: max_days or None]
    seen: dict[str, set] = {}
    n_new = n_days = failed = 0
    blocked = False

    def with_odds(g):
        try:
            g["prices"] = parse_odds(get(ODDS.format(sport=sport, league=league, e=g["id"])))
        except Blocked:
            raise
        except Exception:  # noqa: BLE001 - no price is PENDING
            g["prices"] = None
        return g

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for x in todo:
            try:
                blob = get(SB.format(sport=sport, league=league, d=x.strftime("%Y%m%d"), extra=extra))
                games = [g for g in (parse_game(e, league) for e in blob.get("events") or []) if g]
                new = []
                for g in games:
                    mk = g["date"][:7]
                    p = d / f"{mk}.jsonl"
                    if mk not in seen:
                        seen[mk] = {json.loads(t)["id"] for t in p.read_text(encoding="utf-8").splitlines()} if p.exists() else set()
                    if g["id"] not in seen[mk]:
                        new.append(g)
                priced = list(pool.map(with_odds, new))
            except Blocked:
                blocked = True
                break
            except Exception:  # noqa: BLE001 - this date is read next run
                failed += 1
                continue
            for g in priced:
                seen[g["date"][:7]].add(g["id"])
                with (d / f"{g['date'][:7]}.jsonl").open("a", encoding="utf-8") as f:
                    f.write(json.dumps(g, ensure_ascii=False, separators=(",", ":")) + "\n")
                n_new += 1
            n_days += 1
            if (today - x).days > 2:
                done.add(x.isoformat())
            if n_days % 20 == 0:
                df.write_text(json.dumps(sorted(done)), encoding="utf-8")
            if live:
                time.sleep(pause)
    df.write_text(json.dumps(sorted(done)), encoding="utf-8")
    left = sum(1 for x in days if x.isoformat() not in done)
    return (f"{league}: {n_days} dates read, {n_new} new games, {failed} failed, {left} dates still to read"
            + (" (ESPN said stop: carried on next run)" if blocked else ""))


def load(folder: Path = DIR, leagues=None) -> list[dict]:
    out = []
    for lg in leagues or LEAGUES:
        for p in sorted((folder / lg).glob("*.jsonl")):
            for line in p.read_text(encoding="utf-8").splitlines():
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue
    return out


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2023-07-01")
    ap.add_argument("--end", default=None)
    ap.add_argument("--league", action="append", default=None)
    ap.add_argument("--dir", default=str(DIR))
    a = ap.parse_args()
    end = date.fromisoformat(a.end) if a.end else datetime.now(UTC).date()
    for lg in a.league or LEAGUES:
        print(run(lg, date.fromisoformat(a.start), end, Path(a.dir)))
