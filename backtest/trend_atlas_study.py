"""TREND ATLAS STUDY: which football trends are real, in which market, and which beat the price?

Architect, 2026-11-12: "look for the trends for every market ... league by league, team by team, year by year ...
cover the entire football ... There you will find certain edges ... You test it, then you bring it up, then we deploy."

Every market in engine/trend_atlas.MARKETS gets the same three tests:
  A. LEAGUE FACT  league rate in one season vs the next season (all competitions ESPN lists + internationals).
  B. TEAM FACT    a team's rate at one venue in the first half of its season vs the second half.
     Both: correlation r with a 90% range; Benjamini-Hochberg over every test; REAL = passes and r >= 0.2.
  C. MONEY        the trend's own chance (engine/trend_atlas.Predictor: the home side at home and the away side away
                  this season, shrunk to the league rate; earlier games only) against a real pre-match price:
                  C1 SportyBet, every football game it priced worldwide since 8 Oct 2026 (data/universe), last price
                     before kick-off; the gap rule is chosen on the first half of the period, judged on the second.
                  C2 football-data.co.uk, 22 European leagues 2016-2026, average bookmaker price; rule chosen on
                     2016-20, judged on 2021-26.
                  A rule is an EDGE CANDIDATE only if its judged ROI has a 90% range above 0 on 100+ bets.

RECORD ONLY. Writes backtest/TREND_ATLAS_STUDY.md and output/trend_atlas/study.json (framework-data).
Run: python backtest/trend_atlas_study.py [--espn-dir DIR ...] [--universe-dir DIR]
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backtest"))

from engine import trend_atlas as ta  # noqa: E402

GAPS = (0.03, 0.05, 0.08, 0.12)


# ---------------------------------------------------------------- stats
def corr(xs, ys):
    n = len(xs)
    if n < 10:
        return None, (None, None), n
    mx, my = sum(xs) / n, sum(ys) / n
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if not sx or not sy:
        return None, (None, None), n
    r = max(min(sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True)) / (sx * sy), 0.9999), -0.9999)
    z, se = math.atanh(r), 1 / math.sqrt(n - 3)
    return r, (math.tanh(z - 1.645 * se), math.tanh(z + 1.645 * se)), n


def p_one_sided(r, n):
    return 0.5 * math.erfc(math.atanh(r) * math.sqrt(max(n - 3, 1)) / math.sqrt(2)) if r is not None else 1.0


def roi(rets):
    if not rets:
        return None, None, None
    n = len(rets)
    m = sum(rets) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in rets) / max(n - 1, 1))
    h = 1.645 * sd / math.sqrt(n)
    return m, m - h, m + h


def bh(tests, key="p", q=0.05):
    order = sorted(range(len(tests)), key=lambda i: tests[i][key])
    k = 0
    for rank, i in enumerate(order, 1):
        if tests[i][key] <= q * rank / len(tests):
            k = rank
    for rank, i in enumerate(order, 1):
        tests[i]["bh"] = rank <= k


def f1(x, d=1):
    return "PENDING" if x is None else f"{100 * x:+.{d}f}%"


# ---------------------------------------------------------------- A / B: facts
def league_fact(rows):
    out = []
    agg = defaultdict(lambda: [0, 0.0])
    for m in rows:
        try:
            y = int(m["sk"])
        except (TypeError, ValueError):
            continue
        for mk, f in ta.MARKETS.items():
            v = f(m)
            if v is not None:
                a = agg[(mk, m["lk"], y)]
                a[0] += 1
                a[1] += v
    for mk in ta.MARKETS:
        xs, ys = [], []
        for (k, lk, y), (n, s) in agg.items():
            if k != mk or n < ta.LEAGUE_MIN:
                continue
            nxt = agg.get((mk, lk, y + 1))
            if nxt and nxt[0] >= ta.LEAGUE_MIN:
                xs.append(s / n)
                ys.append(nxt[1] / nxt[0])
        r, ci, n = corr(xs, ys)
        out.append({"market": mk, "level": "league", "r": r, "ci": ci, "n": n, "p": p_one_sided(r, n)})
    return out


def team_fact(rows, min_half=5):
    seq = defaultdict(list)
    for m in rows:
        for team, venue in ((m["hk"], "home"), (m["ak"], "away")):
            seq[(team, m["lk"], m["sk"], venue)].append(m)
    out = []
    for mk, f in ta.MARKETS.items():
        xs, ys = [], []
        for ms in seq.values():
            vals = [v for v in (f(m) for m in ms) if v is not None]
            if len(vals) < 2 * min_half:
                continue
            h = len(vals) // 2
            xs.append(sum(vals[:h]) / h)
            ys.append(sum(vals[h:]) / (len(vals) - h))
        r, ci, n = corr(xs, ys)
        out.append({"market": mk, "level": "team (same venue, 1st half of season vs 2nd)", "r": r, "ci": ci, "n": n,
                    "p": p_one_sided(r, n)})
    return out


# ---------------------------------------------------------------- C1: SportyBet worldwide
def sb_prices(p: dict) -> dict:
    """market -> (yes price, no price) from a universe row's last look."""
    out = {}
    lad = p.get("ladder") or {}
    for ln in ("0.5", "1.5", "2.5", "3.5", "4.5"):
        o, u = lad.get(f"SB:18|total={ln}|Over {ln}"), lad.get(f"SB:18|total={ln}|Under {ln}")
        if not (o and u) and p.get(f"ou{ln}"):
            o, u = p[f"ou{ln}"]
        if o and u:
            out[f"goals over {ln}"] = (o, u)
    if p.get("btts"):
        out["BTTS yes"] = tuple(p["btts"])
    if p.get("1x2"):
        h, d, a = p["1x2"]
        out["home win"], out["draw"], out["away win"] = (h, None), (d, None), (a, None)
        out["_1x2"] = (h, d, a)
    for mid, mk in (("19", "home scores"), ("20", "away scores")):
        o, u = None, None
        for k, v in lad.items():
            if k.startswith(f"SB:{mid}|total=0.5|Over"):
                o = v
            elif k.startswith(f"SB:{mid}|total=0.5|Under"):
                u = v
        if o and u:
            out[mk] = (o, u)
    return out


