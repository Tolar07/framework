"""
SPORT CALENDAR — every sport's next 21 days (and a coarser 90-day view), so the framework knows what is coming and
prepares for it (Architect 2026-11-08 23:52: "after today they are on international break and there is UEFA Nations
League upcoming ... the system needs to understand all the calendar for each sport and each upcoming event to know
how to adjust and prepare for what is coming").

Sports: football, basketball (NBA, NCAA, WNBA, EuroLeague and world basketball), and the rollout sports ice hockey,
american_football (NFL), snooker, darts, volleyball, table_tennis, cricket, rugby, tennis, baseball (MLB).

SOURCES (free, keyless, already used by the framework; every date below comes from a fetch in THIS run):
  * ESPN's public scoreboard (site.api.espn.com): per league, one request returns the season (start/end) and its
    calendar: for "day" leagues every game day of the season (the 90-day view), for "list" leagues the phases and
    weeks (NFL weeks, Nations League phases). Then one request per game day in the 21-day horizon gives the
    fixtures (ranges answer HTTP 400; ESPN's day is the US day, so each event is counted on its UTC kick-off date).
  * Flashscore's day feeds (the feed data/flashscore_results.py and the multisport grading read), today .. +7 days,
    for all 12 sports: fixtures by competition (covers snooker, darts, volleyball, table tennis, cricket, rugby and
    EuroLeague, which ESPN does not).
  * config/calendar_rules.json: KNOWN RECURRING RULES, labelled defaults only (e.g. "a club pause in a FIFA month is
    an international break"). They name what the data shows; they never add a date.

HR59 / HR35: every source carries fetched_at and ok/error; a day no source covers reads PENDING (None), never 0;
a window or event carries its source and a confidence (high / medium / low).

DETECTION is data-driven: a club top flight with no game day for 10+ days inside its season is PAUSED; two or more
top flights paused together while national-team fixtures appear = INTERNATIONAL BREAK. A sport with no listed
fixture in any source = OFF-SEASON (no fixtures listed). NBA / NHL gaps = breaks; NFL weeks, byes and the
postseason from ESPN's own calendar; cup rounds and European nights from the cups' game days; tournaments and
majors (World Championship, Finals, Big Bash ...) from competition names.

RECORD-ONLY: it changes no pick, stake, threshold, value bar or rule. It feeds (a) an expected-volume label, so a
thin board in a break reads "expected (international break)" instead of a fault, (b) a calendar note per pick for
the reasoning step, (c) a rotation / fatigue flag on the first club games after an international break (call-ups:
PENDING, no free call-up source), (d) the COMING UP section of the 23:02 report.

Written to output/calendar/calendar_<date>.json by monitor/calendar_run.py.
"""
from __future__ import annotations

import json
import re
import statistics
import urllib.request
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "output" / "calendar"
RULES_PATH = ROOT / "config" / "calendar_rules.json"
HORIZON, OUTLOOK = 21, 90
ESPN = "https://site.api.espn.com/apis/site/v2/sports/{path}/scoreboard?dates={ymd}&limit=500"
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

SPORTS = ("football", "basketball", "ice_hockey", "american_football", "snooker", "darts", "volleyball",
          "table_tennis", "cricket", "rugby", "tennis", "baseball")
# Flashscore sport ids (the same as engine/multisport.py SPORTS[...]["fs"]; football 1, basketball 3, hockey 4)
FLASHSCORE = {"football": 1, "tennis": 2, "basketball": 3, "ice_hockey": 4, "american_football": 5, "baseball": 6,
              "rugby": 8, "volleyball": 12, "cricket": 13, "darts": 14, "snooker": 15, "table_tennis": 25}
FS_DAYS = 8                 # the day feeds answer today .. +7
# ESPN leagues per sport: (path, label, role). role: club = a club top flight (its pauses find the breaks);
# cup = a domestic cup; euro = a European club competition; national = national teams; league = a team-sport league
# whose game days are tracked (back-to-backs, breaks); tour = tennis tours (events are tournaments).
ESPN_LEAGUES: dict[str, list[tuple[str, str, str]]] = {
    "football": [
        ("soccer/eng.1", "Premier League", "club"), ("soccer/esp.1", "La Liga", "club"),
        ("soccer/ger.1", "Bundesliga", "club"), ("soccer/ita.1", "Serie A", "club"),
        ("soccer/fra.1", "Ligue 1", "club"), ("soccer/ned.1", "Eredivisie", "club"),
        ("soccer/por.1", "Primeira Liga", "club"), ("soccer/sco.1", "Scottish Premiership", "club"),
        ("soccer/tur.1", "Turkish Super Lig", "club"), ("soccer/bel.1", "Belgian Pro League", "club"),
        ("soccer/eng.2", "Championship", "club2"),
        ("soccer/eng.fa", "FA Cup", "cup"), ("soccer/eng.league_cup", "EFL Cup", "cup"),
        ("soccer/uefa.champions", "Champions League", "euro"), ("soccer/uefa.europa", "Europa League", "euro"),
        ("soccer/uefa.europa.conf", "Conference League", "euro"),
        ("soccer/uefa.nations", "UEFA Nations League", "national"),
        ("soccer/fifa.friendly", "International friendlies", "national"),
        ("soccer/fifa.worldq.uefa", "World Cup qualifying (UEFA)", "national"),
        ("soccer/uefa.euroq", "Euro qualifying", "national"),
        ("soccer/concacaf.nations.league", "CONCACAF Nations League", "national"),
        ("soccer/caf.nations_qual", "Africa Cup of Nations qualifying", "national"),
    ],
    "basketball": [("basketball/nba", "NBA", "league"), ("basketball/mens-college-basketball", "NCAA", "league"),
                   ("basketball/wnba", "WNBA", "league")],
    "american_football": [("football/nfl", "NFL", "league"), ("football/college-football", "NCAA football", "league")],
    "ice_hockey": [("hockey/nhl", "NHL", "league")],
    "baseball": [("baseball/mlb", "MLB", "league")],
    "tennis": [("tennis/atp", "ATP", "tour"), ("tennis/wta", "WTA", "tour")],
}
KEEP_TEAMS = {"basketball/nba", "hockey/nhl", "football/nfl"}   # team lists kept: back-to-backs and byes

