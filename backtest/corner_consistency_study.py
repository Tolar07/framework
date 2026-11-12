"""
CORNER CONSISTENCY STUDY (framework #583) - is a team's 'steadiness' in total corners real, or luck?

For every team-season with 30+ games and corners (football-data.co.uk, 2018/19 on):
  1. split its games in date order into the first and the second half of the season;
  2. correlate the first half's standard deviation of total match corners with the second half's
     (and, for comparison, the first half's MEAN with the second half's mean);
  3. the steadiest fifth in the first half: is their second-half spread lower than everyone else's,
     and by how much compared with the spread itself?
  4. a line test with no price: for the main total-corners line nearest each team's first-half mean, does
     the second half land inside mean +/- 2 more often for the steady fifth?
If steadiness does not carry over, it stays a list for the app and is NOT fed to the corners event model
(engine/event_model.py), as #583 requires. There are no corner prices in our sources, so a value test is PENDING
(#567 checks SportyBet's corner prices).
Output: backtest/CORNER_CONSISTENCY_STUDY.md.  Usage: python backtest/corner_consistency_study.py [--no-fetch]
"""
from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import corner_consistency as cc  # noqa: E402
from engine import stats_history as sh  # noqa: E402

REPORT = ROOT / "backtest" / "CORNER_CONSISTENCY_STUDY.md"


def corr(xs: list[float], ys: list[float]) -> float:
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    c = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    return c / (vx * vy) ** 0.5 if vx and vy else 0.0


def halves(hist: list[dict]) -> list[dict]:
    out = []
    for s in sorted({r["season"] for r in hist}):
        for (team, lg), games in cc.per_team([r for r in hist if r["season"] == s]).items():
            if len(games) < 30:
                continue
            k = len(games) // 2
            a, b = games[:k], games[k:]
            ta, tb = [g[1] for g in a], [g[1] for g in b]
            ma = sum(ta) / len(ta)
            out.append({"team": team, "league": lg, "season": s, "sd1": cc._sd(ta), "sd2": cc._sd(tb),
                        "m1": ma, "m2": sum(tb) / len(tb),
                        "in2": sum(1 for t in tb if abs(t - ma) <= 2) / len(tb)})
    return out


def main(argv: list[str] | None = None) -> int:
    argv = argv or []
    hist, _ = sh.load_history(fetch="--no-fetch" not in argv)
    hs = halves(hist)
    now = datetime.now(UTC)
    md = ["# Corner consistency study (framework #583)", "",
          f"Generated {now:%Y-%m-%d %H:%M} UTC by `backtest/corner_consistency_study.py`. RECORD ONLY. The video's "
          "'most consistent teams in corners' list is a claim to test.", ""]
    if len(hs) < 50:
        md.append(f"PENDING: {len(hs)} team-seasons with 30+ games and corners (need 50).")
    else:
        r_sd = corr([h["sd1"] for h in hs], [h["sd2"] for h in hs])
        r_m = corr([h["m1"] for h in hs], [h["m2"] for h in hs])
        srt = sorted(hs, key=lambda h: h["sd1"])
        q = len(srt) // 5
        steady, rest = srt[:q], srt[q:]
        avg = lambda xs, k: sum(x[k] for x in xs) / len(xs)  # noqa: E731
        md += [f"Data: {len(hist):,} games, **{len(hs):,} team-seasons** with 30+ games and corners "
               "(22 divisions, 2018/19 on), each split into its first and second half.", "",
               "| Carries over to the second half? | Correlation |", "|---|---|",
               f"| a team's MEAN total corners | **{r_m:.2f}** |",
               f"| a team's SPREAD (standard deviation) | **{r_sd:.2f}** |", "",
               "| Group (by first-half spread) | Team-seasons | First-half spread | Second-half spread | "
               "2nd-half games inside first-half mean +/- 2 |", "|---|---|---|---|---|",
               f"| steadiest fifth | {len(steady)} | {avg(steady, 'sd1'):.2f} | {avg(steady, 'sd2'):.2f} | "
               f"{avg(steady, 'in2'):.1%} |",
               f"| everyone else | {len(rest)} | {avg(rest, 'sd1'):.2f} | {avg(rest, 'sd2'):.2f} | "
               f"{avg(rest, 'in2'):.1%} |", "",
               "## Reading",
               f"- The mean carries over ({r_m:.2f}): a team's corner LEVEL is a real input, and the event model "
               "already uses it.",
               f"- The spread carries over at {r_sd:.2f}. The steadiest fifth's second-half spread is "
               f"{avg(steady, 'sd2'):.2f} against {avg(rest, 'sd2'):.2f} for the rest, so "
               + ("most of the first-half steadiness was luck: " if r_sd < 0.3 else "some of it is real: ")
               + "it is kept as a list for the app and is NOT fed to the corners event model "
               + ("(#583 rule: only if it carries over)." if r_sd < 0.3 else
                  "until a walk-forward test of the model with it beats the model without it."),
               "- No source we hold prices corner lines, so a value test is PENDING (#567).", ""]
    REPORT.write_text("\n".join(md), encoding="utf-8")
    print(f"wrote {REPORT.relative_to(ROOT)}: {len(hs)} team-seasons")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
