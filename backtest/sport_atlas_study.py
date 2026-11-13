"""SPORT ATLAS STUDY: trends and their price test for every sport we have data for (football: TREND_ATLAS_STUDY).

Architect, 2026-11-12: "It should cover the entire betting market for all sports."

Per sport, three tests (engine/sport_atlas.py):
  FACT        does a team's (player's) rate in each market repeat from the first half of its season to the second?
  STAT TREND  the team's rate (home side at home, away side away, shrunk to the league) against the market's own
              chance at the real pre-game price: bet the side the trend favours by a gap.
  PRICE TREND the team's record AGAINST the price (vs the spread, over/under vs the posted total, wins vs the
              moneyline): does it repeat, and does betting it make money?
Money rules are chosen on the first half of each sport's games (by date) and judged on the second half; an EDGE
CANDIDATE needs 100+ judged bets with a 90% ROI range above 0. Benjamini-Hochberg over the FACT tests.
RECORD ONLY. Writes backtest/SPORT_ATLAS_STUDY.md and output/sport_atlas/study.json (framework-data).
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backtest"))

from engine import sport_atlas as sa  # noqa: E402
from engine import trend_atlas as ta  # noqa: E402
import trend_atlas_study as tas  # noqa: E402

TREND_GAPS = (0.05, 0.10, 0.15)


def team_fact(rows, table, by_venue=True, min_half=5):
    seq = defaultdict(list)
    for m in rows:
        for team, venue in ((m["hk"], "home"), (m["ak"], "away")):
            seq[(team, m["sk"], venue if by_venue else "*")].append((m, venue))
    out = []
    for mk, f in table.items():
        xs, ys = [], []
        for ms in seq.values():
            vals = []
            for m, venue in ms:
                v = f(m)
                if v is None:
                    continue
                # for the team's own view: a 'home ...' market seen from the away side is its opposite
                if not by_venue and venue == "away" and mk.startswith(("home", "first-named")):
                    v = 1 - v
                vals.append(v)
            if len(vals) < 2 * min_half:
                continue
            h = len(vals) // 2
            xs.append(sum(vals[:h]) / h)
            ys.append(sum(vals[h:]) / (len(vals) - h))
        r, ci, n = tas.corr(xs, ys)
        if r is not None:
            out.append({"market": mk, "r": r, "ci": ci, "n": n, "p": tas.p_one_sided(r, n)})
    return out


def money(rows, table, min_team=4, min_games=5):
    """Stat-trend bets (Predictor vs the price) and price-trend bets (record against the price), in date order."""
    priced = [mk for mk in table if mk in sa.PRICED]
    pred = ta.Predictor(list(table), table)
    pt = sa.PriceTrend()
    stat_bets, trend_bets = [], []
    resid_pairs = defaultdict(list)           # (market, team, sk) -> residuals, for the 'does it repeat' test
    for m in rows:
        for mk in priced:
            pr = sa.PRICED[mk](m)
            y = table[mk](m)
            if not pr or y is None:
                continue
            q = sa.fair_yes(pr)
            c = pred.chance(mk, m, min_team=min_team)
            if c is not None:
                stat_bets.append({"ko": m["date"], "market": mk, "p": c["p"], "q": q, "yes": pr[0], "no": pr[1], "y": y})
            s = pt.signal(mk, m, min_games=min_games)
            if s is not None:
                trend_bets.append({"ko": m["date"], "market": mk, "s": s, "yes": pr[0], "no": pr[1], "y": y})
            pt.see(mk, m, y, q)
            resid_pairs[(mk, m["hk"], m["sk"])].append(y - q)
            if not mk.startswith("over"):
                resid_pairs[(mk, m["ak"], m["sk"])].append(q - y)
            else:
                resid_pairs[(mk, m["ak"], m["sk"])].append(y - q)
        pred.see(m)
    # does a team's record against the price repeat (first half of its season vs second)?
    rep = []
    for mk in priced:
        xs, ys = [], []
        for (k, _t, _s), v in resid_pairs.items():
            if k != mk or len(v) < 2 * max(3, min_games):
                continue
            h = len(v) // 2
            xs.append(sum(v[:h]) / h)
            ys.append(sum(v[h:]) / (len(v) - h))
        r, ci, n = tas.corr(xs, ys)
        rep.append({"market": mk, "r": r, "ci": ci, "n": n})
    return stat_bets, trend_bets, rep


def trend_rules(bets, split_at):
    out = []
    by = defaultdict(list)
    for b in bets:
        by[b["market"]].append(b)
    for mk, bs in by.items():
        for g in TREND_GAPS:
            for side in ("yes", "no"):
                d_r, h_r = [], []
                for b in bs:
                    if (side == "yes" and b["s"] < g) or (side == "no" and b["s"] > -g):
                        continue
                    win = b["y"] == 1 if side == "yes" else b["y"] == 0
                    (d_r if b["ko"] < split_at else h_r).append(b[side] - 1 if win else -1.0)
                if not d_r and not h_r:
                    continue
                dm, _, _ = tas.roi(d_r)
                hm, hlo, hhi = tas.roi(h_r)
                out.append({"market": mk, "gap": g, "side": side, "disc_n": len(d_r), "disc_roi": dm, "hold_n": len(h_r),
                            "hold_roi": hm, "hold_lo": hlo, "hold_hi": hhi})
    return out


def pick_best(rules):
    best = {}
    for r in rules:
        if r["disc_n"] >= 50 and r["disc_roi"] is not None:
            k = (r["market"], r["side"])
            if k not in best or r["disc_roi"] > best[k]["disc_roi"]:
                best[k] = r
    return [best[k] for k in sorted(best)]


def verdict(r):
    if r["hold_n"] < 100 or r["hold_roi"] is None:
        return "TOO FEW"
    if r["hold_lo"] > 0:
        return "EDGE CANDIDATE"
    if r["hold_hi"] < 0:
        return "LOSES"
    return "NOT PROVEN"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--us-dir", default=str(ROOT / "data" / "sports_history"))
    ap.add_argument("--universe-dir", default=str(ROOT / "data" / "universe"))
    ap.add_argument("--no-tennis", action="store_true")
    a = ap.parse_args(argv)
    rows = sa.us_rows(Path(a.us_dir)) + ([] if a.no_tennis else sa.tennis_rows()) + sa.sportybet_rows(Path(a.universe_dir))
    by_sport = defaultdict(list)
    for m in rows:
        by_sport[m["sport"]].append(m)
    L = []
    w = L.append
    w("# SPORT ATLAS STUDY: trends and the price, every sport we have data for\n")
    w("Written by `backtest/sport_atlas_study.py` (Architect 2026-11-12: \"It should cover the entire betting market for "
      "all sports\"). Football's full grid (37 markets, 113k matches) is in TREND_ATLAS_STUDY. RECORD ONLY.\n")
    w("## Coverage, every sport\n")
    w("| sport | games here | history | prices for the money test | where |")
    w("|---|---|---|---|---|")
    counts = {s: len(v) for s, v in by_sport.items()}
    for sport, hist, prices, where in sa.SPORTS_REGISTRY:
        key = {"basketball (NBA, WNBA, NCAA)": "basketball", "basketball (world)": "sportybet basketball",
               "ice hockey (NHL)": "hockey", "baseball (MLB)": "baseball", "American football (NFL, college)": "american football",
               "tennis (ATP, WTA)": "tennis", "football": "sportybet football"}.get(sport)
        n = counts.get(key, 0) if key else "PENDING"
        if key == "tennis" and not n:
            n = "PENDING"
            prices = f"{prices} - PENDING: {sa.TENNIS_NOTE or 'tennis not loaded this run'}"
        w(f"| {sport} | {n:,} | {hist} | {prices} | {where} |" if isinstance(n, int) else f"| {sport} | PENDING | {hist} | {prices} | {where} |")
    all_facts, cands, js = [], [], {"sports": {}}
    for sport, rs in sorted(by_sport.items()):
        rs.sort(key=lambda m: m["date"])
        table = sa.SPORT_MARKETS[sport]
        short = sport.startswith("sportybet")        # five weeks so far: smaller samples, all venues together
        facts = team_fact(rs, table, by_venue=not (short or sport == "tennis"), min_half=3 if short else 5)
        for f in facts:
            f["sport"] = sport
        all_facts += facts
        stat_bets, trend_bets, rep = money(rs, table, min_team=2 if short else 4, min_games=3 if short else 5)
        kos = sorted(m["date"] for m in rs)
        split = kos[len(kos) // 2] if kos else "9999"
        srules = pick_best(tas.gap_rules(stat_bets, split))
        trules = pick_best(trend_rules(trend_bets, split))
        js["sports"][sport] = {"games": len(rs), "facts": facts, "stat_rules": srules, "trend_rules": trules, "repeat": rep}
        w(f"\n## {sport} ({len(rs):,} games, {kos[0][:10]} to {kos[-1][:10]}; rules chosen before {split[:10]}, judged after)\n")
        w("**Facts: does the team's rate repeat (first half of its season vs second)?**\n")
        w("| market | teams | r (90% range) |")
        w("|---|---|---|")
        for f in sorted(facts, key=lambda f: -f["r"]):
            w(f"| {f['market']} | {f['n']} | {f['r']:+.2f} ({f['ci'][0]:+.2f} to {f['ci'][1]:+.2f}) |")
        w("\n**Does a team's record AGAINST THE PRICE repeat?** (ATS, over/under vs the posted total, wins vs the moneyline)\n")
        w("| market | teams | r (90% range) |")
        w("|---|---|---|")
        for x in rep:
            w(f"| {x['market']} | {x['n']} | " + ("PENDING (too few)" if x["r"] is None else f"{x['r']:+.2f} ({x['ci'][0]:+.2f} to {x['ci'][1]:+.2f})") + " |")
        for title, rules in (("Money: STAT trend vs the price", srules), ("Money: PRICE trend (back the team's record against the price)", trules)):
            w(f"\n**{title}**\n")
            w("| market | side | gap | bets chosen | ROI chosen | bets judged | ROI judged (90% range) | verdict |")
            w("|---|---|---|---|---|---|---|---|")
            for r in rules:
                v = verdict(r)
                if v == "EDGE CANDIDATE":
                    cands.append((sport, title, r))
                rng = "PENDING" if r["hold_roi"] is None else f"{tas.f1(r['hold_roi'])} ({tas.f1(r['hold_lo'])} to {tas.f1(r['hold_hi'])})"
                w(f"| {r['market']} | {r['side']} | {r['gap']:.2f} | {r['disc_n']} | {tas.f1(r['disc_roi'])} | {r['hold_n']} | {rng} | {v} |")
            if not rules:
                w("| PENDING | | | | | | | too few bets |")
    tas.bh(all_facts)
    w("\n## What to bring to the Architect\n")
    if cands:
        for sport, title, r in cands:
            w(f"- **{sport}: {r['market']} {r['side'].upper()}** ({title.split(':')[1].strip()}, gap {r['gap']:.2f}): "
              f"{r['hold_n']} judged bets, ROI {tas.f1(r['hold_roi'])} ({tas.f1(r['hold_lo'])} to {tas.f1(r['hold_hi'])}). "
              "Next: paper picks before any stake (Architect's decision).")
    else:
        w("- No trend, in any sport here, beat the price on games it was not chosen on.")
    real = sorted({(f["sport"], f["market"]) for f in all_facts if f.get("bh") and f["r"] >= 0.2})
    w(f"- Trends that repeat (r 0.2+, after the correction): " + "; ".join(f"{s}: {m}" for s, m in real) + ".")
    out = ROOT / "backtest" / "SPORT_ATLAS_STUDY.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    p = ROOT / "output" / "sport_atlas" / "study.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    js.update({"built": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "candidates": [{"sport": s, "kind": t, **r} for s, t, r in cands]})
    p.write_text(json.dumps(js, default=str), encoding="utf-8")
    msg = f"sport atlas study: {len(rows)} games in {len(by_sport)} sports, {len(cands)} edge candidates"
    print(msg)
    return msg


if __name__ == "__main__":
    main()
