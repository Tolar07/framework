"""
REASONING IDEAS STUDY (to-do #7, 2026-10-27) — the bot-reasoning research list,
one walk-forward backtest per idea that to-do #3 (cognitive core) and #5 (verdict
panel) did not already build.

Every test is out of sample: games sorted by kick-off, every choice (threshold,
calibration map, bucket) is made on the EARLIER half and scored on the LATER
half only. Scored on return per unit and on closing-line value (CLV):
  clv_sb   price taken / SportyBet's last price for the same side - 1
  clv_mb   price taken x Matchbook's last fair chance - 1 (margin removed), when
           Matchbook priced the game — the sharper close
An idea WINS only when its later half beats the close (CLV > 0) and does not lose
money; everything else is written up as a loser in research/notes/.

Data: data/universe graded games (first/last SportyBet price per side, Matchbook
first/last for ~1,900) and the graded board singles/accas in output/picks.

    python backtest/reasoning_ideas_study.py   -> backtest/REASONING_IDEAS_STUDY.md
"""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from datetime import UTC, datetime
from glob import glob
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backtest"))

from engine import features as F  # noqa: E402
from engine import universe as uv  # noqa: E402

OUT = ROOT / "backtest" / "REASONING_IDEAS_STUDY.md"
FAMS = ("1x2", "ou1.5", "ou2.5", "ou3.5", "btts", "dc")
THRESHOLDS = (0.02, 0.04, 0.06, 0.08)


# ── shared helpers ───────────────────────────────────────────────────────
def _fam(key: str) -> str:
    f = key.split(":")[0]
    return "ou" + f[3:] if f.startswith("o/u") else f


def _side_idx(key: str) -> int | None:
    fam, side = key.split(":")
    order = {"1x2": ("home", "draw", "away"), "btts": ("yes", "no"), "dc": ("1x", "12", "x2")}
    if fam.startswith("o/u"):
        return 0 if side == "over" else 1
    return order[fam].index(side) if fam in order and side in order[fam] else None


def score(bets: list[dict]) -> dict:
    """bets: {won, price, clv_sb, clv_mb}. Return per unit ± se and mean CLVs."""
    n = len(bets)
    if not n:
        return {"n": 0}
    pl = [(b["price"] - 1) if b["won"] else -1.0 for b in bets]
    m = sum(pl) / n
    se = math.sqrt(sum((x - m) ** 2 for x in pl) / max(n - 1, 1) / n)
    sb = [b["clv_sb"] for b in bets if b.get("clv_sb") is not None]
    mb = [b["clv_mb"] for b in bets if b.get("clv_mb") is not None]
    return {"n": n, "hit": sum(b["won"] for b in bets) / n, "roi": m, "se": se,
            "clv_sb": sum(sb) / len(sb) if sb else None, "n_mb": len(mb),
            "clv_mb": sum(mb) / len(mb) if mb else None}


def fmt(s: dict) -> str:
    if not s.get("n"):
        return "no bets"
    c1 = f"{s['clv_sb']:+.1%}" if s.get("clv_sb") is not None else "—"
    c2 = f"{s['clv_mb']:+.1%} (n {s['n_mb']})" if s.get("clv_mb") is not None else "—"
    return f"n {s['n']}, hit {s['hit']:.1%}, return {s['roi']:+.1%} ± {s['se']:.1%}, CLV SB {c1}, CLV MB {c2}"


def wins(s: dict) -> bool:
    clv = s.get("clv_mb") if s.get("clv_mb") is not None and s.get("n_mb", 0) >= 30 else s.get("clv_sb")
    return s.get("n", 0) >= 60 and (clv or 0) > 0 and s["roi"] > -s["se"] / 2