def fair(mk, pr):
    """De-vigged chance of 'yes' from the price pair (1X2 from all three)."""
    if mk in ("home win", "draw", "away win"):
        h, d, a = pr["_1x2"]
        s = 1 / h + 1 / d + 1 / a
        return {"home win": 1 / h, "draw": 1 / d, "away win": 1 / a}[mk] / s
    y, n = pr[mk]
    return (1 / y) / (1 / y + 1 / n)


def load_universe(folder: Path) -> list[dict]:
    out = []
    for f in sorted(folder.glob("graded_*.jsonl.gz")):
        with gzip.open(f, "rt", encoding="utf-8") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if r.get("sport") == "football" and r.get("result") and not r["result"].get("after_90"):
                    out.append(r)
    return out


class _Idx:
    def __init__(self, rows):
        from engine.universe import _tokens
        self.by = defaultdict(list)
        for m in rows:
            if m["lk"].startswith("int:"):
                continue
            for t in _tokens(m["home"] or "") | _tokens(m["away"] or ""):
                self.by[(m["date"][:10], t)].append(m)

    def find(self, home, away, ko, score):
        from data import flashscore_results as fr
        from engine.universe import _tokens
        d0 = datetime.fromisoformat(ko[:10])
        cands = {}
        for off in (-1, 0, 1):
            d = (d0 + timedelta(days=off)).strftime("%Y-%m-%d")
            for t in _tokens(home) | _tokens(away):
                for m in self.by.get((d, t), []):
                    if m["ft"] == score:                    # same score as SportyBet's grade: no wrong-game match
                        cands[m["id"]] = {**m, "kickoff_utc": m["date"], "fthg": m["ft"][0], "ftag": m["ft"][1]}
        return fr.find_result(list(cands.values()), home, away, ko[:10]) if cands else None


