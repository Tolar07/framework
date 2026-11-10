"""
Tennis totals study (framework#386; RECORD ONLY). Writes backtest/TENNIS_TOTALS_STUDY.md.

Why: on Pinnacle's closing main line (ATP 2022-25) overs landed ~48.5% at a ~50% no-vig price, so blind overs lose
~6% and blind unders ~1%, although the average total beats the line: a third set adds 8-13 games and skews the mean
(Buckland, multisport-markets skill step 2b). So a tennis totals rule is judged by HIT RATE and ROI AT THE TAKEN PRICE
against the BLIND-UNDER baseline, never by mean margin and never against zero.

Three parts, each PENDING (HR35) when its data is missing, never invented (HR59):
  1. The board's shadow record (output/multisport/tennis/ms_*.json): every tennis total side (market 189) that has a
     result and a recorded price - overs, unders, and the live rule's own total picks - hit rate and ROI at the first
     recorded SportyBet price, by line bucket and by tour/level read from the competition name.
  2. The sealed hold-out gate for any new cut (judge_cut): seal the latest season, no cut under MIN_TRAIN training bets,
     the cut's hold-out result is read against the blind-under baseline on the same hold-out bets.
  3. The skew itself, from free results (tennis-data.co.uk games per set): mean vs median total games, share over
     each line, split by surface and best-of-3/5, and how many games a deciding set adds.
No price in part 3, so it shows the shape of the distribution only. Nothing here changes a pick, stake, bar,
threshold or live switch.

  python backtest/tennis_totals_study.py
"""
from __future__ import annotations

import re
import statistics
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import multisport as ms  # noqa: E402

OUT = ROOT / "backtest" / "TENNIS_TOTALS_STUDY.md"
TOTAL_MARKET = "189"
MIN_SIDES = 100        # fewer graded sides than this reads PENDING (HR35)
MIN_TRAIN = 1000       # no cut is trusted under ~1,000 training bets (300-bet cuts at 12-15% ROI are noise)
MIN_HOLD = 100         # the hold-out needs this many bets to say anything
MAX_LOOKS = 3          # the sealed season may be looked at 2-3 times at most
LINES = (20.5, 21.5, 22.5, 23.5, 24.5)


# -- part 1: the board's shadow record ---------------------------------------------------------------------------

def level_of(comp: str | None) -> str:
    """Tour / level read from the competition name (the record has no surface or best-of)."""
    c = (comp or "").lower()
    if "itf" in c:
        return "ITF"
    if "challenger" in c:
        return "Challenger"
    if "wta" in c:
        return "WTA"
    if "atp" in c:
        return "ATP"
    return "other"


def total_sides(docs: list[tuple[str, dict]]) -> list[dict]:
    """One row per graded tennis total side with a recorded price: day, side, line, level, won, price."""
    out = []
    for day, doc in docs:
        for g in (doc.get("games") or {}).values():
            for key, s in (g.get("sides") or {}).items():
                _sp, mid, spec, o = ms.split_key(key)
                first = s.get("first") or {}
                line = ms._num(spec, "total")
                side = o.strip().lower()
                if (mid != TOTAL_MARKET or line is None or side not in ("over", "under")
                        or s.get("won") is None or not first.get("price")):
                    continue
                out.append({"day": day, "side": side, "line": line, "level": level_of(g.get("comp")),
                            "won": int(s["won"]), "price": float(first["price"])})
    return out


def roi(rows: list[dict]) -> float | None:
    """Flat 1-unit ROI at the taken price."""
    if not rows:
        return None
    return round(sum((r["price"] - 1) if r["won"] else -1.0 for r in rows) / len(rows), 4)


def summary(rows: list[dict]) -> dict:
    n = len(rows)
    return {"n": n, "hit": round(sum(r["won"] for r in rows) / n, 4) if n else None, "roi": roi(rows)}


def bucket(line: float) -> str:
    return "<=21.5" if line <= 21.5 else "22.5-23.5" if line <= 23.5 else ">=24.5"


def part1(docs: list[tuple[str, dict]]) -> dict:
    rows = total_sides(docs)
    picks = [p for _d, doc in docs for p in doc.get("picks") or []
             if str(p.get("market_id")) == TOTAL_MARKET and p.get("result") in ("won", "lost")]
    pick_rows = [{"won": int(p["result"] == "won"), "price": float(p["price"])} for p in picks if p.get("price")]
    by_level: dict[str, dict] = {}
    for lv in sorted({r["level"] for r in rows}):
        sub = [r for r in rows if r["level"] == lv]
        by_level[lv] = {"over": summary([r for r in sub if r["side"] == "over"]),
                        "under": summary([r for r in sub if r["side"] == "under"])}
    by_line: dict[str, dict] = {}
    for b in ("<=21.5", "22.5-23.5", ">=24.5"):
        sub = [r for r in rows if bucket(r["line"]) == b]
        by_line[b] = {"over": summary([r for r in sub if r["side"] == "over"]),
                      "under": summary([r for r in sub if r["side"] == "under"])}
    return {"sides": len(rows), "over": summary([r for r in rows if r["side"] == "over"]),
            "under": summary([r for r in rows if r["side"] == "under"]),
            "rule": summary(pick_rows), "by_level": by_level, "by_line": by_line}


