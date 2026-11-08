"""
MULTI-SPORT TEAM NEWS / LINE-UPS (framework#354; config/sport_connections.json "team_news_lineups").

Every rollout sport inherits football's engine/team_news.py and the NBA's engine/nba_team_news.py: before a
game, the sport's own "team news" is fetched in session from a free source and turned into a flag per side
and per pick (OK / CAUTION / RISK / NO NEWS / PENDING), with the reason written out.

  ice hockey (NHL)    the PROBABLE STARTING GOALIE (ESPN scoreboard) against the team's No.1 (most starts this
                      season, NHL club stats). A backup in net is CAUTION for that side (and for an Under), but
                      only when the No.1 really is a No.1 (>= NO1_SHARE of the starts: a tandem is not news)
                      and is not already out injured (priced in, as football's squad depth teaches).
  baseball (MLB)      the PROBABLE STARTING PITCHER (ESPN). A change from the pitcher first seen for the game
                      (a scratch) is CAUTION for that side; none named yet is PENDING.
  American football   the official INJURY REPORT (ESPN game summary) for the team's starting QUARTERBACK (its
  (NFL)               season passing leader): Out / Doubtful and reported in the last FRESH_DAYS days = RISK,
                      Questionable = CAUTION; on injured reserve or reported earlier = already priced in, note
                      only. Other positions are noted, never flagged (one non-QB is rarely worth a flag).
  rugby               the TEAM SHEETS (ESPN line-ups: jerseys 1-15 start) against the side's previous match:
                      fewer than RUGBY_CAUTION of the starters kept = CAUTION, fewer than RUGBY_RISK = RISK
                      (a heavily rotated XV). Sheet not out yet = PENDING.
  cricket             the PLAYING XI (ESPN, named at the toss). A starter the scout reported missing who is
                      confirmed absent from the XI is CAUTION for that side; no XI yet = PENDING.
  tennis, darts,      PLAYER WITHDRAWALS: the game, seen at two looks or more, left SportyBet's list within
  snooker,            WITHDRAW_HOURS of its start while later games of its competition were still listed and it
  table tennis        was not re-listed (our own fetch, engine/multisport.py) = CAUTION for every pick on it,
                      RISK when the scout reported the withdrawal too. Starting times are estimates in these
                      sports, so a disappearance alone is never RISK.
  volleyball          no free line-up feed: the scout's finding is noted (unconfirmed), the level is NO NEWS.

The scout's reported absences (engine/multisport_reasoning.py) are CONFIRMED against the sport's feed where
there is one (ESPN's injury list, the XI, the team sheet, the withdrawal) and the note says so; an unconfirmed
web claim never raises a level (HR59: one model's claim is not evidence).

RECORDED ONLY (the Architect decides anything more): nothing here drops, restakes, re-prices or exits a pick,
and these flags are written to their own files (output/ms_team_news/<sport>/tn_<date>.json), never into the
board files the bots read. record() grades the flags against the results into memory/ms_team_news_record.json
(did flagged sides win less often than their price said?) so a false-flag habit shows before it could ever
matter. Missing feed or a failed fetch: PENDING (HR35), never a guessed player.
"""
from __future__ import annotations

import json
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