Getter = Callable[[str], Any]


def _get_json(url: str) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "application/json"})  # noqa: S310
    with urllib.request.urlopen(req, timeout=25) as r:  # noqa: S310 — fixed https hosts
        return json.loads(r.read().decode("utf-8"))


def rules(path: Path = RULES_PATH) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — no rules file = no labelled defaults, data only
        return {}


def _now() -> datetime:
    return datetime.now(UTC)


def _stamp(now: datetime) -> str:
    return now.strftime("%Y-%m-%dT%H:%M:%SZ")


def _d(s: str) -> date:
    return date.fromisoformat(s[:10])


def _days(start: date, n: int) -> list[str]:
    return [(start + timedelta(days=k)).isoformat() for k in range(n)]


# ── ESPN ─────────────────────────────────────────────────────────────────────────────────────
def _events(payload: Any) -> list[dict]:
    """[{id, day (UTC kick-off date), home, away, name, note, status}] from one scoreboard; HR35: an event with no
    date is dropped, never dated by guess."""
    out = []
    for e in (payload or {}).get("events") or []:
        when = e.get("date") or ""
        if not re.match(r"\d{4}-\d{2}-\d{2}", when):
            continue
        comp = (e.get("competitions") or [{}])[0]
        teams = {c.get("homeAway"): (c.get("team") or {}).get("displayName") for c in comp.get("competitors") or []}
        notes = [n.get("headline") for n in comp.get("notes") or [] if n.get("headline")]
        st = ((e.get("status") or comp.get("status") or {}).get("type") or {}).get("name") or ""
        out.append({"id": str(e.get("id")), "day": when[:10], "home": teams.get("home"), "away": teams.get("away"),
                    "name": e.get("name"), "note": "; ".join(notes) or (comp.get("type") or {}).get("abbreviation"),
                    "status": st})
    return out


def _calendar(lg: dict) -> tuple[list[str] | None, list[dict]]:
    """(game days, phases) from ESPN's league calendar: a 'day' calendar lists every game day of the season;
    a 'list' calendar lists phases with their entries (NFL weeks, Nations League phases)."""
    cal = lg.get("calendar") or []
    if cal and all(isinstance(x, str) for x in cal):
        return sorted({x[:10] for x in cal}), []
    phases = []
    for ph in cal:
        if not isinstance(ph, dict):
            continue
        entries = ph.get("entries") or [ph]
        for en in entries:
            if en.get("startDate") and en.get("endDate"):
                phases.append({"phase": ph.get("label"), "label": en.get("label"), "detail": en.get("detail"),
                               "start": en["startDate"][:10], "end": en["endDate"][:10]})
    return None, phases


def fetch_espn(path: str, label: str, role: str, today: date, get: Getter = _get_json,
               now: datetime | None = None, pool: int = 8) -> dict:
    """One ESPN league over yesterday .. today+HORIZON: season, calendar, and fixtures per UTC day."""
    now = now or _now()
    rec: dict[str, Any] = {"league": label, "path": path, "role": role, "source": "espn", "fetched_at": _stamp(now),
                           "ok": False, "error": None, "season": None, "game_days": None, "phases": [], "days": {}}
    start = today - timedelta(days=1)
    span = _days(start, HORIZON + 2)
    try:
        anchor = get(ESPN.format(path=path, ymd=today.strftime("%Y%m%d")))
    except Exception as e:  # noqa: BLE001 — a failed source is said, every day PENDING
        rec["error"] = f"{type(e).__name__}: {str(e)[:120]}"
        return rec
    lg = ((anchor or {}).get("leagues") or [{}])[0]
    season = lg.get("season") or {}
    rec["season"] = {"name": season.get("displayName"), "start": (season.get("startDate") or "")[:10] or None,
                     "end": (season.get("endDate") or "")[:10] or None,
                     "type": (season.get("type") or {}).get("name")}
    game_days, phases = _calendar(lg)
    rec["game_days"], rec["phases"] = game_days, phases
    # a US game day d can hold UTC-(d+1) kick-offs: fetch d and keep each event on its UTC date
    want = [d for d in span if d in set(game_days)] if game_days is not None else span
    seen: dict[str, dict] = {}
    for ev in _events(anchor):
        seen[ev["id"]] = ev
    todo = [d for d in want if d != today.isoformat()]

    def one(d: str) -> list[dict]:
        return _events(get(ESPN.format(path=path, ymd=d.replace("-", ""))))
    failed: list[str] = []
    with ThreadPoolExecutor(max_workers=pool) as ex:
        for d, res in zip(todo, ex.map(lambda d: _safe(one, d), todo), strict=True):
            if res is None:
                failed.append(d)
                continue
            for ev in res:
                seen[ev["id"]] = ev
    days: dict[str, dict] = {d: {"n": 0, "notes": {}} for d in span}
    for ev in seen.values():
        if ev["day"] not in days or "POSTPONED" in ev["status"] or "CANCEL" in ev["status"]:
            continue
        slot = days[ev["day"]]
        slot["n"] += 1
        if ev.get("note") and ev["note"] != "STD":
            slot["notes"][ev["note"]] = slot["notes"].get(ev["note"], 0) + 1
        if path in KEEP_TEAMS:
            slot.setdefault("games", []).append([ev["home"], ev["away"]])
        if role == "tour":
            slot.setdefault("events", [])
            if ev.get("name") and ev["name"] not in slot["events"]:
                slot["events"].append(ev["name"])
    for d in failed:                 # a day whose request failed is PENDING, not 0 (HR35)
        if days.get(d, {}).get("n") == 0:
            days[d]["n"] = None
    rec["days"] = days
    rec["ok"] = True
    rec["failed_days"] = failed
    return rec


