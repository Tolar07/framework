"""
CRICKET walk-forward backtest (framework#343, multi-sport rollout; shadow from 2026-11-05, live 2026-11-12).

The multi-sport board rates cricket with the shared win-probability Elo (engine/multisport.py: K 24, start 1500).
This study replays every men's match Cricsheet lists (free ball-by-ball archive; only the result is used here):
T20 (internationals + leagues incl. Big Bash), ODI and Test, one rating pool per format, in date order:

  - every setting tried is counted (K x side-A edge); the best is chosen on the FIRST years and reported on the
    LATER years only (no peeking);
  - accuracy: Brier and hit rate of the Elo vs a "listed-first side wins as often as in the tuning years" baseline;
  - side A is the team listed first in the match info, never the winner (no leak). No result / tie / draw rows are
    skipped for Brier, and not learned from (a Test draw is not a win for either side).

No free historical cricket CLOSING odds, so this measures accuracy, not return. Return and closing-line value
come from the shadow board's own graded record. Record only: nothing here changes a stake, a bar, a threshold
or the live switch.

  python backtest/cricket_backtest.py      writes backtest/CRICKET_STUDY.md
"""
from __future__ import annotations

import itertools
import json
import sys
import urllib.request
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "backtest" / "CRICKET_STUDY.md"
FORMATS = {"t20s_male": "T20", "odis_male": "ODI", "tests_male": "Test"}
URL = "https://cricsheet.org/downloads/{k}_json.zip"
TUNE_YEARS = (2010, 2018)             # chosen here; 2019 onward is the held-out test
MIN_GAMES, ELO_START = 8, 1500.0
KS = (16.0, 24.0, 32.0)               # 24 = the live board's ELO_K
EDGE_A = (0.0, 25.0)                  # Elo points for the team listed first (venue is not in the result)


def fetch_zip(key: str) -> bytes:
    req = urllib.request.Request(URL.format(k=key), headers={"User-Agent": "olp-xdv-backtest"})
    with urllib.request.urlopen(req, timeout=120) as r:  # noqa: S310 (fixed https URL)
        return r.read()


def parse_match(d: dict, fmt: str) -> dict | None:
    """One finished match with a winner -> {day, fmt, a, b, y (1 = a won)}; else None."""
    try:
        info = d["info"]
        teams = info["teams"]
        out = info.get("outcome") or {}
        win = out.get("winner")
        if len(teams) != 2 or win not in teams or out.get("result") in ("tie", "no result", "draw"):
            return None
        return {"day": info["dates"][0], "fmt": fmt, "a": teams[0], "b": teams[1],
                "y": 1.0 if win == teams[0] else 0.0}
    except (KeyError, TypeError, IndexError):
        return None


def load(fetch=fetch_zip) -> list[dict]:
    games = []
    for key, fmt in FORMATS.items():
        try:
            z = zipfile.ZipFile(BytesIO(fetch(key)))
        except Exception as ex:  # a format that will not load is PENDING, never invented
            print(f"{fmt}: not loaded ({type(ex).__name__})")
            continue
        for name in z.namelist():
            if not name.endswith(".json"):
                continue
            try:
                g = parse_match(json.loads(z.read(name)), fmt)
            except ValueError:
                continue
            if g:
                games.append(g)
    games.sort(key=lambda g: (g["day"], g["fmt"], g["a"], g["b"]))
    for g in games:
        g["year"] = int(g["day"][:4])
    return games


def replay(games: list[dict], k: float, edge: float) -> list[float | None]:
    """Elo chance that side A wins BEFORE each game (None while a side has < MIN_GAMES games), then learn."""
    r, n, out = {}, {}, []
    for g in games:
        pool = g["fmt"]
        a, b = (pool, g["a"]), (pool, g["b"])
        ra, rb = r.get(a, ELO_START), r.get(b, ELO_START)
        e = 1 / (1 + 10 ** ((rb - ra - edge) / 400))
        out.append(e if n.get(a, 0) >= MIN_GAMES and n.get(b, 0) >= MIN_GAMES else None)
        r[a], r[b] = ra + k * (g["y"] - e), rb - k * (g["y"] - e)
        n[a], n[b] = n.get(a, 0) + 1, n.get(b, 0) + 1
    return out


