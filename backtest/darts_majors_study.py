"""
Darts majors study (framework#341, Week A; record-only). Writes backtest/DARTS_MAJORS_STUDY.md.

SHADOW on a wider dated sample: Premier League Darts nights (data/darts/pl_results.json) PLUS the PDC majors with
round-start dates (data/darts/majors_results.json, data/darts_majors_results.py), 2023-2026. The Premier League
alone is a closed field of about 10 players; the majors bring in the rest of the tour, so the Elo has to rate players
who meet rarely. Walk-forward in date order, the Elo (earlier matches only) is scored against the coin flip, and the
Elo settings (K x min games each) are tried; the first half of the scored matches picks a setting, the second half is
sealed and only judges (every try counted). Under MIN_SCORED matches reads PENDING (HR35). No price in this source:
calibration only, never an edge. Nothing here changes a pick, stake, bar or the live switch.

  python backtest/darts_majors_study.py
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest.darts_dated_study import load  # noqa: E402
from engine import multisport as ms  # noqa: E402

OUT = ROOT / "backtest" / "DARTS_MAJORS_STUDY.md"
PL = ROOT / "data" / "darts" / "pl_results.json"
MAJORS = ROOT / "data" / "darts" / "majors_results.json"
COIN = 0.25
MIN_SCORED = 100
TRIES = [(ms.ELO_K, ms.MIN_GAMES), (ms.ELO_K, 3), (ms.ELO_K, 1), (12.0, 1), (40.0, 1)]


def combine(pl: list[dict], majors: list[dict]) -> list[dict]:
    """Both feeds in one date order (a match listed in both with the same date and pair is kept once)."""
    seen: set[tuple] = set()
    out: list[dict] = []
    for g in sorted(pl + majors, key=lambda x: (x["date"], x["kickoff_utc"])):
        key = (g["date"], frozenset((ms.norm(g["home"]), ms.norm(g["away"]))))
        if key in seen:
            continue
        seen.add(key)
        out.append(g)
    return out


def scored(games: list[dict], k: float, min_games: int) -> list[tuple[str, float, float]]:
    """(year, Elo chance of home, home won 0/1) in date order, earlier matches only."""
    rating: dict[str, float] = {}
    played: dict[str, int] = {}
    out: list[tuple[str, float, float]] = []
    for g in games:
        h, a = ms.norm(g["home"]), ms.norm(g["away"])
        rh, ra = rating.get(h, ms.ELO_START), rating.get(a, ms.ELO_START)
        p = 1 / (1 + 10 ** ((ra - rh) / 400))
        y = 1.0 if g["winner"] == 1 else 0.0
        if played.get(h, 0) >= min_games and played.get(a, 0) >= min_games:
            out.append((g["date"][:4], p, y))
        rating[h], rating[a] = rh + k * (y - p), ra - k * (y - p)
        played[h], played[a] = played.get(h, 0) + 1, played.get(a, 0) + 1
    return out


def _brier(rows) -> float | None:
    return round(sum((p - y) ** 2 for _, p, y in rows) / len(rows), 4) if rows else None


def evaluate(games: list[dict]) -> dict:
    table = []
    for k, mg in TRIES:
        rows = scored(games, k, mg)
        half = len(rows) // 2
        table.append({"k": k, "mg": mg, "n": len(rows), "all": _brier(rows), "first": _brier(rows[:half]),
                      "second": _brier(rows[half:]),
                      "years": {y: (sum(1 for r in rows if r[0] == y), _brier([r for r in rows if r[0] == y]))
                                for y in sorted({r[0] for r in rows})}})
    base = next(t for t in table if (t["k"], t["mg"]) == (ms.ELO_K, ms.MIN_GAMES))
    ok = base["n"] >= MIN_SCORED
    return {"table": table, "scored": base["n"], "base": base,
            "best": min((t for t in table if t["first"] is not None), key=lambda t: t["first"]) if ok else None}


def verdict(r: dict) -> str:
    if r["best"] is None:
        return f"PENDING (needs {MIN_SCORED} scored, has {r['scored']})"
    b, base = r["best"], r["base"]
    if (b["k"], b["mg"]) == (base["k"], base["mg"]):
        return "the board setting was best in the first half: no Elo-setting lead"
    d = round(base["second"] - b["second"], 4)
    return (f"K={b['k']:g}, min games {b['mg']} picked on the first half; sealed second half Brier {b['second']} vs "
            f"board {base['second']} ({'better' if d > 0 else 'NOT better'} by {abs(d)}; about {b['n'] // 2} matches "
            "in the sealed half, so a gap under 0.005 is noise)")


def render(games: list[dict], now: datetime) -> str:
    L = ["# Darts majors study", "",
         f"Made {now:%Y-%m-%d %H:%M} UTC by `backtest/darts_majors_study.py` (framework#341). Record only.", ""]
    if not games:
        return "\n".join(L + ["NO DATA - PENDING (run `python data/darts_pl_results.py` and "
                              "`python data/darts_majors_results.py`).", ""])
    days = sorted({g["date"] for g in games})
    names = {ms.norm(n) for g in games for n in (g["home"], g["away"])}
    r = evaluate(games)
    L += [f"Data: {len(games)} dated matches (Premier League Darts nights plus PDC majors at round-start dates), "
          f"{len(names)} players, {len(days)} dates, {days[0]} to {days[-1]}. {r['scored']} scored with the board's "
          f"Elo from earlier matches only. {len(r['table'])} tries, all shown. The first half picks, the second half "
          "is sealed and only judges. The coin flip scores 0.25.", "",
          "| K | Min games each | Scored | Brier, all | Brier, first half | Brier, sealed second half | By year (n, Brier) |",
          "|---|---|---|---|---|---|---|"]
    for t in r["table"]:
        tag = " (board)" if (t["k"], t["mg"]) == (ms.ELO_K, ms.MIN_GAMES) else ""
        yrs = "; ".join(f"{y}: {n}, {b}" for y, (n, b) in t["years"].items()) or "PENDING"
        L.append(f"| {t['k']:g}{tag} | {t['mg']} | {t['n']} | {t['all'] if t['all'] is not None else 'PENDING'} | "
                 f"{t['first'] if t['first'] is not None else 'PENDING'} | "
                 f"{t['second'] if t['second'] is not None else 'PENDING'} | {yrs} |")
    cb = r["base"]["all"]
    L += ["", f"Board setting against the coin flip: {'beats' if cb is not None and cb < COIN else 'does NOT beat'} "
          f"({cb if cb is not None else 'PENDING'} vs {COIN}).", "", f"Verdict: {verdict(r)}", "",
          "A lead to test on new matches, not a change to the Elo. No price here, so no edge is claimed. "
          "Round-start dates mean matches inside one round share a date.", "",
          "Record only: nothing here changes a stake, a bar or the live switch.", ""]
    return "\n".join(L)


def run(now: datetime | None = None) -> str:
    """Reads saved results; when the majors are not saved (data/ is not in git) fetches and saves them."""
    majors = load(MAJORS)
    if not majors:
        from data import darts_majors_results
        majors = darts_majors_results.fetch_all()
        if majors:
            MAJORS.parent.mkdir(parents=True, exist_ok=True)
            MAJORS.write_text(json.dumps(majors, ensure_ascii=False), encoding="utf-8")
    text = render(combine(load(PL), majors), now or datetime.now(UTC))
    OUT.write_text(text, encoding="utf-8")
    return text


if __name__ == "__main__":
    print(run())