def _safe(fn: Callable[[str], list[dict]], d: str) -> list[dict] | None:
    try:
        return fn(d)
    except Exception:  # noqa: BLE001 — one failed day; counted in failed_days
        return None


# ── Flashscore ───────────────────────────────────────────────────────────────────────────────
def fetch_flashscore(sport: str, today: date, get_text: Callable[[int], str] | None = None,
                     now: datetime | None = None) -> dict:
    """{date: {competition: fixtures}} for today .. +7 from Flashscore's day feed of one sport."""
    now = now or _now()
    rec: dict[str, Any] = {"source": "flashscore", "fetched_at": _stamp(now), "ok": False, "error": None,
                           "days": {}}
    if get_text is None:
        from data import flashscore_results as fr
        sign = fr.feed_sign()
        sid = FLASHSCORE[sport]

        def get_text(off: int) -> str:
            return fr._get(fr._FEED.replace("f_1_", f"f_{sid}_").format(offset=off),
                           {"x-fsign": sign, "Referer": "https://www.flashscore.co.uk/"})
    from data import flashscore_results as fr2
    good = 0
    for off in range(FS_DAYS):
        d = (today + timedelta(days=off)).isoformat()
        try:
            evs = fr2.parse_feed(get_text(off), FLASHSCORE[sport])
        except Exception as e:  # noqa: BLE001 — that day stays PENDING
            rec["error"] = f"{type(e).__name__}: {str(e)[:120]}"
            continue
        good += 1
        comps: dict[str, int] = {}
        for ev in evs:
            if ev["kickoff_utc"][:10] != d:
                continue
            comps[ev["league"]] = comps.get(ev["league"], 0) + 1
        rec["days"][d] = comps
    rec["ok"] = good > 0
    return rec


# ── detection ────────────────────────────────────────────────────────────────────────────────
def _has(name: str, words: list[str]) -> bool:
    n = (name or "").lower()
    return any(w in n for w in words)


def is_national(comp: str, rl: dict) -> bool:
    f = rl.get("football") or {}
    return _has(comp, f.get("national_keywords") or []) and not _has(comp, f.get("youth_keywords") or []) \
        and "club" not in comp.lower()


def league_pauses(rec: dict, today: date, min_gap: int) -> list[dict]:
    """Gaps of min_gap+ days between consecutive game days inside the season (ESPN's own calendar), that end on
    or after today and start within OUTLOOK days."""
    gd = rec.get("game_days") or []
    out = []
    for a, b in zip(gd, gd[1:], strict=False):
        da, db = _d(a), _d(b)
        if (db - da).days >= min_gap and db >= today and da <= today + timedelta(days=OUTLOOK):
            out.append({"league": rec["league"], "last_game": a, "next_game": b,
                        "start": (da + timedelta(days=1)).isoformat(), "end": (db - timedelta(days=1)).isoformat()})
    return out


def _sum_role(leagues: list[dict], role: str, day: str) -> int | None:
    vals = [r["days"].get(day, {}).get("n") for r in leagues if r.get("ok") and r["role"] == role]
    vals = [v for v in vals if v is not None]
    return sum(vals) if vals else None


