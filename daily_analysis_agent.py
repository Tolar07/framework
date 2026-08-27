#!/usr/bin/env python3
"""
Daily Analysis Agent — OLP XDV
========================================================

Automated daily analysis system that examines:
1. Heartbeats (history, performance, compounding)
2. AI Survivor / Variant Population (fitness, survival tiers, replication/cull signals)
3. Daily Pipeline Production (board, accas, booking codes, CLV logs)

Three analysis types:
- Functional Analysis: Pipeline gaps, missing artifacts, incomplete stages
- Verification Analysis: Cross-check verified vs produced, settlement accuracy
- Performance Insight: Market/band/variant performance, CLV drift, calibration

Motivation Logic: Fitness-based selection pressure for variant population evolution
based on settled outcomes — drives replication of winners, culling of losers,
and compute allocation via survival tiers.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional
from collections import defaultdict

# Ensure repo root on path
REPO_ROOT = Path(__file__).parent
sys.path.insert(0, str(REPO_ROOT))

# Import OLP XDV modules
from output.heartbeat import get_heartbeat_stats, save_heartbeat_record
from bets.booking_tracker import status as booking_status, settle as booking_settle
from bets.produced_bet import load_produced_bet, verify_produced_bet
from clv.clv_logger import CLVLog, PHASE3_GATE_MIN_LEGS
from clv.phase3_gate import evaluate_gate, load_gate_status
from variant_selection import (
    get_variant_population_status,
    compute_survival_tier_from_variants,
    shouldReplicate,
    shouldCull,
)
from brain.store import Brain
from config import PAPER_PHASE, assert_paper_only

# ---------------------------------------------------------------------------
# DATA MODELS
# ---------------------------------------------------------------------------

@dataclass
class AnalysisResult:
    """Container for a single analysis finding."""
    category: str          # "functional" | "verification" | "performance" | "motivation"
    severity: str          # "info" | "warning" | "critical"
    title: str
    description: str
    evidence: dict = field(default_factory=dict)
    recommendation: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class DailyAnalysisReport:
    """Complete daily analysis report."""
    date: str
    analysis_timestamp: str
    functional: list[AnalysisResult]
    verification: list[AnalysisResult]
    performance: list[AnalysisResult]
    motivation: list[AnalysisResult]
    summary: dict

    def to_dict(self) -> dict:
        return {
            "date": self.date,
            "analysis_timestamp": self.analysis_timestamp,
            "functional": [asdict(r) for r in self.functional],
            "verification": [asdict(r) for r in self.verification],
            "performance": [asdict(r) for r in self.performance],
            "motivation": [asdict(r) for r in self.motivation],
            "summary": self.summary,
        }

    def to_markdown(self) -> str:
        lines = [
            f"# Daily Analysis Report — {self.date}",
            f"Generated: {self.analysis_timestamp}",
            "",
            f"## Summary",
            f"- Functional findings: {len(self.functional)}",
            f"- Verification findings: {len(self.verification)}",
            f"- Performance findings: {len(self.performance)}",
            f"- Motivation signals: {len(self.motivation)}",
            "",
        ]

        for category, findings in [
            ("Functional Analysis", self.functional),
            ("Verification Analysis", self.verification),
            ("Performance Insight", self.performance),
            ("Motivation Logic", self.motivation),
        ]:
            lines.append(f"## {category}")
            if not findings:
                lines.append("_No findings_")
                lines.append("")
                continue
            for f in findings:
                sev_emoji = {"info": "ℹ️", "warning": "⚠️", "critical": "🚨"}[f.severity]
                lines.append(f"### {sev_emoji} {f.title}")
                lines.append(f"**Severity:** {f.severity.upper()}")
                lines.append(f"**Description:** {f.description}")
                if f.evidence:
                    lines.append(f"**Evidence:**")
                    for k, v in f.evidence.items():
                        lines.append(f"  - {k}: {v}")
                if f.recommendation:
                    lines.append(f"**Recommendation:** {f.recommendation}")
                lines.append("")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# DATA SOURCES — Load all production artifacts
# ---------------------------------------------------------------------------

def load_heartbeat_history() -> list[dict]:
    """Load heartbeat history from JSONL."""
    history_file = REPO_ROOT / "data" / "heartbeat" / "history.jsonl"
    if not history_file.exists():
        return []
    with open(history_file, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def load_booking_tracker(target_date: str) -> dict:
    """Load booking tracker produced bet for date."""
    return booking_status(target_date)


def load_produced_bet_record(target_date: str) -> Optional[dict]:
    """Load produced bet record for date."""
    return load_produced_bet(target_date)


def load_clv_log() -> CLVLog:
    """Load CLV logger."""
    return CLVLog()


def load_variant_population() -> dict:
    """Load variant population status."""
    return get_variant_population_status()


def load_board_log(target_date: str) -> Optional[dict]:
    """Load board log for date (daily pipeline output)."""
    board_dir = REPO_ROOT / "output" / "boards"
    board_file = board_dir / f"board_{target_date}.json"
    if not board_file.exists():
        return None
    try:
        with open(board_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def load_variant_ledger() -> list[dict]:
    """Load variant ledger directly."""
    ledger_file = REPO_ROOT / "variant_ledger_log.jsonl"
    if not ledger_file.exists():
        return []
    with open(ledger_file, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


# ---------------------------------------------------------------------------
# FUNCTIONAL ANALYSIS — Pipeline gaps, missing artifacts, incomplete stages
# ---------------------------------------------------------------------------

def run_functional_analysis(target_date: str) -> list[AnalysisResult]:
    """Analyze pipeline completeness and artifact production."""
    findings: list[AnalysisResult] = []

    # 1. Check heartbeat was produced
    hb_history = load_heartbeat_history()
    today_hb = [h for h in hb_history if h.get("date") == target_date]
    if not today_hb:
        findings.append(AnalysisResult(
            category="functional",
            severity="warning",
            title="No Heartbeat Produced Today",
            description=f"No heartbeat record found for {target_date}. Heartbeat should be generated daily at 07:00.",
            evidence={"date": target_date, "history_count": len(hb_history)},
            recommendation="Check daily pipeline run (run_daily.py) completed successfully. Verify Agent 10 (CEO) sign-off.",
        ))
    else:
        hb = today_hb[0]
        if not hb.get("verification_passed", False):
            findings.append(AnalysisResult(
                category="functional",
                severity="warning",
                title="Heartbeat Verification Failed",
                description=f"Today's heartbeat fixture ({hb.get('fixture')}) did not pass ID403 verification.",
                evidence={"fixture": hb.get("fixture"), "verification": hb.get("verification_passed")},
                recommendation="Review verification tier for this fixture. Consider Architect review if TIER_C.",
            ))

    # 2. Check produced bet exists
    produced = load_produced_bet_record(target_date)
    if not produced:
        findings.append(AnalysisResult(
            category="functional",
            severity="critical",
            title="No Produced Bet Record",
            description=f"produce_{target_date}.json not found. The daily pipeline did not produce a bet record.",
            evidence={"date": target_date},
            recommendation="Run run_daily.py manually to diagnose. Check Agent 8 (Execution) output.",
        ))
    elif not produced.get("produced", False):
        findings.append(AnalysisResult(
            category="functional",
            severity="info",
            title="No Rated Fixtures Today",
            description="Daily pipeline ran but no rated fixtures kicked off today. Valid empty record.",
            evidence={"date": target_date, "n_legs": produced.get("n_legs", 0)},
            recommendation="No action needed — this is a valid outcome (ID415).",
        ))

    # 3. Check booking codes were generated
    booking = load_booking_tracker(target_date)
    if not booking.get("accas"):
        findings.append(AnalysisResult(
            category="functional",
            severity="warning",
            title="No Booking Codes Generated",
            description="Produced bet exists but no booking codes were generated for SportyBet.",
            evidence={"date": target_date, "produced_bet": produced.get("n_legs", 0) if produced else 0},
            recommendation="Check booking.booking_codes module. Verify odds availability on SportyBet.",
        ))
    else:
        total_codes = sum(len(a.get("legs", [])) for a in booking.get("accas", []))
        if total_codes == 0:
            findings.append(AnalysisResult(
                category="functional",
                severity="warning",
                title="Booking Codes Empty",
                description="Booking tracker has accas but no legs with valid codes.",
                evidence=booking,
                recommendation="Check odds fetch from SportyBet bridge. Verify market mappings.",
            ))

    # 4. Check CLV log has entries
    clv_log = load_clv_log()
    today_legs = [l for l in clv_log.legs if l.date_logged.startswith(target_date)]
    if not today_legs:
        findings.append(AnalysisResult(
            category="functional",
            severity="info",
            title="No CLV Entries Logged Today",
            description="No legs had entry odds captured today (CL-LIVE capture path).",
            evidence={"date": target_date, "total_legs": len(clv_log.legs)},
            recommendation="Expected if no priced markets available. Verify odds_index in pipeline.",
        ))

    # 5. Check variant population health
    variant_status = load_variant_population()
    summary = variant_status.get("summary", {})
    if summary.get("aliveVariants", 0) == 0:
        findings.append(AnalysisResult(
            category="functional",
            severity="critical",
            title="Variant Population Extinct",
            description="No alive variants in population. Survival tier will be 'dead'.",
            evidence=summary,
            recommendation="Trigger variant replication from config or re-seed population. Check variant_selection.add_variant().",
        ))
    elif summary.get("meanFitness", 0) < 0.4:
        findings.append(AnalysisResult(
            category="functional",
            severity="warning",
            title="Variant Population Fitness Critical",
            description=f"Mean fitness {summary.get('meanFitness', 0):.3f} below critical threshold (0.40).",
            evidence=summary,
            recommendation="Review variant performance. Consider culling worst variants and replicating best.",
        ))

    # 6. Check pipeline board log exists
    board_log = load_board_log(target_date)
    if not board_log:
        findings.append(AnalysisResult(
            category="functional",
            severity="warning",
            title="Board Log Missing",
            description=f"board_{target_date}.json not found. Pipeline may have halted before board output.",
            evidence={"date": target_date},
            recommendation="Check pipeline agent handoffs in olp_xdv_pipeline.py. Look for Agent 7/8/9/10 failures.",
        ))
    else:
        # Check for pipeline stage completion markers
        required_stages = ["ingestion", "verification", "engine", "production", "booking"]
        missing_stages = [s for s in required_stages if s not in str(board_log).lower()]
        if missing_stages:
            findings.append(AnalysisResult(
                category="functional",
                severity="warning",
                title=f"Missing Pipeline Stages: {', '.join(missing_stages)}",
                description="Board log may be incomplete — some pipeline stages not represented.",
                evidence={"available_keys": list(board_log.keys()) if isinstance(board_log, dict) else []},
                recommendation="Verify each agent in olp_xdv_pipeline.py executed and stamped payload.",
            ))

    return findings


# ---------------------------------------------------------------------------
# VERIFICATION ANALYSIS — Cross-check verified vs produced, settlement accuracy
# ---------------------------------------------------------------------------

def run_verification_analysis(target_date: str) -> list[AnalysisResult]:
    """Cross-check verification results against produced bets."""
    findings: list[AnalysisResult] = []

    # Load yesterday's produced bet and today's settlement
    yesterday = (date.fromisoformat(target_date) - timedelta(days=1)).isoformat()

    produced_yesterday = load_produced_bet_record(yesterday)
    if not produced_yesterday:
        findings.append(AnalysisResult(
            category="verification",
            severity="info",
            title="No Produced Bet to Verify",
            description=f"No produced bet for {yesterday} — nothing to verify.",
            evidence={"date": yesterday},
            recommendation="No action needed.",
        ))
        return findings

    # Get verification status from booking tracker
    booking_yesterday = load_booking_tracker(yesterday)

    # Compare produced bet legs with booking tracker settlement
    produced_legs = produced_yesterday.get("legs", [])
    booking_legs = []
    for acca in booking_yesterday.get("accas", []):
        booking_legs.extend(acca.get("legs", []))

    # Check for legs that were produced but not settled
    pending_produced = [l for l in produced_legs if not l.get("settled", False)]
    pending_booking = [l for l in booking_legs if l.get("status") == "PENDING"]

    if pending_produced:
        findings.append(AnalysisResult(
            category="verification",
            severity="warning",
            title=f"{len(pending_produced)} Produced Legs Still Pending Settlement",
            description="Legs from yesterday's produced bet have not been settled yet.",
            evidence={
                "produced_pending": len(pending_produced),
                "booking_pending": len(pending_booking),
                "date": yesterday,
            },
            recommendation="Run booking_tracker.settle() for yesterday. Check football-data.co.uk results availability.",
        ))

    # Check for settlement mismatches
    settled_produced = [l for l in produced_legs if l.get("settled", False)]
    settled_booking = [l for l in booking_legs if l.get("status") in ["WIN", "LOSS"]]

    # Build lookup for comparison
    booking_by_key = {_leg_key(l): l for l in booking_legs}
    for leg in settled_produced:
        key = _leg_key(leg)
        if key in booking_by_key:
            booking_leg = booking_by_key[key]
            produced_hit = leg.get("hit")
            booking_hit = booking_leg.get("hit") or (booking_leg.get("status") == "WIN")
            if produced_hit != booking_hit:
                findings.append(AnalysisResult(
                    category="verification",
                    severity="critical",
                    title="Settlement Mismatch Detected",
                    description=f"Produced bet and booking tracker disagree on leg outcome for {leg.get('fixture')}.",
                    evidence={
                        "fixture": leg.get("fixture"),
                        "produced_hit": produced_hit,
                        "booking_status": booking_leg.get("status"),
                        "booking_hit": booking_hit,
                    },
                    recommendation="Investigate settlement logic divergence. Check engine.markets.settle() vs booking tracker.",
                ))

    # Check CLV capture completeness
    clv_log = load_clv_log()
    legs_with_clv = [l for l in clv_log.legs if l.clv_pct is not None and l.phase == PAPER_PHASE]
    legs_without_clv = [l for l in clv_log.legs if l.clv_pct is None and l.phase == PAPER_PHASE]

    if legs_without_clv:
        findings.append(AnalysisResult(
            category="verification",
            severity="warning",
            title=f"{len(legs_without_clv)} Phase 2 Legs Missing CLV",
            description="Legs have been settled but closing line not captured (CL-ARCHIVE).",
            evidence={
                "legs_with_clv": len(legs_with_clv),
                "legs_without_clv": len(legs_without_clv),
                "clv_capture_rate": f"{len(legs_with_clv)/max(1,len(legs_with_clv)+len(legs_without_clv))*100:.1f}%",
            },
            recommendation="Run clv_logger.grade_all_pending() to capture CL-ARCHIVE closes. Check Data Steward schedule.",
        ))

    # Phase 3 gate status
    gate_status = load_gate_status()
    if not gate_status.get("gate_met", False):
        findings.append(AnalysisResult(
            category="verification",
            severity="info",
            title="Phase 3 Gate Not Met",
            description=f"CLV gate: {gate_status.get('legs_with_clv', 0)}/{PHASE3_GATE_MIN_LEGS} legs, mean CLV {gate_status.get('mean_clv_pct', 0):.3f}%.",
            evidence=gate_status,
            recommendation="Continue paper phase. Accumulate more settled legs with positive CLV.",
        ))
    else:
        findings.append(AnalysisResult(
            category="verification",
            severity="info",
            title="Phase 3 Gate MET — Awaiting Architect Sign-off",
            description="CLV gate requirements satisfied. Capital deployment requires ARCHITECT_SIGNOFF.",
            evidence=gate_status,
            recommendation="Architect must explicitly approve capital deployment via ARCHITECT_SIGNOFF=1.",
        ))

    return findings


def _leg_key(leg: dict) -> str:
    """Stable key for leg matching."""
    return "|".join([
        leg.get("fixture", leg.get("label", "")).strip(),
        leg.get("market_key", leg.get("pick_market", "")).strip(),
        leg.get("pick", "").strip(),
    ])


# ---------------------------------------------------------------------------
# PERFORMANCE INSIGHT — Market/band/variant performance, CLV drift, calibration
# ---------------------------------------------------------------------------

def run_performance_analysis(target_date: str) -> list[AnalysisResult]:
    """Analyze market, odds band, and variant performance."""
    findings: list[AnalysisResult] = []

    clv_log = load_clv_log()
    variant_status = load_variant_population()

    # 1. CLV Performance by Market
    legs_with_clv = [l for l in clv_log.legs if l.clv_pct is not None and l.phase == PAPER_PHASE]
    if legs_with_clv:
        by_market = defaultdict(list)
        for leg in legs_with_clv:
            by_market[leg.market].append(leg.clv_pct)

        for market, clvs in by_market.items():
            mean_clv = sum(clvs) / len(clvs)
            if mean_clv < -2.0 and len(clvs) >= 5:
                findings.append(AnalysisResult(
                    category="performance",
                    severity="warning",
                    title=f"Negative CLV Drift: {market}",
                    description=f"Market {market} shows mean CLV of {mean_clv:.2f}% across {len(clvs)} legs — consistently getting worse prices than close.",
                    evidence={"market": market, "mean_clv_pct": mean_clv, "n_legs": len(clvs)},
                    recommendation="Review model probability calibration for this market. Check odds source freshness.",
                ))
            elif mean_clv > 2.0 and len(clvs) >= 5:
                findings.append(AnalysisResult(
                    category="performance",
                    severity="info",
                    title=f"Positive CLV: {market}",
                    description=f"Market {market} beating the close by {mean_clv:.2f}% on average ({len(clvs)} legs).",
                    evidence={"market": market, "mean_clv_pct": mean_clv, "n_legs": len(clvs)},
                    recommendation="Strong signal — consider increasing allocation to this market type.",
                ))

    # 2. CLV Performance by League
    by_league = defaultdict(list)
    for leg in legs_with_clv:
        by_league[leg.league].append(leg.clv_pct)

    for league, clvs in by_league.items():
        mean_clv = sum(clvs) / len(clvs)
        if mean_clv < -3.0 and len(clvs) >= 3:
            findings.append(AnalysisResult(
                category="performance",
                severity="warning",
                title=f"League Underperforming: {league}",
                description=f"League {league} mean CLV {mean_clv:.2f}% — market consistently sharper than model.",
                evidence={"league": league, "mean_clv_pct": mean_clv, "n_legs": len(clvs)},
                recommendation="Consider league-specific recalibration or exclusion from production.",
            ))

    # 3. Variant Population Performance
    summary = variant_status.get("summary", {})
    variants = variant_status.get("variants", [])

    if variants:
        # Best/worst performing variants
        alive_variants = [v for v in variants if v.get("status") == "alive"]
        if alive_variants:
            best = max(alive_variants, key=lambda v: v.get("fitness", 0))
            worst = min(alive_variants, key=lambda v: v.get("fitness", 0))

            findings.append(AnalysisResult(
                category="performance",
                severity="info",
                title=f"Best Variant: {best.get('variantId')}",
                description=f"Fitness: {best.get('fitness', 0):.3f}, Odds Band: {best.get('oddsBand')}, "
                           f"Wins: {best.get('wins', 0)}, Losses: {best.get('losses', 0)}",
                evidence={"variant": best},
                recommendation="Candidate for replication if fitness sustained.",
            ))

            if worst.get("fitness", 0) < 0.3:
                findings.append(AnalysisResult(
                    category="performance",
                    severity="warning",
                    title=f"Worst Variant: {worst.get('variantId')}",
                    description=f"Fitness: {worst.get('fitness', 0):.3f} — candidate for culling.",
                    evidence={"variant": worst},
                    recommendation="Trigger cull if shouldCull() returns true. Reallocate compute to better variants.",
                ))

    # 4. Survival Tier Analysis
    survival_tier = compute_survival_tier_from_variants(summary)
    tier_emoji = {"normal": "🟢", "low_compute": "🟡", "critical": "🟠", "dead": "🔴"}[survival_tier]

    findings.append(AnalysisResult(
        category="performance",
        severity="info" if survival_tier == "normal" else "warning" if survival_tier == "low_compute" else "critical",
        title=f"Survival Tier: {tier_emoji} {survival_tier.upper()}",
        description=f"Mean fitness: {summary.get('meanFitness', 0):.3f}, "
                   f"Alive: {summary.get('aliveVariants', 0)}/{summary.get('totalVariants', 0)}",
        evidence={
            "tier": survival_tier,
            "mean_fitness": summary.get("meanFitness", 0),
            "alive_variants": summary.get("aliveVariants", 0),
            "total_variants": summary.get("totalVariants", 0),
        },
        recommendation=_tier_recommendation(survival_tier, summary),
    ))

    # 5. Replication/Cull Signals
    if shouldReplicate(summary):
        findings.append(AnalysisResult(
            category="performance",
            severity="info",
            title="Replication Signal Active",
            description="Conditions met for variant replication: mean fitness > 0.55, ≥3 alive, population < 20.",
            evidence=summary,
            recommendation="Spawn new variants from best performers. Use variant_selection.add_variant().",
        ))

    if shouldCull(summary):
        findings.append(AnalysisResult(
            category="performance",
            severity="warning",
            title="Cull Signal Active",
            description="Conditions met for culling: mean fitness < 0.45, >5 variants, ≥2 deaths this window.",
            evidence=summary,
            recommendation="Cull worst-performing variants. Update status to 'dead' via variant_selection.update_variant_status().",
        ))

    # 6. Calibration Check (hit rate vs model probability)
    settled_legs = [l for l in clv_log.legs if l.hit is not None and l.phase == PAPER_PHASE]
    if len(settled_legs) >= 20:
        by_market_cal = defaultdict(lambda: {"hits": 0, "total": 0, "model_prob_sum": 0.0})
        for leg in settled_legs:
            m = by_market_cal[leg.market]
            m["total"] += 1
            m["model_prob_sum"] += leg.model_prob
            if leg.hit:
                m["hits"] += 1

        for market, data in by_market_cal.items():
            if data["total"] >= 10:
                hit_rate = data["hits"] / data["total"]
                avg_model_prob = data["model_prob_sum"] / data["total"]
                calibration_gap = hit_rate - avg_model_prob

                if abs(calibration_gap) > 0.1:
                    severity = "warning" if calibration_gap < 0 else "info"
                    findings.append(AnalysisResult(
                        category="performance",
                        severity=severity,
                        title=f"Calibration {'Gap' if calibration_gap < 0 else 'Surplus'}: {market}",
                        description=f"Hit rate {hit_rate:.1%} vs model prob {avg_model_prob:.1%} "
                                   f"({'under' if calibration_gap < 0 else 'over'}-confident by {abs(calibration_gap):.1%}).",
                        evidence={
                            "market": market,
                            "hit_rate": hit_rate,
                            "avg_model_prob": avg_model_prob,
                            "calibration_gap": calibration_gap,
                            "n_legs": data["total"],
                        },
                        recommendation="Consider Platt scaling or flat nudge recalibration for this market." if calibration_gap < 0 else "Model well-calibrated or slightly conservative.",
                    ))

    return findings


def _tier_recommendation(tier: str, summary: dict) -> str:
    if tier == "normal":
        return "Population healthy. Maintain current compute allocation."
    elif tier == "low_compute":
        return "Near breakeven. Monitor closely. Consider replication if fitness improves."
    elif tier == "critical":
        return "Losing population. Cull worst variants, reduce compute, investigate model drift."
    else:  # dead
        return "Population extinct. Re-seed from config or best historical variants."


# ---------------------------------------------------------------------------
# MOTIVATION LOGIC — Fitness-based selection pressure for variant evolution
# ---------------------------------------------------------------------------

"""
MOTIVATION LOGIC DEFINITION
============================

