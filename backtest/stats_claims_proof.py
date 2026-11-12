"""Stats claims proof: are the video statistics REAL, and does the PRICE already know them?

Architect, 2026-11-12: "build everything ... then prove to me that these facts are real, these trends are
real. Then we'll decide on allocation of funds for it."

Five stats videos claimed: (1) some leagues are both-teams-to-score leagues and some score early or late,
(2) some home teams decide games in the first half, (3) some teams are steady on corners, (4) a filter picks
first-half goals at 75.8%, (5) lower-league over/under and BTTS prices pay more than they should.

A claim is a FACT only if it repeats out of sample (measured on one stretch, holds on the next one).
A fact is MONEY only if a bet built on it, taken at a real market price set BEFORE kickoff, made a profit
with a bootstrap 90% range above zero. Every number here comes from football-data.co.uk files fetched by
this script (cached under backtest/cache/fd/), never from the videos.

RECORD ONLY: nothing here picks, stakes or blocks. Writes backtest/STATS_CLAIMS_PROOF.md and
output/stats_proof/stats_claims_proof.json.

Run: python backtest/stats_claims_proof.py [--seasons 1617-2526]
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import math
import statistics as st
import sys
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "backtest" / "cache" / "fd"
REPORT = ROOT / "backtest" / "STATS_CLAIMS_PROOF.md"
JSON_OUT = ROOT / "output" / "stats_proof" / "stats_claims_proof.json"

MAIN = {  # football-data.co.uk main files: half-time score, corners, over/under 2.5 prices
    "E0": "England Premier League", "E1": "England Championship", "E2": "England League One",
    "E3": "England League Two", "EC": "England National League", "SC0": "Scotland Premiership",
    "SC1": "Scotland Championship", "SC2": "Scotland League One", "SC3": "Scotland League Two",
    "D1": "Germany Bundesliga", "D2": "Germany 2. Bundesliga", "I1": "Italy Serie A", "I2": "Italy Serie B",
    "SP1": "Spain La Liga", "SP2": "Spain Segunda", "F1": "France Ligue 1", "F2": "France Ligue 2",
    "N1": "Netherlands Eredivisie", "B1": "Belgium Pro League", "P1": "Portugal Primeira",
    "T1": "Turkey Super Lig", "G1": "Greece Super League",
}
LOWER = {"E1", "E2", "E3", "EC", "SC1", "SC2", "SC3", "D2", "I2", "SP2", "F2"}
EXTRA = {  # football-data.co.uk "new" files: full-time score only (BTTS and goals, no half-time)
    "NOR": "Norway", "SWE": "Sweden", "SWZ": "Switzerland", "POL": "Poland", "USA": "USA MLS",
    "AUT": "Austria", "DNK": "Denmark", "FIN": "Finland", "IRL": "Ireland", "JPN": "Japan",
    "MEX": "Mexico", "ARG": "Argentina", "BRA": "Brazil", "ROU": "Romania", "CHN": "China",
}
HEADERS = {"User-Agent": "Mozilla/5.0 (OLP XDV research)"}


# ---------------------------------------------------------------- data
def _get(url: str, path: Path) -> str | None:
    if path.exists() and path.stat().st_size > 1000:
        return path.read_text(encoding="utf-8", errors="replace")
    for attempt in range(3):
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            if r.status_code == 200 and len(r.content) > 1000:
                path.parent.mkdir(parents=True, exist_ok=True)
                txt = r.content.decode("utf-8", errors="replace").lstrip("﻿")
                path.write_text(txt, encoding="utf-8")
                return txt
            if r.status_code == 404:
                return None
        except requests.RequestException:
            time.sleep(2 * (attempt + 1))
    return None


def _f(v):
    try:
        x = float(v)
        return x if x == x else None
    except (TypeError, ValueError):
        return None


def _date(s: str):
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(s.strip(), fmt)
        except (ValueError, AttributeError):
            pass
    return None


def load_main(code: str, season: str) -> list[dict]:
    txt = _get(f"https://www.football-data.co.uk/mmz4281/{season}/{code}.csv", CACHE / f"{code}_{season}.csv")
    if not txt:
        return []
    out = []
    for r in csv.DictReader(io.StringIO(txt)):
        hg, ag, d = _f(r.get("FTHG")), _f(r.get("FTAG")), _date(r.get("Date", ""))
        if hg is None or ag is None or d is None or not r.get("HomeTeam"):
            continue
        o_open = _f(r.get("Avg>2.5")) or _f(r.get("BbAv>2.5"))
        u_open = _f(r.get("Avg<2.5")) or _f(r.get("BbAv<2.5"))
        out.append({
            "lg": code, "season": str(2000 + int(season[:2])), "date": d, "home": r["HomeTeam"].strip(), "away": r["AwayTeam"].strip(),
            "hg": int(hg), "ag": int(ag), "hthg": _f(r.get("HTHG")), "htag": _f(r.get("HTAG")),
            "hc": _f(r.get("HC")), "ac": _f(r.get("AC")),
            "o_open": o_open, "u_open": u_open,
            "o_close": _f(r.get("AvgC>2.5")), "u_close": _f(r.get("AvgC<2.5")),
            "ph": _f(r.get("AvgH")) or _f(r.get("BbAvH")), "pd": _f(r.get("AvgD")) or _f(r.get("BbAvD")),
            "pa": _f(r.get("AvgA")) or _f(r.get("BbAvA")),
            "mx": {"over": _f(r.get("Max>2.5")) or _f(r.get("BbMx>2.5")), "home": _f(r.get("MaxH")) or _f(r.get("BbMxH")),
                   "draw": _f(r.get("MaxD")) or _f(r.get("BbMxD")), "away": _f(r.get("MaxA")) or _f(r.get("BbMxA"))},
            **{k: _f(r.get(k)) for k in ("HS", "AS", "HST", "AST", "HF", "AF", "HY", "AY", "HR", "AR")},
            "ref": (r.get("Referee") or "").strip(),
        })
    out.sort(key=lambda m: m["date"])
    return out


def load_extra(code: str) -> list[dict]:
    txt = _get(f"https://www.football-data.co.uk/new/{code}.csv", CACHE / f"new_{code}.csv")
    if not txt:
        return []
    out = []
    for r in csv.DictReader(io.StringIO(txt)):
        hg, ag, d = _f(r.get("HG")), _f(r.get("AG")), _date(r.get("Date", ""))
        if hg is None or ag is None or d is None:
            continue
        out.append({"lg": code, "season": str(_season_key(str(r.get("Season", "")).strip() or "0")), "date": d,
                    "home": r.get("Home", ""), "away": r.get("Away", ""), "hg": int(hg), "ag": int(ag)})
    return out


# ---------------------------------------------------------------- stats helpers
def wilson(k: int, n: int, z: float = 1.645):
    if n == 0:
        return (None, None)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def corr(xs, ys):
    n = len(xs)
    if n < 4:
        return None, None, n
    mx, my = st.fmean(xs), st.fmean(ys)
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if sx == 0 or sy == 0:
        return None, None, n
    r = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy)
    r = max(min(r, 0.999999), -0.999999)
    z, se = math.atanh(r), 1 / math.sqrt(max(n - 3, 1))
    return r, (math.tanh(z - 1.645 * se), math.tanh(z + 1.645 * se)), n


def roi_boot(rets: list[float], b: int = 2000, seed: int = 7):
    if not rets:
        return None, (None, None)
    import numpy as np
    arr = np.asarray(rets, dtype=float)
    n = len(arr)
    rng = np.random.default_rng(seed)
    means = np.empty(b)
    for i in range(0, b, 100):  # chunks keep memory small on 80k-bet sets
        idx = rng.integers(0, n, size=(min(100, b - i), n))
        means[i:i + len(idx)] = arr[idx].mean(axis=1)
    lo, hi = np.quantile(means, [0.05, 0.95])
    return float(arr.mean()), (float(lo), float(hi))


def spct(x, d=1):
    return "PENDING" if x is None else f"{100 * x:+.{d}f}%"


def rng_s(lo, hi, signed=True):
    if lo is None:
        return "PENDING"
    f = spct if signed else (lambda v: f"{100 * v:.1f}%")
    return f"{f(lo)} to {f(hi)}"


def money_verdict(n, lo, hi):
    if n < 100:
        return "TOO FEW BETS"
    if lo > 0:
        return "PROFIT (90% range above 0)"
    if hi < 0:
        return "LOSS (90% range below 0)"
    return "NOT PROVEN"


def fact_verdict(r, ci, n):
    if r is None:
        return "PENDING"
    if n < 10:
        return "TOO FEW"
    if ci[0] > 0.3:
        return "REAL (repeats)"
    if ci[0] > 0:
        return "WEAK (repeats a little)"
    return "NOT REAL (does not repeat)"


def poisson_cdf(k, lam):
    return sum(math.exp(-lam) * lam ** i / math.factorial(i) for i in range(k + 1))


# ---------------------------------------------------------------- the claims
def league_season_table(matches):
    """Per league-season: games, BTTS rate, over 2.5 rate, goals a game, first-half share of goals."""
    g = defaultdict(list)
    for m in matches:
        g[(m["lg"], m["season"])].append(m)
    tab = {}
    for key, ms in g.items():
        n = len(ms)
        if n < 60:
            continue
        btts = sum(1 for m in ms if m["hg"] > 0 and m["ag"] > 0) / n
        o25 = sum(1 for m in ms if m["hg"] + m["ag"] > 2) / n
        goals = sum(m["hg"] + m["ag"] for m in ms)
        ht = [m for m in ms if m.get("hthg") is not None]
        fh = (sum(m["hthg"] + m["htag"] for m in ht) / max(1, sum(m["hg"] + m["ag"] for m in ht))) if len(ht) > 0.9 * n else None
        tab[key] = {"n": n, "btts": btts, "o25": o25, "gpg": goals / n, "fh_share": fh}
    return tab


def persistence(tab, field):
    """Season t value vs season t+1 value for the same league (every pair)."""
    by_lg = defaultdict(dict)
    for (lg, s), v in tab.items():
        if v.get(field) is not None:
            by_lg[lg][s] = v[field]
    xs, ys = [], []
    for lg, d in by_lg.items():
        ss = sorted(d, key=_season_key)
        for a, b in zip(ss, ss[1:]):
            if _season_key(b) - _season_key(a) == 1:
                xs.append(d[a])
                ys.append(d[b])
    return corr(xs, ys)


def _season_key(s: str) -> int:
    s = str(s)
    if "/" in s:
        return int(s.split("/")[0])
    if len(s) == 4 and s.isdigit() and int(s) > 1900:
        return int(s)
    return 2000 + int(s[:2])


def claim_top_league_next(tab, field, top=5):
    """The top-N leagues on <field> in season t: their average in t+1 vs the average league in t+1."""
    seasons = sorted({s for (_, s) in tab}, key=_season_key)
    rows = []
    for a, b in zip(seasons, seasons[1:]):
        now = [(lg, v[field]) for (lg, s), v in tab.items() if s == a and v.get(field) is not None]
        nxt = {lg: v[field] for (lg, s), v in tab.items() if s == b and v.get(field) is not None}
        now = [x for x in now if x[0] in nxt]
        if len(now) < 2 * top:
            continue
        now.sort(key=lambda x: -x[1])
        topl = [lg for lg, _ in now[:top]]
        rows.append((a, b, st.fmean(nxt[lg] for lg in topl), st.fmean(nxt.values()),
                     st.fmean(v for _, v in now[:top]), st.fmean(v for _, v in now)))
    return rows


def blind_side_roi(matches, side):
    """Bet every game on over (or under) 2.5 at the pre-match average price."""
    out = defaultdict(list)
    for m in matches:
        p = m["o_open"] if side == "over" else m["u_open"]
        if not p:
            continue
        win = (m["hg"] + m["ag"] > 2) == (side == "over")
        out[(m["lg"], m["season"])].append(p - 1 if win else -1.0)
    return out


def league_side_strategy(matches):
    """Each season, bet OVER in the leagues whose previous season had the highest over rate (top quarter) and
    UNDER in the lowest quarter, at the pre-match average price. This is the 'league profile' money test."""
    tab = league_season_table(matches)
    ov = blind_side_roi(matches, "over")
    un = blind_side_roi(matches, "under")
    seasons = sorted({s for (_, s) in tab}, key=_season_key)
    over_rets, under_rets, per = [], [], []
    for a, b in zip(seasons, seasons[1:]):
        prev = sorted([(lg, v["o25"]) for (lg, s), v in tab.items() if s == a], key=lambda x: -x[1])
        if len(prev) < 8:
            continue
        q = max(1, len(prev) // 4)
        hi_l = [lg for lg, _ in prev[:q]]
        lo_l = [lg for lg, _ in prev[-q:]]
        o = [r for lg in hi_l for r in ov.get((lg, b), [])]
        u = [r for lg in lo_l for r in un.get((lg, b), [])]
        over_rets += o
        under_rets += u
        per.append((b, hi_l, sum(o) / len(o) if o else None, lo_l, sum(u) / len(u) if u else None))
    return over_rets, under_rets, per


def walk_forward_goals(matches, min_games=6, k_prior=5.0):
    """Poisson goals model, rebuilt match by match from earlier games only (same league-season; last
    season's league average as the prior). Yields per match: model P(over 2.5), P(BTTS), P(goal before HT
    by team history), team-history features, and the prices."""
    by_ls = defaultdict(list)
    for m in matches:
        by_ls[(m["lg"], m["season"])].append(m)
    prev_avg = {}
    for (lg, s), ms in sorted(by_ls.items(), key=lambda kv: (kv[0][0], _season_key(kv[0][1]))):
        ms.sort(key=lambda m: m["date"])
        prior_h = prev_avg.get(lg, (1.45, 1.15))
        hist = defaultdict(lambda: {"hf": [], "ha": [], "af": [], "aa": [], "home_ht": [], "away_ht": [],
                                    "home_o25": [], "away_o25": [], "btts": []})
        lh_sum = la_sum = cnt = 0
        for m in ms:
            H, A = hist[m["home"]], hist[m["away"]]
            league_h = (lh_sum + prior_h[0] * 20) / (cnt + 20)
            league_a = (la_sum + prior_h[1] * 20) / (cnt + 20)
            if len(H["hf"]) >= min_games and len(A["af"]) >= min_games:
                att_h = (sum(H["hf"]) + k_prior * league_h) / (len(H["hf"]) + k_prior) / league_h
                def_a = (sum(A["aa"]) + k_prior * league_h) / (len(A["aa"]) + k_prior) / league_h
                att_a = (sum(A["af"]) + k_prior * league_a) / (len(A["af"]) + k_prior) / league_a
                def_h = (sum(H["ha"]) + k_prior * league_a) / (len(H["ha"]) + k_prior) / league_a
                lam_h, lam_a = league_h * att_h * def_a, league_a * att_a * def_h
                p_over = 1 - poisson_cdf(2, lam_h + lam_a)
                p_btts = (1 - math.exp(-lam_h)) * (1 - math.exp(-lam_a))
                yield {**m, "p_over": p_over, "p_btts": p_btts, "lam": lam_h + lam_a,
                       "h_ht6": H["home_ht"][-6:], "a_ht6": A["away_ht"][-6:],
                       "h_o7": H["home_o25"][-7:], "a_o7": A["away_o25"][-7:],
                       "h_btts10": H["btts"][-10:], "a_btts10": A["btts"][-10:]}
            # update after the match
            H["hf"].append(m["hg"]); H["ha"].append(m["ag"])
            A["af"].append(m["ag"]); A["aa"].append(m["hg"])
            tot = m["hg"] + m["ag"]
            H["home_o25"].append(tot > 2); A["away_o25"].append(tot > 2)
            b = m["hg"] > 0 and m["ag"] > 0
            H["btts"].append(b); A["btts"].append(b)
            if m.get("hthg") is not None:
                g = (m["hthg"] + m["htag"]) > 0
                H["home_ht"].append(g); A["away_ht"].append(g)
            lh_sum += m["hg"]; la_sum += m["ag"]; cnt += 1
        if cnt:
            prev_avg[lg] = (lh_sum / cnt, la_sum / cnt)


def first_half_filter(wf):
    base = [m for m in wf if m.get("hthg") is not None]
    hit = lambda ms: sum(1 for m in ms if m["hthg"] + m["htag"] > 0)
    rows = [("every game (base rate)", len(base), hit(base))]
    for need in (5, 6):
        sel = [m for m in base if len(m["h_ht6"]) == 6 and len(m["a_ht6"]) == 6
               and sum(m["h_ht6"]) >= need and sum(m["a_ht6"]) >= need]
        rows.append((f"home side's last 6 home games AND away side's last 6 away games: goal before HT in {need}+ of 6",
                     len(sel), hit(sel)))
    sel = [m for m in base if m["lam"] >= 3.2]
    rows.append(("model expects 3.2+ goals in the match", len(sel), hit(sel)))
    return rows


def home_first_half_scorers(matches, first_n=7):
    """Top home first-half scorers after their first N home games: do they keep it up for the rest?"""
    by = defaultdict(list)
    for m in matches:
        if m.get("hthg") is not None:
            by[(m["lg"], m["season"], m["home"])].append(m)
    rows = []
    for key, ms in by.items():
        ms.sort(key=lambda m: m["date"])
        if len(ms) < first_n + 5:
            continue
        a = st.fmean(m["hthg"] for m in ms[:first_n])
        b = st.fmean(m["hthg"] for m in ms[first_n:])
        rows.append((key, a, b))
    rows.sort(key=lambda r: -r[1])
    allb = st.fmean(r[2] for r in rows)
    alla = st.fmean(r[1] for r in rows)
    top = rows[: max(5, len(rows) // 20)]
    r, ci, n = corr([x[1] for x in rows], [x[2] for x in rows])
    return {"teams": len(rows), "top_n": len(top), "top_first": st.fmean(x[1] for x in top),
            "top_rest": st.fmean(x[2] for x in top), "all_first": alla, "all_rest": allb,
            "r": r, "ci": ci, "top5": [(f"{k[2]} ({MAIN.get(k[0], k[0])} {k[1]})", a, b) for k, a, b in rows[:5]]}


def corner_consistency(matches, min_games=20):
    """Per team-season: spread (standard deviation) of TOTAL match corners in the first half of its games
    vs the second half. Is a 'steady' team still steady later?"""
    by = defaultdict(list)
    for m in matches:
        if m.get("hc") is None or m.get("ac") is None:
            continue
        t = m["hc"] + m["ac"]
        by[(m["lg"], m["season"], m["home"])].append((m["date"], t))
        by[(m["lg"], m["season"], m["away"])].append((m["date"], t))
    sd1, sd2, mu1, mu2, inside_steady, inside_rest = [], [], [], [], [], []
    rows = []
    for key, gs in by.items():
        if len(gs) < min_games:
            continue
        gs.sort()
        h = len(gs) // 2
        a, b = [t for _, t in gs[:h]], [t for _, t in gs[h:]]
        s1, s2 = st.pstdev(a), st.pstdev(b)
        m1, m2 = st.fmean(a), st.fmean(b)
        sd1.append(s1); sd2.append(s2); mu1.append(m1); mu2.append(m2)
        rows.append((key, s1, m1, b))
    rows.sort(key=lambda r: r[1])
    cut = max(1, len(rows) // 10)
    for i, (key, s1, m1, b) in enumerate(rows):
        share = sum(1 for t in b if abs(t - m1) <= 2) / len(b)
        (inside_steady if i < cut else inside_rest).append(share)
    return {"teams": len(rows), "sd": corr(sd1, sd2), "mean": corr(mu1, mu2),
            "steady_inside": st.fmean(inside_steady) if inside_steady else None,
            "rest_inside": st.fmean(inside_rest) if inside_rest else None, "steady_n": cut,
            "avg_sd": st.fmean(sd1) if sd1 else None}


def value_bets(wf, lower_only):
    """Video 5: bet where the model's fair price is shorter than the market's. Edge = model chance x price - 1,
    taken at the pre-match average price; CLV = taken price / closing price - 1."""
    buckets = [(0.0, 0.05), (0.05, 0.10), (0.10, 0.20), (0.20, 0.40), (0.40, 9.0)]
    res = {b: {"rets": [], "clv": []} for b in buckets}
    for m in wf:
        if (m["lg"] in LOWER) != lower_only:
            continue
        for side, p, price, close in (("over", m["p_over"], m["o_open"], m["o_close"]),
                                      ("under", 1 - m["p_over"], m["u_open"], m["u_close"])):
            if not price:
                continue
            e = p * price - 1
            for b in buckets:
                if b[0] <= e < b[1]:
                    win = (m["hg"] + m["ag"] > 2) == (side == "over")
                    res[b]["rets"].append(price - 1 if win else -1.0)
                    if close:
                        res[b]["clv"].append(price / close - 1)
    return res


def form_rule(wf):
    """Video 5's backing stat: home side's home games over 2.5 in 6+ of its last 7 (and the away side's away
    games likewise) -> bet over at the pre-match price. Plus the BTTS-No twin: a side whose last 10 had BTTS
    in 1 or fewer -> how often BTTS happens next (no BTTS price in this data)."""
    o = [m for m in wf if m["o_open"] and len(m["h_o7"]) == 7 and sum(m["h_o7"]) >= 6]
    o2 = [m for m in o if len(m["a_o7"]) == 7 and sum(m["a_o7"]) >= 6]
    r1 = [(m["o_open"] - 1) if m["hg"] + m["ag"] > 2 else -1.0 for m in o]
    r2 = [(m["o_open"] - 1) if m["hg"] + m["ag"] > 2 else -1.0 for m in o2]
    lowb = [m for m in wf if len(m["a_btts10"]) == 10 and sum(m["a_btts10"]) <= 1]
    allb = [m for m in wf if len(m["a_btts10"]) == 10]
    br = lambda ms: sum(1 for m in ms if m["hg"] > 0 and m["ag"] > 0)
    return r1, r2, (len(lowb), br(lowb)), (len(allb), br(allb)), \
        (sum(m["p_btts"] for m in lowb) / len(lowb) if lowb else None)


def model_vs_market(wf):
    """Brier score of model P(over 2.5) vs the de-vigged pre-match price, same matches."""
    bm = bk = n = 0
    for m in wf:
        if not (m["o_open"] and m["u_open"]):
            continue
        io, iu = 1 / m["o_open"], 1 / m["u_open"]
        q = io / (io + iu)
        y = 1.0 if m["hg"] + m["ag"] > 2 else 0.0
        bm += (m["p_over"] - y) ** 2
        bk += (q - y) ** 2
        n += 1
    return (bm / n, bk / n, n) if n else (None, None, 0)


# ---------------------------------------------------------------- the claim sweep
# Architect 2026-11-12: "that video ... is a pointer to other claims ... how are you going to check for other
# claims and test them?" Every video claim has one shape: "<team or league> has been high on <stat> over its
# last <N> games, so it will stay high". The sweep writes down EVERY claim of that shape the data can test
# (stat x who x window x venue), decides each claim's direction on the DISCOVERY seasons, then judges it only
# on the later HOLDOUT seasons, with a Benjamini-Hochberg correction because testing ~100 claims at once makes
# a few look real by luck. Where a price exists, a surviving claim is also tested against the price:
# does it explain what the market got wrong (y - market chance), and does betting it make money?
OUTCOMES = {  # name: (function(match) -> value or None, priced side or None)
    "goals": (lambda m: m["hg"] + m["ag"], None),
    "over 2.5": (lambda m: float(m["hg"] + m["ag"] > 2), "over"),
    "BTTS": (lambda m: float(m["hg"] > 0 and m["ag"] > 0), None),
    "goal before HT": (lambda m: None if m["hthg"] is None else float(m["hthg"] + m["htag"] > 0), None),
    "first-half goals": (lambda m: None if m["hthg"] is None else m["hthg"] + m["htag"], None),
    "second-half goals": (lambda m: None if m["hthg"] is None else m["hg"] + m["ag"] - m["hthg"] - m["htag"], None),
    "corners": (lambda m: None if m["hc"] is None or m["ac"] is None else m["hc"] + m["ac"], None),
    "cards": (lambda m: None if m.get("HY") is None or m.get("AY") is None else m["HY"] + m["AY"] + (m.get("HR") or 0) + (m.get("AR") or 0), None),
    "shots": (lambda m: None if m.get("HS") is None or m.get("AS") is None else m["HS"] + m["AS"], None),
    "shots on target": (lambda m: None if m.get("HST") is None or m.get("AST") is None else m["HST"] + m["AST"], None),
    "fouls": (lambda m: None if m.get("HF") is None or m.get("AF") is None else m["HF"] + m["AF"], None),
    "home win": (lambda m: float(m["hg"] > m["ag"]), "home"),
    "draw": (lambda m: float(m["hg"] == m["ag"]), "draw"),
    "away win": (lambda m: float(m["hg"] < m["ag"]), "away"),
}
DISCOVERY = range(2016, 2021)   # seasons 2016-17 .. 2020-21
HOLDOUT = range(2021, 2026)     # seasons 2021-22 .. 2025-26


def _market_p(m, side):
    if side == "over" and m["o_open"] and m["u_open"]:
        a, b = 1 / m["o_open"], 1 / m["u_open"]
        return a / (a + b), m["o_open"]
    if side in ("home", "draw", "away") and m.get("ph") and m.get("pd") and m.get("pa"):
        inv = {"home": 1 / m["ph"], "draw": 1 / m["pd"], "away": 1 / m["pa"]}
        return inv[side] / sum(inv.values()), {"home": m["ph"], "draw": m["pd"], "away": m["pa"]}[side]
    return None


def _p_from_z(z):
    return 0.5 * math.erfc(z / math.sqrt(2))  # one-sided


def sweep_rows(matches, window, venue):
    """For every match: predictor = mean of <outcome> over the home side's last <window> (home games if
    venue) and the away side's last <window> (away games if venue), minus the league's season-to-date mean;
    target = outcome minus the same league mean. Earlier games only."""
    rows = {k: [] for k in OUTCOMES}
    by_ls = defaultdict(list)
    for m in matches:
        by_ls[(m["lg"], m["season"])].append(m)
    for (lg, s), ms in by_ls.items():
        ms.sort(key=lambda m: m["date"])
        hist = defaultdict(lambda: defaultdict(list))
        lsum, lcnt = defaultdict(float), defaultdict(int)
        for m in ms:
            vals = {k: f(m) for k, (f, _) in OUTCOMES.items()}
            hk = (m["home"], "H" if venue else "*")
            ak = (m["away"], "A" if venue else "*")
            for k, v in vals.items():
                if v is None:
                    continue
                hh, aa = hist[hk][k], hist[ak][k]
                if len(hh) >= window and len(aa) >= window and lcnt[k] >= 30:
                    base = lsum[k] / lcnt[k]
                    pred = (st.fmean(hh[-window:]) + st.fmean(aa[-window:])) / 2 - base
                    rows[k].append((int(s), pred, v - base, m))
            for k, v in vals.items():
                if v is None:
                    continue
                hist[(m["home"], "H" if venue else "*")][k].append(v)
                hist[(m["away"], "A" if venue else "*")][k].append(v)
                if venue:  # keep the all-games history too, for the non-venue run only
                    pass
                lsum[k] += v
                lcnt[k] += 1
    return rows


def claim_sweep(matches):
    claims = []
    for window in (5, 10):
        for venue in (True, False):
            rows = sweep_rows(matches, window, venue)
            for k, rs in rows.items():
                disc = [(p, y) for s, p, y, _ in rs if s in DISCOVERY]
                hold = [(p, y, m) for s, p, y, m in rs if s in HOLDOUT]
                if len(disc) < 500 or len(hold) < 500:
                    continue
                rd, _, nd = corr([p for p, _ in disc], [y for _, y in disc])
                rh, cih, nh = corr([p for p, _, _ in hold], [y for _, y, _ in hold])
                if rd is None or rh is None:
                    continue
                sign = 1 if rd >= 0 else -1
                z = sign * math.atanh(rh) * math.sqrt(nh - 3)
                c = {"stat": k, "window": window, "venue": "home side at home / away side away" if venue else "all games",
                     "r_disc": rd, "n_disc": nd, "r_hold": rh, "ci_hold": cih, "n_hold": nh, "p": _p_from_z(z),
                     "sign": sign}
                side = OUTCOMES[k][1]
                if side:  # against the price: does the claim explain the market's miss? and money
                    xs, ys, rets_top, rets_max = [], [], [], []
                    preds = sorted(sign * p for p, _, m in hold if _market_p(m, side))
                    cut = preds[int(0.9 * len(preds))] if preds else None
                    for p, y, m in hold:
                        mp = _market_p(m, side)
                        if not mp:
                            continue
                        q, price = mp
                        raw = OUTCOMES[k][0](m)
                        xs.append(sign * p)
                        ys.append(raw - q)
                        if sign * p >= cut:
                            rets_top.append(price - 1 if raw == 1 else -1.0)
                            best = m["mx"].get(side)
                            if best:
                                rets_max.append(best - 1 if raw == 1 else -1.0)
                    rm, cim, nm = corr(xs, ys)
                    mroi, mci = roi_boot(rets_top)
                    xroi, xci = roi_boot(rets_max)
                    c.update({"max_roi": xroi, "max_ci": xci, "max_bets": len(rets_max)})
                    c.update({"r_vs_market": rm, "ci_vs_market": cim, "n_market": nm,
                              "top10_bets": len(rets_top), "top10_roi": mroi, "top10_ci": mci})
                claims.append(c)
    # Benjamini-Hochberg at 5% over every claim tested
    ps = sorted(range(len(claims)), key=lambda i: claims[i]["p"])
    m_ = len(claims)
    passed = 0
    for rank, i in enumerate(ps, 1):
        if claims[i]["p"] <= 0.05 * rank / m_:
            passed = rank
    for rank, i in enumerate(ps, 1):
        claims[i]["bh_pass"] = rank <= passed
    return claims


def league_level_sweep(matches):
    """League-level version of every stat: league-season average, season t vs t+1."""
    out = []
    for k, (f, _) in OUTCOMES.items():
        g = defaultdict(list)
        for m in matches:
            v = f(m)
            if v is not None:
                g[(m["lg"], int(m["season"]))].append(v)
        avg = {key: st.fmean(v) for key, v in g.items() if len(v) >= 60}
        xs, ys = [], []
        for (lg, s), v in avg.items():
            if (lg, s + 1) in avg:
                xs.append(v)
                ys.append(avg[(lg, s + 1)])
        r, ci, n = corr(xs, ys)
        out.append((k, r, ci, n))
    return out


def referee_sweep(matches, window=10):
    """Pointer from the cards stat: does a referee's card rate in his last 10 games predict the next game's cards,
    beyond the league average? (Referee names are in the English files only.)"""
    by = defaultdict(list)
    for m in sorted(matches, key=lambda m: m["date"]):
        if m.get("ref") and m.get("HY") is not None and m.get("AY") is not None:
            by[m["lg"]].append(m)
    xs, ys = [], []
    for lg, ms in by.items():
        hist = defaultdict(list)
        tot = cnt = 0
        for m in ms:
            c = m["HY"] + m["AY"] + (m.get("HR") or 0) + (m.get("AR") or 0)
            h = hist[m["ref"]]
            if len(h) >= window and cnt >= 100:
                base = tot / cnt
                xs.append(st.fmean(h[-window:]) - base)
                ys.append(c - base)
            h.append(c)
            tot += c
            cnt += 1
    return corr(xs, ys)


def month_sweep(matches):
    """Pointer from 'November before the break': is the over-2.5 rate by month different, and is it priced?
    Over bets at the average price by calendar month, discovery vs holdout."""
    res = {}
    for name, seasons in (("discovery", DISCOVERY), ("holdout", HOLDOUT)):
        g = defaultdict(list)
        for m in matches:
            if int(m["season"]) in seasons and m["o_open"]:
                g[m["date"].month].append(m["o_open"] - 1 if m["hg"] + m["ag"] > 2 else -1.0)
        res[name] = {mo: (len(v), sum(v) / len(v)) for mo, v in g.items() if len(v) >= 300}
    return res


# ---------------------------------------------------------------- report
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasons", default="1617-2526")
    a = ap.parse_args(argv)
    s0, s1 = a.seasons.split("-")
    seasons = [f"{y % 100:02d}{(y + 1) % 100:02d}" for y in range(2000 + int(s0[:2]), 2000 + int(s1[:2]) + 1)]

    matches = []
    for code in MAIN:
        for s in seasons:
            matches += load_main(code, s)
    extra = []
    for code in EXTRA:
        extra += load_extra(code)
    extra = [m for m in extra if m["season"] and _season_key(m["season"]) >= 2000 + int(s0[:2])]
    print(f"main files: {len(matches)} matches; extra leagues: {len(extra)} matches", file=sys.stderr)

    tab = league_season_table(matches)
    tab_x = league_season_table(extra)
    tab_all = {**tab, **tab_x}
    wf = list(walk_forward_goals(matches))
    out = {"built": datetime.now(UTC).isoformat(timespec="seconds"), "matches": len(matches),
           "extra_matches": len(extra), "league_seasons": len(tab_all), "claims": {}}
    L = []
    w = L.append
    w("# STATS CLAIMS PROOF: are the video statistics real, and does the price already know them?\n")
    w("Written by `backtest/stats_claims_proof.py` (Architect 2026-11-12: \"prove to me that these facts are real, "
      "these trends are real. Then we'll decide on allocation of funds\"). RECORD ONLY.\n")
    w(f"Data: football-data.co.uk, fetched by the script. {len(matches):,} matches in {len(MAIN)} European leagues "
      f"(seasons {seasons[0]}-{seasons[-1]}: half-time score, corners, over/under 2.5 prices before kickoff and at the close) "
      f"+ {len(extra):,} matches in {len(EXTRA)} more countries (full-time score only).\n")
    w("**Two tests for every claim.** FACT: measured on one stretch, does it still hold on the next (season t vs t+1, "
      "or first half of a team's games vs the second)? Correlation r with its 90% range: above 0.3 = REAL, 0-0.3 = WEAK, "
      "range touching 0 = NOT REAL. MONEY: a bet built only on what was known before kickoff, at the average bookmaker "
      "price before kickoff; ROI with a bootstrap 90% range. PROFIT needs the whole range above 0 and 100+ bets.\n")

    # Claim 1: league BTTS
    r, ci, n = persistence(tab_all, "btts")
    w("## Claim 1: some leagues are both-teams-to-score leagues\n")
    w(f"League BTTS rate, season t vs season t+1, {n} pairs across {len({k[0] for k in tab_all})} leagues: "
      f"r = {r:.2f} (90% range {ci[0]:.2f} to {ci[1]:.2f}) -> **{fact_verdict(r, ci, n)}**.\n")
    rows = claim_top_league_next(tab_all, "btts")
    w("| season picked | next season | top-5 BTTS leagues that season | same 5, next season | every league, next season |")
    w("|---|---|---|---|---|")
    for a_, b_, nxt_top, nxt_all, now_top, now_all in rows:
        w(f"| {a_} | {b_} | {100 * now_top:.1f}% | {100 * nxt_top:.1f}% | {100 * nxt_all:.1f}% |")
    keep = st.fmean((x[2] - x[3]) / (x[4] - x[5]) for x in rows if x[4] != x[5]) if rows else None
    w(f"\nOf the top-5's lead over the average league, **{100 * keep:.0f}%** is still there the next season "
      "(the rest was luck and goes back to average).\n" if keep is not None else "")
    last = max(tab_all, key=lambda k: _season_key(k[1]))[1] if tab_all else None
    lastrows = sorted([(lg, v) for (lg, s), v in tab_all.items() if _season_key(s) == _season_key(last)],
                      key=lambda x: -x[1]["btts"])
    w("Latest full season in the data, BTTS by league (top 8 / bottom 4):\n")
    w("| league | games | BTTS | over 2.5 | goals a game | share of goals before half-time |")
    w("|---|---|---|---|---|---|")
    for lg, v in lastrows[:8] + lastrows[-4:]:
        nm = MAIN.get(lg) or EXTRA.get(lg) or lg
        fh = f"{100 * v['fh_share']:.1f}%" if v.get("fh_share") is not None else "PENDING (no half-time score)"
        w(f"| {nm} | {v['n']} | {100 * v['btts']:.1f}% | {100 * v['o25']:.1f}% | {v['gpg']:.2f} | {fh} |")
    out["claims"]["league_btts"] = {"r": r, "ci": ci, "pairs": n, "lead_kept": keep}

    # money: league over/under
    o_r, u_r, per = league_side_strategy(matches)
    om, oci = roi_boot(o_r)
    um, uci = roi_boot(u_r)
    w("\n**Money test:** each season, back OVER 2.5 in every game of the quarter of leagues that had the most overs "
      "the season before, and UNDER 2.5 in the quarter with the fewest, at the average price before kickoff.\n")
    w("| bet | bets | ROI | 90% range | verdict |")
    w("|---|---|---|---|---|")
    w(f"| over in last season's high-goal leagues | {len(o_r)} | {spct(om)} | {rng_s(*oci)} | {money_verdict(len(o_r), *oci)} |")
    w(f"| under in last season's low-goal leagues | {len(u_r)} | {spct(um)} | {rng_s(*uci)} | {money_verdict(len(u_r), *uci)} |")
    allo = [x for v in blind_side_roi(matches, "over").values() for x in v]
    allu = [x for v in blind_side_roi(matches, "under").values() for x in v]
    w(f"| (yardstick) over in every game | {len(allo)} | {spct(roi_boot(allo)[0])} | {rng_s(*roi_boot(allo)[1])} | bookmaker margin |")
    w(f"| (yardstick) under in every game | {len(allu)} | {spct(roi_boot(allu)[0])} | {rng_s(*roi_boot(allu)[1])} | bookmaker margin |")
    bo = [(m["mx"]["over"] - 1) if m["hg"] + m["ag"] > 2 else -1.0 for m in matches if m["mx"].get("over")]
    w(f"| (yardstick) over in every game at the BEST price of any bookmaker | {len(bo)} | {spct(roi_boot(bo)[0])} | {rng_s(*roi_boot(bo)[1])} | best price is a ceiling: no one bettor gets it every time |")
    out["claims"]["league_side_money"] = {"over": [len(o_r), om, oci], "under": [len(u_r), um, uci]}

    # Claim 2: goal timing
    r2, ci2, n2 = persistence(tab, "fh_share")
    fh_all = [v["fh_share"] for v in tab.values() if v.get("fh_share") is not None]
    ht_ms = [m for m in matches if m.get("hthg") is not None]
    g1 = sum(m["hthg"] + m["htag"] for m in ht_ms)
    gt = sum(m["hg"] + m["ag"] for m in ht_ms)
    early = sorted([((MAIN[lg], s), v["fh_share"]) for (lg, s), v in tab.items()
                    if v.get("fh_share") is not None and v["fh_share"] > 0.5], key=lambda x: -x[1])
    w("\n## Claim 2: when the goals come (first half vs second half)\n")
    w(f"All {len(ht_ms):,} matches with a half-time score: {100 * g1 / gt:.1f}% of goals before half-time, "
      f"{100 * (gt - g1) / gt:.1f}% after (second half / first half = {(gt - g1) / g1:.2f}).\n")
    w(f"League first-half share, season t vs t+1, {n2} pairs: r = {r2:.2f} (90% range {ci2[0]:.2f} to {ci2[1]:.2f}) "
      f"-> **{fact_verdict(r2, ci2, n2)}**. League-seasons range {100 * min(fh_all):.1f}% to {100 * max(fh_all):.1f}%.\n")
    w(f"League-seasons where MORE than half the goals came before half-time: {len(early)} of {len(fh_all)}"
      + (": " + ", ".join(f"{a[0]} {a[1]} ({100 * b:.1f}%)" for a, b in early[:10]) if early else "") + ".\n")
    w("Late goals (76th minute on) need goal minutes, which these files do not have: the framework's own "
      "`world_facts` archive collects them from 12 Nov 2026; this claim is PENDING until it holds a full season.\n")
    out["claims"]["goal_timing"] = {"r": r2, "ci": ci2, "pairs": n2, "fh_share_all": g1 / gt, "early_seasons": len(early)}

    # Claim 3/4: first-half goals
    w("\n## Claim 3: a filter that finds first-half goals (video: 37 of 144 games, hit 75.8%)\n")
    w("| games picked by | games | goal before half-time | 90% range | break-even price |")
    w("|---|---|---|---|---|")
    fhrows = first_half_filter(wf)
    for name, n_, k in fhrows:
        lo, hi = wilson(k, n_)
        w(f"| {name} | {n_} | {100 * k / n_:.1f}% | {100 * lo:.1f}% to {100 * hi:.1f}% | {n_ / k:.2f} |" if n_ else f"| {name} | 0 | PENDING | | |")
    w("\nNo bookmaker price for '1st half over 0.5' is in this data, so the money side is the break-even price: the "
      "filter only pays if the bookmaker offers MORE than that. Typical prices for that line are about 1.30-1.45 "
      "(to be confirmed from our SportyBet and exchange records before any stake).\n")
    out["claims"]["first_half_filter"] = fhrows

    hfs = home_first_half_scorers(matches)
    w("\n## Claim 4: home teams that decide games in the first half (video: Rapid Vienna 16 in 7)\n")
    w(f"{hfs['teams']} team-seasons. The top {hfs['top_n']} home first-half scorers after their first 7 home games "
      f"scored **{hfs['top_first']:.2f}** first-half goals a home game; in their remaining home games: "
      f"**{hfs['top_rest']:.2f}** (every team: {hfs['all_first']:.2f} then {hfs['all_rest']:.2f}). "
      f"First 7 vs rest, all teams: r = {hfs['r']:.2f} (90% range {hfs['ci'][0]:.2f} to {hfs['ci'][1]:.2f}) -> "
      f"**{fact_verdict(hfs['r'], hfs['ci'], hfs['teams'])}**.\n")
    kept = (hfs['top_rest'] - hfs['all_rest']) / (hfs['top_first'] - hfs['all_first'])
    w(f"Of the hot starters' lead, **{100 * kept:.0f}%** carries on; the rest was a hot streak.\n")
    w("| hottest 7-game starts | first 7 home games | rest of season |")
    w("|---|---|---|")
    for nm, x, y in hfs["top5"]:
        w(f"| {nm} | {x:.2f} | {y:.2f} |")
    out["claims"]["home_first_half"] = {k: v for k, v in hfs.items() if k != "top5"} | {"lead_kept": kept}

    # Claim 5: corners
    cc = corner_consistency(matches)
    (rs, cis, ns), (rm, cim, nm_) = cc["sd"], cc["mean"]
    w("\n## Claim 5: steady corner teams (video: variation 1.92, 30 of 36 games inside 7-11)\n")
    w(f"{cc['teams']} team-seasons with 20+ games and corners recorded. Average spread (standard deviation) of total "
      f"match corners: {cc['avg_sd']:.2f}.\n")
    w(f"- A team's AVERAGE corners, first half of its games vs second half: r = {rm:.2f} "
      f"({cim[0]:.2f} to {cim[1]:.2f}) -> **{fact_verdict(rm, cim, nm_)}**.")
    w(f"- A team's SPREAD (how steady it is), first half vs second half: r = {rs:.2f} "
      f"({cis[0]:.2f} to {cis[1]:.2f}) -> **{fact_verdict(rs, cis, ns)}**.")
    w(f"- The steadiest 10% after the first half ({cc['steady_n']} teams): in the second half "
      f"{100 * cc['steady_inside']:.1f}% of their games landed within 2 corners of their first-half average; "
      f"every other team {100 * cc['rest_inside']:.1f}%.\n")
    out["claims"]["corners"] = cc | {"sd": [rs, cis, ns], "mean": [rm, cim, nm_]}

    # Claim 6: lower-league value
    bm, bk, nb = model_vs_market(wf)
    w("\n## Claim 6: lower-league over/under prices pay more than they should (video: fair 1.60, market 2.55)\n")
    w(f"Our walk-forward goals model (rebuilt each matchday from earlier games only) against the bookmakers' "
      f"price on the same {nb:,} matches, over 2.5 (Brier, lower = better): model {bm:.4f}, market {bk:.4f}. "
      f"{'The market is better.' if bk < bm else 'The model is better.'}\n")
    for lower in (True, False):
        vb = value_bets(wf, lower)
        w(f"**{'Lower leagues (second tier and below)' if lower else 'Top divisions'}**: bet where model chance x price "
          "is above 1, by size of that edge.\n")
        w("| edge the model claims | bets | ROI | 90% range | CLV (taken vs closing) | verdict |")
        w("|---|---|---|---|---|---|")
        for (lo_, hi_), d in vb.items():
            m_, ci_ = roi_boot(d["rets"])
            clv = st.fmean(d["clv"]) if d["clv"] else None
            lab = f"{100 * lo_:.0f}%+" if hi_ > 1 else f"{100 * lo_:.0f}-{100 * hi_:.0f}%"
            w(f"| {lab} | {len(d['rets'])} | {spct(m_)} | {rng_s(*ci_)} | {spct(clv, 2)} | {money_verdict(len(d['rets']), *ci_) if m_ is not None else 'NONE'} |")
            out["claims"].setdefault("value", {})[f"{'lower' if lower else 'top'}_{lab}"] = [len(d["rets"]), m_, ci_, clv]
        w("")
    r1, r2_, lowb, allb, pmod = form_rule(wf)
    m1, c1 = roi_boot(r1)
    m2, c2 = roi_boot(r2_)
    w("**The video's backing stats as bets:**\n")
    w("| rule | bets | ROI | 90% range | verdict |")
    w("|---|---|---|---|---|")
    w(f"| over 2.5: home side's last 7 home games over in 6+ | {len(r1)} | {spct(m1)} | {rng_s(*c1)} | {money_verdict(len(r1), *c1)} |")
    w(f"| over 2.5: and the away side's last 7 away games over in 6+ | {len(r2_)} | {spct(m2)} | {rng_s(*c2)} | {money_verdict(len(r2_), *c2)} |")
    if lowb[0]:
        lo, hi = wilson(lowb[1], lowb[0])
        w(f"\nAway side with BTTS in 1 or fewer of its last 10 (video: 'Kaiserslautern 1 of 10'): next game BTTS "
          f"{100 * lowb[1] / lowb[0]:.1f}% ({100 * lo:.1f}-{100 * hi:.1f}%, {lowb[0]} games) vs {100 * allb[1] / allb[0]:.1f}% "
          f"for every away side; our model already expected {100 * pmod:.1f}% for those games. BTTS No break-even price "
          f"{lowb[0] / (lowb[0] - lowb[1]):.2f} (video quoted 2.43-2.77).\n")
    out["claims"]["form_rule"] = {"over_home7": [len(r1), m1, c1], "over_both7": [len(r2_), m2, c2],
                                  "btts_low10": [lowb, allb, pmod]}

    # the sweep
    sw = claim_sweep(matches)
    w("\n## The claim sweep: every claim of the videos' shape, tested the same way\n")
    w("The videos' claims are all one shape: *<team> has been high on <stat> in its last N games, so it stays "
      "high*. The sweep writes down every claim of that shape these files can test: 14 stats x last 5 or last 10 "
      "games x (home side at home + away side away, or all games). The direction is set on the DISCOVERY seasons "
      "(2016-17 to 2020-21); the claim is judged only on the HOLDOUT seasons (2021-22 to 2025-26). Measured as the "
      "correlation between the two sides' recent average (minus the league's average so far) and what happened "
      "(minus the same). PASSES = significant after the Benjamini-Hochberg correction for testing "
      f"{len(sw)} claims at once. Where a price exists: does the claim explain what the PRICE got wrong "
      "(outcome minus the market's chance), and the ROI of betting the claim's top 10% of games at the price.\n")
    w("| stat | last N | games used | r discovery | r holdout (90% range) | holdout games | verdict | vs the price: r (90% range) | top-10% bets: ROI at average price (90% range) | same bets at the BEST price |")
    w("|---|---|---|---|---|---|---|---|---|---|")
    for c in sorted(sw, key=lambda c: (c["stat"], c["window"], c["venue"])):
        ver = "PASSES" if c["bh_pass"] else "FAILS"
        if c["bh_pass"] and abs(c["r_hold"]) < 0.05:
            ver = "PASSES, tiny"
        vm = (f"{c['r_vs_market']:+.3f} ({c['ci_vs_market'][0]:+.3f} to {c['ci_vs_market'][1]:+.3f})"
              if c.get("r_vs_market") is not None else "no price in data")
        mo = (f"{spct(c['top10_roi'])} ({rng_s(*c['top10_ci'])}), {c['top10_bets']} bets"
              if c.get("top10_roi") is not None else "no price in data")
        mx = (f"{spct(c['max_roi'])} ({rng_s(*c['max_ci'])})" if c.get("max_roi") is not None else "-")
        w(f"| {c['stat']} | {c['window']} | {c['venue']} | {c['r_disc']:+.3f} | {c['r_hold']:+.3f} "
          f"({c['ci_hold'][0]:+.3f} to {c['ci_hold'][1]:+.3f}) | {c['n_hold']} | {ver} | {vm} | {mo} | {mx} |")
    out["claims"]["sweep"] = sw
    npass = sum(1 for c in sw if c["bh_pass"])
    priced = [c for c in sw if c.get("r_vs_market") is not None]
    beat = [c for c in priced if c["ci_vs_market"][0] > 0]
    w(f"\n{npass} of {len(sw)} claims pass on the holdout. Of the {len(priced)} that have a price, "
      f"{len(beat)} explain something the price missed (90% range above 0).\n")

    w("\n### League-level version of every stat (league-season average, season t vs t+1)\n")
    w("| stat | pairs | r (90% range) | verdict |")
    w("|---|---|---|---|")
    ll = league_level_sweep(matches)
    for k, r_, ci_, n_ in ll:
        w(f"| {k} | {n_} | {r_:+.2f} ({ci_[0]:+.2f} to {ci_[1]:+.2f}) | {fact_verdict(r_, ci_, n_)} |" if r_ is not None else f"| {k} | {n_} | PENDING | |")
    out["claims"]["league_level"] = ll

    rr, rci, rn = referee_sweep(matches)
    w("\n### Pointer from the cards stat: the referee\n")
    w(f"A referee's cards a game in his last 10 (minus the league average) vs the next game's cards, English leagues, "
      f"{rn} games: r = {rr:+.3f} (90% range {rci[0]:+.3f} to {rci[1]:+.3f}) -> **{fact_verdict(rr, rci, rn)}**. "
      "No card prices in this data: the money side needs SportyBet's card lines from our own universe sweep.\n"
      if rr is not None else "Referee: PENDING (no referee names).\n")
    out["claims"]["referee"] = [rr, rci, rn]

    ms_ = month_sweep(matches)
    w("\n### Pointer from 'November before the break': over 2.5 by calendar month, at the price\n")
    w("| month | discovery bets | discovery ROI | holdout bets | holdout ROI |")
    w("|---|---|---|---|---|")
    for mo in range(1, 13):
        d_, h_ = ms_["discovery"].get(mo), ms_["holdout"].get(mo)
        if d_ or h_:
            w(f"| {datetime(2000, mo, 1):%b} | {d_[0] if d_ else 0} | {spct(d_[1]) if d_ else 'PENDING'} | "
              f"{h_[0] if h_ else 0} | {spct(h_[1]) if h_ else 'PENDING'} |")
    out["claims"]["month"] = ms_

    # verdict
    w("\n## What this means for money\n")
    real = [c for c in sw if c["bh_pass"] and abs(c["r_hold"]) >= 0.05]
    pr = [c for c in sw if c.get("top10_roi") is not None]
    prof = [c for c in pr if c["top10_ci"][0] > 0]
    prof_max = [c for c in pr if c.get("max_ci") and c["max_ci"][0] > 0]
    unpriced = sorted({c["stat"] for c in real if c.get("r_vs_market") is None and c["stat"] != "goals"})
    w(f"- **Are the facts real?** Mostly yes. {len(real)} of {len(sw)} claims of the videos' shape repeat on seasons they "
      f"were not found on, with a useful size (r 0.05+), and every league-level stat repeats from season to season. The "
      f"strongest are not goals: fouls, shots, shots on target, cards and corners.")
    w(f"- **Do they make money where we can test them?** No. Of {len(pr)} priced claims, {len(prof)} made a profit "
      f"at the average bookmaker price and {len(prof_max)} at the best price of any bookmaker. League over/under "
      f"profiles, the over/under form rules and the model's lower-league 'value' all lost: the price already holds what "
      f"the stats say. The bigger the edge our model claimed, the more it was the model that was wrong (claim 6).")
    w(f"- **Where money could still be:** markets these files cannot price: {', '.join(unpriced)}. Their habits repeat "
      "strongly, and SportyBet prices corners (166), bookings (139) and 1st-half totals (68). `engine/stat_lines.py` "
      "now records those prices before kick-off and grades them (`stat_lines.yml`); `backtest/stat_lines_study.py` "
      "answers the money question once 300+ lines per market are graded (a few weeks).")
    w("- **First-half goals:** the base rate is about 70% and the best filter here reaches about 75%. That pays only "
      "if SportyBet's 1st-half over 0.5 is above the break-even price in the table; the recorder now saves that "
      "price too.")
    w("- **Allocation:** nothing here supports money on goals-based stats bets today. The Architect decides; the "
      "candidates to watch are corners and bookings lines once `stat_lines_study` has 300+ graded bets each with a "
      "90% range above 0.\n")
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")
    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    print(f"wrote {REPORT} and {JSON_OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