def football_windows(leagues: list[dict], fs: dict, today: date, rl: dict) -> tuple[list[dict], list[dict]]:
    """(windows, events) for football: international breaks / club pauses, winter breaks, season ends, cup rounds,
    European nights, national-team competitions."""
    f = rl.get("football") or {}
    min_gap = int(f.get("pause_min_gap_days") or 10)
    club = [r for r in leagues if r.get("ok") and r["role"] == "club"]
    pauses = [p for r in club for p in league_pauses(r, today, min_gap)]
    pauses.sort(key=lambda p: p["start"])
    groups: list[list[dict]] = []
    for p in pauses:
        if groups and p["start"] <= max(x["end"] for x in groups[-1]):
            groups[-1].append(p)
        else:
            groups.append([p])
    windows, events = [], []
    for g in groups:
        start = max(p["start"] for p in g)
        end = min(p["end"] for p in g)
        if start > end:
            start, end = min(p["start"] for p in g), max(p["end"] for p in g)
        span = _days(_d(start), (_d(end) - _d(start)).days + 1)
        # the two sources list the same games: per day the larger count, never the sum
        nat = sum(max(_sum_role(leagues, "national", d) or 0,
                      sum(n for c, n in (fs.get("days") or {}).get(d, {}).items() if is_national(c, rl)))
                  for d in span)
        covered = any(d in (fs.get("days") or {}) or _sum_role(leagues, "national", d) is not None for d in span)
        month = _d(start).month
        names = sorted({p["league"] for p in g})
        w = {"sport": "football", "start": start, "end": end, "leagues_paused": names,
             "national_fixtures": nat if covered else None,
             "resume": min(p["next_game"] for p in g)}
        if len(g) >= 2 and covered and nat > 0:
            w.update(kind="international break", confidence="high" if len(g) >= 3 and nat >= 10
                     else "medium", source="espn calendar (club game days) + espn/flashscore national fixtures")
        elif len(g) >= 2 and not covered and month in (f.get("fifa_window_months") or []):
            w.update(kind="international break", confidence="low",
                     source="espn calendar (club pause) + default rule (FIFA window month); national fixtures PENDING")
        elif month in (f.get("winter_break_months") or []) and (_d(end) - _d(start)).days >= 12:
            w.update(kind="winter break", confidence="medium" if len(g) >= 2 else "low",
                     source="espn calendar (club game days) + default rule (winter months)")
        else:
            w.update(kind="club pause", confidence="low" if len(g) == 1 else "medium",
                     source="espn calendar (club game days); reason PENDING")
        if _d(start) > today + timedelta(days=HORIZON):
            # beyond 21 days ESPN's calendar still lacks fixtures that are not dated yet (TV picks): a gap there
            # can be missing dates, not a pause
            w["confidence"] = "low"
            w["note"] = "beyond the 21-day horizon: some fixtures may not be dated yet"
        windows.append(w)
    for r in [x for x in leagues if x.get("ok")]:
        gd = r.get("game_days") or []
        ahead = [d for d in gd if today.isoformat() <= d <= (today + timedelta(days=OUTLOOK)).isoformat()]
        if r["role"] in ("club", "club2") and gd:
            if gd[-1] >= today.isoformat() and _d(gd[-1]) <= today + timedelta(days=OUTLOOK):
                events.append({"sport": "football", "name": f"{r['league']} season ends", "start": gd[-1],
                               "end": gd[-1], "source": "espn calendar", "confidence": "high"})
            if gd[0] > today.isoformat() and _d(gd[0]) <= today + timedelta(days=OUTLOOK):
                events.append({"sport": "football", "name": f"{r['league']} season starts", "start": gd[0],
                               "end": gd[0], "source": "espn calendar", "confidence": "high"})
        if r["role"] in ("cup", "euro", "national"):
            fixture_days = sorted(d for d, v in r["days"].items() if v.get("n") and d >= today.isoformat())
            days_ahead = fixture_days or (ahead if r.get("game_days") is not None else [])
            for blk in _blocks(days_ahead, 3):
                n = sum(r["days"].get(d, {}).get("n") or 0 for d in blk)
                in_h = any(d in r["days"] for d in blk)
                kind = {"cup": "cup round", "euro": "European club matchday", "national": "national teams"}[r["role"]]
                events.append({"sport": "football", "name": f"{r['league']} ({kind})", "start": blk[0],
                               "end": blk[-1], "fixtures": n if in_h else None, "source": "espn",
                               "confidence": "high"})
        for ph in r.get("phases") or []:
            if r["role"] == "national" and ph["end"] >= today.isoformat() \
                    and _d(ph["start"]) <= today + timedelta(days=OUTLOOK):
                events.append({"sport": "football", "name": f"{r['league']}: {ph['label']}", "start": ph["start"],
                               "end": ph["end"], "detail": ph.get("detail"), "source": "espn calendar",
                               "confidence": "high", "phase": True})
    return windows, events


def _blocks(days: list[str], gap: int) -> list[list[str]]:
    out: list[list[str]] = []
    for d in sorted(days):
        if out and (_d(d) - _d(out[-1][-1])).days <= gap:
            out[-1].append(d)
        else:
            out.append([d])
    return out


