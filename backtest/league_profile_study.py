"""
LEAGUE PROFILE STUDY (framework #581) - does knowing a league's both-teams-to-score / goals rate beat the price?

Walk-forward only: a league's rate is taken from games BEFORE the bet (the previous season, or earlier games in
the same window), never from the games it is tested on. Every slice tried is reported (no picking the best one).

  A  Over/under 2.5 at the closing price (football-data.co.uk, 22 divisions, 2019/20 on): bet OVER in leagues
     whose previous-season over-2.5 rate was in the top third, UNDER in the bottom third.
  B  Both teams to score at SportyBet's last price (sweep, since 2026-10-08, 500+ competitions): a league's rate
     from its earlier games in the window (20+); YES when it is 60%+, NO when 45% or less.
  C  First half over 0.5: no source we hold prices it (football-data has no half-time markets, the sweep reads
     no half markets) -> the price test is PENDING; the base rate is reported.
  D  Persistence: does a league's BTTS rate one season predict the next?
  E  The video's claims next to our numbers.

The second-half-season study (#493/#496) found league-table background adds nothing over the price, so the
expected answer is 'no edge'. Output: backtest/LEAGUE_PROFILE_STUDY.md.
Usage: python backtest/league_profile_study.py [--no-fetch]
"""
from __future__ import annotations

import random
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import stats_history as sh  # noqa: E402

REPORT = ROOT / "backtest" / "LEAGUE_PROFILE_STUDY.md"


def roi(bets: list[tuple[bool, float]], seed: int = 7, boots: int = 400) -> dict:
    """Level stakes: n, hit, ROI and the 90% bootstrap range of ROI."""
    n = len(bets)
    if not n:
        return {"n": 0}
    ret = [(p - 1.0) if w else -1.0 for w, p in bets]
    rng = random.Random(seed)  # noqa: S311 - a bootstrap, not cryptography
    sims = sorted(sum(rng.choices(ret, k=n)) / n for _ in range(boots))
    return {"n": n, "hit": sum(1 for w, _ in bets if w) / n, "roi": sum(ret) / n,
            "lo": sims[int(0.05 * boots)], "hi": sims[int(0.95 * boots) - 1],
            "avg_price": sum(p for _, p in bets) / n}


def fmt(s: dict) -> str:
    if not s.get("n"):
        return "0 bets | - | - | -"
    return (f"{s['n']} | {s['hit']:.1%} | {s['roi']:+.1%} | {s['lo']:+.1%} to {s['hi']:+.1%}")


