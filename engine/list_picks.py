"""
LIST TEST - every statistics list tested live, on paper, at SportyBet's real price.

The Architect, 2026-11-12: "We are going to test it ... identify the teams and the club that does what, pick one
each from the list ... test it with the league ... you can build an ACCA, we can do it as single ... if we keep
testing and it is proven, we need to look into those leagues."

PAPER ONLY: nothing is staked, no code is booked, nothing is written where a bot reads (output/picks/,
output/multisport/). Real stakes on a list are the Architect's decision, list by list, on this record.

How a pick is made (same rule for every list, no judgement):
  - a list's ranked entries (its top CANDS teams or leagues) come from output/stat_lists/pick_index.json
    (engine/stat_lists.py, lists 7-21) and, for lists 1, 2, 4, 5, from their own files;
  - each run looks at the games SportyBet is pricing that start within HORIZON_H hours; for each list it takes the game of the
    best-ranked entry, at most one new pick a run and PER_DAY a day (by kick-off date), one pick per game per list;
  - the bet is the list's own claim (LISTS below), at the price SportyBet showed on that look;
  - it is graded from the same results the sweep and the stat-lines recorder already use.
A team must be found by name in the game AND its opponent must belong to the same league's team list, so a
same-named club elsewhere is never picked. A league entry needs both teams in the league's list.

Two price sources, two books (so two workflows never write one file):
  universe  (monitor/universe_sweep.py, every 3 h): full-time markets - BTTS, Over 2.5, draw, win, double chance,
            basketball totals.                         data/list_picks/book_universe.json
  lines     (engine/stat_lines.py run, hourly): 1st-half goals, corners and bookings lines, saved within 3 h of
            kick-off.                                  data/list_picks/book_lines.json
Out: output/list_picks/<source>_<date>.json (the day's picks) and record_<source>.json: per list picks, graded,
won, return on a 1-unit stake, and the daily paper acca (the day's first pick of each list, the ACCA_LEGS shortest
prices). A list is READY TO PROPOSE at READY_N graded picks with a return whose 90% range clears zero.
"""
from __future__ import annotations

import json
import random
import re
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOOKS = ROOT / "data" / "list_picks"
OUT = ROOT / "output" / "list_picks"
INDEX = ROOT / "output" / "stat_lists" / "pick_index.json"
PER_DAY = 3
HORIZON_H = 36     # only games starting within this many hours: a price near kick-off, and the app shows the day
READY_N = 100
ACCA_LEGS = 4
MIN_PRICE = 1.10
CANDS = 25

# list id -> (title, source, market). Lists with no priced market in either source are in NOT_TESTED.
LISTS = {
    "btts_leagues": ("Both teams to score, by league", "universe", "btts_yes"),
    "ou_leagues": ("Goals over and under, by league", "universe", "over25"),
    "clean_sheets": ("Clean sheets and blanks, by team", "universe", "btts_no"),
    "comebacks": ("Comebacks, by team", "universe", "dc_team"),
    "draws": ("Draw-heavy teams", "universe", "draw"),
    "shots_on_target": ("Most shots on target", "universe", "over25"),
    "luck": ("Unlucky teams", "universe", "win_team"),
    "us_totals": ("US sports: teams against the total", "universe", "bb_over"),
    "wb_totals": ("World basketball leagues against the total", "universe", "bb_over"),
    "first_half_leagues": ("Goals before half-time, by league", "lines", "fh_over15"),
    "top_home_first_half": ("Home sides: first-half goals", "lines", "fh_over05"),
    "steady_corners": ("Steadiest corner teams", "lines", "corners_steady"),
    "second_half": ("Quiet first halves, by league", "lines", "fh_under15"),
    "early_goal": ("Early goals, by league", "lines", "fh_over05"),
    "team_corners": ("Most corners in a team's games", "lines", "corners_over"),
    "cards": ("Card-heavy teams", "lines", "bookings_over"),
    "fouls": ("Most fouls in a team's games", "lines", "bookings_over"),
}
NOT_TESTED = {
    "late_goals": "no price kept for goals after the 76th minute",
    "lower_league_value": "has its own paper record (engine/lower_league_value.py)",
    "fh_corners": "no first-half corner counts yet",
    "tennis": "the sweep keeps no tennis price yet",
}
LABEL = {"btts_yes": "BTTS Yes", "btts_no": "BTTS No", "over25": "Over 2.5", "draw": "Draw", "dc_team": "{team} or draw",
         "win_team": "{team} to win", "bb_over": "Over {line}", "fh_over05": "1st half Over 0.5",
         "fh_over15": "1st half Over 1.5", "fh_under15": "1st half Under 1.5", "corners_over": "Corners Over {line}",
         "corners_steady": "Corners {side} {line}", "bookings_over": "Bookings Over {line}"}