def league_windows(sport: str, leagues: list[dict], today: date, rl: dict) -> tuple[list[dict], list[dict]]:
    """NBA / NCAA / WNBA / NHL / NFL / MLB / tennis tours: breaks, off-season, season start/end, phases."""
    windows, events = [], []
    sr = rl.get(sport) or {}
    t, t90 = today.isoformat(), (today + timedelta(days=OUTLOOK)).isoformat()
    for r in [x for x in leagues if x.get("ok")]:
        gd = r.get("game_days")
        s = r.get("season") or {}
        if gd is not None:
            # a calendar day the fetch saw with no game (MLB's post-season placeholder days) is not a game day
            ahead = [d for d in gd if d >= t and ((r["days"].get(d) or {}).get("n", 1) != 0
                                                  or d > max(r["days"] or [t]))]
            if not ahead:
                windows.append({"sport": sport, "kind": "off-season", "league": r["league"],
                                "start": (gd[-1] if gd else t), "end": None, "source": "espn calendar (no game day "
                                f"left in the {s.get('name') or 'season'}); next season PENDING",
                                "confidence": "high", "note": sr.get("note")})
                continue
            if ahead[0] > t:
                events.append({"sport": sport, "name": f"{r['league']} season starts", "start": ahead[0],
                               "end": ahead[0], "source": "espn calendar", "confidence": "high"})
            if ahead[-1] <= t90:
                what = "last listed tour event starts" if r["role"] == "tour" else "last listed game day"
                events.append({"sport": sport, "name": f"{r['league']} {what} (season end)", "start": ahead[-1],
                               "end": ahead[-1], "source": "espn calendar", "confidence": "high",
                               "season_end": True})
            gap = int(sr.get("pause_min_gap_days") or 3)
            if r["role"] != "tour":
                for p in league_pauses(r, today, gap):
                    kind = "break"
                    if sport == "basketball" and _d(p["start"]).month == sr.get("all_star_month"):
                        kind = "All-Star break"
                    windows.append({"sport": sport, "kind": kind, "league": r["league"], "start": p["start"],
                                    "end": p["end"], "resume": p["next_game"], "source": "espn calendar",
                                    "confidence": "high" if kind == "break" else "medium"})
        for ph in r.get("phases") or []:
            if ph["end"] >= t and ph["start"] <= t90:
                events.append({"sport": sport, "name": f"{r['league']} {ph['label']}", "start": ph["start"],
                               "end": ph["end"], "detail": ph.get("detail"), "source": "espn calendar",
                               "confidence": "high", "phase": True})
        notes: dict[str, list[str]] = {}
        for d, v in sorted(r["days"].items()):
            for k in v.get("notes") or {}:
                notes.setdefault(k, []).append(d)
            for name in v.get("events") or []:
                notes.setdefault(name, []).append(d)
        for name, ds in notes.items():
            if r["role"] == "tour" or _has(name, rl.get("major_keywords") or []):
                events.append({"sport": sport, "name": f"{r['league']}: {name}", "start": ds[0], "end": ds[-1],
                               "source": "espn", "confidence": "high",
                               "major": _has(name, rl.get("major_keywords") or [])})
        if r["path"] == "football/nfl":
            events += nfl_byes(r, today)
    return windows, events


def nfl_byes(r: dict, today: date) -> list[dict]:
    """NFL byes per ESPN week: teams seen in the fetched span that play no game in a week fully inside it."""
    teams = {t for v in r["days"].values() for g in v.get("games") or [] for t in g if t}
    out: list[dict] = []
    if len(teams) < 28:
        return out
    fetched = sorted(r["days"])
    for ph in r.get("phases") or []:
        if not (fetched[0] <= ph["start"] and ph["end"] <= fetched[-1]):
            continue
        playing = {t for d, v in r["days"].items() if ph["start"] <= d <= ph["end"]
                   for g in v.get("games") or [] for t in g if t}
        if playing:
            bye = sorted(teams - playing)
            out.append({"sport": "american_football", "name": f"NFL {ph['label']} byes: "
                        + (", ".join(bye) if bye else "none"), "start": ph["start"], "end": ph["end"],
                        "source": "espn", "confidence": "high", "byes": bye})
    return out


def comp_events(sport: str, fs: dict, rl: dict, top: int = 6) -> list[dict]:
    """The sport's main Flashscore competitions over the next 8 days (most fixtures, plus every major)."""
    spans: dict[str, list[str]] = {}
    counts: dict[str, int] = {}
    for d, comps in sorted((fs.get("days") or {}).items()):
        for c, n in comps.items():
            spans.setdefault(c, []).append(d)
            counts[c] = counts.get(c, 0) + n
    majors = [c for c in counts if _has(c, rl.get("major_keywords") or [])]
    main = sorted(counts, key=lambda c: -counts[c])[:top]
    out = []
    for c in dict.fromkeys(majors + main):
        out.append({"sport": sport, "name": c, "start": spans[c][0], "end": spans[c][-1], "fixtures": counts[c],
                    "source": "flashscore", "confidence": "high", "major": c in majors,
                    "national": _has(c, rl.get("national_keywords_any_sport") or [])})
    return out


def detect(sport: str, leagues: list[dict], fs: dict, today: date, rl: dict) -> tuple[list[dict], list[dict]]:
    if sport == "football":
        w, e = football_windows(leagues, fs, today, rl)
    else:
        w, e = league_windows(sport, leagues, today, rl)
    if sport != "football":
        e += comp_events(sport, fs, rl)
    fs_total = [sum(c.values()) for c in (fs.get("days") or {}).values()]
    espn_total = [v.get("n") or 0 for r in leagues if r.get("ok") for d, v in r["days"].items() if d >= today.isoformat()]
    sources_ok = bool(fs.get("ok")) or any(r.get("ok") for r in leagues)
    if sources_ok and not any(fs_total) and not any(espn_total):
        w.append({"sport": sport, "kind": "off-season", "start": today.isoformat(), "end": None,
                  "source": "no fixture listed by " + " / ".join(
                      [x for x, ok in (("flashscore", fs.get("ok")), ("espn", any(r.get("ok") for r in leagues)))
                       if ok]) + " (next 8 days)", "confidence": "medium", "note": (rl.get(sport) or {}).get("note")})
    if sport == "rugby":
        e += rugby_test_window(fs, rl)
    return w, e


