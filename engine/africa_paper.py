"""
AFRICA PAPER BOARD - Africa Cup of Nations qualifiers (and the other CAF national-team qualifiers) and the
CAF club cups, rated and graded ON PAPER ONLY (the Architect, 2026-11-12: "The call is yours, do it", on the
proposal "put AFCON qualifiers (and the CAF club cups) on the board as paper only ... on money only after
100+ graded picks show a profit, and that call stays yours").

Why paper: on the worldwide sweep's record (8 Oct - 12 Nov 2026, 675 African games) the simple bets that
make money in the board's own leagues lose in African football (short favourite -2.2%, double chance
home-or-away -9.9%). So nothing here is staked, nothing is written where a bot reads
(output/multisport/, output/picks/), and no code is booked.

How a game is rated (every 3-hour universe sweep, from SportyBet's own list and prices):
  NATIONAL teams   the national-team Elo (engine/national_elo.py, the same ratings the UEFA Nations League
                   uses; it already holds every African international since 1990). The pick's chance is
                   the board's market anchor: market + MODEL_WEIGHT x (model - market) (engine/slate.py).
                   The pick is the option with the best expected value at a price of 1.20-2.60.
                   `value` is true when that value is above zero (the board's own bar).
  CLUB cups        no model exists for African clubs, so the pick is the bookmaker's own favourite line
                   (the shortest double chance or win price at 1.20-1.50), marked kind "market". It is there
                   to be graded, not because it is expected to win money.
A side the ratings do not know (fewer than 10 games, or a name that does not match) is also "market".

Each pick is graded from the sweep's own result (90 minutes) and kept in data/africa_paper/book.json;
output/africa_paper/africa_<date>.json is the day's board for the Control Room app and
output/africa_paper/record.json the running record per competition and kind. READY TO PROPOSE only with
100+ graded value picks and a return 2 standard errors above zero; then it goes to the Architect.
"""
from __future__ import annotations

import json
import math
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOOK = ROOT / "data" / "africa_paper" / "book.json"
OUT_DIR = ROOT / "output" / "africa_paper"
MODEL_WEIGHT = 0.25                 # engine/slate.py MODEL_WEIGHT (the board's market anchor)
PRICE_MIN, PRICE_MAX = 1.20, 2.60
SAFE_MAX = 1.50
READY_N = 100

_SKIP = re.compile(r"women|olympic|u-?\d\d|under \d\d|youth|futsal|beach", re.I)
_NATIONAL = re.compile(r"africa(n)? cup of nations|afcon|african nations championship|"
                       r"world cup.*qualif.*(caf|africa)|qualif.*(caf|africa).*world cup", re.I)
_CLUB = re.compile(r"\bcaf\b.*(champions league|confederations? cup|super cup)", re.I)

# SportyBet's (Sportradar's) spellings -> the international results dataset's. Normalised form.
ALIASES = {"cote d ivoire": "ivory coast", "cote divoire": "ivory coast", "congo dr": "dr congo",
           "democratic republic of congo": "dr congo", "dr congo": "dr congo", "congo republic": "congo",
           "republic of congo": "congo", "cape verde islands": "cape verde", "cabo verde": "cape verde",
           "swaziland": "eswatini", "the gambia": "gambia", "guinea bissau": "guinea-bissau",
           "sao tome and principe": "são tomé and príncipe", "sao tome e principe": "são tomé and príncipe",
           "central african rep": "central african republic", "car": "central african republic",
           "equat guinea": "equatorial guinea", "south sudan": "south sudan"}


def kind_of(row: dict) -> str | None:
    """'national' / 'club' for a game this board follows, else None."""
    comp = str(row.get("comp") or "")
    if row.get("sport") != "football" or _SKIP.search(comp):
        return None
    if _NATIONAL.search(comp):
        return "national"
    if _CLUB.search(comp):
        return "club"
    return None


def _fold(name: str) -> str:
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", s)).strip()


def team_name(name: str, known: dict[str, str]) -> str | None:
    """The dataset's name for a SportyBet team, or None when it can't be matched (never a guess)."""
    f = _fold(name)
    f = _fold(ALIASES.get(f, f))
    return known.get(f)


def known_teams(model) -> dict[str, str]:
    return {_fold(t): t for t, n in model.n.items() if n >= 10}


def fair(prices: list[float]) -> list[float]:
    inv = [1 / p for p in prices]
    s = sum(inv)
    return [x / s for x in inv]


