"""
BASKETBALL BOARD - NBA and every other basketball league as ONE sport with its own daily board, made the
football way (Architect 2026-11-06 19:06 UK: "NBA is basketball. It should be merged with everything else to
do with basketball ... NBA basketball and everything else to do with basketball should have its own board and
its own singles and ACC, like football, should be made and be placed"). His answers the same minute:
"Everything football has, all staked" and "One board a day, each acca same-window". Framework issue #403.

Built once a day with the morning NBA board (run_nba.py, 06:47 UK) for the NBA night (10:00 UTC to 10:00 UTC):
the night's NBA picks plus every world basketball / NCAA pick of that window known by then, every leg not yet
started and carrying its own SportyBet code. Written to output/picks/basketball_<night>.json with the football
picks file's section names, so the bots map it the way they map football:

  singles     every pick (already placed one by one from the nba_ / wb_ files; listed here for the record)
  safe3       "50+"-style: the strongest-chance legs (SAFE_MIN_CHANCE+), 3 to a slip
  clv_accas   the legs with the most value against the sharp price (basketball's CLV edge), 4 to a slip,
              one per window
  accas       the remaining legs, best value first, 2 to a slip
  megas       every pick of one window on one slip (football's megas; the one place a match may repeat)
  alts        [] - football's alts are alternative markets of the same match; basketball has no priced
              alternative-market legs until the every-market record (#394) prices them
  value       picks priced VALUE_MIN+ over the sharp fair price (singles, already placed)
  fullgame_accas  accas built only from full-game legs (moneyline / handicap / total) by the same bars, so
              Matchbook (multiples refuse half / quarter legs) has accas it can place. Own section: SportyBet's
              placer reads only safe3 / clv_accas / accas / megas / alts, so these are NOT staked there.
              BB_FULLGAME_ACCAS=0 builds none (record-only undo)

WHY THESE BARS, NOT FOOTBALL'S NUMBERS: football's accas take 75%+ legs to a combined 2.00-3.00. Basketball
picks are value lines at ~54-65% priced ~1.6-2.0, so two legs already pass 3.00 and no leg reaches 75%. The
structure is football's (a match in one acca at most, safe -> CLV -> main hand-out order, megas per window);
the sizes fit basketball legs. Change them only from the graded record.

SAME WINDOW: a slip's legs all tip off within WINDOW of the window's first leg. A basketball game runs ~2h15,
so legs inside 90 minutes are live together (cash-out; no early loss killing later legs). NBA midnight games
and EuroLeague evening games never share a slip. A window with too few legs for a slip leaves them singles.

Every slip is booked once and frozen (a rebuild reads the kept file and never rebooks). Graded leg by leg
from the NBA ledgers and the world basketball files (monitor/edge_scoreboard.grade_wb).
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

from engine import exchange as ex

ROOT = Path(__file__).resolve().parent.parent
PICKS_DIR = ROOT / "output" / "picks"
WINDOW = timedelta(minutes=90)
SAFE_LEGS, CLV_LEGS, ACCA_LEGS = 3, 4, 2
SAFE_MIN_CHANCE = 0.60
MEGA_MAX_LEGS = 26              # SportyBet won't take more on one slip (as football)
VALUE_MIN = 0.10
SECTIONS = ("singles", "safe3", "clv_accas", "accas", "megas", "alts", "value", "fullgame_accas")
SLIP_SECTIONS = ("safe3", "clv_accas", "accas", "megas", "alts", "fullgame_accas")
# FULL-GAME ACCAS (Architect 2026-11-08: Matchbook places basketball accas as multiples; they take only full-game
# moneyline (219), handicap (223) and total (225), overtime included, and refuse 1st-half / quarter legs). The same
# bars and shapes as the board's own slips (50+, CLV, 2-leg accas), built from full-game legs only, in a section of
# their own that SportyBet's placer does not read (it stakes bb_<section> for its fixed list only).
FULLGAME_MARKETS = ("219", "223", "225")
FULLGAME_NAMES = {"safe3": "Basketball Full-game 50+ #{n}", "clv_accas": "Basketball Full-game CLV acca {n}",
                  "accas": "Basketball Full-game Acca {n}"}


def path_for(night: str, folder: Path = PICKS_DIR) -> Path:
    return folder / f"basketball_{night}.json"


def _tip(x: dict) -> datetime | None:
    return ex._dt(x.get("tip") or x.get("ko"))


def _edge(x: dict) -> float:
    """Value against the sharp price: the pick's own ev / value, else chance x price - 1."""
    for k in ("ev", "value"):
        if isinstance(x.get(k), (int, float)):
            return float(x[k])
    return float(x.get("chance") or 0) * float(x.get("price") or 0) - 1


