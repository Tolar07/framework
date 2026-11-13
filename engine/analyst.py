"""
THE ANALYST - the statistics lists' picks set beside the framework's own prediction; when the two agree, the
SportyBet bot stakes NGN 500.

The Architect, 2026-11-13: "a data analyst bot that goes and search for trends for the list ... builds a database of
trends ... when it predicts, and if its prediction agrees with the framework, then it is sent to the framework. And if
it does not agree ... it is kept and it is monitored. And if it passes or it wins, it trains the framework" and, same
day: "do the analyst build. So whatever it agrees with the framework, bets 500 naira on it. That's the only thing."

The analyst's predictions are the live list test's picks (engine/list_picks.py: one pick per list per run from the
ranked trends of engine/stat_lists.py, at SportyBet's real price). For each one this module asks the framework:

  AGREE      the framework's own model (a rated fixture on the board's picks file, src "model", calibrated like the
             board: engine/calibration.py) gives the same outcome AGREE_BAR (50%) or more. Booked as a SportyBet
             code and written to output/analyst/agree_<kick-off date>.json; the SportyBet bot places it at NGN 500
             (sportybet-agent place.py ANALYST_STAKE). Frozen once decided: a later model run never takes it back.
  DISAGREE   the framework rates the game and gives that outcome under 50%. Kept on paper and graded.
  NO VIEW    neither the board nor the framework's worldwide view (engine/world_view.py, 2026-11-13: goals and
             1st-half goals in every SportyBet league, corners and bookings in every ESPN league, basketball totals)
             has a number for the game (a team with too few games). Kept on paper and graded; looked at again on
             every run until kick-off. Each verdict records its source ("board" first, then "world ...").

Every pick is graded from the list test's own result (the same sweep grades it). The record is kept by verdict and
by list in output/analyst/record.json - the trends database: each trend, how it did when the framework agreed and
when it did not. LESSONS: a list whose DISAGREE picks reach READY_N graded with a return whose 90% range clears zero
has beaten the framework on its own; it is written to memory/analyst_lessons.json as a lesson for the framework's
model (record only here - a lesson becomes a model input through the shadow-promotion rule of 2026-11-04: walk-forward
at pick time, live only when it beats the live model, with an undo). A lesson never changes a stake or a threshold.

Undo: ANALYST_AGREE=0 (framework repo variable) stops new AGREE codes being written; picks already placed stay placed.
The stake itself is the bot's (SB_ANALYST_STAKE, default 500).
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

from engine import calibration as cal
from engine import list_picks as lp
from engine import markets as mkt

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "data" / "analyst" / "state.json"
OUT = ROOT / "output" / "analyst"
LESSONS = ROOT / "memory" / "analyst_lessons.json"
AGREE_BAR = 0.50
STAKE_NGN = 500                       # what the SportyBet bot stakes on an AGREE pick (the bot holds the number)
ACCOUNTS = [1]                        # SportyBet account 1 (football + basketball + new sports since 2026-11-09)
BOOK_LEAD = timedelta(minutes=20)     # no code is booked for a game starting sooner than this
_EVENT = "https://www.sportybet.com/api/ng/factsCenter/event?eventId={eid}&productId=3"

# list-test market key -> (framework market key for calibration, rated column(s) summed, SportyBet market, outcome)
# rated "p" = [home, draw, away, over1.5, over2.5, over3.5, btts-yes], raw (engine/picks_ledger.py RATED_KEYS)
VIEW = {
    "btts_yes": (mkt.BTTS_YES, (6,), False, "29", "", "Yes"),
    "btts_no": (mkt.BTTS_NO, (6,), True, "29", "", "No"),
    "over25": (mkt.OVER_25, (4,), False, "18", "total=2.5", "Over 2.5"),
    "draw": (mkt.DRAW, (1,), False, "1", "", "Draw"),
    "win_home": (mkt.HOME, (0,), False, "1", "", "Home"),
    "win_away": (mkt.AWAY, (2,), False, "1", "", "Away"),
    "dc_home": (mkt.DC_1X, (0, 1), False, "10", "", "Home or Draw"),
    "dc_away": (mkt.DC_X2, (1, 2), False, "10", "", "Draw or Away"),
}


# WORLD VIEW (Architect 2026-11-13: "fix everything ... worldwide coverage"): when the board does not rate the game,
# the framework's worldwide view gives the number (engine/world_view.py). ANALYST_WORLD=0 = board games only.
WORLD_VIEW = (os.environ.get("ANALYST_WORLD") or "1").strip() != "0"
WORLD_WITHIN = timedelta(hours=24)    # earlier, the board for that day may not be built yet: wait for it, not decide


def enabled(env=os.environ) -> bool:
    return (env.get("ANALYST_AGREE") or "1").strip() != "0"


def _read(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default
    except ValueError:
        return default


def rated_rows(day: str, root: Path = ROOT) -> list[dict]:
    """The framework's own model rows for a board day (never the market-implied ones: those are not its view)."""
    doc = _read(root / "output" / "picks" / f"picks_{day}.json", {})
    return [r for r in doc.get("rated") or [] if isinstance(r, dict) and r.get("src") == "model"
            and isinstance(r.get("p"), list) and len(r["p"]) >= 7]


