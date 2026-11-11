"""
TENNIS walk-forward backtest vs the closing price (framework#345, multi-sport rollout; shadow from 2026-11-05).

Source: tennis-data.co.uk (free ATP + WTA results with Pinnacle and market-average CLOSING prices). Every match is
replayed in date order, one rating pool per tour:

  - Elo (overall + per-surface mix); each setting tried is counted (K x surface weight x market weight);
  - the best setting is chosen on the FIRST years and reported on the LATER years only (no peeking);
  - judged by Brier / log loss against Pinnacle's de-vigged closing chance (the 'source of truth');
    then a flat-stake test: back a side when the model beats the de-vigged Pinnacle close by an edge bar,
    priced at the market-average close (bookmaker prices; exchange commission is not modelled).

Side orientation is by player-name order, never winner-first, so the winner column cannot leak into the model.
Missing odds read PENDING (a row without a price is skipped, never invented). Record only: nothing here changes a
stake, a bar, a threshold or the live switch.

  python backtest/tennis_backtest.py      writes backtest/TENNIS_STUDY.md
"""
from __future__ import annotations

import itertools
import math
import re
import sys
import urllib.request
import zipfile
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "backtest" / "TENNIS_STUDY.md"
SITE = "https://www.tennis-data.co.uk/"
YEARS = tuple(range(2019, 2026))
TUNE_YEARS = (2019, 2022)               # chosen here; 2023 onward is the held-out test
MIN_GAMES, ELO_START = 5, 1500.0
KS = (16.0, 32.0, 48.0)
SURF_W = (0.0, 0.5)                      # share of the rating taken from the surface-only Elo
MKT_W = (0.0, 0.25, 0.5)                 # share of the market's logit blended into the model (anchored model)
EDGES = (0.03, 0.05)
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def col_index(ref: str) -> int:
    n = 0
    for ch in re.match(r"[A-Z]+", ref).group():
        n = n * 26 + ord(ch) - 64
    return n - 1


def read_xlsx(blob: bytes) -> list[dict]:
    """First sheet of an .xlsx as a list of {header: value} rows (stdlib only)."""
    z = zipfile.ZipFile(BytesIO(blob))
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).iter(NS + "si"):
            shared.append("".join(t.text or "" for t in si.iter(NS + "t")))
    rows = []
    for row in ET.fromstring(z.read("xl/worksheets/sheet1.xml")).iter(NS + "row"):
        cells = {}
        for c in row.iter(NS + "c"):
            v = c.find(NS + "v")
            if c.get("t") == "inlineStr":
                val = "".join(t.text or "" for t in c.iter(NS + "t"))
            elif v is None or v.text is None:
                continue
            elif c.get("t") == "s":
                val = shared[int(v.text)]
            else:
                val = v.text
            cells[col_index(c.get("r"))] = val
        rows.append(cells)
    if not rows:
        return []
    head = rows[0]
    return [{head[i]: v for i, v in r.items() if i in head} for r in rows[1:]]


def num(x):
    try:
        v = float(x)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def parse(rows: list[dict], tour: str) -> list[dict]:
    """Completed matches with a Pinnacle close; sides ordered by name (not winner-first)."""
    out = []
    for r in rows:
        d, w, lo = num(r.get("Date")), r.get("Winner"), r.get("Loser")
        pw, pl = num(r.get("PSW")), num(r.get("PSL"))
        if d is None or not w or not lo or w == lo or not pw or not pl or pw <= 1 or pl <= 1:
            continue
        if str(r.get("Comment", "Completed")).strip().lower() != "completed":
            continue                      # retirements / walkovers: the price was for a full match
        day = (datetime(1899, 12, 30) + timedelta(days=d)).strftime("%Y-%m-%d")
        aw, al = num(r.get("AvgW")), num(r.get("AvgL"))
        mw, ml = num(r.get("MaxW")), num(r.get("MaxL"))
        a_first = str(w) < str(lo)
        a, b = (w, lo) if a_first else (lo, w)
        pa, pb = (pw, pl) if a_first else (pl, pw)
        qa, qb = (aw, al) if a_first else (al, aw)
        xa, xb = (mw, ml) if a_first else (ml, mw)       # best price across the books (None when absent)
        wr, lr = num(r.get("WRank")), num(r.get("LRank"))
        ra, rb = (wr, lr) if a_first else (lr, wr)
        out.append({"day": day, "tour": tour, "surface": str(r.get("Surface", "")), "a": str(a), "b": str(b),
                    "y": 1.0 if a_first else 0.0, "pa": pa, "pb": pb, "qa": qa, "qb": qb, "xa": xa, "xb": xb,
                    "ra": ra, "rb": rb, "bo": int(num(r.get("Best of")) or 3),
                    "series": str(r.get("Series", "")).strip(), "round": str(r.get("Round", "")).strip(),
                    "court": str(r.get("Court", "")).strip()})
    return out