_WORDS = {"fc", "sc", "afc", "cf", "ac", "if", "bk", "sk", "fk", "cd", "ud", "sv", "club", "the", "de", "nk", "hnk",
          "fbc", "as", "ss", "us", "sd", "ca", "rc", "kv", "1"}


# a women's, youth, reserve or amateur game: never picked (the lists' teams are senior men's sides)
_VARIANT = re.compile(r"women|\(w\)|\bw$|femen|frauen|\bu-?\d\d\b|under \d\d|youth|junior|reserve|amateur|"
                      r"\b(ii|iii|b)$|\bb team|\bsrl\b|simulated|esoccer|ebasketball|cyber", re.I)


def is_variant(row: dict) -> bool:
    return any(_VARIANT.search(str(row.get(k) or "")) for k in ("home", "away", "comp", "country"))


def norm(name: str | None) -> tuple[str, ...]:
    t = unicodedata.normalize("NFKD", (name or "").lower().replace("ø", "o").replace("æ", "ae").replace("ß", "ss"))
    t = "".join(c if c.isalnum() else " " for c in t if not unicodedata.combining(c))
    return tuple(w for w in t.split() if w not in _WORDS)


def same_team(a: tuple, b: tuple) -> bool:
    if not a or not b:
        return False
    if a == b:
        return True
    sa, sb = set(a), set(b)
    small = sa if len(sa) <= len(sb) else sb
    return (sa <= sb or sb <= sa) and any(len(w) >= 4 for w in small)


class Index:
    """The ranked entries of every list, and each ESPN league's team names."""

    def __init__(self, doc: dict | None, root: Path = ROOT):
        doc = doc or {}
        self.cands = dict(doc.get("cands") or {})
        self.rosters = {lid: [norm(t) for t in r.get("teams") or []] for lid, r in (doc.get("rosters") or {}).items()}
        self._legacy(root)

    def _legacy(self, root: Path) -> None:
        def read(rel):
            p = root / rel
            try:
                return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
            except ValueError:
                return {}
        lp = [x for x in read("output/league_profiles/latest.json").get("leagues") or [] if isinstance(x, dict)]
        btts = sorted((x for x in lp if isinstance(x.get("btts"), (int, float))), key=lambda x: -x["btts"])
        self.cands["btts_leagues"] = [{"sb_league": x["league"]} for x in btts[:CANDS]]
        fh = sorted((x for x in lp if isinstance(x.get("fh_share"), (int, float))), key=lambda x: -x["fh_share"])
        self.cands["first_half_leagues"] = [{"sb_league": x["league"]} for x in fh[:CANDS]]
        th = read("output/first_half/top_home.json").get("teams") or []
        self.cands["top_home_first_half"] = [{"team": t["team"], "home_only": True} for t in th[:CANDS]
                                              if isinstance(t, dict) and t.get("team")]
        co = read("output/corners/consistency.json").get("teams") or []
        self.cands["steady_corners"] = [{"team": t["team"], "mean": t.get("mean")} for t in co[:CANDS]
                                         if isinstance(t, dict) and t.get("team") and t.get("mean") is not None]

    def roster_team(self, lid, name: tuple) -> tuple | None:
        """The one team of a league's list a game's name stands for: the exact name, else the only close one.
        Two close names (Paris FC and Paris Saint-Germain for 'Paris') is no match, never a guess."""
        roster = self.rosters.get(str(lid), ())
        if name in roster:
            return name
        hits = {t for t in roster if same_team(name, t)}
        return hits.pop() if len(hits) == 1 else None

    def match(self, cand: dict, row: dict) -> str | None:
        """'home' / 'away' / 'league' when the game belongs to this entry, else None."""
        h, a = norm(row.get("home")), norm(row.get("away"))
        if "sb_league" in cand:
            return "league" if f"{row.get('country', '')}: {row.get('comp', '')}" == cand["sb_league"] else None
        if "lid" in cand:                                        # ESPN entries: both teams must be in the league's list
            th, ta = self.roster_team(cand["lid"], h), self.roster_team(cand["lid"], a)
            if th is None or ta is None or th == ta:
                return None
            if "team" not in cand:
                return "league"
            t = norm(cand["team"])
            return "home" if th == t else "away" if ta == t and not cand.get("home_only") else None
        t = norm(cand["team"])
        side = "home" if same_team(t, h) else "away" if same_team(t, a) and not cand.get("home_only") else None
        if side is None:
            return None
        if "league" in cand and cand["league"] in ("NBA", "WNBA"):
            return side if cand["league"] in (row.get("comp") or "").upper() else None
        return side if t in (h, a) else None                    # no league list to check against: exact name only