def find_rated(pick: dict, rows: list[dict]) -> dict | None:
    """The rated row for the pick's game: both team names alike, and only one such row (two is no match)."""
    h, a = lp.norm(pick.get("home")), lp.norm(pick.get("away"))
    hits = [r for r in rows if lp.same_team(h, lp.norm(r.get("home"))) and lp.same_team(a, lp.norm(r.get("away")))]
    return hits[0] if len(hits) == 1 else None


def framework_chance(key: str, row: dict | None) -> float | None:
    """The framework's calibrated chance for the pick's outcome, or None (no view)."""
    v = VIEW.get(key)
    if v is None or row is None:
        return None
    fkey, cols, complement, *_ = v
    try:
        raw = sum(float(row["p"][i]) for i in cols)
    except (TypeError, ValueError, IndexError):
        return None
    raw = 1 - raw if complement else raw
    p = cal.model_prob(fkey, min(max(raw, 0.0), 1.0))
    return None if p is None else round(p, 4)


LINE_MARKETS = {"first_half": "68", "corners": "166", "bookings": "139"}   # engine/stat_lines.py MARKETS
BB_TOTAL = "225"                                                           # engine/universe.py: basketball total


def _line_str(x) -> str:
    v = float(x)
    return str(int(v)) if v == int(v) else str(v)


def _target(key: str, line=None) -> tuple[str, str, str] | None:
    """(SportyBet market id, specifier, outcome desc in lower case) for a pick key, or None."""
    if key in VIEW:
        return VIEW[key][3], VIEW[key][4], VIEW[key][5].lower()
    try:
        if key == "bb_over" and line is not None:
            return BB_TOTAL, f"total={_line_str(line)}", f"over {_line_str(line)}"
        mkt, ln, side = key.split("|")
        return LINE_MARKETS[mkt], f"total={_line_str(ln)}", f"{side} {_line_str(ln)}"
    except (KeyError, ValueError, TypeError):
        return None


def _desc_ok(desc: str, want: str) -> bool:
    """SportyBet's outcome text against the wanted one: exact, or a total line with words around it."""
    if desc == want:
        return True
    side, _sp, ln = want.partition(" ")
    return bool(ln) and desc.startswith(side) and desc.split()[-1].replace(",", ".") == ln


def selection(event: dict, key: str, line=None) -> dict | None:
    """The SportyBet selection for the pick on the match page, from SportyBet's own ids (never assumed), open
    markets only. None when the market or outcome is not there (the pick stays unbooked, HR35)."""
    target = _target(key, line)
    if target is None:
        return None
    mid, spec, out = target
    for m in event.get("markets") or []:
        if str(m.get("id")) != mid or (m.get("specifier") or "") != spec or m.get("status") not in (None, 0, "0"):
            continue
        for o in m.get("outcomes") or []:
            if _desc_ok((o.get("desc") or "").strip().lower(), out) and o.get("id") is not None \
                    and o.get("isActive", 1) in (1, "1", True, None):
                try:
                    odds = float(o.get("odds"))
                except (TypeError, ValueError):
                    odds = None
                return {"eventId": event.get("eventId"), "marketId": m.get("id"), "specifier": spec,
                        "outcomeId": o.get("id"), "odds": odds}
    return None