def sportybet_money(rows, universe):
    """Walk the history in time; at each SportyBet game, ask the Predictor (earlier games only) for every priced
    market and keep (time, market, trend chance, fair chance, prices, outcome)."""
    idx = _Idx(rows)
    games = []
    for u in universe:
        hit = idx.find(u["home"], u["away"], u["ko"], [u["result"]["h"], u["result"]["a"]])
        if hit:
            games.append((u["ko"], u, hit))
    games.sort(key=lambda g: g[0])
    pred = ta.Predictor([mk for mk in ta.MARKETS if not mk.startswith(("corners", "cards", "yellow"))])
    out, gi = [], 0
    for m in rows:
        while gi < len(games) and games[gi][0] <= m["date"]:
            ko, u, hit = games[gi]
            pr = sb_prices(u["last"]["p"])
            res = {"ft": [u["result"]["h"], u["result"]["a"]], "ht": u["result"].get("ht")}
            for mk in pr:
                if mk.startswith("_"):
                    continue
                c = pred.chance(mk, hit)
                if c is None:
                    continue
                y = ta.MARKETS[mk](res)
                if y is None:
                    continue
                out.append({"ko": ko, "market": mk, "p": c["p"], "q": fair(mk, pr), "yes": pr[mk][0],
                            "no": pr[mk][1], "y": y, "comp": u.get("comp"), "country": u.get("country")})
            gi += 1
        pred.see(m)
    return out, len(games), len(universe)


def gap_rules(bets, split_at):
    """For each market and gap: bet YES when trend - fair >= gap, NO when fair - trend >= gap (when a NO price
    exists). Chosen on bets before split_at, judged on the rest."""
    res = []
    by = defaultdict(list)
    for b in bets:
        by[b["market"]].append(b)
    for mk, bs in by.items():
        for gap in GAPS:
            for side in ("yes", "no"):
                d_r, h_r = [], []
                for b in bs:
                    price = b[side]
                    if not price:
                        continue
                    edge = (b["p"] - b["q"]) if side == "yes" else (b["q"] - b["p"])
                    if edge < gap:
                        continue
                    win = b["y"] == 1 if side == "yes" else b["y"] == 0
                    (d_r if b["ko"] < split_at else h_r).append(price - 1 if win else -1.0)
                if not d_r and not h_r:
                    continue
                dm, dlo, dhi = roi(d_r)
                hm, hlo, hhi = roi(h_r)
                res.append({"market": mk, "gap": gap, "side": side, "disc_n": len(d_r), "disc_roi": dm,
                            "hold_n": len(h_r), "hold_roi": hm, "hold_lo": hlo, "hold_hi": hhi})
    return res


# ---------------------------------------------------------------- C2: football-data, ten seasons
def fd_money():
    import stats_claims_proof as scp
    seasons = [f"{y % 100:02d}{(y + 1) % 100:02d}" for y in range(2016, 2026)]
    ms = []
    for code in scp.MAIN:
        for s in seasons:
            ms += scp.load_main(code, s)
    rows = []
    for m in ms:
        rows.append({**m, "ft": [m["hg"], m["ag"]], "lk": f"fd:{m['lg']}", "sk": m["season"], "hk": f"fd:{m['home']}", "ak": f"fd:{m['away']}",
                     "date": m["date"].strftime("%Y-%m-%dT%H:%MZ"),
                     "ht": None if m["hthg"] is None else [int(m["hthg"]), int(m["htag"])], "goals": None,
                     "cards": None, "corners": None})
    rows.sort(key=lambda m: m["date"])
    pred = ta.Predictor(["goals over 2.5", "home win", "draw", "away win"])
    bets = []
    for m in rows:
        prices = {}
        if m.get("o_open") and m.get("u_open"):
            prices["goals over 2.5"] = (m["o_open"], m["u_open"])
        if m.get("ph") and m.get("pd") and m.get("pa"):
            prices["_1x2"] = (m["ph"], m["pd"], m["pa"])
            prices["home win"], prices["draw"], prices["away win"] = (m["ph"], None), (m["pd"], None), (m["pa"], None)
        for mk in ("goals over 2.5", "home win", "draw", "away win"):
            if mk not in prices:
                continue
            c = pred.chance(mk, m)
            if c is None:
                continue
            bets.append({"ko": m["date"], "market": mk, "p": c["p"], "q": fair(mk, prices), "yes": prices[mk][0],
                         "no": prices[mk][1], "y": ta.MARKETS[mk](m)})
        pred.see(m)
    return bets, len(rows)