from engine import exchange as ex
from engine import multisport_reasoning as MR
from engine import scout as SC

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "output" / "ms_team_news"
RECORD = ROOT / "memory" / "ms_team_news_record.json"
ESPN = "https://site.api.espn.com/apis/site/v2/sports/{path}"
ESPN_PANEL = "https://site.web.api.espn.com/apis/site/v2/sports/cricket/scorepanel"
NHL_CLUB = "https://api-web.nhle.com/v1/club-stats/{abbr}/now"
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
LEVELS = ("OK", "CAUTION", "RISK")
NO1_SHARE = 0.55              # a goalie with this share of his team's starts is its No.1
FRESH_DAYS = 8                # an NFL report older than this is already priced in
RUGBY_CAUTION, RUGBY_RISK = 0.50, 0.30
KO_TOL = timedelta(hours=3)
FEEDS: dict[str, list[str]] = {
    "ice_hockey": ["hockey/nhl"],
    "american_football": ["football/nfl"],
    "baseball": ["baseball/mlb"],
    # Premiership, URC, Top 14, Champions Cup, Challenge Cup, Six Nations, internationals, Rugby Championship
    "rugby": ["rugby/267979", "rugby/270557", "rugby/270559", "rugby/271937", "rugby/272073", "rugby/180659",
              "rugby/289234", "rugby/244293"],
}
COMP: dict[str, tuple[str, ...]] = {"ice_hockey": ("nhl",), "american_football": ("nfl",), "baseball": ("mlb",)}
NHL_ABBR = {"NJ": "NJD", "TB": "TBL", "LA": "LAK", "SJ": "SJS", "UTAH": "UTA", "UTA": "UTA"}
WITHDRAWAL = ("tennis", "darts", "snooker", "table_tennis")
SIDE_MARKETS = {"186", "219", "251", "340", "406", "1", "410", "11", "16", "223", "256", "493", "187", "188",
                "237", "14", "202", "60", "10"}
TOTAL_MARKETS = {"18", "225", "258", "494", "189", "238"}


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "application/json"})  # noqa: S310
    with urllib.request.urlopen(req, timeout=25) as r:  # noqa: S310 — fixed https hosts
        return json.loads(r.read().decode("utf-8"))


def _dt(s) -> datetime | None:
    return ex._dt(s)


def same(a: str | None, b: str | None) -> bool:
    return bool(a and b) and SC.same_player(str(a), str(b))


# ---------------------------------------------------------------- the pick's side
def pick_side(key: str) -> str | None:
    """'home' / 'away' when the pick leans on one side, None for a total (or anything two-sided)."""
    mid, _spec, out = MR.split(key)
    o = out.strip().lower()
    if mid in SIDE_MARKETS:
        if o.startswith("home") or o == "1x" or o == "home or draw":
            return "home"
        if o.startswith("away") or o == "x2" or o == "draw or away":
            return "away"
    return None


def is_total(key: str) -> str | None:
    mid, _spec, out = MR.split(key)
    o = out.strip().lower()
    return ("over" if o.startswith("over") else "under" if o.startswith("under") else None) if mid in TOTAL_MARKETS else None


# ---------------------------------------------------------------- ESPN events
def espn_events(path: str, day: str, get: Callable = _get) -> list[dict]:
    """The ESPN events of a league on day and the day before (ESPN dates are US local), as plain rows."""
    out: list[dict] = []
    d = datetime.fromisoformat(day)
    for dd in (d - timedelta(days=1), d):
        try:
            sb = get(ESPN.format(path=path) + "/scoreboard?dates=" + dd.strftime("%Y%m%d"))
        except Exception:  # noqa: BLE001,S112 — that league stays PENDING
            continue
        for e in sb.get("events") or []:
            comps = (e.get("competitions") or [{}])[0]
            row: dict = {"id": str(e.get("id")), "ko": e.get("date"), "path": path}
            for c in comps.get("competitors") or []:
                ha = c.get("homeAway")
                if ha not in ("home", "away"):
                    continue
                t = c.get("team") or {}
                row[ha] = t.get("displayName") or t.get("name")
                row[ha + "_abbr"] = t.get("abbreviation")
                row[ha + "_probable"] = next(((p.get("athlete") or {}).get("displayName")
                                              for p in c.get("probables") or [] if p.get("athlete")), None)
            if row.get("home") and row.get("away"):
                out.append(row)
    return out


