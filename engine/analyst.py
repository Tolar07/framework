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
  NO VIEW    the framework does not rate the game (a league it does not model, or a market it has no number for:
             1st-half goals, corners, bookings, basketball totals). Kept on paper and graded; looked at again on
             every run until kick-off, in case a later board run rates the game.

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


def selection(event: dict, key: str) -> dict | None:
    """The SportyBet selection for the pick on the match page, from SportyBet's own ids (never assumed), open
    markets only. None when the market or outcome is not there (the pick stays unbooked, HR35)."""
    _f, _c, _x, mid, spec, out = VIEW[key]
    for m in event.get("markets") or []:
        if str(m.get("id")) != mid or (m.get("specifier") or "") != spec or m.get("status") not in (None, 0, "0"):
            continue
        for o in m.get("outcomes") or []:
            if (o.get("desc") or "").strip().lower() == out.lower() and o.get("id") is not None \
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
            chance = framework_chance(p.get("key"), find_rated(p, rows_by_day[day]))
            if chance is None:
                s["verdict"] = "no_view"
            else:
                s.update({"verdict": "agree" if chance >= AGREE_BAR else "disagree", "chance": chance,
                          "decided": now.strftime("%Y-%m-%dT%H:%MZ")})
                n[s["verdict"]] += 1
        if (s.get("verdict") == "agree" and not s.get("code") and enabled() and ko is not None
                and ko - BOOK_LEAD > now and s.get("tries", 0) < 6):
            s["tries"] = s.get("tries", 0) + 1
            try:
                sel = selection((get(_EVENT.format(eid=p["event"])) or {}).get("data") or {}, p["key"])
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
            "code": s.get("code"), "result": p.get("result"), "score": p.get("score")}


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
    lists = {}
    for lid, (title, src, _m) in lp.LISTS.items():
        if src != "universe":
            continue
        lists[lid] = {"title": title, **{v: lp._stats([p for p, s in ps if p["list"] == lid and s.get("verdict") == v])
                                         for v in verdicts}}
    lessons = [{"list": lid, "title": x["title"], "graded": x["disagree"]["graded"], "roi": x["disagree"]["roi"],
                "roi_low": x["disagree"].get("roi_low")} for lid, x in lists.items() if x["disagree"].get("ready")]
    return {"agree_bar": AGREE_BAR, "stake_ngn": STAKE_NGN, "ready_n": lp.READY_N, "by_verdict": by,
            "lists": lists, "lessons": lessons,
            "note": "AGREE picks are staked NGN 500 on SportyBet account 1; DISAGREE and NO VIEW stay on paper. "
                    "A lesson is a list whose DISAGREE picks beat the price over 100+ graded (90% range above 0)."}


def write(book: dict, state: dict, now: datetime, root: Path = ROOT) -> None:
    (root / "data" / "analyst").mkdir(parents=True, exist_ok=True)
    out = root / "output" / "analyst"
    out.mkdir(parents=True, exist_ok=True)
    (root / "data" / "analyst" / "state.json").write_text(json.dumps(state, separators=(",", ":")), encoding="utf-8")
    stamp = now.strftime("%Y-%m-%dT%H:%MZ")
    for day, doc in agree_files(book, state).items():
        (out / f"agree_{day}.json").write_text(json.dumps({"built": stamp, **doc}, ensure_ascii=False, indent=1),
                                               encoding="utf-8")
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


def attach(now: datetime, root: Path = ROOT, get=None, book_code=None) -> str:
    """The universe sweep's hook, after the list test has added and graded its picks."""
    book = lp.load_book("universe", root / "data" / "list_picks")
    state = _read(root / "data" / "analyst" / "state.json", {})
    n = review(book, state, now, root, get, book_code)
    write(book, state, now, root)
    by = record(book, state)["by_verdict"]
    return (f"analyst: {n['agree']} agree, {n['disagree']} disagree, {n['booked']} booked; graded agree "
            f"{by['agree']['graded']}, disagree {by['disagree']['graded']}, no view {by['no_view']['graded']}")
