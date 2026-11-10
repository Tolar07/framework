"""
CRICKET venue + format first-innings total study (framework#385; record-only, shadow).

Cricket totals depend on venue and format (IPL first innings usually 170-190 by venue). This replays every men's
T20 and ODI match Cricsheet lists (free ball-by-ball archive), in date order, and grades how well two rules guess
the FIRST-INNINGS TOTAL BEFORE the match is played:

  - FORMAT : the format's running mean first-innings total (what a board with no venue knowledge would use);
  - VENUE  : venue mean shrunk toward the format mean, (sum + k*format_mean) / (n + k), k "pseudo matches";
  - the format mean is either all-history or an exponentially decayed mean (scoring drifts upward over years).

Every setting tried is counted; the best is chosen on 2010-2018 and reported on 2019 onward only (no peeking).
Only innings that ran their full course count (all out, or the format's full overs): rain-shortened first innings
are skipped, not guessed. Pitch type, toss and line-ups are NOT in Cricsheet: venue is the proxy, and the report
says so (HR35: what is not measured reads PENDING). Test matches are left out (declarations make one innings total
meaningless). No free historical closing totals exist, so this measures accuracy (MAE), not return; return and CLV
come from the shadow record. Nothing here changes a stake, a bar, a threshold or the live switch.

  python backtest/cricket_venue_study.py      writes backtest/CRICKET_VENUE_STUDY.md
"""
from __future__ import annotations

import itertools
import json
import sys
import zipfile
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backtest.cricket_backtest import TUNE_YEARS, fetch_zip  # noqa: E402

OUT = ROOT / "backtest" / "CRICKET_VENUE_STUDY.md"
FORMATS = {"t20s_male": ("T20", 20), "odis_male": ("ODI", 50)}
KS = (0.0, 5.0, 10.0, 20.0)          # venue shrinkage (pseudo matches); 0 = raw venue mean
DECAYS = (0.0, 0.02)                 # 0 = all-history format mean; 0.02 = decayed (recent matches count more)
MIN_VENUE = 3                        # venue needs this many past matches to be "known"; else the format mean
MIN_FORMAT = 30                      # the format needs this many past innings before any guess is made


def parse_match(d: dict, fmt: str, overs: int) -> dict | None:
    """One finished match -> {day, fmt, venue, total}: first-innings runs, only if that innings ran its course."""
    try:
        info = d["info"]
        venue = info.get("venue")
        inn = d["innings"][0]
        if not venue or int(info.get("overs", overs)) != overs:
            return None
        runs = balls = wk = 0
        for ov in inn["overs"]:
            for dl in ov["deliveries"]:
                runs += dl["runs"]["total"]
                ex = dl.get("extras") or {}
                if "wides" not in ex and "noballs" not in ex:
                    balls += 1
                wk += len(dl.get("wickets") or [])
        if wk < 10 and balls < overs * 6:
            return None  # shortened or abandoned first innings: skipped, not guessed
        return {"day": info["dates"][0], "fmt": fmt, "venue": venue, "total": float(runs)}
    except (KeyError, TypeError, IndexError, ValueError):
        return None


def load(fetch=fetch_zip) -> list[dict]:
    games = []
    for key, (fmt, overs) in FORMATS.items():
        try:
            z = zipfile.ZipFile(BytesIO(fetch(key)))
        except Exception as ex:  # a format that will not load is PENDING, never invented
            print(f"{fmt}: not loaded ({type(ex).__name__})")
            continue
        for name in z.namelist():
            if not name.endswith(".json"):
                continue
            try:
                g = parse_match(json.loads(z.read(name)), fmt, overs)
            except ValueError:
                continue
            if g:
                games.append(g)
    games.sort(key=lambda g: (g["day"], g["fmt"], g["venue"]))
    for g in games:
        g["year"] = int(g["day"][:4])
    return games