def fullgame_on() -> bool:
    """On unless repo variable BB_FULLGAME_ACCAS is 0 (record-only undo: no full-game accas are built)."""
    return (os.environ.get("BB_FULLGAME_ACCAS") or "").strip() != "0"


def legs_for(now: datetime, start: datetime, end: datetime, nba_picks: list[dict],
             wb_docs: list[dict], markets: tuple[str, ...] | None = None) -> list[dict]:
    """The night's legs: NBA picks + world basketball picks tipping in [start, end), not started, bookable,
    one per game (NBA first), in tip-off order. `markets` keeps only those SportyBet market ids (before the
    one-per-game pick, so a game whose first pick is a half total still gives its full-game pick)."""
    out: dict[str, dict] = {}
    world = [x for d in wb_docs for x in d.get("picks") or []]
    for league, xs in (("NBA", nba_picks), (None, world)):
        for x in xs:
            t = _tip(x)
            if markets is not None and str(x.get("market_id")) not in markets:
                continue
            if (t is None or not start <= t < end or t <= now or not x.get("code") or not x.get("outcome_id")
                    or not x.get("market_id") or not x.get("event_id")):
                continue
            out.setdefault(str(x["event_id"]), {**x, "_tip": t, "league": league or x.get("comp")})
    return sorted(out.values(), key=lambda x: x["_tip"])


def windows(legs: list[dict]) -> list[list[dict]]:
    """Legs (tip-off order) into same-window groups: each runs from its first tip-off to WINDOW later."""
    out: list[list[dict]] = []
    for x in legs:
        if out and x["_tip"] - out[-1][0]["_tip"] <= WINDOW:
            out[-1].append(x)
        else:
            out.append([x])
    return out