def _sb_get(url: str) -> dict:
    from engine.stat_lines import _sb_get as get
    return get(url)


def _book(sel: dict) -> str | None:
    if os.environ.get("GITHUB_ACTIONS") != "true":
        return None
    try:
        from pipeline.sportybet_booking import create_booking_code
        return create_booking_code([{k: sel[k] for k in ("eventId", "marketId", "specifier", "outcomeId")}])[0]
    except Exception:  # noqa: BLE001 - PENDING, tried again next run
        return None


def _ko(p: dict) -> datetime | None:
    try:
        return datetime.fromisoformat(str(p["ko"]).replace("Z", "+00:00"))
    except (KeyError, ValueError):
        return None


def review(book: dict, state: dict, now: datetime, root: Path = ROOT, get=None, book_code=None) -> dict:
    """Decide every undecided list pick, book the agreed ones. Returns counts."""
    get, book_code = get or _sb_get, book_code or _book
    n = {"agree": 0, "disagree": 0, "booked": 0}
    rows_by_day: dict = {}
    world = None
    for pid, p in (book.get("picks") or {}).items():
        s = state.setdefault(pid, {"verdict": None})
        ko = _ko(p)
        if s.get("verdict") in ("agree", "disagree") or ko is None:
            pass
        elif ko <= now:                                          # never decided before kick-off: stays no view
            s["verdict"] = s.get("verdict") or "no_view"
        else:
            day = p.get("date") or ko.strftime("%Y-%m-%d")
            if day not in rows_by_day:
                rows_by_day[day] = rated_rows(day, root)
            chance, source = framework_chance(p.get("key"), find_rated(p, rows_by_day[day])), "board"
            if chance is None and WORLD_VIEW and ko - now <= WORLD_WITHIN:   # the day's board is built by then
                if world is None:
                    from engine.world_view import World
                    world = World(root, now)
                try:
                    got = world.chance(p)
                except Exception:  # noqa: BLE001 - an archive that cannot be read gives no view, never a guess
                    got = None
                if got is not None:
                    chance, source = round(got[0], 4), got[1]
            if chance is None:
                s["verdict"] = "no_view"
            else:
                s.update({"verdict": "agree" if chance >= AGREE_BAR else "disagree", "chance": chance,
                          "source": source, "decided": now.strftime("%Y-%m-%dT%H:%MZ")})
                n[s["verdict"]] += 1
        if (s.get("verdict") == "agree" and not s.get("code") and enabled() and ko is not None
                and ko - BOOK_LEAD > now):
            s["tries"] = s.get("tries", 0) + 1
            try:
                sel = selection((get(_EVENT.format(eid=p["event"])) or {}).get("data") or {}, p["key"], p.get("line"))
            except Exception:  # noqa: BLE001 - SportyBet down: tried again next run
                sel = None
            code = book_code(sel) if sel else None
            if code:
                s.update({"code": code, "market_id": sel["marketId"], "specifier": sel["specifier"],
                          "outcome_id": sel["outcomeId"], "booked_price": sel.get("odds") or p.get("price"),
                          "booked": now.strftime("%Y-%m-%dT%H:%MZ")})
                n["booked"] += 1
    return n


def _row(pid: str, p: dict, s: dict) -> dict:
    return {"id": pid, "list": p.get("list"), "title": p.get("title"), "date": p.get("date"), "ko": p.get("ko"),
            "home": p.get("home"), "away": p.get("away"), "country": p.get("country"), "comp": p.get("comp"),
            "pick": p.get("pick"), "price": p.get("price"), "verdict": s.get("verdict"), "chance": s.get("chance"),
            "source": s.get("source"), "sport": p.get("sport", "football"), "code": s.get("code"), "result": p.get("result"), "score": p.get("score")}