def replay(games: list[dict], k: float, decay: float) -> tuple[list, list]:
    """(venue-rule guess, format-rule guess) BEFORE each match, then learn it. None until the format is known."""
    fm, fn, vs, vn = {}, {}, {}, {}
    venue_out, fmt_out = [], []
    for g in games:
        f, v = g["fmt"], (g["fmt"], g["venue"])
        base = fm.get(f) if fn.get(f, 0) >= MIN_FORMAT else None
        fmt_out.append(base)
        if base is None:
            venue_out.append(None)
        elif vn.get(v, 0) >= MIN_VENUE:
            venue_out.append((vs[v] + k * base) / (vn[v] + k))
        else:
            venue_out.append(base)
        t = g["total"]
        if f not in fm:
            fm[f] = t
        else:
            fm[f] += (decay if decay else 1.0 / (fn[f] + 1)) * (t - fm[f])
        fn[f] = fn.get(f, 0) + 1
        vs[v], vn[v] = vs.get(v, 0.0) + t, vn.get(v, 0) + 1
    return venue_out, fmt_out


def mae(games, guesses, years, fmt=None) -> dict:
    n, s = 0, 0.0
    for g, p in zip(games, guesses, strict=True):
        if p is None or not (years[0] <= g["year"] <= years[1]) or (fmt and g["fmt"] != fmt):
            continue
        n += 1
        s += abs(p - g["total"])
    return {"n": n, "mae": s / n if n else None}


def run(games: list[dict]) -> str:
    last = max(g["year"] for g in games)
    test = (TUNE_YEARS[1] + 1, last)
    cache = {(k, d): replay(games, k, d) for k, d in itertools.product(KS, DECAYS)}
    tries = len(cache)
    tuned = {kd: mae(games, c[0], TUNE_YEARS) for kd, c in cache.items()}
    ok = {kd: t for kd, t in tuned.items() if t["n"] >= 100}
    best = min(ok, key=lambda kd: ok[kd]["mae"]) if ok else None
    made = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    counts = {f: sum(1 for g in games if g["fmt"] == f) for f, _ in FORMATS.values()}
    L = ["# Cricket venue + format first-innings total study", "",
         f"Made {made} by `backtest/cricket_venue_study.py` (framework#385, record-only). "
         f"{len(games)} full first innings ({', '.join(f'{k} {v}' for k, v in counts.items())}), men's, Cricsheet. "
         f"Settings tried: **{tries}** (venue shrinkage k x format-mean decay); chosen on "
         f"{TUNE_YEARS[0]}-{TUNE_YEARS[1]}, reported on **{test[0]}-{test[1]} only**.", ""]
    if not best:
        L.append("Too few tuning matches: PENDING.")
        return "\n".join(L) + "\n"
    fmt_rule = cache[(0.0, best[1])][1]
    L += ["| Rule (held-out years) | Matches | MAE runs |", "|---|---|---|"]

    def row(name, r):
        return f"| {name} | {r['n']} | " + (f"{r['mae']:.1f}" if r["n"] else "PENDING") + " |"

    fm_all = mae(games, fmt_rule, test)
    ve_all = mae(games, cache[best][0], test)
    L.append(row("FORMAT mean only (no venue)", fm_all))
    L.append(row(f"VENUE shrunk: k={best[0]:.0f}, decay={best[1]}", ve_all))
    for f, _ in FORMATS.values():
        L.append(row(f"  {f}: format only", mae(games, fmt_rule, test, f)))
        L.append(row(f"  {f}: venue shrunk", mae(games, cache[best][0], test, f)))
    L += ["", "## Reading", ""]
    if fm_all["n"]:
        gain = fm_all["mae"] - ve_all["mae"]
        L.append(f"- Venue knowledge changes the first-innings guess by {gain:+.2f} runs of average error "
                 f"({fm_all['mae']:.1f} -> {ve_all['mae']:.1f}); " +
                 ("it helps, so a venue baseline belongs beside the totals line as a shadow." if gain > 0.5 else
                  "that is too small to claim an edge: keep it record-only."))
    L += [f"- {tries} settings tried; the held-out line is the honest one.",
          "- Pitch type (green / dusty / flat), toss and line-ups are not in Cricsheet: PENDING, venue is the proxy.",
          "- No free historical closing totals, so no return figure: CLV comes from the shadow record.",
          "- Record only: nothing here changes a stake, a bar or the live switch."]
    return "\n".join(L) + "\n"


def main() -> int:
    games = load()
    if len(games) < 1000:
        print(f"only {len(games)} first innings read: NO DATA - PENDING")
        return 1
    text = run(games)
    OUT.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