def cricket_events(get: Callable = _get) -> list[dict]:
    """Today's cricket events across every league ESPN's score panel lists."""
    out: list[dict] = []
    try:
        sp = get(ESPN_PANEL)
    except Exception:  # noqa: BLE001
        return out
    for sc in sp.get("scores") or []:
        lid = str(((sc.get("leagues") or [{}])[0]).get("id") or "")
        for e in sc.get("events") or []:
            comps = (e.get("competitions") or [{}])[0]
            teams = [((c.get("team") or {}).get("displayName"), c.get("homeAway")) for c in comps.get("competitors") or []]
            if len(teams) != 2 or not lid:
                continue
            home = next((n for n, h in teams if h == "home"), teams[0][0])
            away = next((n for n, h in teams if h == "away"), teams[1][0])
            out.append({"id": str(e.get("id")), "ko": e.get("date"), "path": f"cricket/{lid}", "home": home, "away": away})
    return out


def match(g: dict, events: list[dict]) -> dict | None:
    """The ESPN event of one board game: start within KO_TOL and both names close (either way round)."""
    ko = _dt(g.get("ko"))
    best, score = None, 0.0
    for e in events:
        t = _dt(e.get("ko"))
        if ko is None or t is None or abs(t - ko) > KO_TOL:
            continue
        sh, sa = ex.alike(g.get("home") or "", e["home"]), ex.alike(g.get("away") or "", e["away"])
        if min(sh, sa) >= 0.6 and sh + sa > score:
            best, score = e, sh + sa
    return best


def injuries(summary: dict, ev: dict) -> dict:
    """{'home': [{name, status, pos, date}], 'away': [...]} from an ESPN game summary; None side = unread."""
    out: dict = {"home": [], "away": []}
    for t in summary.get("injuries") or []:
        ab = (t.get("team") or {}).get("abbreviation")
        side = "home" if ab == ev.get("home_abbr") else "away" if ab == ev.get("away_abbr") else None
        if side is None:
            continue
        for i in t.get("injuries") or []:
            a = i.get("athlete") or {}
            out[side].append({"name": a.get("displayName"), "status": str(i.get("status") or ""),
                              "pos": ((a.get("position") or {}).get("abbreviation") or ""), "date": i.get("date")})
    return out


def lineup(summary: dict, ev: dict, sport: str) -> dict:
    """{'home': [names] or None, 'away': ...}: rugby's starting XV (jerseys 1-15), cricket's XI."""
    out: dict = {"home": None, "away": None}
    for r in summary.get("rosters") or []:
        name = (r.get("team") or {}).get("displayName") or ""
        side = r.get("homeAway") or ("home" if ex.alike(name, ev["home"]) >= ex.alike(name, ev["away"]) else "away")
        names = []
        for x in r.get("roster") or []:
            a = x.get("athlete") or {}
            if sport == "rugby":
                try:
                    if not 1 <= int(x.get("jersey") or 0) <= 15:
                        continue
                except ValueError:
                    continue
            names.append(a.get("displayName"))
        need = 15 if sport == "rugby" else 11
        out[side] = [n for n in names if n] if len(names) >= need else None
    return out


def passing_leader(summary: dict, abbr: str | None) -> str | None:
    """An NFL team's season passing leader (its starting quarterback) from the ESPN game summary."""
    for t in summary.get("leaders") or []:
        if (t.get("team") or {}).get("abbreviation") != abbr:
            continue
        for c in t.get("leaders") or []:
            if c.get("name") == "passingYards":
                return ((c.get("leaders") or [{}])[0].get("athlete") or {}).get("displayName")
    return None


def previous_xv(summary: dict, ev: dict, es: str, get: Callable = _get) -> list[str] | None:
    """The starting XV of a rugby side's previous match (ESPN's last-five list, same league path)."""
    team = ev.get(es) or ""
    ko = _dt(ev.get("ko"))
    for t in summary.get("lastFiveGames") or []:
        if ex.alike((t.get("team") or {}).get("displayName") or "", team) < 0.8:
            continue
        past = [e for e in t.get("events") or [] if _dt(e.get("gameDate") or e.get("date")) and ko
                and _dt(e.get("gameDate") or e.get("date")) < ko]  # type: ignore[operator]
        past.sort(key=lambda e: str(e.get("gameDate") or e.get("date")), reverse=True)
        for e in past[:1]:
            try:
                s = get(ESPN.format(path=ev["path"]) + f"/summary?event={e.get('id')}")
            except Exception:  # noqa: BLE001
                return None
            pev = {"home": team, "away": "", "path": ev["path"]}
            for r in s.get("rosters") or []:
                if ex.alike((r.get("team") or {}).get("displayName") or "", team) >= 0.8:
                    xv = lineup({"rosters": [{**r, "homeAway": "home"}]}, pev, "rugby")["home"]
                    return xv
    return None


