"""
FIRST-HALF STUDY (framework #582) - does the first-half model (engine/first_half.py) know more than the league?

Walk-forward: every game is predicted from games BEFORE it only (its own season so far plus the whole previous
season), then added. Scored against the half-time score:
  - Brier score of P(goal before half-time), model vs the league-rate baseline (lower is better);
  - calibration by decile of the model's chance;
  - the 'filter': the model's most confident quarter / tenth of games and what they really hit, next to the
    base rate and the break-even price (1 / hit rate). The video's filter claims 75.8%.
Datasets: football-data.co.uk (22 divisions, half-time scores, 2019/20 on) and the SportyBet sweep (since
2026-10-08; names are SportyBet's own, so its teams only meet themselves).
No source we hold prices first-half goal lines, so the value test is PENDING (the shadow board logs the model's
chance; SportyBet's 1st-half prices need a market id the sweep does not read yet).
Output: backtest/FIRST_HALF_STUDY.md.  Usage: python backtest/first_half_study.py [--no-fetch]
"""
from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import first_half as fh  # noqa: E402
from engine import stats_history as sh  # noqa: E402

REPORT = ROOT / "backtest" / "FIRST_HALF_STUDY.md"


def walk(rows: list[dict], by_season: bool) -> list[tuple[float, float, int]]:
    """(model p, baseline p, outcome) for every game that had history before it."""
    out = []
    if by_season:
        seasons = sorted({r["season"] for r in rows})
        for i, s in enumerate(seasons[1:], 1):
            prev = [r for r in rows if r["season"] == seasons[i - 1]]
            m = fh.FirstHalf(prev)
            for r in (r for r in rows if r["season"] == s):
                if r.get("hthg") is None:
                    continue
                _lh, _la, n = m.league_rates(r["league"])
                if n >= 30:
                    p = m.predict(r["league"], r["home"], r["away"])["over05"]
                    out.append((p, m.league_over05(r["league"]), int(r["hthg"] + r["htag"] > 0)))
                m.add(r)
    else:
        m = fh.FirstHalf()
        for r in rows:
            if r.get("hthg") is None:
                continue
            _lh, _la, n = m.league_rates(r["league"])
            if m.all[0] >= 500:
                p = m.predict(r["league"], r["home"], r["away"])["over05"]
                out.append((p, m.league_over05(r["league"]), int(r["hthg"] + r["htag"] > 0)))
            m.add(r)
    return out


def report(name: str, res: list[tuple[float, float, int]]) -> list[str]:
    if len(res) < 200:
        return [f"### {name}", f"- PENDING: {len(res)} games scored (need 200)."]
    n = len(res)
    base = sum(y for *_x, y in res) / n
    bm = sum((p - y) ** 2 for p, _b, y in res) / n
    bb = sum((b - y) ** 2 for _p, b, y in res) / n
    lines = [f"### {name}", f"- {n:,} games scored; a goal before half-time in **{base:.1%}**.",
             f"- Brier: model **{bm:.4f}**, league baseline {bb:.4f} "
             f"({'model better' if bm < bb else 'model NOT better'} by {abs(bb - bm):.4f}).", "",
             "| Model's chance (decile) | Games | Average chance | Actually happened |", "|---|---|---|---|"]
    srt = sorted(res, key=lambda t: t[0])
    for d in range(10):
        part = srt[d * n // 10:(d + 1) * n // 10]
        if part:
            lines.append(f"| {d + 1} | {len(part)} | {sum(p for p, *_ in part) / len(part):.1%} | "
                         f"{sum(y for *_x, y in part) / len(part):.1%} |")
    lines += ["", "| Filter | Games | Hit | Break-even price |", "|---|---|---|---|"]
    for label, frac in (("every game", 1.0), ("most confident quarter", 0.25), ("most confident tenth", 0.10),
                        ("most confident 2%", 0.02)):
        part = srt[int(n * (1 - frac)):]
        hit = sum(y for *_x, y in part) / len(part)
        lines.append(f"| {label} | {len(part):,} | {hit:.1%} | {1 / hit:.2f} |")
    return lines


def main(argv: list[str] | None = None) -> int:
    argv = argv or []
    hist, _cov = sh.load_history(fetch="--no-fetch" not in argv)
    sporty = sh.load_sportybet()
    a = walk(hist, by_season=True)
    b = walk(sporty, by_season=False)
    now = datetime.now(UTC)
    cur = [r for r in hist if r["season"] == sh.CURRENT]
    tops = fh.top_home(cur, top=10)
    md = ["# First-half goals study (framework #582)", "",
          f"Generated {now:%Y-%m-%d %H:%M} UTC by `backtest/first_half_study.py`. SHADOW ONLY: nothing here picks "
          "or stakes. The video's '75.8% filter' and '90-96%' figures are claims to test.", "",
          *report("A. football-data.co.uk (22 divisions, 2019/20 on)", a), "",
          *report("B. SportyBet sweep (every listed football game since 2026-10-08)", b), "",
          "## How the shrinkage was chosen",
          "- Team rates are pulled toward the league rate by SHRINK pseudo-games. Five values were tried (6, 12, "
          "20, 30, 50) on 2019/20-2022/23 only; 50 was least bad there (Brier 0.21098 vs league 0.21092). On "
          "2023/24 on, not used to choose it, 50 beat the league rate by 0.0005 and 6 lost by 0.0025. The team "
          "signal for first-half goals is real in ranking but tiny in size.", "",
          "## Price test", "- **PENDING**: no source we hold prices first-half goal lines. To beat the price a "
          "filter's hit rate must clear 1 / price after the margin; at a typical 1.30-1.40 for 1st-half over 0.5 "
          "that is 71-77% before the margin, about the base rate.", "",
          f"## Home sides with the most first-half goals at home, {sh.CURRENT} so far (min {fh.MIN_TEAM} home games)",
          "| Team | League | Home games | 1st-half goals | Per game | Wins |", "|---|---|---|---|---|---|",
          *[f"| {t['team']} | {t['league']} | {t['home_games']} | {t['fh_goals']} | {t['fh_per_game']} | {t['wins']} |"
            for t in tops], "",
          "## Reading",
          "- A filter is worth something only if its hit rate beats the price it is bet at, not the 70% base rate. "
          "Until a priced 1st-half line is in our data, the model is a shadow record and a list for the app.", ""]
    REPORT.write_text("\n".join(md), encoding="utf-8")
    print(f"wrote {REPORT.relative_to(ROOT)}: {len(a)} + {len(b)} games scored")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