def load_index(root: Path = ROOT) -> Index:
    p = root / "output" / "stat_lists" / "pick_index.json"
    try:
        doc = json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
    except ValueError:
        doc = None
    return Index(doc, root)


# ---------------------------------------------------------------- the bet a list makes on a game
def _main(lines: dict | None):
    """SportyBet's main line of an over/under market: the one priced closest to even."""
    best = None
    for ln, px in (lines or {}).items():
        if px and len(px) == 2 and px[0] and px[1]:
            gap = abs(1 / px[0] - 1 / px[1])
            if best is None or gap < best[0]:
                best = (gap, ln, px)
    return best and (best[1], best[2])


def offer(market: str, side: str, cand: dict, row: dict, source: str) -> dict | None:
    """{"key", "label", "price", ...} for this list's claim on this game, or None when SportyBet has no price."""
    team = row.get("home") if side == "home" else row.get("away") if side == "away" else None
    if source == "universe":
        p = ((row.get("last") or {}).get("p")) or {}
        if market == "btts_yes" and p.get("btts"):
            return {"key": "btts_yes", "price": p["btts"][0]}
        if market == "btts_no" and p.get("btts"):
            return {"key": "btts_no", "price": p["btts"][1]}
        if market == "over25" and p.get("ou2.5"):
            return {"key": "over25", "price": p["ou2.5"][0]}
        if market == "draw" and p.get("1x2") and len(p["1x2"]) == 3:
            return {"key": "draw", "price": p["1x2"][1]}
        if market == "win_team" and p.get("1x2") and len(p["1x2"]) == 3 and team:
            return {"key": f"win_{side}", "price": p["1x2"][0 if side == "home" else 2], "team": team}
        if market == "dc_team" and p.get("dc") and team:
            return {"key": f"dc_{side}", "price": p["dc"][0 if side == "home" else 2], "team": team}
        if market == "bb_over" and p.get("total"):
            return {"key": "bb_over", "price": p["total"][1], "line": p["total"][0]}
        return None
    lines = ((row.get("last") or {}).get("lines")) or {}
    if market in ("fh_over05", "fh_over15", "fh_under15"):
        ln = "0.5" if market == "fh_over05" else "1.5"
        px = (lines.get("first_half") or {}).get(ln)
        if px:
            over = market != "fh_under15"
            return {"key": f"first_half|{ln}|{'over' if over else 'under'}", "price": px[0 if over else 1]}
        return None
    mkt = "corners" if market.startswith("corners") else "bookings"
    m = _main(lines.get(mkt))
    if not m:
        return None
    ln, px = m
    over = True
    if market == "corners_steady":
        over = float(cand.get("mean") or 0) > float(ln)
    return {"key": f"{mkt}|{ln}|{'over' if over else 'under'}", "price": px[0 if over else 1], "line": ln,
            "side": "Over" if over else "Under"}