# ---------------------------------------------------------------- per sport
def _flag(level: str, why: str) -> dict:
    return {"level": level, "why": why}


def hockey_side(probable: str | None, goalies: list[dict] | None, hurt: list[dict]) -> list[dict]:
    """Flags for one NHL side from its probable goalie and its goalies' starts this season."""
    if not probable:
        return [_flag("PENDING", "no probable starting goalie named yet")]
    if not goalies:
        return [_flag("PENDING", f"probable goalie {probable}; the club's goalie starts were unreadable")]
    total = sum(int(g.get("gs") or 0) for g in goalies)
    no1 = max(goalies, key=lambda g: int(g.get("gs") or 0))
    share = (int(no1.get("gs") or 0) / total) if total else 0.0
    if same(probable, no1["name"]):
        return [_flag("OK", f"No.1 {no1['name']} expected in net ({no1['gs']}/{total} starts)")]
    if share < NO1_SHARE:
        return [_flag("OK", f"{probable} expected in net; a tandem ({no1['name']} {no1['gs']}/{total} starts), not news")]
    if any(same(i.get("name"), no1["name"]) for i in hurt):
        return [_flag("OK", f"{probable} in net; No.1 {no1['name']} already out injured (priced in)")]
    return [_flag("CAUTION", f"backup {probable} expected in net, not No.1 {no1['name']} ({no1['gs']}/{total} starts)")]


def nhl_goalies(abbr: str | None, get: Callable = _get) -> list[dict] | None:
    if not abbr:
        return None
    try:
        c = get(NHL_CLUB.format(abbr=NHL_ABBR.get(abbr, abbr)))
    except Exception:  # noqa: BLE001
        return None
    return [{"name": f"{(g.get('firstName') or {}).get('default', '')} {(g.get('lastName') or {}).get('default', '')}".strip(),
             "gs": int(g.get("gamesStarted") or 0)} for g in c.get("goalies") or []] or None


def nfl_side(qb: str | None, hurt: list[dict], now: datetime) -> list[dict]:
    """Flags for one NFL side from its starting QB (season passing leader) and the injury report."""
    if not qb:
        return [_flag("PENDING", "starting quarterback unreadable")]
    flags = []
    for i in hurt:
        st = i.get("status", "")
        if not same(i.get("name"), qb):
            continue
        at = _dt(i.get("date"))
        fresh = at is not None and now - at <= timedelta(days=FRESH_DAYS)
        if st.lower().startswith("injured reserve") or not fresh:
            flags.append(_flag("OK", f"QB {qb} {st} since {str(i.get('date'))[:10]} (priced in)"))
        elif st in ("Out", "Doubtful"):
            flags.append(_flag("RISK", f"starting QB {qb} {st} on the injury report"))
        elif st == "Questionable":
            flags.append(_flag("CAUTION", f"starting QB {qb} Questionable on the injury report"))
    others = [f"{i['name']} ({i['pos']}, {i['status']})" for i in hurt if not same(i.get("name"), qb)
              and i.get("status") in ("Out", "Doubtful")][:4]
    if others:
        flags.append(_flag("OK", "also out: " + ", ".join(others) + " (noted, not flagged)"))
    return flags or [_flag("OK", f"QB {qb} not on the injury report")]


