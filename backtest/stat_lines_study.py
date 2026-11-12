"""STAT LINES STUDY: do SportyBet's corners, bookings and 1st-half total prices pay, and do the stats claims beat them?

Reads data/stat_lines/graded/*.jsonl (engine/stat_lines.py) and data/world_facts_detail/*.jsonl.
Two questions, each with its sample size and a 90% range; nothing is judged before 300 graded lines:
1. The price alone: per market and side, the hit rate against the price's own chance (de-vigged) and the ROI
   at SportyBet's last price before kick-off. This is the margin a stats bet has to overcome.
2. The claim: backtest/STATS_CLAIMS_PROOF.md found teams' corner and card counts repeat from game to game.
   Here: the two teams' average corners (or yellow cards) in their last 5 matches in our archive, summed,
   against the line. Bet over when that sum is 1.5+ above the line, under when 1.5+ below. ROI at the price.
3. The ESPN trend claim (framework#601): the trend chance at the line (engine/trend_atlas.Predictor on ESPN's team
   history, earlier games only) against SportyBet's de-vigged chance; bet when 0.05+ apart. Yellow cards only, no
   red-card games (as the grader). Plus a daily paper list, output/stat_lines/paper_<date>.json, graded later.
RECORD ONLY. Writes output/stat_lines/STAT_LINES_STUDY.md (framework-data). Nothing here picks, stakes or blocks.
"""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIN_JUDGE = 300
GAP = 0.05                      # trend chance vs SportyBet's fair chance (framework#601)
TREND_STAT = {"corners": "corners", "bookings": "yellow"}
STAT_OF = {"corners": "corners", "bookings": "yellow"}


def _rows(folder: Path) -> list[dict]:
    out = []
    for p in sorted(folder.glob("*.jsonl")):
        for line in p.read_text(encoding="utf-8").splitlines():
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    return out


def roi_range(rets: list[float]):
    if not rets:
        return None, None, None
    n = len(rets)
    m = sum(rets) / n
    sd = math.sqrt(sum((r - m) ** 2 for r in rets) / max(1, n - 1))
    h = 1.645 * sd / math.sqrt(n)
    return m, m - h, m + h


def team_history(detail: list[dict]) -> dict:
    """{team: [(ko, {"corners": n, "yellow": n}), ...]} from the world_facts detail archive."""
    h = defaultdict(list)
    for d in detail:
        st = ((d.get("stats") or {}).get("match") or {})
        for side, team in ((0, d["home"]), (1, d["away"])):
            vals = {k: st[k][0] + st[k][1] for k in ("corners", "yellow") if k in st and None not in st[k]}
            if vals:
                h[team].append((d["ko"], vals))
    for v in h.values():
        v.sort(key=lambda x: x[0])
    return h


def recent(hist: dict, team: str, ko: str, stat: str, n: int = 5):
    vals = [v[stat] for t, v in hist.get(team, []) if t < ko and stat in v][-n:]
    return sum(vals) / len(vals) if len(vals) == n else None


def fmt(m, lo, hi):
    return "PENDING" if m is None else f"{100 * m:+.1f}% ({100 * lo:+.1f}% to {100 * hi:+.1f}%)"


# ------------------------------------------------------------ framework#601: ESPN trend vs SportyBet's lines
def _yellow_clean(m):
    """ESPN yellow-card count; None (PENDING) when cards are missing or any red card was shown (grader rule)."""
    c = m.get("cards")
    if c is None or any(x[2] == "R" for x in c):
        return None
    return float(sum(1 for x in c if x[2] == "Y"))


def _corner_total(m):
    c = m.get("corners")
    return None if not c else float(c[0] + c[1])


def _over(f, line):
    def g(m):
        v = f(m)
        return None if v is None else float(v > line)
    return g


def trend_market(stat: str, line: str) -> str:
    return f"{stat} over {line}"