def rugby_test_window(fs: dict, rl: dict) -> list[dict]:
    nat = club = 0
    for comps in (fs.get("days") or {}).values():
        for c, n in comps.items():
            if _has(c, rl.get("national_keywords_any_sport") or []):
                nat += n
            else:
                club += n
    if nat and nat >= club:
        return [{"sport": "rugby", "name": f"test window: {nat} international(s) v {club} club game(s) in 8 days",
                 "start": min(fs["days"]), "end": max(fs["days"]), "source": "flashscore", "confidence": "medium"}]
    return []


def day_counts(sport: str, leagues: list[dict], fs: dict, today: date) -> dict[str, dict]:
    """Per day: all fixtures Flashscore lists (today..+7), the tracked ESPN leagues' fixtures (to +21), and the
    board-level count (football: club top flights + national teams). None = PENDING, never 0."""
    out: dict[str, dict] = {}
    for d in _days(today, HORIZON + 1):
        fsd = (fs.get("days") or {}).get(d)
        by_l = {r["league"]: r["days"][d]["n"] for r in leagues
                if r.get("ok") and d in r["days"] and r["days"][d]["n"] is not None}
        board = None
        if sport == "football":
            parts = [_sum_role(leagues, role, d) for role in ("club", "national", "euro", "cup")]
            board = sum(p for p in parts if p is not None) if any(p is not None for p in parts) else None
        elif by_l:
            board = sum(by_l.values())
        out[d] = {"all": sum(fsd.values()) if fsd is not None else None,
                  "tracked": board, "by_league": by_l or None,
                  "top_competitions": dict(sorted(fsd.items(), key=lambda kv: -kv[1])[:8]) if fsd else None}
    return out


def build(today: date | None = None, get: Getter = _get_json,
          fs_get: Callable[[str], Callable[[int], str]] | None = None, now: datetime | None = None,
          sports: tuple[str, ...] = SPORTS) -> dict:
    """The calendar for today .. +21 (90-day outlook where ESPN's calendar gives it). Never raises per source."""
    now = now or _now()
    today = today or now.date()
    rl = rules()
    doc: dict[str, Any] = {"date": today.isoformat(), "built_at": _stamp(now), "horizon_days": HORIZON,
                           "outlook_days": OUTLOOK, "record_only": True, "sources": [], "sports": {}}
    for sport in sports:
        leagues = [fetch_espn(p, lab, role, today, get, now) for p, lab, role in ESPN_LEAGUES.get(sport, [])]
        try:
            fs = fetch_flashscore(sport, today, fs_get(sport) if fs_get else None, now)
        except Exception as e:  # noqa: BLE001 — Flashscore down: those days PENDING
            fs = {"source": "flashscore", "fetched_at": _stamp(now), "ok": False,
                  "error": f"{type(e).__name__}: {str(e)[:120]}", "days": {}}
        for r in leagues:
            doc["sources"].append({"sport": sport, "source": "espn", "league": r["league"], "ok": r["ok"],
                                   "fetched_at": r["fetched_at"], "error": r["error"],
                                   "failed_days": r.get("failed_days")})
        doc["sources"].append({"sport": sport, "source": "flashscore", "ok": fs["ok"], "fetched_at": fs["fetched_at"],
                               "error": fs.get("error"), "days": len(fs.get("days") or {})})
        windows, events = detect(sport, leagues, fs, today, rl)
        days = day_counts(sport, leagues, fs, today)
        doc["sports"][sport] = {
            "days": days, "windows": windows, "events": events,
            "leagues": {r["league"]: {"role": r["role"], "ok": r["ok"], "season": r.get("season"),
                                      "next_game_days": [d for d in (r.get("game_days") or [])
                                                         if today.isoformat() <= d
                                                         <= (today + timedelta(days=OUTLOOK)).isoformat()]
                                      if r.get("game_days") is not None else None,
                                      "phases": r.get("phases") or [],
                                      "games": {d: v["games"] for d, v in r["days"].items() if v.get("games")}
                                      if r["path"] in KEEP_TEAMS else None}
                        for r in leagues},
        }
        doc["sports"][sport]["volume"] = {d: expected_volume(doc, sport, d) for d in days}
        if sport == "football":
            doc["sports"][sport]["rotation_flags"] = rotation_flags(doc, leagues, today)
    return doc


# ── adjust and prepare (record-only) ─────────────────────────────────────────────────────────
def windows_on(doc: dict, sport: str, day: str) -> list[dict]:
    out = []
    for w in ((doc.get("sports") or {}).get(sport) or {}).get("windows") or []:
        end = w.get("end") or "9999-12-31"
        if w.get("start") and w["start"] <= day <= end:
            out.append(w)
    return out


