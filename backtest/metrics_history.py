"""
BACKTEST METRICS HISTORY (Phase 3.5) — track metrics over time.

The report is a full measurement of ONE run; the history is the accumulation
of many runs so the trend is visible — does mean CLV drift, improve, or stay
flat as the engine evolves commit by commit?

Each row is one backtest run (one record_run call), written as a single JSON
line to backtest/results/metrics_history.jsonl. Every row carries the run's
fingerprint (season, selector, leagues, config) so a change of settings is
visibly a DIFFERENT experiment, not a revision of this one — the same rule
the report applies to config.

HONESTY (the same rules as the report, carried through):
  - raw-price legs only. DERIVED O1.5 legs are never pooled into the headline
    (probability space, no margin drift) — summarise() already splits them,
    and record_run keeps that split.
  - context is recorded ("manual" | "ci_push" | "ci_pr" | "ci_nightly") so a
    partial CI slice is never mistaken for a full run.
  - render_history groups rows by (season, selector) family and shows the
    trend WITHIN a family — a 2-league CI slice never pollutes a full run's
    numbers, and a corrupt line is skipped, never allowed to kill the view.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from backtest import backtest_report as br
from engine.softness import DEPLOY_ELIGIBLE_TIERS, softness_tier

RESULTS_DIR = Path(__file__).parent / "results"
METRICS_PATH = RESULTS_DIR / "metrics_history.jsonl"


def record_run(legs: list, flags: list[str], coverage: dict, cfg,
               run_id: str, context: str = "manual",
               run_date: str | None = None) -> dict:
    """Append one run's metrics to the history and return the row.

    `legs` is the full list of PaperLegs; raw-price legs are summarised
    (DERIVED O1.5 excluded from the headline, exactly as the report does). The
    softness-thesis split (A/B deploy-eligible vs C/D control) is recorded so
    the trend can show whether any CLV is concentrated where it is actually
    deployable. Returns the dict that was written — the caller may print it."""
    raw = [lg for lg in legs if not lg.derived]
    s = br.summarise(raw, "ALL")
    ab = [lg for lg in raw if softness_tier(lg.league) in DEPLOY_ELIGIBLE_TIERS]
    cd = [lg for lg in raw if softness_tier(lg.league) not in DEPLOY_ELIGIBLE_TIERS]
    s_ab, s_cd = br.summarise(ab, "ab"), br.summarise(cd, "cd")

    row = {
        "run_id": run_id,
        "recorded_at": (run_date or
                        datetime.now(UTC).isoformat(timespec="seconds")),
        "context": context,
        "test_season": cfg.test_season,
        "selector": cfg.selector,
        "fingerprint": cfg.fingerprint(),
        "leagues": list(cfg.leagues),
        "calibrate": bool(getattr(cfg, "calibrate", False)),
        "blend_market": bool(getattr(cfg, "blend_market", False)),
        "n_legs_selected": s["n_legs_selected"],
        "n_with_clv": s["n_with_clv"],
        "n_distinct_matches": s["n_distinct_matches"],
        "mean_clv_pct": s["mean_clv_pct"],
        "median_clv_pct": s["median_clv_pct"],
        "t_stat": s["t_stat"],
        "pct_beat_close": s["pct_beat_close"],
        "hit_rate_pct": s["hit_rate_pct"],
        "roi_pct": s["roi_pct"],
        "n_graded": s["n_graded"],
        "mean_overround_open": s["mean_overround_open"],
        "mean_overround_close": s["mean_overround_close"],
        "tier_ab_mean_clv": s_ab["mean_clv_pct"],
        "tier_ab_n": s_ab["n_with_clv"],
        "tier_cd_mean_clv": s_cd["mean_clv_pct"],
        "tier_cd_n": s_cd["n_with_clv"],
        "n_flags": len(flags),
    }
    METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(METRICS_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")
    return row


def read_history(path: str | Path = METRICS_PATH) -> list[dict]:
    """All recorded rows, oldest first. A non-JSON line (header comment or a
    corrupted write) is skipped, never allowed to kill the history view."""
    p = Path(path)
    if not p.exists():
        return []
    rows: list[dict] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _fmt_mean(v) -> str:
    return "—" if v is None else f"{v:+.2f}"


def _fmt(v, dp: int = 1) -> str:
    return "—" if v is None else f"{v:.{dp}f}"


def render_history(path: str | Path = METRICS_PATH) -> str:
    """A compact trend table, grouped by (test_season, selector) family so a
    partial CI slice is never compared against a full run as if equal."""
    rows = read_history(path)
    out = ["BACKTEST METRICS HISTORY (Phase 3.5) — metrics over time",
           "=" * 78]
    if not rows:
        out.append("  empty — run a backtest (or python -m backtest.metrics_history "
                   "after one) to record the first row.")
        return "\n".join(out)

    families: dict[str, list[dict]] = {}
    for r in rows:
        fam = f"{r.get('test_season', '?')}_{r.get('selector', '?')}"
        families.setdefault(fam, []).append(r)

    for fam in sorted(families, reverse=True):
        fr = families[fam]
        out.append("")
        out.append(f"FAMILY: {fam}  ({len(fr)} run{'s' if len(fr) != 1 else ''})")
        out.append(f"  {'recorded':<21}{'ctx':<10}{'legs':>6}{'clv_n':>6}"
                   f"{'mean%':>8}{'beat%':>7}{'t':>7}{'A/B diff':>9}")
        for r in fr:
            ab_diff = "—"
            if r.get("tier_ab_mean_clv") is not None and r.get("tier_cd_mean_clv") is not None:
                ab_diff = f"{r['tier_ab_mean_clv'] - r['tier_cd_mean_clv']:+.2f}"
            out.append(
                f"  {str(r.get('recorded_at', '?'))[:19]:<21}"
                f"{str(r.get('context', '?')):<10}"
                f"{r.get('n_legs_selected', 0):>6}{r.get('n_with_clv', 0):>6}"
                f"{_fmt_mean(r.get('mean_clv_pct')):>8}"
                f"{_fmt(r.get('pct_beat_close')):>7}"
                f"{_fmt(r.get('t_stat')):>7}"
                f"{ab_diff:>9}")
    out.append("")
    out.append("  Compare rows WITHIN a family. Different seasons, selectors, or")
    out.append("  league sets are different experiments — the fingerprint column in")
    out.append("  the jsonl records that, and a CI slice (ctx) is never a full run.")
    out.append("HONEST EDGE LINE: history tracks the trend; only logged forward CLV proves.")
    return "\n".join(out)


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="Print the backtest metrics history")
    ap.add_argument("--json", action="store_true",
                    help="dump the raw rows as JSON (newest last)")
    args = ap.parse_args()
    if args.json:
        print(json.dumps(read_history(), indent=2))
    else:
        print(render_history())


if __name__ == "__main__":
    main()