def agree_files(book: dict, state: dict) -> dict[str, dict]:
    """{kick-off date: the bot's file} - every booked AGREE pick, in the shape the bot reads (code, market_id, ko)."""
    out: dict = {}
    for pid, p in (book.get("picks") or {}).items():
        s = state.get(pid) or {}
        if s.get("verdict") != "agree" or not s.get("code"):
            continue
        day = (p.get("ko") or "")[:10]
        doc = out.setdefault(day, {"date": day, "stake_ngn": STAKE_NGN, "accounts": ACCOUNTS, "picks": []})
        doc["picks"].append({**_row(pid, p, s), "sb_event_id": p.get("event"), "market_id": s.get("market_id"),
                             "specifier": s.get("specifier"), "outcome_id": s.get("outcome_id"),
                             "price": s.get("booked_price") or p.get("price"), "sport": p.get("sport", "football"),
                             "accounts": ACCOUNTS})
    for doc in out.values():
        doc["picks"].sort(key=lambda x: x.get("ko") or "")
    return out


def record(book: dict, state: dict) -> dict:
    """The trends database: every list's record when the framework agreed, disagreed or had no view."""
    ps = [(p, state.get(pid) or {}) for pid, p in (book.get("picks") or {}).items()]
    verdicts = ("agree", "disagree", "no_view")
    by = {v: lp._stats([p for p, s in ps if s.get("verdict") == v]) for v in verdicts}
    sources = sorted({s.get("source") for _p, s in ps if s.get("source")})
    by_source = {src: {v: lp._stats([p for p, s in ps if s.get("source") == src and s.get("verdict") == v])
                       for v in ("agree", "disagree")} for src in sources}
    lists = {}
    for lid, (title, _src, _m) in lp.LISTS.items():
        lists[lid] = {"title": title, **{v: lp._stats([p for p, s in ps if p["list"] == lid and s.get("verdict") == v])
                                         for v in verdicts}}
    lessons = [{"list": lid, "title": x["title"], "graded": x["disagree"]["graded"], "roi": x["disagree"]["roi"],
                "roi_low": x["disagree"].get("roi_low")} for lid, x in lists.items() if x["disagree"].get("ready")]
    return {"agree_bar": AGREE_BAR, "stake_ngn": STAKE_NGN, "ready_n": lp.READY_N, "by_verdict": by, "by_source": by_source,
            "lists": lists, "lessons": lessons,
            "note": "AGREE picks are staked NGN 500 on SportyBet account 1; DISAGREE and NO VIEW stay on paper. "
                    "A lesson is a list whose DISAGREE picks beat the price over 100+ graded (90% range above 0)."}


# Two jobs run the analyst, each on its own book and its OWN files, so one job's save never overwrites the other's
# (a lost booking could be booked again under a second code and staked twice):
#   universe sweep (3-hourly)  full-time markets   data/analyst/state.json        output/analyst/agree_<date>.json
#   stat-lines run (hourly)    1st half, corners,  data/analyst/state_lines.json  output/analyst/agree_lines_<date>.json
#                              bookings (their picks are made within 3 h of kick-off)
# The universe sweep also writes the shared views (picks_<date>.json, record.json, lessons) from both states.
STATE_FILE = {"universe": "state.json", "lines": "state_lines.json"}
AGREE_PREFIX = {"universe": "agree_", "lines": "agree_lines_"}


def _both(root: Path) -> tuple[dict, dict]:
    """Both books' picks and both states, for the shared views."""
    picks, state = {}, {}
    for src in ("universe", "lines"):
        picks.update(lp.load_book(src, root / "data" / "list_picks").get("picks") or {})
        state.update(_read(root / "data" / "analyst" / STATE_FILE[src], {}))
    return {"picks": picks}, state