def expected_volume(doc: dict | None, sport: str, day: str) -> dict:
    """{level: normal | low | none | PENDING, reason, fixtures}: how big the sport's board can be that day."""
    if not doc or sport not in (doc.get("sports") or {}):
        return {"level": "PENDING", "reason": "no calendar for the day", "fixtures": None}
    s = doc["sports"][sport]
    row = (s.get("days") or {}).get(day) or {}
    n = _n(sport, row)
    kinds = ("international break", "off-season", "winter break", "club pause", "break", "All-Star break")
    ws = [w for w in windows_on(doc, sport, day) if w.get("kind") in kinds]
    # one league's window (WNBA off-season, an NBA rest day) is not the sport's: it counts only when every
    # tracked league of the sport is in a window that day, or the window is sport-wide
    leagues = [k for k, v in (s.get("leagues") or {}).items() if v.get("ok")]
    off = {w["league"] for w in ws if w.get("league")}
    ws = [w for w in ws if not w.get("league")] or ([w for w in ws if w.get("league")]
                                                    if leagues and set(leagues) <= off else [])
    if sport == "football":
        ws = [w for w in ws if w.get("kind") != "club pause" or len(w.get("leagues_paused") or []) >= 3]
    if ws:
        w = ws[0]
        return {"level": "none" if n == 0 or (n is None and w["kind"] == "off-season") else "low",
                "reason": w["kind"] + (f" ({w['start']}..{w.get('end') or 'PENDING'})"),
                "fixtures": n, "confidence": w.get("confidence")}
    if n is None:
        return {"level": "PENDING", "reason": "no source covers the day", "fixtures": None}
    vals = [x for x in (_n(sport, v) for v in (s.get("days") or {}).values()) if x]
    med = statistics.median(vals) if vals else 0
    if n == 0:
        return {"level": "none", "reason": "no fixtures listed", "fixtures": 0}
    if med and n < 0.4 * med:
        return {"level": "low", "reason": f"light day ({n} v a usual {med:.0f})", "fixtures": n}
    return {"level": "normal", "reason": f"{n} fixtures listed", "fixtures": n}


def _n(sport: str, row: dict) -> int | None:
    """The day's fixture count for the board: football = club top flights + national teams + European / cup
    games (ESPN); every other sport = all Flashscore lists, else the tracked ESPN leagues."""
    first, second = ("tracked", "all") if sport == "football" else ("all", "tracked")
    return row.get(first) if row.get(first) is not None else row.get(second)


def board_label(doc: dict | None, sport: str, day: str, n_picks: int) -> tuple[bool, str]:
    """(expected, text) for a board's pick count: a thin or empty board in a break / off-season is EXPECTED."""
    v = (doc or {}).get("sports", {}).get(sport, {}).get("volume", {}).get(day) or expected_volume(doc, sport, day)
    if n_picks:
        return True, f"{n_picks} pick(s); calendar: {v['level']} ({v['reason']})"
    if v["level"] in ("low", "none"):
        return True, f"0 picks — expected ({v['reason']})"
    if v["level"] == "PENDING":
        return False, "0 picks — calendar PENDING (cannot say whether expected)"
    return False, f"0 picks — NOT expected: the calendar lists {v['fixtures']} fixture(s)"


def rotation_flags(doc: dict, leagues: list[dict], today: date) -> list[dict]:
    """Club fixtures in the first 4 days after an international break: recorded rotation / fatigue flag. Which
    players were on national duty is PENDING (no free call-up source is read)."""
    out = []
    for w in (doc["sports"].get("football") or {}).get("windows") or []:
        if w.get("kind") != "international break" or not w.get("end"):
            continue
        after = _days(_d(w["end"]) + timedelta(days=1), 4)
        for r in leagues:
            if not r.get("ok") or r["role"] not in ("club", "club2"):
                continue
            for d in after:
                n = r["days"].get(d, {}).get("n")
                if n:
                    out.append({"league": r["league"], "day": d, "fixtures": n,
                                "flag": "first club round after the international break: rotation / travel fatigue",
                                "call_ups": "PENDING (no free call-up source)", "record_only": True})
    return out


def _teams(fixture: str) -> tuple[str, str]:
    parts = re.split(r"\s+(?:v|vs|vs\.|at|-)\s+", fixture or "", maxsplit=1)
    return (parts[0].strip(), parts[1].strip()) if len(parts) == 2 else ("", "")


def _club_league(league: str) -> bool:
    return not _has(league, ["nations", "friendly", "international", "qualif", "world cup"])