def mlb_side(probable: str | None, first: str | None) -> list[dict]:
    if not probable:
        return [_flag("PENDING", "no probable starting pitcher named yet")]
    if first and not same(probable, first):
        return [_flag("CAUTION", f"starting pitcher changed: {first} -> {probable}")]
    return [_flag("OK", f"probable starting pitcher {probable}")]


def rugby_side(xv: list[str] | None, prev: list[str] | None) -> list[dict]:
    if xv is None:
        return [_flag("PENDING", "team sheet not out yet")]
    if not prev:
        return [_flag("OK", "team sheet out; previous match's XV unreadable, rotation not judged")]
    kept = sum(1 for n in xv if any(same(n, p) for p in prev)) / max(1, len(xv))
    lvl = "RISK" if kept < RUGBY_RISK else "CAUTION" if kept < RUGBY_CAUTION else "OK"
    return [_flag(lvl, f"team sheet keeps {kept:.0%} of the previous match's starting XV")]


def scout_confirm(absences: list[dict], side: str, out_names: list[str] | None, xi: list[str] | None) -> list[dict]:
    """Scout absences for one side, confirmed by the feed's out list or by the published XI. Cricket's
    confirmed starter out is CAUTION; elsewhere a confirmation is a note (the sport's own rule sets the level)."""
    flags = []
    for ab in absences or []:
        if ab.get("team") != side or ab.get("status") != "out":
            continue
        by = ("ESPN injury report" if out_names and any(same(n, ab["player"]) for n in out_names) else
              "the published line-up" if xi and not any(same(n, ab["player"]) for n in xi) else None)
        if by:
            flags.append(_flag("NOTE", f"scout: {ab['player']} ({ab.get('role')}) out, confirmed by {by}"))
        else:
            flags.append(_flag("NOTE", f"scout says {ab['player']} out; not confirmed (no level)"))
    return flags


WITHDRAW_HOURS = 6.0           # a match dropped this close to its start (not a re-scheduled draw placeholder)


def _looks(g: dict) -> list[str]:
    return sorted({str((s.get(k) or {}).get("at") or "") for s in (g.get("sides") or {}).values()
                   for k in ("first", "last")} - {""})


def withdrawn(doc: dict, gid: str) -> bool:
    """The game was seen at two looks or more, then dropped from SportyBet's list while the next look (still
    within WITHDRAW_HOURS of its start, before it) listed later games of the same competition, and it was not
    listed again under another id with the same names (a re-listing). From our own looks only; tennis
    starting times are estimates, so this is CAUTION alone, RISK only with the scout's report too."""
    games = doc.get("games") or {}
    g = games.get(gid) or {}
    ko = _dt(g.get("ko"))
    seen = _looks(g)
    if g.get("result") or ko is None or len(seen) < 2:
        return False
    last = seen[-1]
    later = sorted({x for oid, o in games.items() if oid != gid and o.get("comp") == g.get("comp")
                    and (_dt(o.get("ko")) or ko) > ko for x in _looks(o) if x > last})
    nxt = _dt(later[0]) if later else None
    if nxt is None or not (timedelta(0) < ko - nxt <= timedelta(hours=WITHDRAW_HOURS)):
        return False
    names = (MR.fixture(g), f"{g.get('away')} v {g.get('home')}")
    return not any(MR.fixture(o) in names and _looks(o) and _looks(o)[-1] > last
                   for oid, o in games.items() if oid != gid)


def worst(flags: list[dict]) -> str:
    lv = [f["level"] for f in flags if f["level"] in LEVELS]
    if "RISK" in lv:
        return "RISK"
    if "CAUTION" in lv:
        return "CAUTION"
    if lv:
        return "OK"
    return "PENDING" if any(f["level"] == "PENDING" for f in flags) else "NO NEWS"


# ---------------------------------------------------------------- one sport-day
def path_for(sport: str, day: str, out_dir: Path = OUT_DIR) -> Path:
    return out_dir / sport / f"tn_{day}.json"