def settle_universe(key: str, res: dict | None, sport: str, line=None):
    """1 won / 0 lost / None not settled (no result, extra time, a push)."""
    if not res or res.get("h") is None:
        return None
    h, a = res["h"], res["a"]
    if sport == "football" and res.get("after_90"):
        return None
    if key == "btts_yes":
        return int(h > 0 and a > 0)
    if key == "btts_no":
        return int(not (h > 0 and a > 0))
    if key == "over25":
        return int(h + a > 2.5)
    if key == "draw":
        return int(h == a)
    if key == "win_home":
        return int(h > a)
    if key == "win_away":
        return int(a > h)
    if key == "dc_home":
        return int(h >= a)
    if key == "dc_away":
        return int(a >= h)
    if key == "bb_over" and line is not None:
        return None if h + a == line else int(h + a > line)
    return None


# ---------------------------------------------------------------- the book
def load_book(source: str, folder: Path = BOOKS) -> dict:
    p = folder / f"book_{source}.json"
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"picks": {}}
    except ValueError:
        return {"picks": {}}


def add_picks(book: dict, rows: list[dict], now: datetime, idx: Index, source: str) -> int:
    picks = book.setdefault("picks", {})
    live = []
    for r in rows:
        try:
            ko = datetime.fromisoformat(r["ko"].replace("Z", "+00:00"))
        except (KeyError, ValueError):
            continue
        if now < ko <= now + timedelta(hours=HORIZON_H) and r.get("id") and r.get("home") and r.get("away") and not is_variant(r):
            live.append(r)
    live.sort(key=lambda r: r["ko"])
    new = 0
    for lid, (title, src, market) in LISTS.items():
        if src != source:
            continue
        per_day: dict = {}
        for p in picks.values():
            if p["list"] == lid:
                per_day[p["date"]] = per_day.get(p["date"], 0) + 1
        done = False
        for rank, cand in enumerate(idx.cands.get(lid) or [], 1):
            for r in live:
                if (market == "bb_over") != (r.get("sport") == "basketball") and source == "universe":
                    continue
                pid = f"{lid}|{r['id']}"
                if pid in picks or per_day.get(r["ko"][:10], 0) >= PER_DAY:
                    continue
                side = idx.match(cand, r)
                if side is None:
                    continue
                o = offer(market, side, cand, r, source)
                if not o or not o.get("price") or o["price"] < MIN_PRICE:
                    continue
                label = LABEL[market].format(team=o.get("team", ""), line=o.get("line", ""), side=o.get("side", ""))
                picks[pid] = {"list": lid, "title": title, "date": r["ko"][:10], "ko": r["ko"], "event": r["id"],
                              "home": r["home"], "away": r["away"], "country": r.get("country"), "comp": r.get("comp"),
                              "entry": cand.get("team") or cand.get("league") or cand.get("sb_league"), "rank": rank,
                              "pick": label, "key": o["key"], "line": o.get("line"), "price": o["price"],
                              "sport": r.get("sport", "football"), "at": now.strftime("%Y-%m-%dT%H:%MZ"),
                              "result": None}
                new += 1
                done = True
                break
            if done:
                break
    return new


def grade_universe(book: dict, graded: list[dict]) -> int:
    by = {g.get("id"): g for g in graded}
    n = 0
    for p in book.get("picks", {}).values():
        g = by.get(p["event"])
        if p["result"] is not None or g is None:
            continue
        res = g.get("result")
        r = settle_universe(p["key"], res, g.get("sport", "football"), p.get("line"))
        p["result"] = "void" if r is None else int(r)
        p["score"] = None if not res or res.get("h") is None else f"{res['h']}-{res['a']}"
        n += 1
    return n


def grade_lines(book: dict, done: list[dict]) -> int:
    by = {g.get("id"): g for g in done}
    n = 0
    for p in book.get("picks", {}).values():
        g = by.get(p["event"])
        if p["result"] is not None or g is None:
            continue
        mkt, ln, side = p["key"].split("|")
        r = (((g.get("graded") or {}).get(mkt) or {}).get(ln) or {}).get(side)
        p["result"] = "void" if r is None else int(r)
        p["score"] = (g.get("result") or {}).get(mkt)
        n += 1
    return n


def _ci(rets: list[float], boots: int = 400) -> tuple[float, float]:
    rng = random.Random(7)  # noqa: S311 - a fixed-seed resample, not a secret
    means = sorted(sum(rng.choice(rets) for _ in rets) / len(rets) for _ in range(boots))
    return means[int(0.05 * boots)], means[int(0.95 * boots) - 1]