# ---------------------------------------------------------------- report
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--espn-dir", action="append", default=None)
    ap.add_argument("--universe-dir", default=str(ROOT / "data" / "universe"))
    ap.add_argument("--wf-dir", default=None)
    ap.add_argument("--no-internationals", action="store_true")
    ap.add_argument("--no-fd", action="store_true")
    a = ap.parse_args(argv)
    rows = ta.load_all(ROOT, [Path(d) for d in a.espn_dir] if a.espn_dir else None,
                       internationals=not a.no_internationals, wf_dir=Path(a.wf_dir) if a.wf_dir else None)
    atlas = ta.build(rows)
    ta.write(atlas)
    n_lg = len({m["lk"] for m in rows})
    print(f"rows {len(rows)} in {n_lg} competitions", file=sys.stderr)

    facts = league_fact(rows) + team_fact(rows)
    facts = [f for f in facts if f["r"] is not None]
    bh(facts)
    universe = load_universe(Path(a.universe_dir))
    sb_bets, matched, total_u = sportybet_money(rows, universe)
    kos = sorted(b["ko"] for b in sb_bets)
    split = kos[len(kos) // 2] if kos else "9999"
    sb_rules = gap_rules(sb_bets, split)
    fd_rules, fd_n = ([], 0) if a.no_fd else (lambda b: (gap_rules(b[0], "2021-07-01"), b[1]))(fd_money())

    L = []
    w = L.append
    w("# TREND ATLAS STUDY: every market, league by league, team by team, season by season\n")
    w("Written by `backtest/trend_atlas_study.py` (Architect 2026-11-12: \"look for the trends for every market ... cover "
      "the entire football ... You test it, then you bring it up, then we deploy it\"). RECORD ONLY.\n")
    src = defaultdict(int)
    for m in rows:
        src[m["lk"].split(":")[0]] += 1
    w(f"**Data:** {len(rows):,} matches in {n_lg:,} competitions: ESPN (every competition it lists, worldwide, "
      f"July 2023 on) {src['espn']:,}; Flashscore world facts {src['fs']:,}; men's internationals since 2010 "
      f"(FIFA, continental, qualifiers, friendlies) {src['int']:,}. {len(ta.MARKETS)} markets. Corners and cards come "
      "from ESPN's match stats; goal-minute markets only where the minutes add up to the score.\n")

    w("## A + B. Which trends are real? (repeat on the next season / the second half of the season)\n")
    w("| market | level | pairs | r (90% range) | verdict |")
    w("|---|---|---|---|---|")
    for f in sorted(facts, key=lambda f: (f["level"], -f["r"])):
        v = "REAL" if f["bh"] and f["r"] >= 0.2 else "WEAK" if f["bh"] else "NOT REAL"
        w(f"| {f['market']} | {f['level']} | {f['n']} | {f['r']:+.2f} ({f['ci'][0]:+.2f} to {f['ci'][1]:+.2f}) | {v} |")

    w("\n## Atlas: latest season's top 5 competitions per market (30+ games)\n")
    w("Full lists (top and bottom 30 leagues and teams per market) are in `output/trend_atlas/atlas.json`.\n")
    w("| market | season | top 5 (rate, games) |")
    w("|---|---|---|")
    for mk in ta.MARKETS:
        lrows = atlas["leagues"].get(mk) or []
        if not lrows:
            w(f"| {mk} | - | PENDING |")
            continue
        latest = max(r[2] for r in lrows)
        cur = [r for r in lrows if r[2] == latest][:5]
        w(f"| {mk} | {latest} | " + "; ".join(f"{r[0]} {100 * r[4]:.0f}% ({r[3]})" for r in cur) + " |")

    def rule_table(rules, title, note):
        w(f"\n## {title}\n")
        w(note + "\n")
        w("| market | side | trend gap | bets (chosen period) | ROI (chosen) | bets (judged period) | ROI judged (90% range) | verdict |")
        w("|---|---|---|---|---|---|---|---|")
        best = {}
        for r in rules:
            if r["disc_n"] >= 50 and r["disc_roi"] is not None:
                k = (r["market"], r["side"])
                if k not in best or r["disc_roi"] > best[k]["disc_roi"]:
                    best[k] = r
        cands = []
        for k in sorted(best):
            r = best[k]
            if r["hold_n"] >= 100 and r["hold_lo"] > 0:
                ver = "EDGE CANDIDATE"
                cands.append(r)
            elif r["hold_n"] < 100:
                ver = "TOO FEW"
            elif r["hold_hi"] < 0:
                ver = "LOSES"
            else:
                ver = "NOT PROVEN"
            rng = "PENDING" if r["hold_roi"] is None else f"{f1(r['hold_roi'])} ({f1(r['hold_lo'])} to {f1(r['hold_hi'])})"
            w(f"| {r['market']} | {r['side']} | {r['gap']:.2f} | {r['disc_n']} | {f1(r['disc_roi'])} | {r['hold_n']} | {rng} | {ver} |")
        return cands

    c1 = rule_table(sb_rules, "C1. Money against SportyBet, worldwide (8 Oct 2026 on)",
                    f"{total_u:,} graded SportyBet football games; {matched:,} matched to our history with the same "
                    f"score; {len(sb_bets):,} market prices where the trend had both teams' 4+ games at that venue. "
                    f"Rule chosen before {split[:10]}, judged after. Price = SportyBet's last before kick-off; "
                    "'trend gap' = trend chance minus SportyBet's de-vigged chance.")
    c2 = [] if a.no_fd else rule_table(fd_rules, "C2. Money against the bookmakers' average price, 22 European leagues, 2016-2026",
                                       f"{fd_n:,} matches. Rule chosen on 2016-17 to 2020-21, judged on 2021-22 to 2025-26.")

    w("\n## What to bring to the Architect\n")
    cands = [("SportyBet", r) for r in c1] + [("bookmakers' average", r) for r in c2]
    if cands:
        for venue, r in cands:
            w(f"- **{r['market']} {r['side'].upper()}** when the trend is {r['gap']:.2f}+ away from {venue}'s price: "
              f"{r['hold_n']} judged bets, ROI {f1(r['hold_roi'])} ({f1(r['hold_lo'])} to {f1(r['hold_hi'])}). "
              "Next: paper picks for 2 weeks on the live board before any stake (Architect's decision).")
    else:
        w("- No trend beat the price on bets it was not chosen on. The trends that are REAL above are already in the "
          "price where a price exists; corners and cards are tested against SportyBet's own lines by "
          "`backtest/stat_lines_study.py` as those lines are graded.")
    real = sorted({f["market"] for f in facts if f["bh"] and f["r"] >= 0.2})
    w(f"- Real trends ({len(real)} markets): {', '.join(real)}.")
    out = ROOT / "backtest" / "TREND_ATLAS_STUDY.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    js = ROOT / "output" / "trend_atlas" / "study.json"
    js.parent.mkdir(parents=True, exist_ok=True)
    js.write_text(json.dumps({"built": datetime.now(timezone.utc).isoformat(timespec="seconds"), "matches": len(rows),
                              "competitions": n_lg, "facts": facts, "sportybet_rules": sb_rules, "fd_rules": fd_rules,
                              "candidates": [{"venue": v, **r} for v, r in cands]}, default=str), encoding="utf-8")
    msg = f"trend atlas study: {len(rows)} matches, {n_lg} competitions, {len(cands)} edge candidates"
    print(msg)
    return msg


if __name__ == "__main__":
    main()