The "motivation logic" is a fitness-based selection pressure mechanism that drives
the variant population's evolution based on SETTLED OUTCOMES (not paper predictions).

Core principle: Variants that produce winning legs with positive CLV should:
1. REPLICATE — spawn new variants with similar characteristics (odds band, market type)
2. RECEIVE MORE COMPUTE — higher survival tier = more inference budget
3. INFLUENCE CONSENSUS — higher weight in ensemble consensus

Variants that produce losing legs with negative CLV should:
1. BE CULLED — marked dead, removed from active population
2. LOSE COMPUTE — lower survival tier = restricted inference budget
3. LOSE CONSENSUS WEIGHT — lower weight in ensemble

This creates an evolutionary pressure where the population naturally adapts to
markets/leagues/bands where the model has genuine edge, as measured by CLV.

The motivation logic operates on SETTLED legs only (paper or capital) with
logged CLV — never on paper predictions alone.
"""

@dataclass
class MotivationSignal:
    """A motivation signal for a specific variant."""
    variant_id: str
    signal_type: str  # "replicate" | "cull" | "promote" | "demote" | "maintain"
    strength: float   # 0.0 to 1.0
    reason: str
    evidence: dict
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


def compute_motivation_signals() -> list[MotivationSignal]:
    """
    Compute motivation signals for all variants based on SETTLED outcomes with CLV.

    This is the core MOTIVATION LOGIC — it reads the variant ledger and CLV log,
    matches variants to their settled legs, and emits signals that drive:
    - Replication (spawn new variants)
    - Culling (mark variants dead)
    - Survival tier transitions (compute allocation)
    - Ensemble weight adjustments (consensus influence)
    """
    signals: list[MotivationSignal] = []

    # Load data sources
    variant_ledger = load_variant_ledger()
    clv_log = load_clv_log()

    # Get settled legs with CLV (the ground truth)
    settled_legs = [l for l in clv_log.legs
                    if l.hit is not None
                    and l.clv_pct is not None
                    and l.phase == PAPER_PHASE]

    if not settled_legs:
        # No settled evidence yet — emit maintenance signals
        for variant in variant_ledger:
            if variant.get("status") == "alive":
                signals.append(MotivationSignal(
                    variant_id=variant.get("variant_id", "unknown"),
                    signal_type="maintain",
                    strength=0.5,
                    reason="No settled CLV evidence yet — maintaining current state",
                    evidence={"settled_legs": 0},
                ))
        return signals

    # Group settled legs by variant (via odds_band/market mapping)
    # Since variant_ledger doesn't directly track which legs belong to which variant,
    # we infer from odds_band and market_type
    variant_performance: dict[str, dict] = defaultdict(lambda: {
        "legs": [], "wins": 0, "losses": 0, "clv_sum": 0.0, "clv_count": 0
    })

    for leg in settled_legs:
        # Find matching variant by odds_band (from variant ledger)
        # This is a simplification — in production, legs would carry variant_id
        for variant in variant_ledger:
            if variant.get("odds_band") == leg.market:  # approximate mapping
                vp = variant_performance[variant["variant_id"]]
                vp["legs"].append(leg)
                if leg.hit:
                    vp["wins"] += 1
                else:
                    vp["losses"] += 1
                vp["clv_sum"] += leg.clv_pct
                vp["clv_count"] += 1
                break

    # Generate signals per variant
    for variant in variant_ledger:
        vid = variant.get("variant_id", "unknown")
        perf = variant_performance.get(vid, {"legs": [], "wins": 0, "losses": 0, "clv_sum": 0.0, "clv_count": 0})

        n_legs = len(perf["legs"])
        if n_legs == 0:
            # No direct evidence for this variant
            signals.append(MotivationSignal(
                variant_id=vid,
                signal_type="maintain",
                strength=0.3,
                reason="No settled legs attributed to this variant",
                evidence={"attributed_legs": 0, "variant_fitness": variant.get("fitness", 0)},
            ))
            continue

        win_rate = perf["wins"] / n_legs
        mean_clv = perf["clv_sum"] / perf["clv_count"] if perf["clv_count"] > 0 else 0.0
        current_fitness = variant.get("fitness", 0.0)

        # MOTIVATION LOGIC RULES:

        # 1. STRONG POSITIVE: High win rate + positive CLV → REPLICATE
        if win_rate >= 0.6 and mean_clv > 1.0 and n_legs >= 5:
            signals.append(MotivationSignal(
                variant_id=vid,
                signal_type="replicate",
                strength=min(1.0, (win_rate - 0.5) + (mean_clv / 10.0)),
                reason=f"Strong performer: {win_rate:.1%} win rate, {mean_clv:.1f}% mean CLV over {n_legs} legs",
                evidence={
                    "win_rate": win_rate,
                    "mean_clv_pct": mean_clv,
                    "n_legs": n_legs,
                    "current_fitness": current_fitness,
                },
            ))

        # 2. POSITIVE CLV but moderate win rate → PROMOTE (increase fitness)
        elif mean_clv > 0.5 and n_legs >= 3:
            signals.append(MotivationSignal(
                variant_id=vid,
                signal_type="promote",
                strength=min(1.0, mean_clv / 5.0),
                reason=f"Positive CLV ({mean_clv:.1f}%) — boosting fitness",
                evidence={
                    "win_rate": win_rate,
                    "mean_clv_pct": mean_clv,
                    "n_legs": n_legs,
                    "current_fitness": current_fitness,
                    "suggested_fitness": min(1.0, current_fitness + 0.05),
                },
            ))

        # 3. NEGATIVE CLV consistently → CULL
        elif mean_clv < -1.0 and n_legs >= 5:
            signals.append(MotivationSignal(
                variant_id=vid,
                signal_type="cull",
                strength=min(1.0, abs(mean_clv) / 10.0),
                reason=f"Consistently negative CLV ({mean_clv:.1f}%) over {n_legs} legs",
                evidence={
                    "win_rate": win_rate,
                    "mean_clv_pct": mean_clv,
                    "n_legs": n_legs,
                    "current_fitness": current_fitness,
                },
            ))

        # 4. LOW WIN RATE + negative/neutral CLV → DEMOTE
        elif win_rate < 0.4 and mean_clv <= 0 and n_legs >= 5:
            signals.append(MotivationSignal(
                variant_id=vid,
                signal_type="demote",
                strength=min(1.0, (0.4 - win_rate) + abs(mean_clv) / 10.0),
                reason=f"Poor win rate ({win_rate:.1%}) with non-positive CLV ({mean_clv:.1f}%)",
                evidence={
                    "win_rate": win_rate,
                    "mean_clv_pct": mean_clv,
                    "n_legs": n_legs,
                    "current_fitness": current_fitness,
                    "suggested_fitness": max(0.0, current_fitness - 0.05),
                },
            ))

        # 5. INSUFFICIENT EVIDENCE → MAINTAIN
        else:
            signals.append(MotivationSignal(
                variant_id=vid,
                signal_type="maintain",
                strength=0.5,
                reason=f"Insufficient evidence for strong signal: {n_legs} legs, WR={win_rate:.1%}, CLV={mean_clv:.1f}%",
                evidence={
                    "win_rate": win_rate,
                    "mean_clv_pct": mean_clv,
                    "n_legs": n_legs,
                    "current_fitness": current_fitness,
                },
            ))

    return signals


def apply_motivation_signals(signals: list[MotivationSignal]) -> dict:
    """
    Apply motivation signals to the variant population.

    Returns summary of actions taken.
    """
    actions = {
        "replicated": [],
        "culled": [],
        "promoted": [],
        "demoted": [],
        "maintained": [],
        "errors": [],
    }

    for signal in signals:
        try:
            if signal.signal_type == "replicate" and signal.strength > 0.7:
                # Spawn new variant from this one
                variant_ledger = load_variant_ledger()
                source = next((v for v in variant_ledger if v.get("variant_id") == signal.variant_id), None)
                if source:
                    new_id = f"{source['variant_id']}_rep_{datetime.now().strftime('%m%d%H%M')}"
                    # Add with slightly mutated odds band or same
                    from variant_selection import add_variant
                    success = add_variant(
                        variant_id=new_id,
                        variant_type=source.get("variant_type", "league_based"),
                        odds_band=source.get("odds_band", ""),
                        fitness=source.get("fitness", 0.5) * 0.9  # Slight fitness penalty for new variant
                    )
                    if success:
                        actions["replicated"].append({"from": signal.variant_id, "new": new_id})

            elif signal.signal_type == "cull" and signal.strength > 0.6:
                from variant_selection import update_variant_status
                success = update_variant_status(signal.variant_id, "dead")
                if success:
                    actions["culled"].append(signal.variant_id)

            elif signal.signal_type == "promote":
                from variant_selection import update_variant_status
                new_fitness = signal.evidence.get("suggested_fitness", signal.evidence.get("current_fitness", 0.5))
                success = update_variant_status(signal.variant_id, "alive", fitness=new_fitness)
                if success:
                    actions["promoted"].append({"variant": signal.variant_id, "new_fitness": new_fitness})

            elif signal.signal_type == "demote":
                from variant_selection import update_variant_status
                new_fitness = signal.evidence.get("suggested_fitness", signal.evidence.get("current_fitness", 0.5))
                success = update_variant_status(signal.variant_id, "alive", fitness=new_fitness)
                if success:
                    actions["demoted"].append({"variant": signal.variant_id, "new_fitness": new_fitness})

            else:
                actions["maintained"].append(signal.variant_id)

        except Exception as e:
            actions["errors"].append({"variant": signal.variant_id, "error": str(e)})

    return actions


def run_motivation_analysis(target_date: str) -> list[AnalysisResult]:
    """Run motivation logic and return analysis findings."""
    findings: list[AnalysisResult] = []

    signals = compute_motivation_signals()

    # Summarize signals by type
    by_type = defaultdict(list)
    for s in signals:
        by_type[s.signal_type].append(s)

    # Report replication signals
    for s in by_type.get("replicate", []):
        findings.append(AnalysisResult(
            category="motivation",
            severity="info",
            title=f"REPLICATION SIGNAL: {s.variant_id}",
            description=s.reason,
            evidence=s.evidence,
            recommendation=f"Spawn new variant from {s.variant_id}. Strength: {s.strength:.2f}",
        ))

    # Report cull signals
    for s in by_type.get("cull", []):
        findings.append(AnalysisResult(
            category="motivation",
            severity="warning",
            title=f"CULL SIGNAL: {s.variant_id}",
            description=s.reason,
            evidence=s.evidence,
            recommendation=f"Mark variant dead. Strength: {s.strength:.2f}",
        ))

    # Report promote signals
    for s in by_type.get("promote", []):
        findings.append(AnalysisResult(
            category="motivation",
            severity="info",
            title=f"PROMOTE SIGNAL: {s.variant_id}",
            description=s.reason,
            evidence=s.evidence,
            recommendation=f"Increase fitness to {s.evidence.get('suggested_fitness', 'N/A')}. Strength: {s.strength:.2f}",
        ))

    # Report demote signals
    for s in by_type.get("demote", []):
        findings.append(AnalysisResult(
            category="motivation",
            severity="warning",
            title=f"DEMOTE SIGNAL: {s.variant_id}",
            description=s.reason,
            evidence=s.evidence,
            recommendation=f"Decrease fitness to {s.evidence.get('suggested_fitness', 'N/A')}. Strength: {s.strength:.2f}",
        ))

    # Summary signal
    if signals:
        replicate_count = len(by_type.get("replicate", []))
        cull_count = len(by_type.get("cull", []))
        promote_count = len(by_type.get("promote", []))
        demote_count = len(by_type.get("demote", []))

        findings.append(AnalysisResult(
            category="motivation",
            severity="info",
            title="Motivation Logic Summary",
            description=f"Signals: {replicate_count} replicate, {cull_count} cull, "
                       f"{promote_count} promote, {demote_count} demote, "
                       f"{len(by_type.get('maintain', []))} maintain",
            evidence={
                "replicate": replicate_count,
                "cull": cull_count,
                "promote": promote_count,
                "demote": demote_count,
                "maintain": len(by_type.get("maintain", [])),
                "total_variants": len(signals),
            },
            recommendation="Review and apply signals via apply_motivation_signals() if approved.",
        ))

    return findings


# ---------------------------------------------------------------------------
# MAIN ORCHESTRATION
# ---------------------------------------------------------------------------

def run_daily_analysis(target_date: Optional[str] = None, apply_motivation: bool = False) -> DailyAnalysisReport:
    """Run complete daily analysis for a given date."""
    if target_date is None:
        target_date = date.today().isoformat()

    print(f"[DAILY ANALYSIS] Running for {target_date}...")

    # Run all three analysis types
    print("  → Functional analysis...")
    functional = run_functional_analysis(target_date)

    print("  → Verification analysis...")
    verification = run_verification_analysis(target_date)

    print("  → Performance insight...")
    performance = run_performance_analysis(target_date)

    print("  → Motivation logic...")
    motivation = run_motivation_analysis(target_date)

    # Apply motivation signals if requested
    motivation_actions = {}
    if apply_motivation:
        print("  → Applying motivation signals...")
        signals = compute_motivation_signals()
        motivation_actions = apply_motivation_signals(signals)

    # Build summary
    summary = {
        "date": target_date,
        "functional_findings": len(functional),
        "verification_findings": len(verification),
        "performance_findings": len(performance),
        "motivation_signals": len(motivation),
        "critical_count": sum(1 for f in functional + verification + performance + motivation if f.severity == "critical"),
        "warning_count": sum(1 for f in functional + verification + performance + motivation if f.severity == "warning"),
        "info_count": sum(1 for f in functional + verification + performance + motivation if f.severity == "info"),
        "motivation_actions": motivation_actions,
    }

    report = DailyAnalysisReport(
        date=target_date,
        analysis_timestamp=datetime.now().isoformat(),
        functional=functional,
        verification=verification,
        performance=performance,
        motivation=motivation,
        summary=summary,
    )

    return report


def save_analysis_report(report: DailyAnalysisReport, output_dir: Optional[Path] = None) -> Path:
    """Save analysis report to JSON and Markdown."""
    if output_dir is None:
        output_dir = REPO_ROOT / "output" / "analysis"
    output_dir.mkdir(parents=True, exist_ok=True)

    date_str = report.date
    json_path = output_dir / f"analysis_{date_str}.json"
    md_path = output_dir / f"analysis_{date_str}.md"

    # Save JSON
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)

    # Save Markdown
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(report.to_markdown())

    print(f"[DAILY ANALYSIS] Report saved to {json_path} and {md_path}")
    return json_path


# Exit with error code if critical findings
    if report and report.summary.get("critical_count", 0) > 0:
        sys.exit(1)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="OLP XDV Daily Analysis Agent")
    parser.add_argument("--date", help="Target date (YYYY-MM-DD), defaults to today")
    parser.add_argument("--apply-motivation", action="store_true",
                        help="Apply motivation signals to variant population")
    parser.add_argument("--output-dir", help="Output directory for reports")
    parser.add_argument("--json-only", action="store_true", help="Only output JSON to stdout")
    parser.add_argument("--compute-motivation", action="store_true",
                        help="Only compute and output motivation signals (JSON), used by bridge")
    parser.add_argument("--signals", help="Pass signals JSON for apply-motivation bridge usage")

    args = parser.parse_args()

    target_date = args.date or date.today().isoformat()
    output_dir = Path(args.output_dir) if args.output_dir else None

    # Bridge mode: compute motivation signals only
    if args.compute_motivation:
        signals = compute_motivation_signals()
        output = {
            "signals": [
                {
                    "variantId": s.variant_id,
                    "signalType": s.signal_type,
                    "strength": s.strength,
                    "reason": s.reason,
                    "evidence": s.evidence,
                    "timestamp": s.timestamp,
                }
                for s in signals
            ],
            "count": len(signals),
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))
        sys.exit(0)

    # Bridge mode: apply motivation signals from passed JSON
    if args.signals:
        try:
            import_sigs = json.loads(args.signals)
            signals = [
                MotivationSignal(
                    variant_id=s.get("variantId", s.get("variant_id", "unknown")),
                    signal_type=s.get("signalType", s.get("signal_type", "maintain")),
                    strength=s.get("strength", 0.5),
                    reason=s.get("reason", ""),
                    evidence=s.get("evidence", {}),
                    timestamp=s.get("timestamp", datetime.now().isoformat()),
                )
                for s in import_sigs
            ]
            actions = apply_motivation_signals(signals)
            print(json.dumps({"actions": actions}, indent=2, ensure_ascii=False))
            sys.exit(0)
        except Exception as e:
            print(json.dumps({"error": str(e)}, indent=2))
            sys.exit(1)

    # Full report mode
    report = run_daily_analysis(target_date, apply_motivation=args.apply_motivation)

    if args.json_only:
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    else:
        save_analysis_report(report, output_dir)
        print(report.to_markdown())

    # Exit with error code if critical findings
    if report.summary.get("critical_count", 0) > 0:
        sys.exit(1)