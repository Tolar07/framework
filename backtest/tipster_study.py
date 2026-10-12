"""
TIPSTER STUDY — what the slips tipsters post on X actually return (Architect
2026-10-08, via the coordinator session). Reads graded slips (engine/tipsters.py)
from a folder and writes TIPSTER_STUDY.md next to them:
  1. per poster: slips, legs, how often slips and legs landed against the chance
     their prices implied, £1 return per slip with its standard error;
  2. legs by market and by price band;
  3. consensus: does a game that appears on several slips that day land more often?
  4. official "Top Picks" codes vs everyone else, against the bookmaker's margin;
  5. closing-line value (Architect 2026-10-12: "add closing-line value to the
     tipster study"): each leg is found in the universe sweep (data/universe/,
     by SportyBet event id, else the strict name match) and its entry price
     compared with SportyBet's last price before kick-off. Winning or losing is
     noise at these sample sizes; a tipster who knows something gets prices
     that shorten before kick-off.
Implied chance = 1 / price, margin INCLUDED (a slip shows only the chosen
price), so a fairly priced leg lands a little MORE often than implied — the
margin-free bar is ~5% above it. Same bar as the paper book: nothing is trusted
before 100+ slips, and nothing is promoted without the Architect. Paper only.

    python backtest/tipster_study.py --dir <folder>
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime
from math import sqrt
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from engine import tipsters as tp  # noqa: E402
from engine import universe as uv  # noqa: E402

MIN_SLIPS = 100
BANDS = ((1.0, 1.3), (1.3, 1.6), (1.6, 2.0), (2.0, 3.0), (3.0, 1000.0))


def _se(xs: list[float]) -> float:
    if len(xs) < 2:
        return float("inf")
    m = sum(xs) / len(xs)
    return sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1) / len(xs))


def _slip_row(name: str, slips: list[dict]) -> str:
    g = [s for s in slips if s["status"] in ("won", "lost")]
    if not g:
        return f"| {name} | {len(slips)} | — | — | — | — |"
    pnl = [s["payout"] - 1 for s in g]
    won = sum(s["status"] == "won" for s in g)
    legs = [leg for s in g for leg in s["legs"] if leg.get("result") in ("win", "lose", "half_win", "half_lose")]
    lw = sum(leg["result"] in ("win", "half_win") for leg in legs)
    imp = sum(s["implied"] for s in g) / len(g)
    return (f"| {name} | {len(slips)} ({len(g)} graded) | {won}/{len(g)} landed vs {imp:.1%} implied | "
            f"{lw}/{len(legs)} legs | {sum(pnl) / len(pnl):+.0%} ± {_se(pnl):.0%} | "
            f"{'learning' if len(g) < MIN_SLIPS else 'enough to judge'} |")


# ── closing-line value ───────────────────────────────────────────────────────
DC_PAIRS = {"1x": (0, 1), "12": (0, 2), "x2": (1, 2)}


def _devig(ps: list[float]) -> list[float]:
    inv = [1 / p for p in ps]
    return [i / sum(inv) for i in inv]


def leg_quote(leg: dict, p: dict) -> tuple[float, float | None] | None:
    """(SportyBet price, margin-free chance) of the leg's own outcome in one
    universe price snapshot `p`, or None when the sweep doesn't keep that market
    or line. Double chance is priced from the 1X2 (margin removed there)."""
    m, sel, line = leg.get("market"), leg.get("selection"), leg.get("line")
    side = {"home": 0, "draw": 1, "away": 2}
    if leg.get("sport") == "football":
        if m == "1x2" and sel in side:
            row = p.get("1x2")
            return (row[side[sel]], _devig(row)[side[sel]]) if row else None
        if m in ("1up", "2up") and sel in side:
            # Both teams can go 1 (or 2) up in the same game, so the row's
            # chances don't add up to one: no margin-free chance, price only.
            row = p.get(m)
            return (row[side[sel]], None) if row else None
        if m == "dc" and sel in DC_PAIRS and p.get("dc") and p.get("1x2"):
            i, j = DC_PAIRS[sel]
            fair = _devig(p["1x2"])
            return p["dc"][("1x", "12", "x2").index(sel)], fair[i] + fair[j]
        if m == "ou" and sel in ("over", "under") and line is not None:
            row = p.get(f"ou{line}")
            k = 0 if sel == "over" else 1
            return (row[k], _devig(row)[k]) if row else None
        if m == "btts" and sel in ("yes", "no") and p.get("btts"):
            k = 0 if sel == "yes" else 1
            return p["btts"][k], _devig(p["btts"])[k]
        return None
    if leg.get("sport") == "basketball":
        if m == "win" and sel in ("home", "away") and p.get("win"):
            k = 0 if sel == "home" else 1
            return p["win"][k], _devig(p["win"])[k]
        if m == "total" and sel in ("over", "under") and p.get("total") and line == p["total"][0]:
            k = 1 if sel == "over" else 2
            return p["total"][k], _devig(p["total"][1:])[k - 1]
        if m == "spread" and sel in ("home", "away") and p.get("hcp") and line is not None:
            hl = line if sel == "home" else -line              # leg line is the SELECTED side's
            if hl == p["hcp"][0]:
                k = 1 if sel == "home" else 2
                return p["hcp"][k], _devig(p["hcp"][1:])[k - 1]
    return None


class UniverseIndex:
    """Universe rows by SportyBet event id, and by the strict name match."""

    def __init__(self, rows: list[dict]):
        self.by_id = {r["id"]: r for r in rows if r.get("id")}
        self.by_sport: dict[str, list[dict]] = defaultdict(list)
        for r in rows:
            if r.get("ko") and r.get("home") and r.get("away"):
                self.by_sport[r["sport"]].append({**r, "kickoff_utc": r["ko"]})

    def find(self, leg: dict) -> dict | None:
        row = self.by_id.get((leg.get("sb") or {}).get("event") or "")
        if row is not None:
            return row
        if not (leg.get("home") and leg.get("away") and leg.get("kickoff")):
            return None
        from data import flashscore_results as fr
        return fr.find_result(self.by_sport.get(leg.get("sport") or "", []),
                              leg["home"], leg["away"], leg["kickoff"][:10])


def leg_clv(leg: dict, entry_at: str | None, idx: UniverseIndex) -> dict | None:
    """The leg against the close. None when the game or market isn't in the
    sweep, or the entry price was read after the sweep's last look (no close
    to compare with). clv = entry / closing − 1, as for our own picks (order 20);
    ev_close = closing fair chance × entry − 1 (margin removed); move = how far
    the market moved TOWARDS the leg between the sweep's first and last look,
    in points of fair chance — independent of when the entry price was read."""
    row = idx.find(leg)
    if row is None or not leg.get("price"):
        return None
    close = leg_quote(leg, row["last"]["p"])
    first = leg_quote(leg, row["first"]["p"])
    if close is None or not entry_at or entry_at > row["last"]["at"]:
        return None
    return {"clv": leg["price"] / close[0] - 1,
            "ev_close": close[1] * leg["price"] - 1 if close[1] is not None else None,
            "move": (close[1] - first[1]) if first and first[1] is not None and close[1] is not None else None,
            "lead_h": (datetime.fromisoformat(row["ko"].replace("Z", "+00:00"))
                       - datetime.fromisoformat(entry_at.replace("Z", "+00:00"))).total_seconds() / 3600}


def _clv_row(name: str, xs: list[dict]) -> str:
    if not xs:
        return f"| {name} | 0 | — | — | — | — |"
    c = [x["clv"] for x in xs]
    e = [x["ev_close"] for x in xs if x["ev_close"] is not None]
    mv = [x["move"] for x in xs if x["move"] is not None]
    lead = sorted(x["lead_h"] for x in xs)[len(xs) // 2]
    return (f"| {name} | {len(xs)} | {sum(c) / len(c):+.1%} ± {_se(c):.1%} · beat {sum(v > 0 for v in c) / len(c):.0%} | "
            f"{f'{sum(e) / len(e):+.1%} ± {_se(e):.1%}' if e else '—'} | "
            f"{f'{100 * sum(mv) / len(mv):+.2f} ± {100 * _se(mv):.2f} pts' if mv else '—'} | {lead:.0f} h |")


def clv_section(slips: list[dict], folder: Path, rows: list[dict] | None = None) -> tuple[list[str], dict]:
    """The study's closing-line section and its nameless aggregates."""
    rows = uv.load_graded() if rows is None else rows
    L = ["", "## Closing-line value — did the price move towards the tip?", "",
         "Each leg is looked up in the universe sweep (`data/universe/`; every SportyBet football and "
         "basketball game, first and last price before kick-off, swept every 3 h) and compared with "
         "SportyBet's LAST price there. CLV = entry price / closing price − 1 (positive = the price "
         "shortened after the tip, as for our own picks, order 20). EV vs close = the closing price's "
         "margin-free chance × the entry price − 1 (a fair bet reads 0; the bookmaker's margin makes "
         "the average leg about −5%). Move = how many points of margin-free chance the market moved "
         "TOWARDS the leg between the sweep's first and last look — it doesn't depend on when the "
         "entry price was read. Entry price: a SportyBet leg's price when its code was DECODED "
         "(SportyBet's share API gives today's price, not the price at posting — decode soon after "
         "collecting), a bet365 leg's price as posted. A leg whose entry price was read after the "
         "sweep's last look has no close and is left out, as is a market the sweep doesn't keep "
         "(handicaps, team totals, specials other than 1UP/2UP). 1UP/2UP legs get a CLV but no EV or move: "
         "both teams can go a goal up in the same game, so that row's chances don't add up to one.", ""]
    if not rows:
        L.append("No universe sweep data in this checkout (`data/universe/`) — NO DATA — PENDING.")
        return L, {}
    idx = UniverseIndex(rows)
    decoded = tp._done(folder, "decoded")
    out: list[tuple[dict, dict, dict]] = []
    looked = 0
    for s in slips:
        entry_at = ((decoded.get(s["post_url"]) or {}).get("decoded_at") if s.get("book") == "sportybet"
                    else s.get("posted_at"))
        entry_at = entry_at.replace("+00:00", "Z")[:16] + "Z" if entry_at else None
        for leg in s["legs"]:
            looked += 1
            r = leg_clv(tp.remap(leg), entry_at, idx)
            if r is not None:
                out.append((s, leg, r))
    L += [f"{len(out)} of {looked} legs measured against the close.", "",
          "| Group | legs | CLV ± se · beat close | EV vs close ± se | moved towards the leg | median entry → kick-off |",
          "|---|---|---|---|---|---|"]
    L.append(_clv_row("all legs", [r for _, _, r in out]))
    for book in ("sportybet", "bet365"):
        L.append(_clv_row(f"{book} slips", [r for s, _, r in out if s.get("book") == book]))
    L.append(_clv_row("official Top Picks", [r for s, _, r in out if s.get("official")]))
    for cls in ("aligned", "middle", "special", "risky"):
        L.append(_clv_row(f"class: {cls}", [r for _, leg, r in out if tp.leg_class(tp.remap(leg)) == cls]))
    by_p: dict[str, list[dict]] = defaultdict(list)
    for s, _, r in out:
        by_p[s.get("poster") or "?"].append(r)
    L += ["", "Per poster (nothing trusted before 100+ legs measured):", "",
          "| Poster | legs | CLV ± se · beat close | EV vs close ± se | moved towards the leg | median entry → kick-off |",
          "|---|---|---|---|---|---|"]
    for p in sorted(by_p, key=lambda p: -len(by_p[p])):
        L.append(_clv_row(p, by_p[p]))
    L += ["", "Reading it: a poster with a CLV and a 'moved towards' clearly above zero over 100+ legs is "
          "spotting prices before the market corrects them — the one sign of real skill. Near zero "
          "with a high landing rate means they pick favourites the price already describes."]
    agg = {"legs_measured": len(out)}
    for cls in ("aligned", "middle", "special", "risky"):
        xs = [r for _, leg, r in out if tp.leg_class(tp.remap(leg)) == cls]
        if xs:
            ev = [x["ev_close"] for x in xs if x["ev_close"] is not None]
            agg[cls] = {"legs": len(xs), "clv_avg": sum(x["clv"] for x in xs) / len(xs),
                        "ev_close_avg": sum(ev) / len(ev) if ev else None}
    return L, agg