def evaluate(games, probs, years, base=0.5, fmt=None) -> dict:
    n = hits = 0
    b = b0 = 0.0
    for g, p in zip(games, probs):
        if p is None or not (years[0] <= g["year"] <= years[1]) or (fmt and g["fmt"] != fmt):
            continue
        n += 1
        b += (p - g["y"]) ** 2
        b0 += (base - g["y"]) ** 2
        hits += (p > 0.5) == (g["y"] == 1.0)
    return {"n": n, "brier": b / n if n else None, "base": b0 / n if n else None, "hit": hits / n if n else None}


def run(games: list[dict]) -> str:
    last = max(g["year"] for g in games)
    test = (TUNE_YEARS[1] + 1, last)
    tune_g = [g for g in games if TUNE_YEARS[0] <= g["year"] <= TUNE_YEARS[1]]
    base = sum(g["y"] for g in tune_g) / len(tune_g) if tune_g else 0.5
    cache = {(k, e): replay(games, k, e) for k, e in itertools.product(KS, EDGE_A)}
    tries = len(cache)
    tuned = {ke: evaluate(games, p, TUNE_YEARS) for ke, p in cache.items()}
    ok = {ke: t for ke, t in tuned.items() if t["n"] >= 100}
    best = min(ok, key=lambda ke: ok[ke]["brier"]) if ok else None
    live = evaluate(games, cache[(24.0, 0.0)], test, base)
    held = evaluate(games, cache[best], test, base) if best else None
    fmt_n = {f: sum(1 for g in games if g["fmt"] == f) for f in FORMATS.values()}

    def line(name, r):
        if not r["n"]:
            return f"| {name} | 0 | PENDING | PENDING | PENDING |"
        return f"| {name} | {r['n']} | {r['brier']:.4f} | {r['base']:.4f} | {r['hit']:.1%} |"

    made = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    L = ["# Cricket walk-forward backtest", "",
         f"Made {made} by `backtest/cricket_backtest.py` (framework#343). {len(games)} matches with a winner "
         f"({', '.join(f'{k} {v}' for k, v in fmt_n.items())}), results only (Cricsheet, men's). Settings tried: "
         f"**{tries}** (K x side-A edge); chosen on {TUNE_YEARS[0]}-{TUNE_YEARS[1]}, reported on "
         f"**{test[0]}-{test[1]} only**. Side A (listed first) won {base:.1%} in the tuning years.", "",
         f"| Rule (held-out years) | Games rated | Brier | Brier flat baseline ({base:.1%}) | Winner hit rate |",
         "|---|---|---|---|---|",
         line("Live board: Elo K24, no edge", live)]
    for f in FORMATS.values():
        L.append(line(f"  of which {f}", evaluate(games, cache[(24.0, 0.0)], test, base, f)))
    if held:
        L.append(line(f"Best on tuning years: K{best[0]:.0f}, side-A edge {best[1]:.0f}", held))
    L += ["", "## Reading", ""]
    if live["n"]:
        beat = live["brier"] < live["base"]
        L.append(f"- Live-board Elo Brier {live['brier']:.4f} vs baseline {live['base']:.4f}: "
                 + ("the Elo carries real information." if beat else
                    "the Elo does NOT beat a flat baseline here; lean on the exchange price."))
    if held and live["n"]:
        L.append(f"- Held-out Brier of the tuned setting {held['brier']:.4f} vs {live['brier']:.4f} for the live one.")
    L += [f"- {tries} settings tried; the held-out line is the honest one.",
          "- Venue, pitch, toss and line-ups are not in this study (issue #385 covers venue/pitch).",
          "- No free historical closing odds, so no return figure: return and CLV come from the shadow record.",
          "- Record only: nothing here changes a stake, a bar or the live switch."]
    return "\n".join(L) + "\n"


def main() -> int:
    games = load()
    if len(games) < 1000:
        print(f"only {len(games)} matches read: NO DATA - PENDING")
        return 1
    text = run(games)
    OUT.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
