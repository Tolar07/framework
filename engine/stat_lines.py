"""
STAT LINES - SportyBet's own prices on the statistics markets, kept and graded, so a stats claim can be
tested against the price we would really get.

The Architect, 2026-11-12: "prove to me that these facts are real, these trends are real. Then we'll decide on
allocation of funds." backtest/STATS_CLAIMS_PROOF.md found the corner, card, shot and foul habits of teams
repeat from game to game far more than goal habits do, but football-data.co.uk carries no price for those
markets, so whether they pay is unknown. SportyBet does price them, inside each match's full market list
(not the upcoming-games feed the universe sweep reads):
    68  1st Half - Over/Under (total=0.5, 1, 1.5, ...)
    166 Corners - Over/Under (total=6.5 ... 12.5)
    139 Bookings - Over/Under (total=1.5 ...)
This module saves those lines before kick-off (first look and last look) and grades them afterwards from the
framework's own world_facts archive (Flashscore: half-time score, corners, yellow and red cards).

Grading rules (HR35: an outcome we are not sure of stays PENDING, never guessed):
  1st-half totals:  the half-time score.
  corners:          Flashscore 'corner kicks' for the match.
  bookings:         graded ONLY when the match had no red card (yellow cards = bookings); a red card leaves the
                    bookings line ungraded, because SportyBet's count for a red (and a second yellow) is not
                    confirmed here.
A whole line (x.0) that lands exactly on the total is a push and is kept as such.

RECORD ONLY. Nothing here picks, stakes or blocks; backtest/stat_lines_study.py reads the graded files.
Files (framework-data): data/stat_lines/pending.json, data/stat_lines/graded/<month>.jsonl
"""
from __future__ import annotations

import json
import re
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from engine import sb_markets

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "data" / "stat_lines"
MARKETS = {"68": "first_half", "166": "corners", "139": "bookings"}
_LIST = ("https://www.sportybet.com/api/ng/factsCenter/pcUpcomingEvents"
         "?sportId=sr:sport:1&marketId=1&pageSize=100&pageNum={page}")
_EVENT = "https://www.sportybet.com/api/ng/factsCenter/event?eventId={eid}&productId=3"
_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/124.0 Safari/537.36", "Accept": "application/json"}
WINDOW = timedelta(hours=3)      # games starting within this window are looked at (close to the closing price)
PER_RUN = 150                    # match pages read per run (polite)
PAUSE = 0.3
GRADE_AFTER = timedelta(hours=3)
GIVE_UP_AFTER = timedelta(days=4)


def _f(x):
    try:
        v = float(x)
        return v if v > 1.0 else None
    except (TypeError, ValueError):
        return None


def lines_of(event: dict) -> dict:
    """{"corners": {"9.5": [over, under]}, ...} from one SportyBet match page; open lines only."""
    out: dict = {}
    for m in event.get("markets") or []:
        key = MARKETS.get(str(m.get("id")))
        if not key or m.get("status") not in (None, 0, "0"):
            continue
        mt = re.search(r"total=([0-9.]+)", m.get("specifier") or "")
        if not mt:
            continue
        line = mt.group(1)
        px = {(o.get("desc") or "").split(" ")[0].lower(): _f(o.get("odds")) for o in m.get("outcomes") or []
              if o.get("isActive", 1) in (1, "1", True, None)}
        if px.get("over") and px.get("under"):
            out.setdefault(key, {})[line] = [px["over"], px["under"]]
    return out


def update(pending: dict, event: dict, lines: dict, now: datetime) -> bool:
    """First look kept, last look replaced. True when the match is new."""
    eid = event.get("eventId")
    if not eid or not lines:
        return False
    ko = datetime.fromtimestamp(event["estimateStartTime"] / 1000, tz=UTC).strftime("%Y-%m-%dT%H:%MZ")
    snap = {"at": now.strftime("%Y-%m-%dT%H:%MZ"), "lines": lines}
    old = pending.get(eid)
    if old:
        old["last"], old["looks"], old["ko"] = snap, old["looks"] + 1, ko
        return False
    cat = (event.get("sport") or {}).get("category") or {}
    pending[eid] = {"id": eid, "ko": ko, "home": event.get("homeTeamName"), "away": event.get("awayTeamName"),
                    "country": cat.get("name"), "comp": ((event.get("sport") or {}).get("category") or {})
                    .get("tournament", {}).get("name"), "first": snap, "last": snap, "looks": 1}
    return True