def options(p: dict, home: str, away: str) -> list[dict]:
    """Every priced option of one game: {key, pick, price, market (margin-free chance), settle key}."""
    out: list[dict] = []
    x = p.get("1x2")
    f3 = fair(x) if x else None
    if x:
        for i, (key, text) in enumerate((("1", f"{home} to win"), ("X", "Draw"), ("2", f"{away} to win"))):
            out.append({"key": key, "pick": text, "price": x[i], "market": f3[i]})
    dc = p.get("dc")
    if dc and f3:
        for i, (key, text, mk) in enumerate((("1X", f"{home} or draw", f3[0] + f3[1]),
                                             ("12", f"{home} or {away}", f3[0] + f3[2]),
                                             ("X2", f"{away} or draw", f3[1] + f3[2]))):
            out.append({"key": key, "pick": text, "price": dc[i], "market": mk})
    for line in ("1.5", "2.5", "3.5"):
        ou = p.get(f"ou{line}")
        if ou:
            f2 = fair(ou)
            out.append({"key": f"O{line}", "pick": f"Over {line} goals", "price": ou[0], "market": f2[0]})
            out.append({"key": f"U{line}", "pick": f"Under {line} goals", "price": ou[1], "market": f2[1]})
    bt = p.get("btts")
    if bt:
        f2 = fair(bt)
        out.append({"key": "BY", "pick": "Both teams to score: yes", "price": bt[0], "market": f2[0]})
        out.append({"key": "BN", "pick": "Both teams to score: no", "price": bt[1], "market": f2[1]})
    return out


def model_chances(fp) -> dict[str, float]:
    """The model's chance of every option key, from a FixtureProbabilities."""
    return {"1": fp.p_home, "X": fp.p_draw, "2": fp.p_away,
            "1X": fp.p_home + fp.p_draw, "12": fp.p_home + fp.p_away, "X2": fp.p_draw + fp.p_away,
            "O1.5": fp.p_over_15, "U1.5": 1 - fp.p_over_15, "O2.5": fp.p_over_25, "U2.5": 1 - fp.p_over_25,
            "O3.5": fp.p_over_35, "U3.5": 1 - fp.p_over_35, "BY": fp.p_btts_yes, "BN": 1 - fp.p_btts_yes}


def settle(key: str, h: int, a: int) -> bool:
    t = h + a
    return {"1": h > a, "X": h == a, "2": a > h, "1X": h >= a, "12": h != a, "X2": a >= h,
            "O1.5": t > 1, "U1.5": t <= 1, "O2.5": t > 2, "U2.5": t <= 2, "O3.5": t > 3, "U3.5": t <= 3,
            "BY": h > 0 and a > 0, "BN": not (h > 0 and a > 0)}[key]


def make_pick(row: dict, model, known: dict[str, str], predict) -> dict | None:
    """The paper pick for one listed game, or None when nothing is priced in the band."""
    kind = kind_of(row)
    p = ((row.get("last") or row.get("first") or {}).get("p")) or {}
    if not kind or not p.get("1x2"):
        return None
    home, away = row.get("home") or "", row.get("away") or ""
    opts = [o for o in options(p, home, away) if o["price"]]
    base = {"id": row.get("id"), "league": row.get("comp"), "home": home, "away": away,
            "kickoff_utc": (row.get("ko") or "").replace("Z", ":00Z") if len(row.get("ko") or "") == 17 else row.get("ko"),
            "paper": True, "result": None}
    fp = None
    if kind == "national" and model is not None:
        h, a = team_name(home, known), team_name(away, known)
        if h and a:
            fp = predict(model, h, a)
    if fp is not None:
        mc = model_chances(fp)
        best = None
        for o in opts:
            if not (PRICE_MIN <= o["price"] <= PRICE_MAX) or o["key"] not in mc:
                continue
            chance = o["market"] + MODEL_WEIGHT * (mc[o["key"]] - o["market"])
            ev = chance * o["price"] - 1
            if best is None or ev > best["edge"]:
                best = {**o, "chance": chance, "edge": ev, "model": mc[o["key"]]}
        if best is None:
            return None
        return {**base, "kind": "model", "key": best["key"], "pick": best["pick"], "price": best["price"],
                "chance": round(best["chance"], 4), "model": round(best["model"], 4),
                "market": round(best["market"], 4), "edge": round(best["edge"], 4), "value": best["edge"] > 0,
                "xg": [fp.lambda_home, fp.lambda_away]}
    safe = [o for o in opts if o["key"] in ("1", "2", "1X", "X2", "12") and PRICE_MIN <= o["price"] <= SAFE_MAX]
    if not safe:
        return None
    o = max(safe, key=lambda z: z["market"])
    return {**base, "kind": "market", "key": o["key"], "pick": o["pick"], "price": o["price"],
            "chance": round(o["market"], 4), "model": None, "market": round(o["market"], 4),
            "edge": round(o["market"] * o["price"] - 1, 4), "value": False,
            "why_market": "club cup: no model for African clubs" if kind == "club" else "a side the ratings do not know"}