# -- part 2: the sealed hold-out gate ------------------------------------------------------------------------------

def judge_cut(rows: list[dict], cut, seal_year: int | None = None, looks: int = 1) -> dict:
    """Judge one candidate cut (a function row -> bool selecting the bets) the sealed hold-out way.

    rows need day (YYYY-MM-DD), side, won, price. The latest season (default: latest year in the rows) is sealed:
    the cut is built on the rest. Trusted only with >= MIN_TRAIN training bets in the cut and >= MIN_HOLD hold-out
    bets, at most MAX_LOOKS looks, and judged against the blind-under baseline on the SAME hold-out bets (not zero).
    """
    if not rows:
        return {"verdict": "PENDING (no bets)"}
    seal = seal_year if seal_year is not None else max(int(r["day"][:4]) for r in rows)
    train = [r for r in rows if int(r["day"][:4]) < seal]
    hold = [r for r in rows if int(r["day"][:4]) == seal]
    tr, ho = [r for r in train if cut(r)], [r for r in hold if cut(r)]
    base = [r for r in hold if r["side"] == "under"]
    out = {"seal_year": seal, "train": summary(tr), "hold": summary(ho), "blind_under_hold": summary(base),
           "looks": looks}
    if looks > MAX_LOOKS:
        out["verdict"] = f"REJECTED: {looks} looks at the sealed season (max {MAX_LOOKS}); it is no longer sealed"
    elif len(tr) < MIN_TRAIN:
        out["verdict"] = f"PENDING: {len(tr)} training bets in the cut (needs {MIN_TRAIN})"
    elif len(ho) < MIN_HOLD or not base:
        out["verdict"] = f"PENDING: {len(ho)} hold-out bets in the cut (needs {MIN_HOLD})"
    else:
        beat = (out["hold"]["roi"] or 0) > (out["blind_under_hold"]["roi"] or 0)
        out["verdict"] = ("HELD: beat the blind-under baseline on the sealed season" if beat
                          else "FAILED: did not beat the blind-under baseline on the sealed season")
    return out


# -- part 3: the games distribution from free results --------------------------------------------------------------

def games_of(r: dict) -> tuple[int, int] | None:
    """(total games, sets played) from the W1..W5 / L1..L5 columns of a tennis-data row; None if unreadable."""
    total = sets = 0
    for i in range(1, 6):
        w, lo = r.get(f"W{i}"), r.get(f"L{i}")
        try:
            w, lo = int(float(w)), int(float(lo))
        except (TypeError, ValueError):
            break
        total += w + lo
        sets += 1
    if sets < 2:
        return None
    if str(r.get("Comment", "Completed")).strip().lower() != "completed":
        return None      # a retirement or walkover is not a full match
    return total, sets


def distribution(rows: list[dict]) -> dict:
    """Skew of total games by surface and best-of, plus what a deciding set adds."""
    recs = []
    for r in rows:
        g = games_of(r)
        if g is None:
            continue
        try:
            bo = int(float(r.get("Best of") or 3))
        except (TypeError, ValueError):
            bo = 3
        recs.append({"total": g[0], "sets": g[1], "bo": bo, "surface": str(r.get("Surface") or "?")})
    out = {"n": len(recs), "groups": {}, "decider": {}}
    keys = sorted({(x["bo"], x["surface"]) for x in recs})
    for bo, surf in keys:
        t = [x["total"] for x in recs if x["bo"] == bo and x["surface"] == surf]
        if len(t) < 30:
            continue
        mean, med = statistics.fmean(t), statistics.median(t)
        out["groups"][f"Bo{bo} {surf}"] = {
            "n": len(t), "mean": round(mean, 2), "median": med, "mean_minus_median": round(mean - med, 2),
            "over": {ln: round(sum(1 for v in t if v > ln) / len(t), 3) for ln in LINES}}
    for bo in (3, 5):
        short = [x["total"] for x in recs if x["bo"] == bo and x["sets"] == (bo + 1) // 2]
        full = [x["total"] for x in recs if x["bo"] == bo and x["sets"] == bo]
        if len(short) >= 30 and len(full) >= 30:
            out["decider"][f"Bo{bo}"] = {"straight": len(short), "straight_mean": round(statistics.fmean(short), 2),
                                         "decider": len(full), "decider_mean": round(statistics.fmean(full), 2),
                                         "decider_share": round(len(full) / (len(full) + len(short)), 3)}
    return out


def load_results() -> list[dict]:
    """Raw tennis-data rows for ATP + WTA; an unreachable site or year is PENDING, never invented."""
    from backtest import tennis_backtest as tb
    try:
        page = tb.fetch(tb.SITE + "alldata.php").decode("latin-1", "replace")
    except Exception as ex:
        print(f"index not loaded ({type(ex).__name__})")
        return []
    rows: list[dict] = []
    for suffix in ("", "w"):
        for y in tb.YEARS:
            m = re.search(rf'HREF="([^"]*/{y}{suffix}/{y}\.xlsx)"', page, re.I)
            if not m:
                continue
            try:
                rows += tb.read_xlsx(tb.fetch(tb.SITE + m.group(1)))
            except Exception as ex:
                print(f"{y}{suffix}: not loaded ({type(ex).__name__})")
    return rows


# -- report ---------------------------------------------------------------------------------------------------------

def pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x * 100:.1f}%"