def devig(pa: float, pb: float) -> float:
    x, y = 1 / pa, 1 / pb
    return x / (x + y)


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "olp-xdv-backtest"})
    with urllib.request.urlopen(req, timeout=90) as r:  # noqa: S310 (fixed https URL)
        return r.read()


def load(get=fetch) -> list[dict]:
    try:
        page = get(SITE + "alldata.php").decode("latin-1", "replace")
    except Exception as ex:
        print(f"index not loaded ({type(ex).__name__})")
        return []
    games = []
    for tour, suffix in (("ATP", ""), ("WTA", "w")):
        for y in YEARS:
            m = re.search(r'HREF="([^"]*/%d%s/%d\.xlsx)"' % (y, suffix, y), page, re.I)
            if not m:
                print(f"{tour} {y}: no link")
                continue
            try:
                games += parse(read_xlsx(get(SITE + m.group(1))), tour)
            except Exception as ex:  # a year that will not load is PENDING, never invented
                print(f"{tour} {y}: not loaded ({type(ex).__name__})")
    games.sort(key=lambda g: (g["day"], g["a"], g["b"]))
    for g in games:
        g["year"] = int(g["day"][:4])
        g["mkt"] = devig(g["pa"], g["pb"])
    return games


def logit(p: float) -> float:
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def sig(z: float) -> float:
    return 1 / (1 + math.exp(-z))


def replay(games: list[dict], k: float, sw: float) -> list[float | None]:
    """Elo chance that side a wins BEFORE each match (None while a player has < MIN_GAMES), then learn."""
    r, rs, n, out = {}, {}, {}, []
    for g in games:
        ta, tb, s = (g["tour"], g["a"]), (g["tour"], g["b"]), g["surface"]
        sa, sb = (g["tour"], g["a"], s), (g["tour"], g["b"], s)
        oa = (1 - sw) * r.get(ta, ELO_START) + sw * rs.get(sa, ELO_START)
        ob = (1 - sw) * r.get(tb, ELO_START) + sw * rs.get(sb, ELO_START)
        e = 1 / (1 + 10 ** ((ob - oa) / 400))
        out.append(e if n.get(ta, 0) >= MIN_GAMES and n.get(tb, 0) >= MIN_GAMES else None)
        d = k * (g["y"] - e)
        r[ta], r[tb] = r.get(ta, ELO_START) + d, r.get(tb, ELO_START) - d
        es = 1 / (1 + 10 ** ((rs.get(sb, ELO_START) - rs.get(sa, ELO_START)) / 400))
        ds = k * (g["y"] - es)
        rs[sa], rs[sb] = rs.get(sa, ELO_START) + ds, rs.get(sb, ELO_START) - ds
        n[ta], n[tb] = n.get(ta, 0) + 1, n.get(tb, 0) + 1
    return out


def blend(p: float, mkt: float, w: float) -> float:
    return sig((1 - w) * logit(p) + w * logit(mkt))


def evaluate(games, probs, years, mw=0.0) -> dict:
    n = hits = 0
    b = ll = lm = 0.0
    for g, p in zip(games, probs):
        if p is None or not (years[0] <= g["year"] <= years[1]):
            continue
        q = blend(p, g["mkt"], mw)
        n += 1
        b += (q - g["y"]) ** 2
        ll -= math.log(q if g["y"] else 1 - q)
        lm -= math.log(g["mkt"] if g["y"] else 1 - g["mkt"])
        hits += (q > 0.5) == (g["y"] == 1.0)
    return {"n": n, "brier": b / n if n else None, "ll": ll / n if n else None,
            "mkt_ll": lm / n if n else None, "hit": hits / n if n else None}


def bets(games, probs, years, mw, edge) -> dict:
    """Flat 1-unit bets on a side the model rates `edge` above Pinnacle's de-vigged close, at the average close."""
    n = 0
    pnl = 0.0
    for g, p in zip(games, probs):
        if p is None or not (years[0] <= g["year"] <= years[1]) or not g["qa"] or not g["qb"]:
            continue
        q = blend(p, g["mkt"], mw)
        for side_p, side_m, price, won in ((q, g["mkt"], g["qa"], g["y"] == 1.0),
                                           (1 - q, 1 - g["mkt"], g["qb"], g["y"] == 0.0)):
            if side_p - side_m >= edge:
                n += 1
                pnl += (price - 1) if won else -1.0
    return {"n": n, "roi": pnl / n if n else None}


