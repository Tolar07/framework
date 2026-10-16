"""
MATCHBOOK PRICE STUDY — SportyBet's price against Matchbook's on the same
market of the same game (Architect 2026-10-16: "integrate Matchbook into the
framework fully ... so we don't have any price mismatch or missing market";
bet365 retired, Matchbook replaces it).

Reads data/universe/graded_*.jsonl (the sweep adds `mb_last`, Matchbook's best
back prices, via data/matchbook_prices.py) and writes
backtest/MATCHBOOK_PRICE_STUDY.md:
  1. coverage — how many SportyBet games Matchbook lists, and which SportyBet
     markets it lacks;
  2. every market side priced at both: how often SportyBet pays more than
     Matchbook does after its 2% commission, and the £1 return backing every
     side at each;
  3. MISMATCHES — sides where SportyBet's price beats Matchbook's FAIR price
     (exchange margin removed): the price errors the framework looks for. Their
     £1 return at SportyBet is the test of whether Matchbook is the sharper book.
Nothing here selects a pick. A finding becomes a rule only by the Architect.

    python backtest/matchbook_price_study.py
"""
from __future__ import annotations

import sys
from collections import defaultdict
from math import sqrt
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from data import matchbook_prices as mbp  # noqa: E402
from engine import universe as uv  # noqa: E402

OUT = ROOT / "backtest" / "MATCHBOOK_PRICE_STUDY.md"
START = "2026-10-16"            # the first sweep that carried Matchbook prices


def _net(price: float) -> float:
    """What a Matchbook back pays after commission on the winnings."""
    return 1 + (price - 1) * (1 - mbp.COMMISSION)


def _fair(price: float, market: list[float], key: str) -> float:
    """Matchbook's chance with the exchange's (small) margin removed; a double
    chance side covers two of three outcomes, so its book sums to 2."""
    book = sum(1 / x for x in market if x)
    return (1 / price) / (book / (2 if key.startswith("dc:") else 1))


def _se(xs: list[float]) -> float:
    if len(xs) < 2:
        return 0.0
    m = sum(xs) / len(xs)
    return sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1) / len(xs))


def rows_since(rows: list[dict], start: str = START) -> list[dict]:
    return [r for r in rows if (r.get("ko") or "") >= start]


def compare(rows: list[dict]) -> dict:
    """Per market family: sides priced at both, SportyBet better, returns, mismatches."""
    fam: dict[str, dict] = defaultdict(lambda: {"n": 0, "sb_better": 0, "sb_ret": [], "mb_ret": [],
                                                "mis_ret": [], "mis_won": 0})
    for r in rows:
        mb, res = r.get("mb_last"), r.get("result")
        if not mb or not res:
            continue
        sport = r.get("sport") or "football"
        sb = {k: (w, x) for k, w, x, _p in uv.outcomes(sport, (r.get("last") or {}).get("p") or {}, res)}
        for k, w, x, market in uv.outcomes(sport, mb.get("p") or {}, res):
            if k not in sb:
                continue
            sw, sx = sb[k]
            f = fam[f"{sport} {k.split(':')[0]}"]
            f["n"] += 1
            f["sb_better"] += int(sx > _net(x))
            f["sb_ret"].append(sw * sx - 1)
            f["mb_ret"].append(w * _net(x) - 1)
            if sx * _fair(x, market, k) > 1:          # SportyBet pays more than Matchbook's fair chance
                f["mis_ret"].append(sw * sx - 1)
                f["mis_won"] += sw
    return fam


def coverage(rows: list[dict]) -> tuple[dict, dict]:
    games: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    missing: dict[str, list[int]] = defaultdict(lambda: [0, 0])     # [on SportyBet, also on Matchbook]
    for r in rows:
        sport = r.get("sport") or "football"
        g = games[sport]
        g[0] += 1
        mb = (r.get("mb_last") or {}).get("p")
        if not mb:
            continue
        g[1] += 1
        for k in (r.get("last") or {}).get("p") or {}:
            m = missing[f"{sport} {k}"]
            m[0] += 1
            m[1] += int(k in mb)
    return games, missing


def _pct(xs: list[float]) -> str:
    return f"{sum(xs) / len(xs):+.1%} ± {_se(xs):.1%}" if xs else "—"


def write(rows: list[dict] | None = None, out: Path = OUT) -> str:
    rows = rows_since(uv.load_graded() if rows is None else rows)
    games, missing = coverage(rows)
    fam = compare(rows)
    L = ["# MATCHBOOK PRICE STUDY", "",
         "Written by `backtest/matchbook_price_study.py` from `data/universe/graded_*.jsonl`: every SportyBet "
         "game the sweep watches, with Matchbook's best back price for the same market "
         "(`data/matchbook_prices.py`, public prices, no login). Matchbook prices are shown after its "
         f"{mbp.COMMISSION:.0%} commission. A study, not a selector.", "",
         f"Games kicking off from {START}: {sum(g[0] for g in games.values())} graded.", "",
         "## 1. Coverage — what Matchbook lists", "",
         "| Sport | Graded games | On Matchbook | Share |", "|---|---:|---:|---:|"]
    for s, (n, m) in sorted(games.items()):
        L.append(f"| {s} | {n} | {m} | {m / n:.0%} |" if n else f"| {s} | 0 | 0 | — |")
    L += ["", "SportyBet markets on games Matchbook lists — how often Matchbook has the same market "
          "(1UP/2UP early payout is SportyBet-only):", "",
          "| Market | SportyBet | Matchbook too | Missing on Matchbook |", "|---|---:|---:|---:|"]
    for k, (n, m) in sorted(missing.items()):
        L.append(f"| {k} | {n} | {m} | {(n - m) / n:.0%} |")
    L += ["", "## 2. Same market, both books", "",
          "Every side priced at both. \"SportyBet pays more\" = SportyBet's price above Matchbook's after "
          "commission. Return = £1 on every side at that book.", "",
          "| Market | Sides | SportyBet pays more | Return at SportyBet | Return at Matchbook |",
          "|---|---:|---:|---:|---:|"]
    for k, f in sorted(fam.items(), key=lambda kv: -kv[1]["n"]):
        L.append(f"| {k} | {f['n']} | {f['sb_better'] / f['n']:.0%} | {_pct(f['sb_ret'])} | {_pct(f['mb_ret'])} |")
    if not fam:
        L.append("| — | 0 | — | — | — |")
    L += ["", "## 3. Mismatches — SportyBet above Matchbook's fair price", "",
          "Sides where SportyBet's price beats the chance Matchbook's exchange gives (margin removed). If "
          "Matchbook is the sharper book, backing these at SportyBet should return more than backing "
          "everything (section 2).", "",
          "| Market | Mismatches | Won | Return at SportyBet |", "|---|---:|---:|---:|"]
    any_mis = False
    for k, f in sorted(fam.items(), key=lambda kv: -len(kv[1]["mis_ret"])):
        if f["mis_ret"]:
            any_mis = True
            L.append(f"| {k} | {len(f['mis_ret'])} | {f['mis_won'] / len(f['mis_ret']):.0%} | {_pct(f['mis_ret'])} |")
    if not any_mis:
        L.append("| — | 0 | — | — |")
    L += ["", "Small samples first: a return needs a few hundred sides before it means anything; "
          "± is one standard error.", ""]
    text = "\n".join(L)
    out.write_text(text, encoding="utf-8")
    return text


def main() -> int:
    write()
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