def write(book: dict, state: dict, now: datetime, root: Path = ROOT, source: str = "universe") -> None:
    (root / "data" / "analyst").mkdir(parents=True, exist_ok=True)
    out = root / "output" / "analyst"
    out.mkdir(parents=True, exist_ok=True)
    (root / "data" / "analyst" / STATE_FILE[source]).write_text(json.dumps(state, separators=(",", ":")),
                                                                encoding="utf-8")
    stamp = now.strftime("%Y-%m-%dT%H:%MZ")
    for day, doc in agree_files(book, state).items():
        (out / f"{AGREE_PREFIX[source]}{day}.json").write_text(
            json.dumps({"built": stamp, **doc}, ensure_ascii=False, indent=1), encoding="utf-8")
    if source != "universe":
        return
    book, state = _both(root)
    rec = record(book, state)
    (out / "record.json").write_text(json.dumps({"built": stamp, **rec}, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
    for k in (-1, 0, 1):
        day = (now + timedelta(days=k)).strftime("%Y-%m-%d")
        rows = sorted((_row(pid, p, state.get(pid) or {}) for pid, p in (book.get("picks") or {}).items()
                       if p.get("date") == day), key=lambda r: r.get("ko") or "")
        if rows:
            (out / f"picks_{day}.json").write_text(json.dumps({"built": stamp, "date": day, "picks": rows},
                                                              ensure_ascii=False, indent=1), encoding="utf-8")
    if rec["lessons"]:
        (root / "memory").mkdir(parents=True, exist_ok=True)
        (root / "memory" / "analyst_lessons.json").write_text(json.dumps(
            {"built": stamp, "lessons": rec["lessons"], "applied": False,
             "how": "shadow input first; live only through the 2026-11-04 shadow-promotion rule"}, indent=1),
            encoding="utf-8")


# ANALYST ACCAS (the Architect, 2026-11-13: "book it as single, book it as acca"): the agreed picks also go on
# together. Built only by the hourly stat-lines run (so one job owns the acca files), from BOTH jobs' agreed picks
# that are booked as singles: when the soonest of the not-yet-used ones starts within ACCA_LEAD, every agreed pick
# starting within ACCA_SPAN of now (one leg per game, the likeliest, at most ACCA_MAX legs) goes on one code, frozen.
# A pick is in one acca at most; a lone pick stays a single. The SportyBet bot places each acca at NGN 500.
ACCA_LEAD = timedelta(minutes=90)
ACCA_SPAN = timedelta(hours=24)
ACCA_MAX = 8
ACCA_STATE = "accas.json"


def _book_many(sels: list[dict]) -> str | None:
    if os.environ.get("GITHUB_ACTIONS") != "true":
        return None
    try:
        from pipeline.sportybet_booking import create_booking_code
        return create_booking_code([{k: s[k] for k in ("eventId", "marketId", "specifier", "outcomeId")}
                                    for s in sels])[0]
    except Exception:  # noqa: BLE001 - tried again next run
        return None


def build_accas(book: dict, state: dict, accas: dict, now: datetime, book_many=None) -> int:
    """Book at most one new acca from the agreed, booked, unused picks; returns 1 when booked."""
    if not enabled():
        return 0
    book_many = book_many or _book_many
    used = {pid for a in accas.get("accas", []) for pid in a["legs"]}
    best: dict = {}
    for pid, p in (book.get("picks") or {}).items():
        s = state.get(pid) or {}
        ko = _ko(p)
        if (s.get("verdict") != "agree" or not s.get("code") or not s.get("outcome_id") or pid in used
                or ko is None or not (now + BOOK_LEAD < ko <= now + ACCA_SPAN)):
            continue
        ev = p.get("event")
        if ev not in best or (s.get("chance") or 0) > (state[best[ev]].get("chance") or 0):
            best[ev] = pid
    legs = sorted(best.values(), key=lambda pid: -(state[pid].get("chance") or 0))[:ACCA_MAX]
    if len(legs) < 2 or min(_ko(book["picks"][pid]) for pid in legs) > now + ACCA_LEAD:
        return 0
    sels = [{"eventId": book["picks"][pid]["event"], "marketId": state[pid]["market_id"],
             "specifier": state[pid].get("specifier") or "", "outcomeId": state[pid]["outcome_id"]} for pid in legs]
    code = book_many(sels)
    if not code:
        return 0
    odds = 1.0
    for pid in legs:
        odds *= float(state[pid].get("booked_price") or book["picks"][pid].get("price") or 1.0)
    first = min(book["picks"][pid]["ko"] for pid in legs)
    accas.setdefault("accas", []).append({"code": code, "legs": legs, "odds": round(odds, 2), "ko": first,
                                          "booked": now.strftime("%Y-%m-%dT%H:%MZ")})
    return 1


def acca_files(book: dict, state: dict, accas: dict) -> dict[str, dict]:
    """{date of the first leg's kick-off: the bot's file} - every booked analyst acca with its legs."""
    out: dict = {}
    for a in accas.get("accas", []):
        day = a["ko"][:10]
        legs = [{"home": book["picks"][pid].get("home"), "away": book["picks"][pid].get("away"),
                 "pick": book["picks"][pid].get("pick"), "ko": book["picks"][pid].get("ko"),
                 "price": (state.get(pid) or {}).get("booked_price") or book["picks"][pid].get("price"),
                 "chance": (state.get(pid) or {}).get("chance"), "source": (state.get(pid) or {}).get("source"),
                 "list": book["picks"][pid].get("list"), "result": book["picks"][pid].get("result")}
                for pid in a["legs"] if pid in book["picks"]]
        res = [x["result"] for x in legs]
        result = (None if any(r is None for r in res) else "void" if any(r == "void" for r in res)
                  else int(all(r == 1 for r in res)))
        doc = out.setdefault(day, {"date": day, "stake_ngn": STAKE_NGN, "accounts": ACCOUNTS, "accas": []})
        doc["accas"].append({"code": a["code"], "name": f"Analyst acca ({len(legs)} legs)", "odds": a["odds"],
                             "ko": a["ko"], "legs": legs, "result": result, "accounts": ACCOUNTS})
    return out


def attach_accas(now: datetime, root: Path = ROOT, book_many=None) -> str:
    """The stat-lines run's acca step, after its own picks are reviewed."""
    book, state = _both(root)
    f = root / "data" / "analyst" / ACCA_STATE
    accas = _read(f, {"accas": []})
    n = build_accas(book, state, accas, now, book_many)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(accas, separators=(",", ":")), encoding="utf-8")
    out = root / "output" / "analyst"
    out.mkdir(parents=True, exist_ok=True)
    stamp = now.strftime("%Y-%m-%dT%H:%MZ")
    for day, doc in acca_files(book, state, accas).items():
        (out / f"acca_{day}.json").write_text(json.dumps({"built": stamp, **doc}, ensure_ascii=False, indent=1),
                                              encoding="utf-8")
    return f"analyst accas: {n} booked, {len(accas.get('accas', []))} in all"


def attach(now: datetime, root: Path = ROOT, get=None, book_code=None, source: str = "universe") -> str:
    """A job's hook, after the list test has added and graded its picks: the universe sweep (source "universe")
    or the stat-lines run (source "lines")."""
    book = lp.load_book(source, root / "data" / "list_picks")
    state = _read(root / "data" / "analyst" / STATE_FILE[source], {})
    n = review(book, state, now, root, get, book_code)
    write(book, state, now, root, source)
    by = record(*_both(root))["by_verdict"]
    tail = ""
    if source == "lines":                                      # the acca files have one owner: the hourly run
        try:
            tail = " · " + attach_accas(now, root)
        except Exception as e:  # noqa: BLE001 - singles are already out; an acca failure never stops them
            tail = f" · analyst accas skipped ({type(e).__name__})"
    return (f"analyst ({source}): {n['agree']} agree, {n['disagree']} disagree, {n['booked']} booked; graded agree "
            f"{by['agree']['graded']}, disagree {by['disagree']['graded']}, no view {by['no_view']['graded']}" + tail)