def trend_table(rows: list[tuple[str, str]]) -> dict:
    """{market name: function} for the (stat, line) pairs asked. Whole lines are left out: a push is not a trend."""
    fn = {"corners": _corner_total, "yellow": _yellow_clean}
    return {trend_market(st, ln): _over(fn[st], float(ln)) for st, ln in set(rows) if float(ln) % 1 == 0.5}


def espn_rows(root: Path) -> list[dict]:
    from data import espn_history
    from engine import trend_atlas as ta
    rows = [ta.norm(m, "espn") for m in espn_history.load(root / "data" / "espn_matches")]
    rows.sort(key=lambda m: m["date"])
    return rows


def _fs_scores(root: Path) -> dict:
    out = {}
    for d in _rows(root / "data" / "world_facts"):
        if d.get("id") and d.get("ft"):
            out[d["id"]] = d["ft"]
    return out


def _lines_asked(graded: list[dict]) -> list[tuple[str, str]]:
    return [(TREND_STAT[mkt], ln) for r in graded for mkt, lines in (r.get("graded") or {}).items()
            if mkt in TREND_STAT for ln in lines]


def _side(p: float, q: float, gap: float):
    return "over" if p - q >= gap else "under" if q - p >= gap else None


def trend_claim(graded: list[dict], rows: list[dict], scores: dict, gap: float = GAP):
    """-> (bets, matched, total). Each bet: {market, side, p, q, price, hit, ko}. Games are matched to ESPN strictly
    (Flashscore names, same date and the same full-time score); the trend chance uses earlier games only."""
    import trend_atlas_study as tas

    from engine import trend_atlas as ta
    table = trend_table(_lines_asked(graded))
    if not table or not rows:
        return [], 0, len(graded)
    idx = tas._Idx(rows)
    games = []
    for r in graded:
        ft = scores.get(r.get("fs_id"))
        if not ft or not r.get("graded"):
            continue
        hit = idx.find(r.get("fs_home") or r["home"], r.get("fs_away") or r["away"], r["ko"], list(ft))
        if hit:
            games.append((r["ko"], r, hit))
    games.sort(key=lambda g: g[0])
    pred = ta.Predictor(list(table), table)
    bets, gi = [], 0
    for m in rows:
        while gi < len(games) and games[gi][0] <= m["date"]:
            ko, r, hit = games[gi]
            gi += 1
            for mkt, lines in r["graded"].items():
                st = TREND_STAT.get(mkt)
                for ln, res in lines.items():
                    name = trend_market(st, ln) if st else None
                    if name not in table or res["over"] is None:
                        continue
                    c = pred.chance(name, hit)
                    if c is None:
                        continue
                    o, u = r["last"]["lines"][mkt][ln]
                    q = (1 / o) / (1 / o + 1 / u)
                    side = _side(c["p"], q, gap)
                    if side:
                        bets.append({"market": mkt, "line": ln, "side": side, "p": c["p"], "q": q,
                                     "price": o if side == "over" else u, "hit": res[side], "ko": ko})
        pred.see(m)
    return bets, len(games), len(graded)


def trend_report(bets: list[dict], matched: int, total: int) -> list[str]:
    L = ["\n## 3. The ESPN trend vs the line (framework#601, gap 0.05+, 90% range)\n",
         f"{matched} of {total} graded matches found in the ESPN history (same teams, date and score); "
         "the trend chance uses earlier games only. Nothing is judged before "
         f"{MIN_JUDGE} bets in a row.\n",
         "| market | side | bets | hit | trend chance | ROI | judged? |", "|---|---|---|---|---|---|---|"]
    by = defaultdict(list)
    for b in bets:
        by[(b["market"], b["side"])].append(b)
    for mkt in ("corners", "bookings"):
        for side in ("over", "under"):
            bs = by.get((mkt, side), [])
            n = len(bs)
            m, lo, hi = roi_range([b["price"] - 1 if b["hit"] else -1.0 for b in bs])
            hit = f"{100 * sum(b['hit'] for b in bs) / n:.1f}%" if n else "PENDING"
            tc = f"{100 * sum(b['p'] for b in bs) / n:.1f}%" if n else "PENDING"
            L.append(f"| {mkt} | {side} | {n} | {hit} | {tc} | {fmt(m, lo, hi)} | "
                     f"{'yes' if n >= MIN_JUDGE else 'PENDING (too few)'} |")
    return L