def load_book(path: Path | None = None) -> dict:
    try:
        return json.loads((path or BOOK).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def add_picks(book: dict, pending_rows, now: datetime, model, predict) -> int:
    """A pick for every followed game that has not kicked off and has none yet. The pick is frozen at the
    price first seen with it (never re-picked), like the board's frozen codes."""
    known = known_teams(model) if model is not None else {}
    n = 0
    for row in pending_rows:
        rid = row.get("id")
        if not rid or rid in book or not kind_of(row):
            continue
        try:
            ko = datetime.strptime(row["ko"], "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc)
        except (KeyError, ValueError):
            continue
        if ko <= now:
            continue
        pick = make_pick(row, model, known, predict)
        if pick:
            pick["picked_at"] = now.strftime("%Y-%m-%dT%H:%MZ")
            book[rid] = pick
            n += 1
    return n


def grade(book: dict, graded_rows) -> int:
    """Settle the book's open picks from the sweep's graded games (90-minute score)."""
    n = 0
    for row in graded_rows:
        b = book.get(row.get("id"))
        res = row.get("result") or {}
        if not b or b.get("result") or res.get("h") is None or res.get("a") is None:
            continue
        won = settle(b["key"], int(res["h"]), int(res["a"]))
        b.update(result="won" if won else "lost", ft=f"{res['h']}-{res['a']}",
                 pnl=round(b["price"] - 1, 4) if won else -1.0)
        n += 1
    return n


def record(book: dict) -> dict:
    """The running record: all picks, value picks only, and per competition / kind."""
    def line(rows: list[dict]) -> dict:
        done = [r for r in rows if r.get("result")]
        n = len(done)
        if not n:
            return {"picks": len(rows), "graded": 0}
        pnl = [r["pnl"] for r in done]
        mean = sum(pnl) / n
        se = math.sqrt(sum((x - mean) ** 2 for x in pnl) / n / n) if n > 1 else None
        return {"picks": len(rows), "graded": n, "won": sum(r["result"] == "won" for r in done),
                "return": round(mean, 4), "se": round(se, 4) if se is not None else None,
                "ready": bool(n >= READY_N and se is not None and mean - 2 * se > 0)}
    rows = list(book.values())
    by: dict[str, list[dict]] = {}
    for r in rows:
        by.setdefault(f"{r.get('league')} | {r.get('kind')}", []).append(r)
    return {"all": line(rows), "value_only": line([r for r in rows if r.get("value")]),
            "model": line([r for r in rows if r.get("kind") == "model"]),
            "market": line([r for r in rows if r.get("kind") == "market"]),
            "by": {k: line(v) for k, v in sorted(by.items())},
            "note": "PAPER ONLY. Ready to propose = 100+ graded picks with a return 2 standard errors above zero."}


def write(book: dict, now: datetime, book_path: Path | None = None, out_dir: Path | None = None) -> list[str]:
    """Save the book, the record, and one board file per kick-off date still worth showing (last 3 days on)."""
    bp, od = book_path or BOOK, out_dir or OUT_DIR
    bp.parent.mkdir(parents=True, exist_ok=True)
    od.mkdir(parents=True, exist_ok=True)
    bp.write_text(json.dumps(book, indent=1, ensure_ascii=False), encoding="utf-8")
    rec = record(book)
    (od / "record.json").write_text(json.dumps({"updated": now.strftime("%Y-%m-%dT%H:%MZ"), **rec}, indent=1,
                                               ensure_ascii=False), encoding="utf-8")
    days: dict[str, list[dict]] = {}
    for r in book.values():
        d = str(r.get("kickoff_utc") or "")[:10]
        if d and (now.date() - datetime.strptime(d, "%Y-%m-%d").date()).days <= 3:
            days.setdefault(d, []).append(r)
    written = []
    for d, picks in days.items():
        picks.sort(key=lambda r: (r.get("kickoff_utc") or "", r.get("home") or ""))
        (od / f"africa_{d}.json").write_text(json.dumps(
            {"date": d, "paper": True, "generated_at": now.strftime("%Y-%m-%dT%H:%MZ"),
             "note": "Paper only: never staked, no codes.", "picks": picks}, indent=1, ensure_ascii=False),
            encoding="utf-8")
        written.append(d)
    return sorted(written)


def attach(pending: dict, graded: list[dict], now: datetime) -> str:
    """The sweep's hook: pick the followed games it has listed, grade the ones it has just graded, save."""
    from engine import national_elo
    book = load_book()
    try:
        from data import international_source as intl
        intl._fetch_csv(national_elo.CSV.parent)        # the results file, at most 12 h old
        model = national_elo.build()
    except Exception as e:  # noqa: BLE001 - no ratings file: national games fall back to the market pick
        model = None
        why = f" (no national ratings: {type(e).__name__})"
    else:
        why = ""
    new = add_picks(book, list(pending.values()), now, model, national_elo.predict)
    done = grade(book, graded)
    if new or done or not BOOK.exists():
        write(book, now)
    rec = record(book)["all"]
    return f"africa paper: {new} new, {done} graded, {rec.get('graded', 0)}/{rec.get('picks', 0)} in the book{why}"
