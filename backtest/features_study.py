"""
FEATURES STUDY (autonomy plan item 5, 2026-10-20) — does each richer-data
feature add information beyond the model's own chance?

For every graded rated fixture with the model's own numbers (src "model"),
walk-forward by day (engine/walkforward.feature_test): the feature's weight is
fitted on earlier days only, and the day is scored with and without it.
Outcomes: home win, over 2.5, both teams score. Features:
  xG edge / xG total   — FotMob xG form before the match (data/match_stats/)
  team-news edge       — injuries/absences share of XI value (capture_news;
                         before that only the picks carried it, `missing`)
  soft close gap       — SportyBet's last price (margin removed) minus model
  sharp close gap      — Matchbook's last price (margin removed) minus model
  Betfair close gap    — Betfair Exchange close (football-data, main leagues)
A close is only known at kick-off, so the close gaps measure how much the
market knew that the model didn't — not a bet the board could have taken.

    python backtest/features_study.py   -> backtest/FEATURES_STUDY.md
A study, not a selector.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from data import fixture_features as ff  # noqa: E402
from engine import features as F  # noqa: E402
from engine import walkforward as wf  # noqa: E402

OUT = ROOT / "backtest" / "FEATURES_STUDY.md"
OUTCOMES = (("home win", 0, "home"), ("over 2.5", 4, "over25"), ("BTTS yes", 6, "btts"))


def _y(ft: str) -> list[int] | None:
    try:
        h, a = (int(x) for x in ft.split("-"))
    except (AttributeError, ValueError):
        return None
    return [int(h > a), int(h == a), int(h < a), int(h + a > 1.5), int(h + a > 2.5),
            int(h + a > 3.5), int(h > 0 and a > 0)]


def _num(x):
    return x if isinstance(x, (int, float)) and not isinstance(x, bool) else None


def collect(ledger_dir: Path = ff.LEDGER_DIR, feat_dir: Path = ff.FEAT_DIR,
            stats_rows: list[dict] | None = None, urows: list[dict] | None = None,
            bidx: dict | None = None) -> list[dict]:
    """One record per graded model-rated fixture: day, model p, outcomes, features."""
    if stats_rows is None:
        from data import match_stats
        stats_rows = match_stats.load()
    if urows is None:
        from engine import universe as uv
        urows = uv.load_graded()
    uidx = ff.universe_index(urows)
    paths = sorted(ledger_dir.glob("picks_*.json"))
    if bidx is None:
        bidx = {}
        days = [p.stem[6:] for p in paths]
        leagues = {fx.get("league") or "" for d in days for fx in ff.rated(d, ledger_dir)}
        for season in sorted({ff.season_of(d) for d in days}):
            bidx.update(ff.betfair_index(leagues, season))
    out = []
    for path in paths:
        doc = json.loads(path.read_text(encoding="utf-8"))
        day = doc.get("date") or path.stem[6:]
        news = ff._load(feat_dir / f"news_{day}.json")
        picks_missing = {f"{s.get('home')} v {s.get('away')}": s.get("missing")
                         for s in doc.get("singles", []) if isinstance(s.get("missing"), dict)}
        for fx in doc.get("rated", []):
            y = _y(fx.get("ft"))
            if fx.get("src") != "model" or y is None or not fx.get("home"):
                continue
            k = f"{fx['home']} v {fx['away']}"
            snap = news.get(k)
            if snap is None and picks_missing.get(k):
                m = picks_missing[k]
                snap = {"home_missing_share": m.get("home"), "away_missing_share": m.get("away")}
            feat = F.build(fx, day, stats_rows, snap, ff.find_universe(fx, day, uidx),
                           ff.find_betfair(fx, day, bidx))
            out.append({"day": day, "p": fx["p"], "y": y, "f": feat})
    return out


def feature_rows(recs: list[dict]) -> dict[str, dict[str, list]]:
    """{outcome: {feature: [(day, p, y, value)]}}"""
    res: dict[str, dict[str, list]] = {}
    for label, i, ck in OUTCOMES:
        by: dict[str, list] = {"xG edge": [], "xG total": [], "team-news edge": [],
                               "soft close gap": [], "sharp close gap": [], "Betfair close gap": []}
        for r in recs:
            f, p, y, d = r["f"], r["p"][i], r["y"][i], r["day"]
            sign = 1 if i == 0 else 0          # edges favour home; only the home-win outcome reads them
            by["xG edge"].append((d, p, y, _num(f["xg"]["edge"]) if sign else None))
            by["xG total"].append((d, p, y, _num(f["xg"]["total"]) if not sign else None))
            by["team-news edge"].append((d, p, y, _num(f["news"]["edge"]) if sign else None))
            for name, src in (("soft close gap", "soft"), ("sharp close gap", "sharp"),
                              ("Betfair close gap", "betfair")):
                c = _num(f["close"][src][ck])
                by[name].append((d, p, y, None if c is None else c - p))
        keep = ("xG edge", "team-news edge") if i == 0 else ("xG total",)
        res[label] = {k: v for k, v in by.items()
                      if k in keep or ("close" in k and (ck != "btts" or "Betfair" not in k))}
    return res


def coverage(recs: list[dict]) -> dict[str, int]:
    def n(fn) -> int:
        return sum(1 for r in recs if fn(r["f"]) not in (None, F.PENDING))
    return {"graded model-rated fixtures": len(recs),
            "with xG form (both teams, 2+ prior matches)": n(lambda f: f["xg"]["edge"]),
            "with team news": n(lambda f: f["news"]["edge"]),
            "with confirmed lineups": sum(1 for r in recs if r["f"]["news"]["lineup"] == "confirmed"),
            "with SportyBet close": n(lambda f: f["close"]["soft"]["home"]),
            "with Matchbook (sharp) close": n(lambda f: f["close"]["sharp"]["home"]),
            "with Betfair Exchange close": n(lambda f: f["close"]["betfair"]["home"])}


def report(recs: list[dict]) -> str:
    L = ["# FEATURES STUDY — does the richer data add information beyond the model?", "",
         "Written by `backtest/features_study.py` (autonomy plan item 5). Every graded fixture the board "
         "rated with the model's own numbers; walk-forward by day — a feature's weight is fitted on "
         f"earlier days only (from {wf.MIN_TRAIN} rows), then the day is scored with and without it. "
         "**gain** = Brier of the model alone minus Brier with the feature (positive = the feature helped), "
         "± its standard error. ADDS INFORMATION needs 100+ scored fixtures and a gain over 2 se. "
         "The close gaps use the last price before kick-off, so they measure what the market knew that "
         "the model didn't. A study, not a selector: nothing here changes a pick.", ""]
    if not recs:
        L.append("No graded model-rated fixture yet — NO DATA — PENDING.")
        return "\n".join(L) + "\n"
    days = sorted({r["day"] for r in recs})
    L += [f"{len(recs)} fixtures, {days[0]} to {days[-1]}.", "", "## Coverage", "",
          "| Data | fixtures |", "|---|---|"]
    L += [f"| {k} | {v} |" for k, v in coverage(recs).items()]
    L += ["", "## Walk-forward result", "",
          "| Outcome | Feature | with feature | scored | model Brier | gain | ± se | verdict |",
          "|---|---|---|---|---|---|---|---|"]
    for label, feats in feature_rows(recs).items():
        for name, rows in feats.items():
            t = wf.feature_test(rows)
            mb = "PENDING" if t["brier_model"] is None else f"{t['brier_model']:.4f}"
            L.append(f"| {label} | {name} | {t['rows']} | {t['scored']} | {mb} | "
                     f"{t['gain']:+.5f} | {t['se']:.5f} | {t['verdict']} |")
    L += ["", "NOT ENOUGH DATA is the honest answer while a feed is young: the xG archive started "
          "2026-10-04, Matchbook prices 2026-10-16, the Betfair close comes only for the main leagues, team news for every rated fixture 2026-10-20. "
          "The study reruns every morning (universe sweep) and the research harness reads it."]
    return "\n".join(L) + "\n"


def main() -> int:
    recs = collect()
    OUT.write_text(report(recs), encoding="utf-8")
    print(f"features study: {len(recs)} graded fixtures -> {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