def assess_day(sport: str, day: str, doc: dict, scout_doc: dict | None = None, old: dict | None = None,
               get: Callable = _get, now: datetime | None = None) -> dict:
    """The team-news document of one sport's board: per game (picks first, then every game the feed covers)
    both sides' flags, and per pick its level. Never raises on a feed failure: that game reads PENDING."""
    now = now or datetime.now(UTC)
    old = old or {}
    scouts = {r.get("fixture"): r.get("absences") or [] for r in (scout_doc or {}).get("fixtures") or []}
    pick_games = {str(p.get("sb_event_id")) for p in MR.real_picks(doc)}
    games = {gid: g for gid, g in (doc.get("games") or {}).items() if not MR.simulated(g)}
    feed = FEEDS.get(sport)
    events: list[dict] = []
    if feed:
        for path in feed:
            events += espn_events(path, day, get)
    elif sport == "cricket":
        events = cricket_events(get)
    toks = COMP.get(sport)
    out_games: dict = {}
    for gid, g in games.items():
        fx = MR.fixture(g)
        ko = _dt(g.get("ko"))
        if ko is None or ko <= now:          # started: the pre-game record stands as it was (it is what gets graded)
            if gid in (old.get("games") or {}):
                out_games[gid] = old["games"][gid]
            continue
        if toks and not any(t in str(g.get("comp") or "").lower() for t in toks) and gid not in pick_games:
            continue
        if sport in (*WITHDRAWAL, "volleyball") and gid not in pick_games and not g.get("matchbook"):
            continue                         # no feed: the games the board or the exchange carries
        prev = (old.get("games") or {}).get(gid) or {}
        rec: dict = {"fixture": fx, "comp": g.get("comp"), "ko": g.get("ko"), "source": None, "espn_id": None,
                     "first": prev.get("first") or {}, "home": [], "away": []}
        ab = scouts.get(fx) or []
        if sport in WITHDRAWAL:
            rec["source"] = "SportyBet list (our own looks)"
            gone = withdrawn(doc, gid)
            told = any(a.get("status") == "out" for a in ab)
            for side in ("home", "away"):
                if gone:
                    rec[side] = [_flag("RISK" if told else "CAUTION",
                                       "the match left SportyBet's list shortly before its start: withdrawal / walkover?"
                                       + (" The scout reported a withdrawal too." if told else ""))]
                else:
                    rec[side] = [_flag("OK", "still listed")]
                rec[side] += scout_confirm(ab, side, None, None)
        elif sport == "volleyball":
            rec["source"] = "none free (scout only)"
            for side in ("home", "away"):
                rec[side] = [_flag("NO NEWS", "no free line-up feed")] + scout_confirm(ab, side, None, None)
        else:
            ev = match(g, events)
            if ev is None:
                if gid not in pick_games:
                    continue
                for side in ("home", "away"):
                    rec[side] = [_flag("PENDING", "game not found on ESPN")]
                rec["level"] = {"home": "PENDING", "away": "PENDING"}
                out_games[gid] = rec
                continue
            rec["espn_id"], rec["source"] = ev["id"], f"ESPN {ev['path']}"
            try:
                summ = get(ESPN.format(path=ev["path"]) + f"/summary?event={ev['id']}")
            except Exception:  # noqa: BLE001
                summ = None
            # ESPN lists the teams in its own order: map its home/away onto the board's
            flip = ex.alike(g.get("home") or "", ev["away"]) > ex.alike(g.get("home") or "", ev["home"])
            side_of = {"home": "away" if flip else "home", "away": "home" if flip else "away"}
            hurt = injuries(summ, ev) if summ else {"home": [], "away": []}
            xi = lineup(summ, ev, sport) if summ and sport in ("rugby", "cricket") else {"home": None, "away": None}
            for side in ("home", "away"):
                es = side_of[side]
                h = hurt.get(es) or []
                if summ is None:
                    rec[side] = [_flag("PENDING", "ESPN game summary unreadable")]
                    continue
                if sport == "ice_hockey":
                    rec[side] = hockey_side(ev.get(es + "_probable"), nhl_goalies(ev.get(es + "_abbr"), get), h)
                elif sport == "american_football":
                    qb = next(((c.get("leaders") or [{}])[0].get("athlete") or {}).get("displayName")
                              for t in summ.get("leaders") or [] if (t.get("team") or {}).get("abbreviation") == ev.get(es + "_abbr")
                              for c in t.get("leaders") or [] if c.get("name") == "passingYards") \
                        if summ.get("leaders") else None
                    rec[side] = nfl_side(qb, h, now)
                elif sport == "baseball":
                    p = ev.get(es + "_probable")
                    first = rec["first"].get(side) or p
                    if p and not rec["first"].get(side):
                        rec["first"][side] = p
                    rec[side] = mlb_side(p, first)
                elif sport == "rugby":
                    pxv = (prev.get("prev_xv") or {}).get(side)
                    if pxv is None and xi.get(es) is not None:
                        pxv = previous_xv(summ, ev, es, get)
                    if pxv:
                        rec.setdefault("prev_xv", {})[side] = pxv
                    rec[side] = rugby_side(xi.get(es), pxv)
                elif sport == "cricket":
                    rec[side] = ([_flag("PENDING", "playing XI not named yet")] if xi.get(es) is None
                                 else [_flag("OK", "playing XI named")])
                outs = [i["name"] for i in h if i.get("status") in ("Out", "Injured Reserve")]
                conf = scout_confirm(ab, side, outs, xi.get(es))
                if sport == "cricket":
                    conf = [_flag("CAUTION", f["why"]) if "confirmed by" in f["why"] else f for f in conf]
                rec[side] += conf
        rec["level"] = {side: worst(rec[side]) for side in ("home", "away")}
        out_games[gid] = rec
    picks = []
    for p in MR.real_picks(doc):
        prec = out_games.get(str(p.get("sb_event_id")))
        key = p.get("key") or ""
        pside, tot = pick_side(key), is_total(key)
        if prec is None:
            lvl, note = "PENDING", "no team news for this game"
        elif pside:
            lvl, note = prec["level"][pside], "; ".join(f["why"] for f in prec[pside])
        elif sport in WITHDRAWAL and prec["level"]["home"] in ("CAUTION", "RISK"):
            lvl, note = prec["level"]["home"], "; ".join(f["why"] for f in prec["home"])
        elif tot == "under" and sport == "ice_hockey" and "CAUTION" in prec["level"].values():
            lvl, note = "CAUTION", "a backup goalie in net lifts goals: " + "; ".join(
                f["why"] for s in ("home", "away") for f in prec[s] if f["level"] == "CAUTION")
        else:
            lvl, note = "OK", "the pick does not depend on one side's news"
        picks.append({"id": MR.pick_id(p), "fixture": MR.fixture(p), "pick": p.get("pick"), "key": key,
                      "side": pside, "level": lvl, "note": note[:400]})
    return {"tag": "team_news", "recorded_only": True, "sport": sport, "date": day,
            "checked_at": now.isoformat(timespec="seconds"), "games": out_games, "picks": picks}