def result_from(base: dict | None, detail: dict | None) -> dict:
    """What happened, from world_facts rows (Flashscore). Keys present only when known."""
    res: dict = {}
    if base and base.get("ht") and None not in base["ht"]:
        res["first_half"] = base["ht"][0] + base["ht"][1]
    st = ((detail or {}).get("stats") or {}).get("match") or {}
    if "corners" in st and None not in st["corners"]:
        res["corners"] = st["corners"][0] + st["corners"][1]
    if "yellow" in st and None not in st["yellow"]:
        red = st.get("red") or [0, 0]
        if (red[0] or 0) + (red[1] or 0) == 0:
            res["bookings"] = st["yellow"][0] + st["yellow"][1]
    return res


def settle(line: str, total: float) -> dict:
    """{"over": 1/0/None(push), "under": ...} for one line."""
    x = float(line)
    if total == x:
        return {"over": None, "under": None}
    return {"over": int(total > x), "under": int(total < x)}


class _Index:
    def __init__(self, rows: list[dict]):
        from engine.universe import _tokens
        self.by = {}
        for r in rows:
            for t in _tokens(r["home"]) | _tokens(r["away"]):
                self.by.setdefault((r["ko"][:10], t), []).append(r)

    def find(self, home: str, away: str, ko: str):
        from data import flashscore_results as fr
        from engine.universe import _tokens
        d0 = datetime.fromisoformat(ko[:10])
        cands = {}
        for off in (-1, 0, 1):
            d = (d0 + timedelta(days=off)).strftime("%Y-%m-%d")
            for t in _tokens(home) | _tokens(away):
                for r in self.by.get((d, t), []):
                    cands[r["id"]] = {**r, "kickoff_utc": r["ko"], "fthg": r["ft"][0], "ftag": r["ft"][1]}
        return fr.find_result(list(cands.values()), home, away, ko[:10]) if cands else None


def _read_jsonl(folder: Path, months: set[str]) -> list[dict]:
    rows = []
    for m in months:
        p = folder / f"{m}.jsonl"
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    continue
    return rows


def grade(pending: dict, root: Path, now: datetime, fetch_detail=None) -> tuple[list[dict], int]:
    """Graded rows (out of pending) and how many were given up. fetch_detail(flashscore id) -> detail row or
    None reads a match's stats when the world_facts run has not read it yet."""
    due = [r for r in pending.values()
           if now - datetime.fromisoformat(r["ko"].replace("Z", "+00:00")) >= GRADE_AFTER]
    if not due:
        return [], 0
    months = {r["ko"][:7] for r in due} | {(datetime.fromisoformat(r["ko"][:10]) + timedelta(days=1)).strftime("%Y-%m")
                                           for r in due}
    base = _read_jsonl(root / "data" / "world_facts", months)
    detail = {d["id"]: d for d in _read_jsonl(root / "data" / "world_facts_detail", months)}
    idx = _Index(base)
    done, gave_up = [], 0
    for r in due:
        hit = idx.find(r["home"], r["away"], r["ko"])
        if hit is None:
            if now - datetime.fromisoformat(r["ko"].replace("Z", "+00:00")) > GIVE_UP_AFTER:
                done.append({**r, "fs_id": None, "result": None, "graded_at": now.strftime("%Y-%m-%dT%H:%MZ")})
                gave_up += 1
                del pending[r["id"]]
            continue
        d = detail.get(hit["id"])
        if d is None and fetch_detail is not None and any(k in r["last"]["lines"] for k in ("corners", "bookings")):
            try:
                d = fetch_detail(hit)
            except Exception:  # noqa: BLE001 - stats feed down: graded on what we have
                d = None
        res = result_from(hit, d)
        graded = {}
        for mkt, lines in r["last"]["lines"].items():
            if mkt in res:
                graded[mkt] = {ln: settle(ln, res[mkt]) for ln in lines}
        done.append({**r, "fs_id": hit["id"], "fs_league": hit.get("league"),
                     "fs_home": hit.get("home"), "fs_away": hit.get("away"), "result": res, "graded": graded,
                     "graded_at": now.strftime("%Y-%m-%dT%H:%MZ")})
        del pending[r["id"]]
    return done, gave_up


def _sb_get(url: str) -> dict:
    import urllib.request
    for i in range(3):
        try:
            req = urllib.request.Request(url, headers=_UA)  # noqa: S310 (fixed https URL)
            with urllib.request.urlopen(req, timeout=40) as r:  # noqa: S310 (fixed https URL)
                return json.loads(r.read())
        except Exception:  # noqa: BLE001 - retry, then report
            time.sleep(2 + 2 * i)
    raise RuntimeError("SportyBet feed unavailable")