def note_for(doc: dict | None, sport: str, league: str, kickoff: str, fixture: str = "",
             home: str = "", away: str = "") -> str | None:
    """A short calendar note for one pick (advisory, recorded only), or None."""
    if not doc or not kickoff:
        return None
    s = (doc.get("sports") or {}).get(sport) or {}
    day = kickoff[:10]
    notes: list[str] = []
    if not (home and away):
        home, away = _teams(fixture)
    if sport == "football":
        for w in s.get("windows") or []:
            if w.get("kind") != "international break" or not w.get("end"):
                continue
            if _club_league(league or ""):
                after = (_d(day) - _d(w["end"])).days
                before = (_d(w["start"]) - _d(day)).days
                if 1 <= after <= 4:
                    notes.append(f"first club game after the international break ({w['start']}..{w['end']}): "
                                 "rotation / travel fatigue possible, call-ups PENDING")
                elif 0 <= before <= 3:
                    notes.append(f"last club game before the international break ({w['start']}..{w['end']})")
        if not _club_league(league or ""):
            for e in s.get("events") or []:
                if e.get("phase") and "nations" in e["name"].lower() and "league phase" in e["name"].lower():
                    nl_days = sorted(d for d, v in (s.get("days") or {}).items()
                                     if (v.get("by_league") or {}).get("UEFA Nations League") and d <= e["end"])
                    if nl_days and day in nl_days[-3:]:
                        notes.append(f"Nations League final league-phase matchday (phase ends {e['end']}): "
                                     "group may be decided, rotation possible")
        for e in s.get("events") or []:
            if e["name"].endswith("season ends") and league and league.lower() in e["name"].lower() \
                    and 0 <= (_d(e["start"]) - _d(day)).days <= 7:
                notes.append(f"end of season ({e['start']})")
    else:
        games: dict[str, list] = {}
        for lg in (s.get("leagues") or {}).values():
            for d, gs in (lg.get("games") or {}).items():
                games.setdefault(d, []).extend(gs)
        prev = (_d(day) - timedelta(days=1)).isoformat()
        nxt = (_d(day) + timedelta(days=1)).isoformat()
        for team in (home, away):
            if not team:
                continue
            played = any(team in g for g in games.get(prev, []))
            plays = any(team in g for g in games.get(nxt, []))
            if played:
                notes.append(f"{team}: second night of a back-to-back")
            elif plays:
                notes.append(f"{team}: plays again tomorrow (back-to-back)")
        for e in s.get("events") or []:
            if e.get("major") and e["start"] <= day <= e["end"] and (not league or _has(e["name"], [league.lower()])
                                                                      or _has(league, [e["name"].lower()])):
                notes.append(f"major event: {e['name']}")
    for w in windows_on(doc, sport, day):
        if w.get("kind") in ("off-season",):
            notes.append(f"{w.get('league') or sport}: off-season")
    return "; ".join(dict.fromkeys(notes)) or None


def coming_up_lines(doc: dict | None, today: str, days: int = 14) -> list[str]:
    """COMING UP (next N days): one line per sport with the main windows / events."""
    if not doc:
        return ["calendar PENDING (no calendar file)"]
    end = (_d(today) + timedelta(days=days)).isoformat()
    y = _d(today).year
    out = []
    for sport in SPORTS:
        s = (doc.get("sports") or {}).get(sport)
        if not s:
            continue
        bits: list[str] = []
        for w in s.get("windows") or []:
            if w.get("start") and w["start"] <= end and (w.get("end") or "9999") >= today:
                who = f" {w['league']}" if w.get("league") else ""
                bits.append(f"{w['kind']}{who} {_short(w['start'], y)}-{_short(w.get('end'), y)}"
                            + (f" ({w['national_fixtures']} national-team games)" if w.get("national_fixtures") else "")
                            + (f" [{w['confidence']}]" if w.get("confidence") != "high" else ""))
        evs = [e for e in s.get("events") or [] if e["start"] <= end and e["end"] >= today
               and not (e.get("phase") and e["start"] < today and e["end"] > end)]
        evs = [e for e in evs if not (e.get("phase") and sport == "football" and e["start"] >= today)]
        evs.sort(key=lambda e: (not e.get("major"), bool(e.get("phase")), not e.get("season_end"), e["start"]))
        for e in evs[:5]:
            if e.get("phase") and e["start"] < today:
                bits.append(f"{e['name']} ends {_short(e['end'], y)}")
            else:
                bits.append(f"{e['name']} {_short(e['start'], y)}"
                            + (f"-{_short(e['end'], y)}" if e["end"] != e["start"] else ""))
        if not bits:
            v = [x for x in (s.get("volume") or {}).values() if x.get("fixtures") is not None]
            bits.append("normal schedule" if v else "PENDING (no source answered)")
        out.append(f"{sport}: " + "; ".join(bits[:6]))
    return out


def _short(d: str | None, year: int | None = None) -> str:
    if not d:
        return "PENDING"
    x = _d(d)
    return x.strftime("%d %b").lstrip("0") + (x.strftime(" %Y") if year and x.year != year else "")


# ── files ────────────────────────────────────────────────────────────────────────────────────
def path_for(day: str, out_dir: Path = OUT_DIR) -> Path:
    return out_dir / f"calendar_{day}.json"


def save(doc: dict, out_dir: Path = OUT_DIR) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    p = path_for(doc["date"], out_dir)
    p.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    return p


def load_latest(day: str | None = None, out_dir: Path = OUT_DIR, max_age_days: int = 3) -> dict | None:
    """The newest calendar built on or before `day` (default today), at most max_age_days old; None if none."""
    day = day or _now().date().isoformat()
    try:
        files = sorted(p for p in out_dir.glob("calendar_*.json") if p.stem[9:] <= day)
    except OSError:
        return None
    for p in reversed(files):
        if (_d(day) - _d(p.stem[9:])).days > max_age_days:
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001, S112 — a broken file: try the one before
            continue
    return None