def test_a(hist: list[dict]) -> tuple[list[str], int]:
    by: dict[tuple, list] = {}
    for r in hist:
        by.setdefault((r["league"], r["season"]), []).append(r)
    rate = {k: sum(1 for r in v if r["hg"] + r["ag"] > 2) / len(v) for k, v in by.items() if len(v) >= 100}
    seasons = sorted({s for _, s in by})
    over_hi, under_lo, all_over, all_under = [], [], [], []
    for i, s in enumerate(seasons[1:], 1):
        prev = {lg: rate[(lg, seasons[i - 1])] for (lg, ss) in rate if ss == seasons[i - 1]}
        if len(prev) < 6:
            continue
        cut = sorted(prev.values())
        lo, hi = cut[len(cut) // 3], cut[(2 * len(cut)) // 3]
        for (lg, ss), rows in by.items():
            if ss != s or lg not in prev:
                continue
            for r in rows:
                over = r["hg"] + r["ag"] > 2
                if r["o25"]:
                    all_over.append((over, r["o25"]))
                    if prev[lg] >= hi:
                        over_hi.append((over, r["o25"]))
                if r["u25"]:
                    all_under.append((not over, r["u25"]))
                    if prev[lg] <= lo:
                        under_lo.append((not over, r["u25"]))
    lines = ["| Slice | Bets | Hit | ROI | 90% range |", "|---|---|---|---|---|",
             f"| OVER 2.5, leagues in last season's top third | {fmt(roi(over_hi))} |",
             f"| UNDER 2.5, leagues in last season's bottom third | {fmt(roi(under_lo))} |",
             f"| baseline: OVER 2.5 every game | {fmt(roi(all_over))} |",
             f"| baseline: UNDER 2.5 every game | {fmt(roi(all_under))} |"]
    return lines, 2


def test_b(sporty: list[dict]) -> tuple[list[str], int]:
    seen: dict[str, list[int]] = {}
    yes, no, all_yes, all_no = [], [], [], []
    for r in sporty:                      # time order: the league's rate uses only earlier games
        bt = (r.get("prices") or {}).get("btts")
        both = r["hg"] > 0 and r["ag"] > 0
        a = seen.get(r["league"])
        if bt and len(bt) == 2 and bt[0] and bt[1]:
            all_yes.append((both, bt[0]))
            all_no.append((not both, bt[1]))
            if a and a[1] >= 20:
                rt = a[0] / a[1]
                if rt >= 0.60:
                    yes.append((both, bt[0]))
                elif rt <= 0.45:
                    no.append((not both, bt[1]))
        a = seen.setdefault(r["league"], [0, 0])
        a[0] += both
        a[1] += 1
    lines = ["| Slice | Bets | Hit | ROI | 90% range |", "|---|---|---|---|---|",
             f"| BTTS YES, league 60%+ so far | {fmt(roi(yes))} |",
             f"| BTTS NO, league 45% or less so far | {fmt(roi(no))} |",
             f"| baseline: BTTS YES every game | {fmt(roi(all_yes))} |",
             f"| baseline: BTTS NO every game | {fmt(roi(all_no))} |"]
    return lines, 2


def test_c(hist: list[dict], sporty: list[dict]) -> list[str]:
    out = []
    for name, rows in (("football-data.co.uk (22 divisions)", hist), ("SportyBet sweep (all listed)", sporty)):
        ht = [r for r in rows if r.get("hthg") is not None and r.get("htag") is not None]
        if ht:
            k = sum(1 for r in ht if r["hthg"] + r["htag"] > 0)
            out.append(f"- {name}: a goal before half-time in **{k / len(ht):.1%}** of {len(ht):,} games "
                       f"(break-even price {len(ht) / k:.2f}).")
    out.append("- Price test: **PENDING** - no source we hold prices first-half goal lines.")
    return out


def test_d(hist: list[dict]) -> list[str]:
    by: dict[tuple, list] = {}
    for r in hist:
        by.setdefault((r["league"], r["season"]), []).append(r)
    rate = {k: sum(1 for r in v if r["hg"] > 0 and r["ag"] > 0) / len(v) for k, v in by.items() if len(v) >= 100}
    seasons = sorted({s for _, s in rate})
    xs, ys = [], []
    for i in range(1, len(seasons)):
        for (lg, s), v in rate.items():
            if s == seasons[i] and (lg, seasons[i - 1]) in rate:
                xs.append(rate[(lg, seasons[i - 1])])
                ys.append(v)
    if len(xs) < 10:
        return ["- PENDING: fewer than 10 league-season pairs."]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    r = cov / (vx * vy) ** 0.5 if vx and vy else 0.0
    slope = cov / vx if vx else 0.0
    return [f"- {len(xs)} league-season pairs: correlation of BTTS rate year to year **{r:.2f}**; "
            f"slope {slope:.2f} (1.0 = a league keeps all of its difference from the average, 0 = none)."]


CLAIMS = [  # (claim text, how to find it in our rows: predicate on league name, field, claimed value)
    ("Dutch second division BTTS 69.1%", lambda lg: "netherlands" in lg.lower() and "eerste" in lg.lower(), "btts", .691),
    ("Switzerland BTTS 68.4%", lambda lg: lg.lower().startswith("switzerland:") and "super league" in lg.lower(), "btts", .684),
    ("Poland BTTS 65.3%", lambda lg: lg.lower().startswith("poland:") and "ekstraklasa" in lg.lower(), "btts", .653),
    ("Norway second tier BTTS 64.6%", lambda lg: lg.lower().startswith("norway:") and ("1st division" in lg.lower() or "obos" in lg.lower()), "btts", .646),
    ("MLS BTTS 63.9%", lambda lg: lg.lower().endswith("mls"), "btts", .639),
    ("Premier League BTTS 49%", lambda lg: lg in ("Premier League", "England: Premier League"), "btts", .49),
    ("Scottish Premiership: more goals before half-time (52.8%)", lambda lg: lg in ("Scottish Premiership", "Scotland: Premiership"), "fh_share", .528),
]


def test_e(profiles: list[dict]) -> list[str]:
    lines = ["| Claim | Our league row | Games | Ours |", "|---|---|---|---|"]
    for text, pred, field, _v in CLAIMS:
        hits = [p for p in profiles if pred(p["league"])]
        if not hits:
            lines.append(f"| {text} | not in our sources | - | PENDING |")
        for p in hits:
            val = p.get(field)
            shown = f"{val:.1%}" if isinstance(val, float) else str(val)
            lines.append(f"| {text} | {p['league']} ({p['source']}, {p['season']}) | {p['games']} | {shown} |")
    return lines


def main(argv: list[str] | None = None) -> int:
    argv = argv or []
    fetch = "--no-fetch" not in argv
    now = datetime.now(UTC)
    hist, cov = sh.load_history(fetch=fetch)
    sporty = sh.load_sportybet()
    from engine import league_profile as lp
    cur = [r for r in hist if r["season"] in (sh.CURRENT, "2526")]
    profiles = lp.build(cur, sporty, now, lp.late_shares())["leagues"]
    a, na = test_a(hist)
    b, nb = test_b(sporty)
    pending = sorted(f"{lg} {s}" for lg, ss in cov.items() for s, v in ss.items() if v == "PENDING")
    md = [
        "# League profile study (framework #581)", "",
        f"Generated {now:%Y-%m-%d %H:%M} UTC by `backtest/league_profile_study.py`. RECORD ONLY: nothing here "
        "picks or stakes. The league figures come from the Architect's video of 2026-11-12 and are claims to "
        "test, not rules.", "",
        f"Data: football-data.co.uk {len(hist):,} games (22 divisions, 2018/19 on; files not read: "
        f"{', '.join(pending) if pending else 'none'}); SportyBet sweep {len(sporty):,} graded football games "
        "since 2026-10-08.", "",
        f"**Slices tried: {na + nb}** (A: {na}, B: {nb}). Each has a 5% chance of a range wholly above zero by luck, "
        f"so about {0.05 * (na + nb):.1f} such slices are expected from luck alone; only a slice whose whole range "
        "sits above zero, and above its every-game baseline, counts.", "",
        "## A. Over/under 2.5 at the closing price, by last season's league rate", *a, "",
        "## B. Both teams to score at SportyBet's price, by the league's rate so far", *b, "",
        "## C. A goal before half-time", *test_c(hist, sporty), "",
        "## D. Does a league's BTTS rate carry over to the next season?", *test_d(hist), "",
        "## E. The video's claims next to our numbers", *test_e(profiles), "",
        "## Reading",
        "- A league's rate is real and partly persistent (D), but the bookmaker already prices it: compare each "
        "slice with its every-game baseline. Unless a slice's whole range is above zero, a league's BTTS or "
        "goals rate is a **list for the app, not a bet**.",
        "- Late-goal shares (goals from the 76th minute) need goal minutes; the world-facts detail archive "
        "(#596) only started on 2026-11-12, so they read PENDING until a league has 20 such games.", "",
    ]
    REPORT.write_text("\n".join(md), encoding="utf-8")
    print(f"wrote {REPORT.relative_to(ROOT)}: {len(hist)} history rows, {len(sporty)} sweep rows")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