def run(now: datetime | None = None, root: Path = ROOT, get=None, fetch_detail=None) -> str:
    """One pass: record the lines of games starting within WINDOW, grade the finished ones. One line back."""
    now = now or datetime.now(UTC)
    get = get or _sb_get
    folder = root / "data" / "stat_lines"
    folder.mkdir(parents=True, exist_ok=True)
    pf = folder / "pending.json"
    pending = json.loads(pf.read_text(encoding="utf-8")) if pf.exists() else {}
    # framework#567: the market catalogue and the model-vs-price value watch (engine/sb_markets.py), record only
    wf, cf = folder / "wide_pending.json", folder / "market_catalogue.json"
    wide = json.loads(wf.read_text(encoding="utf-8")) if wf.exists() else {}
    cat = json.loads(cf.read_text(encoding="utf-8")) if cf.exists() else {}
    games = sb_markets.load_games(root, now.strftime("%Y-%m-%d")) +         sb_markets.load_games(root, (now + timedelta(days=1)).strftime("%Y-%m-%d"))
    soon = []
    for page in range(1, 60):  # the feed is ordered by competition, not time: read it all
        try:
            blob = get(_LIST.format(page=page))
        except Exception:  # noqa: BLE001 - SportyBet down: grade only
            break
        ts = (blob.get("data") or {}).get("tournaments") or []
        evs = [e for t in ts for e in t.get("events") or []]
        if not evs:
            break
        for e in evs:
            ko = datetime.fromtimestamp(e.get("estimateStartTime", 0) / 1000, tz=UTC)
            if timedelta(0) < ko - now <= WINDOW:
                soon.append(e)
    soon.sort(key=lambda e: (e.get("eventId") in pending, e.get("estimateStartTime", 0)))
    new = looked = 0
    for e in soon[:PER_RUN]:
        try:
            page = get(_EVENT.format(eid=e["eventId"]))
            if get is _sb_get:
                time.sleep(PAUSE)
        except Exception:  # noqa: BLE001 - next run
            continue
        ev = page.get("data") or {}
        ev.setdefault("estimateStartTime", e.get("estimateStartTime"))
        ev.setdefault("eventId", e.get("eventId"))
        ev.setdefault("homeTeamName", e.get("homeTeamName"))
        ev.setdefault("awayTeamName", e.get("awayTeamName"))
        lines = lines_of(ev)
        try:
            sb_markets.catalogue_update(cat, ev)
            sb_markets.observe(wide, ev, now.strftime("%Y-%m-%dT%H:%MZ"), games)
            if ev.get("eventId") in wide:
                wide[ev["eventId"]].setdefault("ko", datetime.fromtimestamp(
                    ev["estimateStartTime"] / 1000, tz=UTC).strftime("%Y-%m-%dT%H:%MZ"))
                wide[ev["eventId"]].setdefault("home", ev.get("homeTeamName"))
                wide[ev["eventId"]].setdefault("away", ev.get("awayTeamName"))
        except Exception as exc:  # noqa: BLE001 - the watch never stops the recorder
            print(f"sb_markets watch skipped ({type(exc).__name__}: {str(exc)[:80]})")
        looked += 1
        new += update(pending, ev, lines, now)
    done, gave_up = grade(pending, root, now, fetch_detail)
    gdir = folder / "graded"
    gdir.mkdir(parents=True, exist_ok=True)
    for r in done:
        with (gdir / f"{r['ko'][:7]}.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n")
    pf.write_text(json.dumps(pending, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    sb_markets.settle_wide(wide, root, now, gdir / "wide", fetch_detail)
    wf.write_text(json.dumps(wide, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    cf.write_text(json.dumps(cat, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    try:
        # PAPER ONLY (Architect 2026-11-12): the statistics lists tested on these lines (engine/list_picks.py)
        from engine import list_picks
        tail = " · " + list_picks.attach_lines(pending, done, now, root)
    except Exception as e:  # noqa: BLE001 - never stops the recorder
        tail = f" · list test skipped ({type(e).__name__}: {str(e)[:60]})"
    try:
        # THE ANALYST (Architect 2026-11-13): these lines' list picks against the framework's view; agreed ones
        # booked for the SportyBet bot at NGN 500 (engine/analyst.py, its own state file for this job)
        from engine import analyst
        tail += " · " + analyst.attach(now, root, source="lines")
    except Exception as e:  # noqa: BLE001 - never stops the recorder
        tail += f" · analyst skipped ({type(e).__name__}: {str(e)[:60]})"
    return (f"stat lines: {len(soon)} games start within {int(WINDOW.total_seconds() // 3600)} h, {looked} pages read "
            f"({new} new); graded {len(done) - gave_up}, gave up {gave_up}, {len(pending)} waiting" + tail)


def flashscore_detail(match: dict) -> dict | None:
    """Read one match's stats tab from Flashscore (the world_facts reader), for grading."""
    from data import flashscore_results as fr
    from engine import world_facts as wf
    sign = fr.feed_sign()
    txt = fr._get(wf._FEED + "df_st_1_" + match["id"], {"x-fsign": sign, "Referer": "https://www.flashscore.co.uk/"})
    return {"id": match["id"], "stats": wf.parse_stats(txt)}