def cell(s: dict) -> str:
    return f"{s['n']} / {pct(s['hit'])} / {pct(s['roi'])}"


def render(docs: list[tuple[str, dict]], result_rows: list[dict], now: datetime) -> str:
    L = ["# Tennis totals study", "",
         f"Made {now:%Y-%m-%d %H:%M} UTC by `backtest/tennis_totals_study.py` (framework#386). Record only. Cells are "
         "bets / hit rate / ROI at the taken price. Judged against the blind-under baseline, never zero, never by "
         "mean margin.", "", "## 1. The board's shadow record (SportyBet tennis totals, first recorded price)", ""]
    p1 = part1(docs)
    if p1["sides"] < MIN_SIDES:
        L += [f"PENDING (HR35): {p1['sides']} graded tennis total sides in the record (needs {MIN_SIDES}).", ""]
    else:
        L += [f"{p1['sides']} graded total sides. Blind overs: {cell(p1['over'])}. Blind unders (the baseline): "
              f"{cell(p1['under'])}. The live rule's own total picks: {cell(p1['rule'])}.", "",
              "| Cut | Overs | Unders |", "|---|---|---|"]
        for lv, v in p1["by_level"].items():
            L.append(f"| {lv} | {cell(v['over'])} | {cell(v['under'])} |")
        for b, v in p1["by_line"].items():
            L.append(f"| line {b} | {cell(v['over'])} | {cell(v['under'])} |")
        L += ["", "The record has no surface or best-of, so clay / indoor / Bo5 cuts wait for those fields (PENDING).",
              ""]
    L += ["## 2. The sealed hold-out gate (`judge_cut`)", "",
          f"Any new cut: seal the latest season, no cut under {MIN_TRAIN} training bets, at least {MIN_HOLD} hold-out "
          f"bets, at most {MAX_LOOKS} looks at the sealed season, and beat the blind-under baseline on the same "
          "hold-out bets. A cut with a verdict other than HELD is not a result.", ""]
    L += ["## 3. The games distribution (free results, no price)", ""]
    d = distribution(result_rows)
    if d["n"] < 100:
        L += ["PENDING (HR35): free results did not load (tennis-data.co.uk returned nothing from this machine).", ""]
    else:
        L += [f"{d['n']} completed ATP + WTA matches with set scores.", "",
              "| Group | Matches | Mean games | Median | Mean - median | " + " | ".join(f"Over {x}" for x in LINES) + " |",
              "|---|---|---|---|---|" + "---|" * len(LINES)]
        for k, v in d["groups"].items():
            L.append(f"| {k} | {v['n']} | {v['mean']} | {v['median']} | {v['mean_minus_median']} | "
                     + " | ".join(f"{v['over'][x] * 100:.1f}%" for x in LINES) + " |")
        L += [""]
        for k, v in d["decider"].items():
            L.append(f"- {k}: straight-set matches average {v['straight_mean']} games ({v['straight']} matches); "
                     f"deciding-set matches {v['decider_mean']} ({v['decider']}); a decider happens in "
                     f"{v['decider_share'] * 100:.1f}% of matches. That tail is what lifts the mean above the median "
                     "and makes the over hit less often than the average suggests.")
        L += [""]
    L += ["Record only: nothing here changes a pick, stake, bar, threshold or the live switch.", ""]
    return "\n".join(L)


def run(now: datetime | None = None) -> str:
    text = render(ms.load_all("tennis"), load_results(), now or datetime.now(UTC))
    OUT.write_text(text, encoding="utf-8")
    return text


if __name__ == "__main__":
    print(run())