def run(games: list[dict]) -> str:
    last = max(g["year"] for g in games)
    test = (TUNE_YEARS[1] + 1, last)
    cache = {(k, sw): replay(games, k, sw) for k, sw in itertools.product(KS, SURF_W)}
    combos = list(itertools.product(KS, SURF_W, MKT_W))
    tries = len(combos) + len(EDGES) * 2
    tuned = {c: evaluate(games, cache[c[:2]], TUNE_YEARS, c[2]) for c in combos}
    ok = {c: t for c, t in tuned.items() if t["n"] >= 500}
    best = min(ok, key=lambda c: ok[c]["ll"]) if ok else None
    plain = (32.0, 0.0, 0.0)
    rp = evaluate(games, cache[plain[:2]], test, plain[2])
    rb = evaluate(games, cache[best[:2]], test, best[2]) if best else None
    tour_n = {t: sum(1 for g in games if g["tour"] == t) for t in ("ATP", "WTA")}
    mkt_hit = [(g["mkt"] > 0.5) == (g["y"] == 1.0) for g in games if test[0] <= g["year"] <= test[1]]

    def line(name, r):
        if not r or not r["n"]:
            return f"| {name} | 0 | PENDING | PENDING | PENDING | PENDING |"
        return f"| {name} | {r['n']} | {r['brier']:.4f} | {r['ll']:.4f} | {r['hit']:.1%} | {r['mkt_ll']:.4f} |"

    made = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    L = ["# Tennis walk-forward backtest", "",
         f"Made {made} by `backtest/tennis_backtest.py` (framework#345). {len(games)} completed matches with a "
         f"Pinnacle close (ATP {tour_n['ATP']}, WTA {tour_n['WTA']}; tennis-data.co.uk). Tries counted: **{tries}** "
         f"(K x surface mix x market weight, then the edge bars on two models); chosen on "
         f"{TUNE_YEARS[0]}-{TUNE_YEARS[1]}, reported on **{test[0]}-{test[1]} only**.", "",
         "| Rule (held-out years) | Matches | Brier | Log loss | Winner hit rate | Pinnacle close log loss |",
         "|---|---|---|---|---|---|",
         line("Elo K32 alone (no market)", rp)]
    if rb:
        L.append(line(f"Best on tuning years: K{best[0]:.0f}, surface {best[1]:.0%}, market weight {best[2]:.0%}", rb))
    if mkt_hit:
        L += ["", f"Pinnacle's favourite won {sum(mkt_hit) / len(mkt_hit):.1%} of the same held-out matches."]
    L += ["", "## Flat-stake test (model vs Pinnacle close, priced at the market-average close)", "",
          "| Setting | Edge bar | Bets | ROI per unit |", "|---|---|---|---|"]
    for name, c in (("Elo K32 alone", plain), ("Best on tuning years", best)):
        if not c:
            continue
        for e in EDGES:
            r = bets(games, cache[c[:2]], test, c[2], e)
            L.append(f"| {name} | {e:.0%} | {r['n']} | " + (f"{r['roi']:+.1%}" if r["n"] else "PENDING") + " |")
    L += ["", "## Reading", ""]
    if rp["n"]:
        L.append(f"- Elo alone log loss {rp['ll']:.4f} vs Pinnacle's close {rp['mkt_ll']:.4f}: "
                 + ("the Elo beats the closing price." if rp["ll"] < rp["mkt_ll"] else
                    "the closing price is the better chance; the Elo adds nothing on its own."))
    if rb and rb["n"]:
        L.append(f"- Market-anchored best setting log loss {rb['ll']:.4f} vs Pinnacle {rb['mkt_ll']:.4f}: "
                 + ("some information beyond the price." if rb["ll"] < rb["mkt_ll"] else
                    "no information beyond the price held-out: price the sport off the exchange."))
    L += [f"- {tries} tries made; the held-out lines are the honest ones, and any ROI above is one of them, not a result to bank.",
          "- Bookmaker average prices carry a margin; exchange commission is not modelled. Rows without a price are skipped.",
          "- Record only: nothing here changes a stake, a bar, a threshold or the live switch."]
    return "\n".join(L) + "\n"


def main() -> int:
    games = load()
    if len(games) < 3000:
        print(f"only {len(games)} matches read: NO DATA - PENDING")
        return 1
    text = run(games)
    OUT.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