def _slip(name: str, g: list[dict]) -> dict:
    odds = chance = 1.0
    for x in g:
        odds *= float(x.get("price") or 1.0)
        chance *= float(x.get("chance") or 0.0)
    ts = [x["_tip"] for x in g]
    return {"name": name, "code": None, "odds": round(odds, 2), "chance": round(chance, 5),
            "legs": [x["event_id"] for x in g], "codes": [x["code"] for x in g], "result": None,
            "earliest_tip_utc": min(ts).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "latest_tip_utc": max(ts).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "spread_minutes": int((max(ts) - min(ts)).total_seconds() // 60),
            "leg_detail": [{"event_id": x["event_id"], "league": x.get("league"), "home": x.get("home"),
                            "away": x.get("away"), "tip": x["_tip"].strftime("%Y-%m-%dT%H:%M:%SZ"),
                            "market_id": x["market_id"], "specifier": x.get("specifier") or "",
                            "outcome_id": x["outcome_id"], "pick": x.get("pick"), "price": x.get("price"),
                            "chance": x.get("chance"), "code": x["code"]} for x in g]}


def _letters(i: int) -> str:
    s, i = "", i + 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def build(legs: list[dict]) -> dict:
    """{section: [slips]} for the night's legs, before booking. Inside each window the legs are handed out
    as football's are: 50+ first, then the CLV acca, then the main accas; a match is in one of them at most.
    Megas take every pick of a window."""
    out: dict[str, list[dict]] = {s: [] for s in SECTIONS}
    for x in legs:
        out["singles"].append(_slip(f"{x.get('home')} v {x.get('away')}: {x.get('pick')}", [x]))
        if _edge(x) >= VALUE_MIN:
            out["value"].append(_slip(f"Value {len(out['value']) + 1}", [x]))
    for w in windows(legs):
        pool = list(w)
        strong = sorted([x for x in pool if float(x.get("chance") or 0) >= SAFE_MIN_CHANCE],
                        key=lambda x: -float(x.get("chance") or 0))
        while len(strong) >= SAFE_LEGS:
            g, strong = strong[:SAFE_LEGS], strong[SAFE_LEGS:]
            out["safe3"].append(_slip(f"Basketball 50+ #{len(out['safe3']) + 1}", g))
            pool = [x for x in pool if x not in g]
        pool.sort(key=lambda x: -_edge(x))
        if len(pool) >= CLV_LEGS:
            g, pool = pool[:CLV_LEGS], pool[CLV_LEGS:]
            out["clv_accas"].append(_slip(f"Basketball CLV acca {_letters(len(out['clv_accas']))}", g))
        while len(pool) >= ACCA_LEGS:
            g, pool = pool[:ACCA_LEGS], pool[ACCA_LEGS:]
            out["accas"].append(_slip(f"Basketball Acca {_letters(len(out['accas']))}", g))
        if len(w) >= 2:
            ranked = sorted(w, key=lambda x: -float(x.get("chance") or 0))
            size = -(-len(ranked) // -(-len(ranked) // MEGA_MAX_LEGS))
            for i in range(0, len(ranked), size):
                g = ranked[i:i + size]
                taken = {frozenset(x["legs"]) for sec in ("safe3", "clv_accas", "accas") for x in out[sec]}
                if len(g) >= 2 and frozenset(x["event_id"] for x in g) not in taken:   # never the same slip twice
                    out["megas"].append(_slip(f"Basketball Mega {len(out['megas']) + 1}", g))
    return out


def _sig(s: dict) -> frozenset:
    return frozenset((d["event_id"], str(d["market_id"]), d["specifier"], str(d["outcome_id"]))
                     for d in s["leg_detail"])


def build_fullgame(full_legs: list[dict], existing: dict[str, list[dict]]) -> list[dict]:
    """Full-game-only accas from the full-game legs, by the board's own rules (build): per window the 3
    strongest 60%+ legs as 50+, the 4 best-value as a CLV acca, then 2-leg accas, best value first; a game in
    one of them at most. No megas. A slip with exactly the legs of one already on the board is left out."""
    b = build(full_legs)
    have = {_sig(s) for sec in SLIP_SECTIONS for s in existing.get(sec) or []}
    out: list[dict] = []
    counts = {"safe3": 0, "clv_accas": 0, "accas": 0}
    for sec in ("safe3", "clv_accas", "accas"):
        for s in b[sec]:
            if _sig(s) in have:
                continue
            s["name"] = FULLGAME_NAMES[sec].format(n=_letters(counts[sec]) if sec != "safe3" else counts[sec] + 1)
            counts[sec] += 1
            out.append(s)
    return out


def book_all(board: dict, book_many) -> bool:
    """Book every multi-leg slip (a one-leg slip keeps its pick's own code). False if any failed."""
    ok = True
    for sec in SECTIONS:
        for s in board[sec]:
            if len(s["legs"]) == 1:
                s["code"] = s["codes"][0]
                continue
            s["code"] = book_many([{"eventId": d["event_id"], "marketId": d["market_id"],
                                    "specifier": d["specifier"], "outcomeId": d["outcome_id"]}
                                   for d in s["leg_detail"]])
            ok = ok and bool(s["code"])
    return ok


def make(now: datetime, night: str, start: datetime, end: datetime, nba_picks: list[dict], wb_docs: list[dict],
         book_many, folder: Path = PICKS_DIR) -> dict | None:
    """Build, book and freeze the night's basketball board; the kept file if already made (never rebooked).
    None when fewer than 2 legs. A slip whose booking failed keeps code None (PENDING, never placed)."""
    path = path_for(night, folder)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    legs = legs_for(now, start, end, nba_picks, wb_docs)
    if len(legs) < 2:
        return None
    board = build(legs)
    board["fullgame_accas"] = (build_fullgame(legs_for(now, start, end, nba_picks, wb_docs, FULLGAME_MARKETS), board)
                               if fullgame_on() else [])
    booked = book_all(board, book_many)
    doc = {"date": night, "sport": "basketball", "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
           "window_minutes": int(WINDOW.total_seconds() // 60), "all_booked": booked,
           "alts_note": "no alternative-market basketball legs priced yet (#394)", **board}
    folder.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    return doc


def slips(doc: dict) -> list[dict]:
    """Every multi-leg slip on the board (for the NBA board text, the WhatsApp mirror and grading)."""
    return [s for sec in SLIP_SECTIONS for s in doc.get(sec) or []]


def render(doc: dict) -> list[str]:
    """The board's lines: each section's slips with codes, as football's board lists them."""
    labels = {"safe3": "50+ ACCAS (3 strongest legs)", "clv_accas": "CLV ACCAS (most value vs the sharp price)",
              "accas": "ACCAS (2 legs, best value)", "megas": "MEGAS (every pick of one tip-off window)",
              "value": "VALUE SINGLES (10%+ over fair)",
              "fullgame_accas": "FULL-GAME ACCAS (moneyline / handicap / total only: what Matchbook multiples take)"}
    L = ["=" * 34, f"BASKETBALL BOARD {doc['date']} - NBA + every league", "=" * 34]
    for sec in ("safe3", "clv_accas", "accas", "megas", "fullgame_accas", "value"):
        if not doc.get(sec):
            continue
        L += ["", labels[sec]]
        for s in doc[sec]:
            L.append(f"  {s['name']} ({len(s['legs'])} leg(s), odds {s['odds']:.2f}): {s.get('code') or 'PENDING'}")
    return L + [""]
