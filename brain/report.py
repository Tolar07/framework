"""Plain-language /stats renderer for the brain.

The Architect is non-technical, so this speaks the same prose as the board:
no column codes, no raw SQL. HR35 is kept throughout — a query with no data
reads NO DATA — PENDING, never a guessed number.

render_stats(brain, "")  -> the overview (CLV by market/league/tier, prediction
                            counts, last-run summary, pending corrections).
render_stats(brain, arg) -> "what did I predict for <team/fixture>" lookup.
"""
from __future__ import annotations

from datetime import datetime, timezone

from config import PAPER_PHASE

# Softness tier labels shown to the Architect (engine.softness uses A/B/C/D).
_TIER_LABEL = {"A": "Tier A (deploy)", "B": "Tier B (deploy)",
               "C": "Tier C (scan-only)", "D": "Tier D (scan-only)",
               "?": "unrated"}


def _pct(x: float | None) -> str:
    return f"{x * 100:.0f}%" if x is not None else "—"


def render_stats(brain, arg: str = "") -> str:
    arg = (arg or "").strip()
    if arg:
        return _render_lookup(brain, arg)
    return _render_overview(brain)


def _render_overview(brain) -> str:
    gate = brain.gate_status()
    run = brain.last_run()
    preds = brain.predictions_summary()
    out: list[str] = []
    out.append("OLP XDV — STATS (brain memory)")
    out.append(f"As of the last daily run: "
               f"{_friendly(run['started_at']) if run else 'no run recorded yet'}")
    out.append("")

    out.append("CLV by market — paper legs with a logged closing line")
    mk = brain.clv_by_market(PAPER_PHASE)
    if not mk:
        out.append("  NO DATA — PENDING (no closing line logged yet)")
    else:
        for r in mk:
            out.append(f"  {r['market']}: n={r['n']}, mean "
                       f"{r['mean_clv_pct']:+.2f}%, beat the close "
                       f"{r['n_beat_close']}/{r['n']}")
    out.append("")

    out.append("CLV by league")
    lg = brain.clv_by_league(PAPER_PHASE)
    if not lg:
        out.append("  NO DATA — PENDING")
    else:
        for r in lg:
            out.append(f"  {r['league']}: n={r['n']}, mean {r['mean_clv_pct']:+.2f}%")
    out.append("")

    out.append("CLV by softness tier")
    tiers = brain.clv_by_tier(PAPER_PHASE)
    if not tiers:
        out.append("  NO DATA — PENDING")
    else:
        for r in tiers:
            out.append(f"  {_TIER_LABEL.get(r['tier'], r['tier'])}: n={r['n']}, "
                       f"mean {r['mean_clv_pct']:+.2f}%")
    out.append("")

    out.append("Engine calibration — the model learning from settled legs")
    from engine import recalibration as recal
    rows = brain.calibration_by_market(PAPER_PHASE)
    if not rows:
        out.append("  NO DATA — PENDING (needs ≥15 settled legs with a closing "
                   "line per market before the engine adjusts)")
    else:
        cal = recal.adjustments_for(rows)
        for r in rows:
            adj = cal.get(r["market"])
            suffix = f" -> adjust {adj:+.1%}" if adj else \
                " (below evidence gate — NO DATA — PENDING)"
            out.append(f"  {r['market']}: n={r['n']}, hit {r['mean_hit'] * 100:.0f}% "
                       f"vs model {r['mean_model_prob'] * 100:.0f}%, "
                       f"CLV {r['mean_clv_pct']:+.2f}%{suffix}")
    out.append("")

    out.append(f"Phase-3 gate: {gate['legs_with_clv']} of "
               f"{gate['gate_requirement']} legs with logged CLV"
               + (f" — mean {gate['mean_clv_pct']:+.2f}%"
                  if gate["mean_clv_pct"] is not None else " — NO DATA — PENDING"))
    out.append("")

    out.append("Road to the gate — how fast the paper record is actually building")
    tm = brain.leg_telemetry(PAPER_PHASE)
    out.append(f"  Legs logged: {tm['n_legs']} ({tm['n_with_clv']} with a closing line, "
               f"{tm['n_settled']} settled)")
    cap = tm["clv_capture_rate"]
    out.append("  Closing-line capture: "
               + (f"{cap * 100:.0f}% of settled legs earn a CLV number"
                  if cap is not None else "NO DATA — PENDING (nothing settled yet)"))
    out.append(f"  Legs per day (observed): {tm['legs_per_day']:.2f}")
    if tm["days_to_gate"] is not None:
        out.append(f"  At the current rate: ~{tm['days_to_gate']:.0f} days "
                   f"to the {tm['gate_requirement']}-leg gate "
                   f"(sustained {tm['clv_legs_per_day']:.3f} CLV legs/day)")
    else:
        out.append("  Projected days to gate: NO DATA — PENDING "
                   "(no CLV legs are being produced yet — nothing to project)")
    out.append("")

    out.append(f"Predictions stored: {preds['n_rows']} across "
               f"{preds['n_runs']} run(s)")
    oc = brain.outcome_summary()
    out.append(
        f"Outcome record (model vs reality): "
        + (f"{oc['n']} settled, hit rate {oc['hit_rate'] * 100:.0f}%"
           if oc["n"] else "0 settled — NO DATA — PENDING (matches still to play)"))

    if run:
        out.append(
            f"Last run: {run['status']}, {run['leagues_scanned']} leagues, "
            f"{run['fixtures_seen']} fixtures, {run['predictions_logged']} "
            f"predictions, {run['legs_logged']} legs")
        out.append(
            f"Fits reused: {run['dc_reused']} of "
            f"{run['dc_reused'] + run['dc_refit']} leagues (0 refits on "
            f"unchanged data) — model fit time {run['fit_seconds'] or 0:.0f}s")
    else:
        out.append("Last run: NO DATA — PENDING")
    out.append("")

    cold = _last_cold_elo(brain)
    out.append(f"Elo history: last cold refit "
               f"{cold if cold else 'never (all runs incremental)'}")
    out.append("")

    pend = brain.corrections_pending()
    if pend:
        out.append(f"Pending corrections: {len(pend)} — read back, never "
                   f"applied silently")
        for c in pend[:5]:
            out.append(f"  · {c['logged_at'][:10]}: {c['note']}")
    else:
        out.append("Pending corrections: none")
    out.append("")

    out.append("Honest edge: an excellent informed process, NOT a demonstrated "
               "profitable edge. Capital authority: THE ARCHITECT.")
    return "\n".join(out)