def write(folder: Path, out: Path, universe_rows: list[dict] | None = None) -> str:
    slips = tp.load_graded(folder)
    L = ["# TIPSTER STUDY — slips posted on X, graded", "",
         "Written by `backtest/tipster_study.py` from graded slips (`engine/tipsters.py`). Implied chance = "
         "1 / price with the bookmaker's margin included — a fairly priced leg lands ~5% more often than that. "
         f"Nothing is trusted before {MIN_SLIPS}+ graded slips; nothing is promoted without the Architect. Paper only.", ""]
    if not slips:
        L.append("No graded slip yet — NO DATA — PENDING.")
        out.write_text("\n".join(L) + "\n", encoding="utf-8")
        return "\n".join(L)
    graded = [s for s in slips if s["status"] in ("won", "lost")]
    L += [f"{len(slips)} slips looked at: {len(graded)} graded, "
          f"{sum(s['status'] == 'ungradable' for s in slips)} ungradable (a leg's result or market couldn't be read).", "",
          "## Per poster", "", "| Poster | slips | slips landed | legs landed | £1 a slip: return ± se | verdict |",
          "|---|---|---|---|---|---|"]
    by_poster: dict[str, list[dict]] = defaultdict(list)
    for s in slips:
        by_poster[s["poster"] or "?"].append(s)
    for p in sorted(by_poster, key=lambda p: -len(by_poster[p])):
        L.append(_slip_row(p, by_poster[p]))
    # a leg read with no price (bet365 team totals, 10 Oct) has no implied chance
    legs = [leg for s in graded for leg in s["legs"]
            if leg.get("result") in ("win", "lose", "half_win", "half_lose") and leg.get("price")]
    L += ["", "## Legs by market", "", "| Market | legs | landed | implied (avg) |", "|---|---|---|---|"]
    by_m: dict[str, list[dict]] = defaultdict(list)
    for leg in legs:
        by_m[f"{leg['sport']} {leg['market']}"].append(leg)
    for k in sorted(by_m, key=lambda k: -len(by_m[k])):
        xs = by_m[k]
        L.append(f"| {k} | {len(xs)} | {sum(x['result'] in ('win', 'half_win') for x in xs) / len(xs):.0%} | "
                 f"{sum(1 / x['price'] for x in xs) / len(xs):.0%} |")
    L += ["", "## Legs by price band", "", "| Price | legs | landed | implied (avg) |", "|---|---|---|---|"]
    for lo, hi in BANDS:
        xs = [x for x in legs if lo <= x["price"] < hi]
        if xs:
            L.append(f"| {lo:.2f}–{hi:.2f} | {len(xs)} | {sum(x['result'] in ('win', 'half_win') for x in xs) / len(xs):.0%} | "
                     f"{sum(1 / x['price'] for x in xs) / len(xs):.0%} |")
    count: dict[tuple[str, str, str], int] = defaultdict(int)
    for s in graded:
        for game in {(s["posted_at"][:10], (leg.get("home") or "").lower(), (leg.get("away") or "").lower())
                     for leg in s["legs"]}:
            count[game] += 1
    L += ["", "## Consensus — a game on several slips the same day", "",
          "| Slips carrying the game | legs | landed | implied (avg) |", "|---|---|---|---|"]
    for lo, hi, name in ((1, 2, "1"), (2, 3, "2"), (3, 999, "3+")):
        xs = [leg for s in graded for leg in s["legs"]
              if leg.get("result") in ("win", "lose", "half_win", "half_lose") and leg.get("price")
              and lo <= count[(s["posted_at"][:10], (leg.get("home") or "").lower(), (leg.get("away") or "").lower())] < hi]
        if xs:
            L.append(f"| {name} | {len(xs)} | {sum(x['result'] in ('win', 'half_win') for x in xs) / len(xs):.0%} | "
                     f"{sum(1 / x['price'] for x in xs) / len(xs):.0%} |")
    L += ["", "## Legs by class — aligned vs risky add-ons", "",
          "aligned = a plain market at 60%+ implied (≤ 1.67, the kind of leg our F8/F1/F2/B1 rules bet); "
          "special = a SportyBet special we grade (1UP/2UP early payout, \"or Over 2.5\", win either half, "
          "3 in a row) at 2.00 or shorter; risky = a price over 2.00 or a market we can't read; "
          "middle = the rest.", "",
          "| Class | legs | landed | implied (avg) | ungradable |", "|---|---|---|---|---|"]
    agg: dict = {"slips_graded": len(graded), "classes": {}}
    all_legs = [tp.remap(leg) for s in slips for leg in s["legs"]]
    for cls in ("aligned", "middle", "special", "risky"):
        xs = [x for x in all_legs if tp.leg_class(x) == cls]
        gx = [x for x in xs if x.get("result") in ("win", "lose", "half_win", "half_lose")]
        if not xs:
            continue
        landed = sum(x["result"] in ("win", "half_win") for x in gx)
        px = [x for x in gx if x.get("price")]
        imp = sum(1 / x["price"] for x in px) / len(px) if px else None
        L.append(f"| {cls} | {len(xs)} | {f'{landed}/{len(gx)} = {landed / len(gx):.0%}' if gx else '—'} | "
                 f"{f'{imp:.0%}' if imp else '—'} | {len(xs) - len(gx)} |")
        agg["classes"][cls] = {"legs": len(xs), "graded": len(gx), "landed": landed, "implied_avg": imp}
    kept = []
    for s in graded:
        al = [x for x in s["legs"] if tp.leg_class(x) == "aligned"]
        if al and all(x.get("result") in ("win", "lose", "half_win", "half_lose", "push") for x in al):
            kept.append(all(x["result"] in ("win", "half_win", "push") for x in al))
    if kept:
        L += ["", f"Counterfactual — the same slips with ONLY their aligned legs: {sum(kept)}/{len(kept)} would have "
              f"landed (as posted: {sum(s['status'] == 'won' for s in graded)}/{len(graded)})."]
        agg["aligned_only_slips"] = {"landed": sum(kept), "of": len(kept)}
    clv_lines, agg["clv"] = clv_section(slips, folder, universe_rows)
    # nameless aggregates only — the one output that may feed the framework's learning
    (out.parent / "aggregates.json").write_text(json.dumps(agg, indent=1), encoding="utf-8")
    L += ["", "## Official Top Picks vs everyone else", "",
          "| Source | slips | slips landed | legs landed | £1 a slip: return ± se | verdict |", "|---|---|---|---|---|---|"]
    L.append(_slip_row("official (@SportyBet / @SportyBetNG)", [s for s in slips if s["official"]]))
    L.append(_slip_row("tipsters", [s for s in slips if not s["official"]]))
    L += ["", "A bookmaker's margin of ~5% a leg compounds on an acca: 6 legs at fair prices still return about "
          "−26% on average, so a long acca slip must beat that just to break even."]
    L += clv_lines + [""]
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, help="folder holding slips_*.jsonl (and decoded_/graded_ files)")
    ap.add_argument("--out", help="where to write the study (default: <dir>/TIPSTER_STUDY.md)")
    a = ap.parse_args(argv)
    folder = Path(a.dir)
    print(write(folder, Path(a.out) if a.out else folder / "TIPSTER_STUDY.md"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