def _stats(ps: list[dict]) -> dict:
    g = [p for p in ps if p["result"] in (0, 1)]
    rets = [p["price"] - 1 if p["result"] else -1.0 for p in g]
    out = {"picks": len(ps), "graded": len(g), "won": sum(p["result"] for p in g),
           "roi": round(sum(rets) / len(g), 4) if g else None, "ready": False}
    if len(g) >= READY_N:
        lo, hi = _ci(rets)
        out.update({"roi_low": round(lo, 4), "roi_high": round(hi, 4), "ready": lo > 0})
    return out


def record(book: dict, source: str) -> dict:
    ps = list(book.get("picks", {}).values())
    lists = {}
    for lid, (title, src, _m) in LISTS.items():
        if src == source:
            lists[lid] = {"title": title, **_stats([p for p in ps if p["list"] == lid])}
    days: dict = {}
    for p in sorted(ps, key=lambda p: p["at"]):
        d = days.setdefault(p["date"], {})
        d.setdefault(p["list"], p)                       # the day's first pick of each list
    accas = []
    for day, firsts in sorted(days.items()):
        legs = sorted(firsts.values(), key=lambda p: p["price"])[:ACCA_LEGS]
        if len(legs) < ACCA_LEGS or any(p["result"] is None for p in legs):
            continue
        if any(p["result"] == "void" for p in legs):
            continue
        price = 1.0
        for p in legs:
            price *= p["price"]
        accas.append({"date": day, "price": round(price, 2), "won": int(all(p["result"] == 1 for p in legs))})
    rets = [a["price"] - 1 if a["won"] else -1.0 for a in accas]
    return {"source": source, "lists": lists, "all": _stats(ps),
            "acca": {"legs": ACCA_LEGS, "days": len(accas), "won": sum(a["won"] for a in accas),
                     "roi": round(sum(rets) / len(rets), 4) if rets else None, "last": accas[-7:]},
            "not_tested": NOT_TESTED, "ready_n": READY_N, "paper_only": True}


def write(book: dict, source: str, now: datetime, books: Path = BOOKS, out: Path = OUT) -> None:
    books.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    (books / f"book_{source}.json").write_text(json.dumps(book, ensure_ascii=False, separators=(",", ":")),
                                               encoding="utf-8")
    stamp = now.strftime("%Y-%m-%dT%H:%MZ")
    for k in (-1, 0, 1):
        day = (now + timedelta(days=k)).strftime("%Y-%m-%d")
        ps = sorted((p for p in book["picks"].values() if p["date"] == day), key=lambda p: p["ko"])
        if ps:
            (out / f"{source}_{day}.json").write_text(json.dumps(
                {"date": day, "source": source, "built": stamp, "paper_only": True, "picks": ps},
                ensure_ascii=False, indent=1), encoding="utf-8")
    (out / f"record_{source}.json").write_text(json.dumps({"built": stamp, **record(book, source)},
                                                          ensure_ascii=False, indent=1), encoding="utf-8")


def _run(source: str, rows: list[dict], graded: list[dict], now: datetime, root: Path) -> str:
    book = load_book(source, root / "data" / "list_picks")
    new = add_picks(book, rows, now, load_index(root), source)
    done = (grade_universe if source == "universe" else grade_lines)(book, graded)
    if new or done or not (root / "data" / "list_picks" / f"book_{source}.json").exists():
        write(book, source, now, root / "data" / "list_picks", root / "output" / "list_picks")
    a = _stats(list(book["picks"].values()))
    return f"list test ({source}): {new} new, {done} graded, {a['graded']}/{a['picks']} in the book"


def attach_universe(pending: dict, graded: list[dict], now: datetime, root: Path = ROOT) -> str:
    """The universe sweep's hook (full-time markets)."""
    return _run("universe", list(pending.values()), graded, now, root)


def attach_lines(pending: dict, done: list[dict], now: datetime, root: Path = ROOT) -> str:
    """The stat-lines recorder's hook (1st-half goals, corners, bookings)."""
    return _run("lines", [{**r, "sport": "football"} for r in pending.values()], done, now, root)