def run(dates: list[str], out_dir: Path = OUT_DIR, get: Callable = _get, now: datetime | None = None,
        scout_dir: Path | None = None, ms_dir: Path | None = None, ih_dir: Path | None = None) -> list[str]:
    """Team news for every rollout sport's board on each date. Never raises; returns the lines to print."""
    lines = []
    for d in dates:
        for sport in MR.SPORTS:
            try:
                doc = MR.load_board(sport, d, ms_dir, ih_dir)
                if not doc:
                    continue
                p = path_for(sport, d, out_dir)
                try:
                    old = json.loads(p.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    old = None
                try:
                    sdoc = json.loads(MR.scout_path(sport, d, scout_dir or MR.OUT_DIR).read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    sdoc = None
                tn = assess_day(sport, d, doc, sdoc, old, get, now)
                if old:                                  # the first flag each game got is kept, for grading
                    for gid, rec in tn["games"].items():
                        rec["first_level"] = ((old.get("games") or {}).get(gid) or {}).get("first_level") or rec["level"]
                else:
                    for rec in tn["games"].values():
                        rec["first_level"] = rec["level"]
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(json.dumps(tn, indent=1, ensure_ascii=False), encoding="utf-8")
                flagged = [x for x in tn["picks"] if x["level"] in ("CAUTION", "RISK")]
                sides = sum(1 for r in tn["games"].values() for v in r["level"].values() if v in ("CAUTION", "RISK"))
                lines.append(f"team news {sport} {d}: {len(tn['games'])} games, {sides} sides flagged, "
                             f"picks {len(tn['picks'])} ({len(flagged)} flagged, recorded only)"
                             + "".join(f"\n  {x['level']} {x['pick']} ({x['fixture']}): {x['note'][:160]}" for x in flagged))
            except Exception as e:  # noqa: BLE001 — one sport failing never stops the others
                lines.append(f"team news {sport} {d}: failed: {type(e).__name__}: {str(e)[:120]}")
    return lines


# ---------------------------------------------------------------- grading the flags
def _winner_price(g: dict, side: str) -> float | None:
    for key, s in (g.get("sides") or {}).items():
        mid, _spec, out = MR.split(key)
        if mid in MR.WINNER_MARKETS and out.strip().lower() == side:
            return (s.get("first") or {}).get("price")
    return None


def record(out_dir: Path = OUT_DIR, ms_dir: Path | None = None, ih_dir: Path | None = None) -> dict:
    """Per sport and level: graded sides, how many won, and how many the price said (sum of 1/price). A
    flag earns trust only if flagged sides win clearly less often than their price said; else it is noise."""
    sports: dict = {}
    for sport in MR.SPORTS:
        folder = out_dir / sport
        by: dict = {}
        for f in sorted(folder.glob("tn_*.json")) if folder.exists() else []:
            try:
                tn = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            doc = MR.load_board(sport, str(tn.get("date")), ms_dir, ih_dir) or {}
            for gid, rec in (tn.get("games") or {}).items():
                g = (doc.get("games") or {}).get(gid) or {}
                res = g.get("result") or {}
                fin = res.get("final") or []
                win = res.get("winner") or ((1 if fin[0] > fin[1] else 2 if fin[1] > fin[0] else 0) if len(fin) == 2 else None)
                if win is None:
                    continue
                for side in ("home", "away"):
                    lvl = (rec.get("first_level") or rec.get("level") or {}).get(side)
                    price = _winner_price(g, side)
                    if lvl not in LEVELS or not price:
                        continue
                    b = by.setdefault(lvl, {"n": 0, "won": 0, "price_said": 0.0})
                    b["n"] += 1
                    b["won"] += int(win == (1 if side == "home" else 2))
                    b["price_said"] = round(b["price_said"] + 1 / float(price), 3)
        sports[sport] = by
    return {"updated": datetime.now(UTC).date().isoformat(), "recorded_only": True, "sports": sports}


def summary_line(rec: dict) -> str:
    parts = []
    for sport, by in (rec.get("sports") or {}).items():
        fl = [f"{lv} {b['won']}/{b['n']} (price said {b['price_said']:.1f})" for lv, b in by.items()
              if lv in ("CAUTION", "RISK") and b["n"]]
        if fl:
            parts.append(f"{sport} " + ", ".join(fl))
    return "Multi-sport team news (recorded only): " + (" · ".join(parts) if parts else "no flagged side graded yet")


def lines_for_context(sport: str, day: str, out_dir: Path = OUT_DIR) -> dict:
    """{pick id: 'LEVEL: note'} for the reasoning step's context (engine/multisport_reasoning.py)."""
    try:
        tn = json.loads(path_for(sport, day, out_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {x["id"]: f"{x['level']}: {x['note']}" for x in tn.get("picks") or []}