# ── the side-level table every universe test reads ─────────────────────────
def sides() -> tuple[list[dict], str]:
    """One record per (game, side) at the first price, with closes and fair chances."""
    rows = [r for r in uv.load_graded() if r.get("sport", "football") == "football"]
    rows.sort(key=lambda r: r.get("ko") or "")
    cut = rows[len(rows) // 2].get("ko") or ""
    out = []
    for r in rows:
        fp = (r.get("first") or {}).get("p") or {}
        lp = (r.get("last") or {}).get("p") or {}
        mbl = ((r.get("mb_last") or {}).get("p")) or {}
        mbf = ((r.get("mb_first") or {}).get("p")) or {}
        last = {k: x for k, _, x, _ in uv.outcomes("football", lp, r["result"])}
        for k, won, x, mkt in uv.outcomes("football", fp, r["result"]):
            fam, i = _fam(k), _side_idx(k)
            if fam not in FAMS or i is None:
                continue
            fair = F.fair(mkt)
            mbl_f, mbf_f = F.fair(mbl.get(fam)), F.fair(mbf.get(fam))
            lx = last.get(k)
            out.append({
                "game": r["id"], "ko": r.get("ko") or "", "late": (r.get("ko") or "") >= cut,
                "country": r.get("country") or "", "comp": r.get("comp") or "", "key": k, "fam": fam,
                "won": won, "price": x, "fair": fair[i] if fair else None, "fp": fp, "lp": lp,
                "last": lx, "clv_sb": (x / lx - 1) if lx else None,
                "mb_first": mbf_f[i] if mbf_f else None, "mb_last": mbl_f[i] if mbl_f else None,
                "clv_mb": (x * mbl_f[i] - 1) if mbl_f else None,
            })
    return out, cut


def walk(bets_by_t: dict[float, list[dict]]) -> tuple[float, dict, dict]:
    """Pick the threshold on the earlier half (best return with 30+ bets), score the later half."""
    best, best_roi = None, -9.0
    for t, bets in bets_by_t.items():
        e = score([b for b in bets if not b["late"]])
        if e.get("n", 0) >= 30 and e["roi"] > best_roi:
            best, best_roi = t, e["roi"]
    t = best if best is not None else min(bets_by_t)
    bets = bets_by_t[t]
    return t, score([b for b in bets if not b["late"]]), score([b for b in bets if b["late"]])


# ── idea 2 + 11: calibration by market and by league, and bias checks ────────
def bias_table(S: list[dict]) -> list[str]:
    """Flat return of every side family at SportyBet's first price, by fair-chance band."""
    bands = ((0, .2), (.2, .4), (.4, .6), (.6, .8), (.8, 1.01))
    agg: dict[tuple, list] = defaultdict(list)
    for s in S:
        if s["fair"] is None:
            continue
        b = next(f"{lo:.0%}-{min(hi, 1):.0%}" for lo, hi in bands if lo <= s["fair"] < hi)
        side = s["key"].split(":")[1]
        agg[(s["fam"], side, b)].append(s)
    lines = ["| market | fair band | n | landed | fair | return (both halves) |", "|---|---|---|---|---|---|"]
    for (fam, side, b), xs in sorted(agg.items()):
        if len(xs) < 150:
            continue
        sc = score(xs)
        fair = sum(x["fair"] for x in xs) / len(xs)
        flag = " **" if abs(sc["roi"]) > 2 * sc["se"] and sc["roi"] > 0 else ""
        lines.append(f"| {fam}:{side} | {b} | {sc['n']} | {sc['hit']:.1%} | {fair:.1%} | {sc['roi']:+.1%} ± {sc['se']:.1%}{flag} |")
    return lines


def calibrated_bets(S: list[dict], by: str) -> dict[float, list[dict]]:
    """Fit landed-vs-fair per (family:side, band[, league]) on the earlier half; bet the
    later half where calibrated chance x price - 1 >= threshold. The earlier half is
    scored in-sample only to choose the threshold."""
    def bucket(s):                              # league: no chance band, the league is thin enough
        if by == "league":
            return (s["key"], s["country"] + "|" + s["comp"])
        return (s["key"], min(int(s["fair"] * 10), 9))
    fit: dict[tuple, list[int]] = defaultdict(lambda: [0, 0, 0.0])
    for s in S:
        if s["fair"] is not None and not s["late"]:
            f = fit[bucket(s)]
            f[0] += s["won"]
            f[1] += 1
            f[2] += s["fair"]
    out: dict[float, list[dict]] = {t: [] for t in THRESHOLDS}
    for s in S:
        if s["fair"] is None:
            continue
        w, n, fsum = fit.get(bucket(s), (0, 0, 0.0))
        if n < (60 if by == "league" else 100):
            continue
        k = 50                                   # shrink the bucket's gap toward zero
        cal = s["fair"] + (w - fsum) / (n + k)
        for t in THRESHOLDS:
            if cal * s["price"] - 1 >= t:
                out[t].append(s)
    return out


# ── idea 5: cross-market consistency (Poisson from SportyBet's own 1X2 + O/U 2.5) ──
def _pois(lam: float, k: int) -> float:
    return math.exp(-lam) * lam ** k / math.factorial(k)


def _grid(lh: float, la: float, n: int = 11) -> list[list[float]]:
    ph, pa = [_pois(lh, i) for i in range(n)], [_pois(la, j) for j in range(n)]
    return [[ph[i] * pa[j] for j in range(n)] for i in range(n)]


def implied(p_home: float, p_away: float, p_over: float) -> dict[str, float] | None:
    """λ total from P(over 2.5), split from P(home) - P(away); returns implied fair chances."""
    lo, hi = 0.2, 7.0
    for _ in range(50):
        mid = (lo + hi) / 2
        under = sum(_pois(mid, k) for k in range(3))
        lo, hi = (mid, hi) if 1 - under < p_over else (lo, mid)
    tot = (lo + hi) / 2
    lo, hi = 0.02, 0.98
    for _ in range(40):
        s = (lo + hi) / 2
        g = _grid(tot * s, tot * (1 - s))
        d = sum(g[i][j] for i in range(11) for j in range(11) if i > j) - sum(
            g[i][j] for i in range(11) for j in range(11) if i < j)
        lo, hi = (s, hi) if d < p_home - p_away else (lo, s)
    g = _grid(tot * (lo + hi) / 2, tot * (1 - (lo + hi) / 2))
    cell = [(i, j, g[i][j]) for i in range(11) for j in range(11)]
    over = lambda line: sum(p for i, j, p in cell if i + j > line)  # noqa: E731
    btts = sum(p for i, j, p in cell if i > 0 and j > 0)
    return {"o/u1.5:over": over(1.5), "o/u1.5:under": 1 - over(1.5),
            "o/u3.5:over": over(3.5), "o/u3.5:under": 1 - over(3.5),
            "btts:yes": btts, "btts:no": 1 - btts}


def cross_market_bets(S: list[dict]) -> tuple[dict[float, list[dict]], dict[float, list[dict]]]:
    """(Poisson-implied O/U 1.5/3.5 + BTTS, 1X2-implied double chance) value bets by threshold."""
    by_game: dict[str, list[dict]] = defaultdict(list)
    for s in S:
        by_game[s["game"]].append(s)
    pois: dict[float, list[dict]] = {t: [] for t in THRESHOLDS}
    dc: dict[float, list[dict]] = {t: [] for t in THRESHOLDS}
    for xs in by_game.values():
        fp = xs[0]["fp"]
        f1, fo = F.fair(fp.get("1x2")), F.fair(fp.get("ou2.5"))
        if not f1:
            continue
        imp = implied(f1[0], f1[2], fo[0]) if fo else None
        dci = {"dc:1x": f1[0] + f1[1], "dc:12": f1[0] + f1[2], "dc:x2": f1[1] + f1[2]}
        for s in xs:
            for src, book in ((imp, pois), (dci, dc)):
                if src and s["key"] in src:
                    for t in THRESHOLDS:
                        if src[s["key"]] * s["price"] - 1 >= t:
                            book[t].append(s)
    return pois, dc


# ── idea 4 + 17: timing (who is right at the close), steam, price shopping ─────
def timing(S: list[dict]) -> dict:
    """Log loss of SportyBet first/last and Matchbook first/last on 1X2, same games."""
    games: dict[str, list[dict]] = defaultdict(list)
    for s in S:
        if s["fam"] == "1x2":
            games[s["game"]].append(s)
    ll = defaultdict(float)
    n = 0
    for xs in games.values():
        if len(xs) != 3 or any(x["mb_first"] is None or x["mb_last"] is None for x in xs):
            continue
        lf = F.fair(xs[0]["lp"].get("1x2"))
        if not lf:
            continue
        w = next(i for i, x in enumerate(xs) if x["won"])
        n += 1
        ll["SportyBet first"] -= math.log(max(xs[w]["fair"], 1e-4))
        ll["SportyBet last"] -= math.log(max(lf[w], 1e-4))
        ll["Matchbook first"] -= math.log(max(xs[w]["mb_first"], 1e-4))
        ll["Matchbook last"] -= math.log(max(xs[w]["mb_last"], 1e-4))
    return {"n": n, **{k: v / n for k, v in ll.items()}} if n else {"n": 0}


def steam_bets(S: list[dict]) -> dict[str, dict[float, list[dict]]]:
    """Matchbook moved toward a side (fair chance up >= t) between its first and last look:
    'follow' bets that side at SportyBet's FIRST price only if SportyBet's first look came
    after Matchbook's first (not knowable here — so we bet at SportyBet's LAST price and score
    on result only); 'shop' bets SportyBet's last price when it beats Matchbook's last fair."""
    follow: dict[float, list[dict]] = {t: [] for t in (0.01, 0.02, 0.03, 0.05)}
    shop: dict[float, list[dict]] = {t: [] for t in THRESHOLDS}
    for s in S:
        if s["mb_last"] is None or s["mb_first"] is None or not s["last"]:
            continue
        late = dict(s, price=s["last"], clv_sb=None, clv_mb=s["last"] * s["mb_last"] - 1)
        for t in follow:
            if s["mb_last"] - s["mb_first"] >= t and late["clv_mb"] > 0:
                follow[t].append(late)
        for t in shop:
            if late["clv_mb"] >= t:
                shop[t].append(late)
    return {"follow": follow, "shop": shop}


def entry_time_h001(S: list[dict]) -> tuple[dict, dict]:
    """H001 (SportyBet 1X2 3%+ above Matchbook's first fair): enter at first vs at last price."""
    sel = [s for s in S if s["fam"] == "1x2" and s["mb_first"] and s["price"] * s["mb_first"] - 1 >= 0.03]
    first = score([s for s in sel if s["late"]])
    last = score([dict(s, price=s["last"], clv_sb=None) for s in sel if s["late"] and s["last"]])
    return first, last


# ── board singles: ideas 9, 15, 8/16 ───────────────────────────────────────
def board() -> list[dict]:
    import price_band_study as pb
    xs = [s for s in pb.singles() if s.get("result") in ("won", "lost") and s.get("chance")]
    xs.sort(key=lambda s: (s.get("kickoff_utc") or s.get("kickoff") or ""))
    return xs


def _bet(s: dict) -> dict:
    cp = s.get("closing_price")
    return {"won": int(s["result"] == "won"), "price": s["price"], "clv_sb": (s["price"] / cp - 1) if cp else None}


def disagreement(B: list[dict]) -> list[str]:
    """Idea 9: does the gap between the board's chance and SportyBet's implied chance
    (1/price x 0.95 for the margin) predict worse results? Bands fitted on the earlier
    half (terciles), scored on the later half."""
    def gap(s):
        return s["chance"] - min(0.99, 0.95 / s["price"])
    mid = len(B) // 2
    early = sorted(gap(s) for s in B[:mid])
    q1, q2 = early[len(early) // 3], early[2 * len(early) // 3]
    lines = [f"Terciles from the earlier half: gap ≤ {q1:+.3f} | ≤ {q2:+.3f} | above.", "",
             "| gap band | earlier half | later half |", "|---|---|---|"]
    res = {}
    for name, lo, hi in (("low", -9, q1), ("mid", q1, q2), ("high", q2, 9)):
        e = [s for s in B[:mid] if lo < gap(s) <= hi]
        lt = [s for s in B[mid:] if lo < gap(s) <= hi]
        conv = lambda xs: [_bet(s) for s in xs]  # noqa: E731
        res[name] = (score(conv(e)), score(conv(lt)))
        lines.append(f"| {name} | {fmt(res[name][0])} | {fmt(res[name][1])} |")
    # Kelly shrunk by disagreement vs flat, later half, stake units summed to the same total
    late = B[mid:]
    flat = [(s["price"] - 1) if s["result"] == "won" else -1 for s in late]
    w = [max(0.0, 1 - abs(gap(s)) / max(abs(q2), 1e-3)) for s in late]
    tw = sum(w) or 1
    shr = sum(wi * pl for wi, pl in zip(w, flat, strict=True)) / tw
    lines += ["", f"Later half, same total stake: flat {sum(flat) / len(flat):+.2%} per unit, "
              f"stake shrunk by disagreement {shr:+.2%} per unit."]
    return lines


def drift(B: list[dict]) -> list[str]:
    """Idea 15: a CUSUM on (stated - landed) per pick; while the alarm is up, stake 0.5.
    Parameters chosen on the earlier half, scored on the later half."""
    def run(xs, k, h):
        c, pl_on, pl_flat, alarms, on, saved = 0.0, 0.0, 0.0, 0, False, []
        for s in xs:                              # the alarm state is set BEFORE this pick settles
            pl = (s["price"] - 1) if s["result"] == "won" else -1.0
            pl_flat += pl
            pl_on += pl * (0.5 if on else 1.0)
            saved.append(-0.5 * pl if on else 0.0)
            c = max(0.0, c + (s["chance"] - (s["result"] == "won")) - k)
            if c > h and not on:
                on, alarms = True, alarms + 1
            if on and c == 0.0:
                on = False
        m = sum(saved) / len(saved)
        se = math.sqrt(sum((x - m) ** 2 for x in saved) / max(len(saved) - 1, 1) / len(saved))
        return pl_on / len(xs), pl_flat / len(xs), alarms, se, sum(1 for x in saved if x)
    mid = len(B) // 2
    best = max(((k, h) for k in (0.02, 0.05, 0.1) for h in (1.0, 2.0, 4.0)),
               key=lambda kh: run(B[:mid], *kh)[0] - run(B[:mid], *kh)[1])
    e, lt = run(B[:mid], *best), run(B[mid:], *best)
    return [f"Chosen on the earlier half: k = {best[0]}, h = {best[1]}.",
            f"Earlier half: with the alarm {e[0]:+.2%} per pick vs flat {e[1]:+.2%} ({e[2]} alarms, {e[4]} picks at half stake).",
            f"Later half: with the alarm {lt[0]:+.2%} per pick vs flat {lt[1]:+.2%} ({lt[2]} alarms, {lt[4]} picks at half "
            f"stake); gain {lt[0] - lt[1]:+.2%} ± {lt[3]:.2%} per pick."]


def exposure(B: list[dict]) -> list[str]:
    """Idea 16: cap picks per league per day. Do the picks past the cap (ranked by stated
    chance) do worse than the ones inside it? Cap chosen on the earlier half."""
    def split(xs, cap):
        grp: dict[tuple, list[dict]] = defaultdict(list)
        for s in xs:
            grp[((s.get("kickoff") or "")[:10], s.get("league"))].append(s)
        keep, over = [], []
        for g in grp.values():
            g.sort(key=lambda s: -s["chance"])
            keep += g[:cap]
            over += g[cap:]
        return score([_bet(s) for s in keep]), score([_bet(s) for s in over])
    mid = len(B) // 2
    best = max((1, 2, 3, 4), key=lambda c: (split(B[:mid], c)[0].get("roi", -9) - split(B[:mid], c)[1].get("roi", 9))
               if split(B[:mid], c)[1].get("n", 0) >= 30 else -9)
    e, lt = split(B[:mid], best), split(B[mid:], best)
    return [f"Cap chosen on the earlier half: {best} pick(s) per league per day.",
            f"- earlier: inside the cap {fmt(e[0])}; past it {fmt(e[1])}",
            f"- later: inside the cap **{fmt(lt[0])}**; past it **{fmt(lt[1])}**"]


def correlation(B: list[dict]) -> list[str]:
    """Ideas 8 + 16: residuals (won - stated) of two board picks on the same day — same
    league vs different league. And accas: landed vs the product of stated leg chances."""
    by_day: dict[str, list[dict]] = defaultdict(list)
    for s in B:
        by_day[(s.get("kickoff") or "")[:10]].append(s)
    same, diff = [], []
    for xs in by_day.values():
        for i in range(len(xs)):
            for j in range(i + 1, len(xs)):
                if xs[i].get("fixture") == xs[j].get("fixture"):
                    continue
                ri = (xs[i]["result"] == "won") - xs[i]["chance"]
                rj = (xs[j]["result"] == "won") - xs[j]["chance"]
                (same if xs[i].get("league") == xs[j].get("league") else diff).append(ri * rj)
    out = []
    for name, v in (("same league, same day", same), ("different league, same day", diff)):
        if v:
            m = sum(v) / len(v)
            se = math.sqrt(sum((x - m) ** 2 for x in v) / max(len(v) - 1, 1) / len(v))
            out.append(f"- {name}: {len(v)} pairs, residual covariance {m:+.4f} ± {se:.4f}")
    accs = []
    for f in sorted(glob(str(ROOT / "output" / "picks" / "picks_*.json"))):
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        for a in d.get("accas") or []:
            if a.get("result") in ("won", "lost") and a.get("chance"):
                accs.append(a)
    if accs:
        landed = sum(a["result"] == "won" for a in accs) / len(accs)
        stated = sum(a["chance"] for a in accs) / len(accs)
        out.append(f"- accas: {len(accs)} graded, landed {landed:.1%} vs stated {stated:.1%}")
        mid = len(accs) // 2
        e, lt = accs[:mid], accs[mid:]
        ratio = (sum(a["result"] == "won" for a in e) / len(e)) / (sum(a["chance"] for a in e) / len(e))
        bri = lambda xs, f: sum((f * a["chance"] - (a["result"] == "won")) ** 2 for a in xs) / len(xs)  # noqa: E731
        out.append(f"- acca chance x {ratio:.2f} (fitted on the earlier {len(e)}): later-half Brier "
                   f"{bri(lt, 1.0):.4f} -> {bri(lt, ratio):.4f}; later landed "
                   f"{sum(a['result'] == 'won' for a in lt) / len(lt):.1%} vs stated {sum(a['chance'] for a in lt) / len(lt):.1%}")
    return out


# ── report ─────────────────────────────────────────────────────────────────
def main() -> int:
    S, cut = sides()
    B = board()
    verdicts: list[tuple[str, str, str]] = []
    L = [f"# REASONING IDEAS STUDY — {datetime.now(UTC):%Y-%m-%d %H:%MZ}", "",
         f"To-do #7. {len({s['game'] for s in S})} graded football games from data/universe "
         f"({len(S)} priced sides at SportyBet's first look); the later half starts at kick-off {cut}. "
         f"{len(B)} graded board singles. Every threshold or map is chosen on the earlier half; the "
         "verdict reads the later half only. CLV MB = price taken x Matchbook's last fair chance - 1.", ""]

    L += ["## Ideas 2 + 11 — calibration by market and league, bias checks", "",
          "Flat 1-unit return of every side at SportyBet's first price (all games; ** = return above 2 se):", ""]
    L += bias_table(S) + [""]
    for by in ("market", "league"):
        t, e, lt = walk(calibrated_bets(S, by))
        L += [f"**Calibrated by {by}** (threshold {t:.0%}): earlier {fmt(e)}; later **{fmt(lt)}**", ""]
        verdicts.append((f"calibration by {by}", "WIN" if wins(lt) else "LOSE", fmt(lt)))

    L += ["## Idea 5 — cross-market consistency inside SportyBet", "",
          "Poisson goals fitted to SportyBet's own 1X2 + Over/Under 2.5 (margin removed); bet O/U 1.5, "
          "O/U 3.5 and BTTS when SportyBet's price beats the implied chance. Double chance read straight "
          "from the 1X2.", ""]
    pois, dc = cross_market_bets(S)
    for name, book in (("Poisson O/U 1.5/3.5 + BTTS", pois), ("1X2-implied double chance", dc)):
        t, e, lt = walk(book)
        L += [f"**{name}** (threshold {t:.0%}): earlier {fmt(e)}; later **{fmt(lt)}**", ""]
        verdicts.append((f"cross-market: {name}", "WIN" if wins(lt) else "LOSE", fmt(lt)))

    L += ["## Ideas 4 + 17 — timing, steam, price shopping", ""]
    tm = timing(S)
    if tm["n"]:
        L += [f"1X2 log loss on {tm['n']} games both books priced (lower is better):", ""]
        L += [f"- {k}: {v:.4f}" for k, v in tm.items() if k != "n"] + [""]
    st = steam_bets(S)
    for name in ("follow", "shop"):
        t, e, lt = walk(st[name])
        label = {"follow": "Follow Matchbook steam at SportyBet's last price",
                 "shop": "Price-shop at the close (SportyBet last vs Matchbook last fair)"}[name]
        L += [f"**{label}** (threshold {t:.0%}): earlier {fmt(e)}; later **{fmt(lt)}**", ""]
        verdicts.append((label, "WIN" if lt.get("n", 0) >= 60 and lt["roi"] > lt["se"] else "LOSE", fmt(lt)))
    f1, f2 = entry_time_h001(S)
    L += [f"**H001 entry time** (later half): at the first price {fmt(f1)}; at the last price {fmt(f2)}", ""]

    L += ["## Idea 9 — Kelly shrunk by model disagreement (board singles)", ""] + disagreement(B) + [""]
    L += ["## Idea 15 — drift detection (board singles)", ""] + drift(B) + [""]
    L += ["## Ideas 8 + 16 — correlation of picks and accas, exposure caps", ""] + correlation(B) + [""]
    L += exposure(B) + [""]

    L += ["## Verdicts (later half)", "", "| idea | verdict | later half |", "|---|---|---|"]
    L += [f"| {a} | {b} | {c} |" for a, b, c in verdicts]
    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L[-len(verdicts) - 2:]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