def _render_lookup(brain, arg: str) -> str:
    rows = brain.predictions_for(team=arg, limit=400)
    if not rows:
        return (f'No stored predictions match "{arg}" — NO DATA — PENDING')
    # Group per FIXTURE (not per run — the same match predicted on two runs is
    # one answer, and the lookup says how many runs covered it).
    groups: dict[tuple, list[dict]] = {}
    for r in rows:
        groups.setdefault((r["fixture"], r["league"]), []).append(r)
    out: list[str] = [f'PREDICTIONS matching "{arg}" (most recent first)']
    for i, ((fixture, league), rws) in enumerate(sorted(
            groups.items(),
            key=lambda kv: max(r["predicted_at"] for r in kv[1]),
            reverse=True)[:10], 1):
        latest = max(r["predicted_at"] for r in rws)
        rws = [r for r in rws if r["predicted_at"] == latest]
        n_runs = len({r["predicted_at"] for r in groups[(fixture, league)]})
        run_note = f" · seen in {n_runs} run(s)" if n_runs > 1 else ""
        dc = {r["market"]: r["model_prob"]
              for r in rws if r["model_engine"] in ("dc", "cross")}
        elo = {r["market"]: r["model_prob"]
               for r in rws if r["model_engine"] == "elo"}
        xg = {r["market"]: r["model_prob"]
              for r in rws if r["model_engine"] == "xg"}
        priced = next((r for r in rws if r.get("entry_odds") is not None), None)
        out.append(f"{i}. {latest[:10]} | {fixture} ({league}){run_note}")
        if dc:
            out.append(f"   model: {_pct(dc.get('1X2_HOME'))} home / "
                       f"{_pct(dc.get('1X2_DRAW'))} draw / "
                       f"{_pct(dc.get('1X2_AWAY'))} away"
                       + (f" · Over2.5 {_pct(dc.get('OVER_2_5'))}"
                          if dc.get("OVER_2_5") is not None else ""))
        if elo:
            out.append(f"   Elo second opinion: {_pct(elo.get('1X2_HOME'))} / "
                       f"{_pct(elo.get('1X2_DRAW'))} / {_pct(elo.get('1X2_AWAY'))}")
        if xg:
            out.append(f"   xG third opinion: {_pct(xg.get('1X2_HOME'))} / "
                       f"{_pct(xg.get('1X2_DRAW'))} / {_pct(xg.get('1X2_AWAY'))}")
        book = {r["market"]: r["model_prob"]
                for r in rws if r["model_engine"] == "bookmaker"}
        if book:
            out.append(f"   bookmaker implied: {_pct(book.get('1X2_HOME'))} home / "
                       f"{_pct(book.get('1X2_DRAW'))} draw / "
                       f"{_pct(book.get('1X2_AWAY'))} away")
        cons = {r["market"]: r["model_prob"]
                for r in rws if r["model_engine"] == "consensus"}
        if cons:
            out.append(f"   consensus (ID412): {_pct(cons.get('1X2_HOME'))} home / "
                       f"{_pct(cons.get('1X2_DRAW'))} draw / "
                       f"{_pct(cons.get('1X2_AWAY'))} away")
        if priced:
            clv = (f"CLV {priced['clv_pct']:+.2f}%"
                   if priced.get("clv_pct") is not None
                   else "CLV NO DATA — PENDING")
            out.append(f"   paper leg: {priced['market']} at "
                       f"{priced['entry_odds']:.2f} ({priced.get('bookmaker')})"
                       f" — {clv}")
        else:
            out.append("   no paper leg logged for this fixture")
    return "\n".join(out)


def _last_cold_elo(brain) -> str:
    """Days since the most recent run that had to cold-start any Elo (a run
    with elo_seeded=0 means no snapshot existed — a cold refit happened)."""
    rows = brain.run_history(limit=60)
    for r in rows:
        if r["status"] == "ok" and not r["elo_seeded"]:
            return f"{_days_ago(r['started_at'])} day(s) ago"
    return ""


def _days_ago(iso: str) -> int:
    try:
        start = datetime.fromisoformat(iso)
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        return max(0, (datetime.now(timezone.utc) - start).days)
    except (ValueError, TypeError):
        return -1


def _friendly(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso)
        return dt.strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return iso