def paper_picks(root: Path, rows: list[dict], today: str, gap: float = GAP) -> list[dict]:
    """Trend picks for the games stat_lines has priced and not yet graded (data/stat_lines/pending.json).
    Teams are matched to ESPN team ids by the strict name rule (flashscore_results, unambiguous only)."""
    from data import flashscore_results as fr
    from engine import trend_atlas as ta
    pf = root / "data" / "stat_lines" / "pending.json"
    if not pf.exists() or not rows:
        return []
    pending = json.loads(pf.read_text(encoding="utf-8"))
    teams = {}                                       # team key -> (name, league key, season key), latest row wins
    for m in rows:
        teams[m["hk"]] = (m["home"], m["lk"], m["sk"])
        teams[m["ak"]] = (m["away"], m["lk"], m["sk"])

    def team_of(name: str):
        sc = sorted(((fr._name_sim(name, v[0]), k) for k, v in teams.items()), reverse=True)[:2]
        if not sc or sc[0][0] < fr.MATCH_MIN or (len(sc) > 1 and sc[1][0] >= sc[0][0] - 0.02):
            return None
        return sc[0][1]

    todo = [p for p in pending.values() if p["ko"][:10] >= today]
    table = trend_table([(TREND_STAT[mkt], ln) for p in todo for mkt, lines in p["last"]["lines"].items()
                         if mkt in TREND_STAT for ln in lines])
    if not table:
        return []
    pred = ta.Predictor(list(table), table)
    for m in rows:
        pred.see(m)
    out = []
    for p in todo:
        hk, ak = team_of(p["home"] or ""), team_of(p["away"] or "")
        if not hk or not ak or teams[hk][1] != teams[ak][1]:
            continue                                  # unmatched or different leagues: PENDING, never guessed
        m = {"hk": hk, "ak": ak, "lk": teams[hk][1], "sk": teams[hk][2]}
        for mkt, lines in p["last"]["lines"].items():
            st = TREND_STAT.get(mkt)
            for ln, (o, u) in lines.items():
                name = trend_market(st, ln) if st else None
                c = pred.chance(name, m) if name in table else None
                if c is None:
                    continue
                q = (1 / o) / (1 / o + 1 / u)
                side = _side(c["p"], q, gap)
                if side:
                    out.append({"id": p["id"], "ko": p["ko"], "home": p["home"], "away": p["away"], "market": mkt,
                                "line": ln, "side": side, "trend_chance": round(c["p"], 4), "fair_chance": round(q, 4),
                                "price": o if side == "over" else u, "result": None})
    return out


def write_paper(root: Path, rows: list[dict], graded: list[dict], today: str) -> str:
    """Once a day: today's picks to paper_<today>.json (never overwritten), then grade every open paper file."""
    folder = root / "output" / "stat_lines"
    folder.mkdir(parents=True, exist_ok=True)
    f = folder / f"paper_{today}.json"
    if not f.exists():
        f.write_text(json.dumps({"date": today, "picks": paper_picks(root, rows, today)}, ensure_ascii=False),
                     encoding="utf-8")
    by_id = {r["id"]: r for r in graded if r.get("graded")}
    done = 0
    for p in sorted(folder.glob("paper_*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        changed = False
        for pk in d["picks"]:
            res = ((by_id.get(pk["id"]) or {}).get("graded") or {}).get(pk["market"], {}).get(pk["line"])
            if pk["result"] is None and res and res[pk["side"]] is not None:
                pk["result"] = int(res[pk["side"]])
                changed = True
        done += sum(1 for pk in d["picks"] if pk["result"] is not None)
        if changed:
            p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    today_n = len(json.loads(f.read_text(encoding="utf-8"))["picks"])
    return f"paper picks today {today_n}, graded to date {done}"


def main(root: Path = ROOT) -> str:
    graded = [r for r in _rows(root / "data" / "stat_lines" / "graded") if r.get("graded")]
    detail = _rows(root / "data" / "world_facts_detail")
    hist = team_history(detail)
    price = defaultdict(lambda: {"rets": [], "hits": 0, "p": 0.0})
    claim = defaultdict(list)
    for r in graded:
        for mkt, lines in r["graded"].items():
            for ln, res in lines.items():
                o, u = r["last"]["lines"][mkt][ln]
                q_over = (1 / o) / (1 / o + 1 / u)
                for side, px, q in (("over", o, q_over), ("under", u, 1 - q_over)):
                    if res[side] is None:
                        continue
                    k = (mkt, side)
                    price[k]["rets"].append(px - 1 if res[side] else -1.0)
                    price[k]["hits"] += res[side]
                    price[k]["p"] += q
                stat = STAT_OF.get(mkt)
                if stat and res["over"] is not None:
                    a, b = recent(hist, r.get("fs_home") or r["home"], r["ko"], stat), recent(hist, r.get("fs_away") or r["away"], r["ko"], stat)
                    if a is None or b is None:
                        continue
                    gap = a + b - float(ln)
                    if gap >= 1.5:
                        claim[mkt].append(o - 1 if res["over"] else -1.0)
                    elif gap <= -1.5:
                        claim[mkt].append(u - 1 if res["under"] else -1.0)
    L = ["# STAT LINES STUDY (record only)\n",
         f"{len(graded)} matches graded with SportyBet's own corners / bookings / 1st-half total lines "
         f"(`engine/stat_lines.py`). Nothing is judged before {MIN_JUDGE} bets in a row of the table.\n",
         "## 1. The price alone (ROI at SportyBet's last price before kick-off, 90% range)\n",
         "| market | side | bets | hit | price's own chance | ROI | judged? |", "|---|---|---|---|---|---|---|"]
    for (mkt, side), d in sorted(price.items()):
        n = len(d["rets"])
        m, lo, hi = roi_range(d["rets"])
        L.append(f"| {mkt} | {side} | {n} | {100 * d['hits'] / n:.1f}% | {100 * d['p'] / n:.1f}% | {fmt(m, lo, hi)} | "
                 f"{'yes' if n >= MIN_JUDGE else 'PENDING (too few)'} |")
    L += ["\n## 2. The claim: last-5 average of both teams vs the line (gap 1.5+)\n",
          "| market | bets | ROI | judged? |", "|---|---|---|---|"]
    for mkt in ("corners", "bookings"):
        rets = claim.get(mkt, [])
        m, lo, hi = roi_range(rets)
        L.append(f"| {mkt} | {len(rets)} | {fmt(m, lo, hi)} | {'yes' if len(rets) >= MIN_JUDGE else 'PENDING (too few)'} |")
    L.append("\nTeam history comes from the world_facts detail archive (from 12 Nov 2026), so the claim column fills "
             "as both teams build 5 recorded matches.")
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "backtest"))
    paper, bets = "paper PENDING", []
    try:
        rows = espn_rows(root)
        bets, matched, total = trend_claim(graded, rows, _fs_scores(root))
        L += trend_report(bets, matched, total)
        paper = write_paper(root, rows, graded, datetime.now(UTC).strftime("%Y-%m-%d"))
    except Exception as e:  # noqa: BLE001 - the ESPN part never stops the older tables
        L.append(f"\n## 3. The ESPN trend vs the line\n\nPENDING ({type(e).__name__}: {str(e)[:80]})")
    out = root / "output" / "stat_lines" / "STAT_LINES_STUDY.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    return (f"stat lines study: {len(graded)} graded matches, claim bets corners {len(claim.get('corners', []))}, bookings {len(claim.get('bookings', []))}; "
           f"ESPN trend bets {len(bets)}; {paper}")


if __name__ == "__main__":
    print(main())
