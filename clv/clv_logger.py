"""
HR46 — CLV Log on Lock.
A closing line must be captured and logged for every capital/paper leg.
Three capture paths: CL-LIVE (session running), CL-ARCHIVE (odds archive),
CL-PM (Polymarket, shelved).

This is the ONLY instrument that separates a real edge from a good run
(Section 13 of the master doc). Phase 3 is gated on >=30 Phase 2 legs with
logged CLV + positive mean CLV + Architect (V7) sign-off.
"""
from __future__ import annotations
import csv
import json
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import PAPER_PHASE, assert_paper_only  # noqa: E402

PHASE3_GATE_MIN_LEGS = 30

# The phase prefix backtest legs carry. Defined HERE, next to the gate that
# excludes it, rather than as a magic string in a distant module — so anyone
# reading the Phase 3 gate can see what is and isn't counted toward it.
BACKTEST_PHASE = "backtest"

# Default on-disk location. Was a POSIX absolute path ("/home/claude/...")
# which on Windows silently resolves to C:\home\claude\... — surprising, and
# it put the capital-gate ledger outside the project.
DEFAULT_LOG_PATH = Path(__file__).parent / "clv_log.json"


@dataclass
class LoggedLeg:
    leg_id: str
    date_logged: str
    league: str
    fixture: str  # "Home v Away"
    market: str   # e.g. "O1.5", "BTTS Yes", "1X2 Home"
    model_prob: float
    # KICKOFF date of the match this leg is on (ISO), as distinct from
    # date_logged. Without it, grading matched a leg only on (home, away) — and
    # since the same pairing recurs every season, a leg on a FUTURE fixture was
    # settled against LAST season's meeting of the same two clubs, inventing
    # both a result and a closing price. Appended per HR48; legs written before
    # this field existed carry None and are refused for grading.
    match_date: Optional[str] = None
    entry_odds: Optional[float] = None       # price taken at pick time (paper or capital)
    entry_capture_path: str = "CL-LIVE"      # CL-LIVE / CL-ARCHIVE / CL-PM
    closing_odds: Optional[float] = None
    closing_capture_path: Optional[str] = None
    clv_pct: Optional[float] = None          # (entry_implied_prob... see clv formula below
    # Publish-time snapshot of what the MODEL claimed, frozen at log_entry and
    # NEVER rewritten by a later refit (HR "every code kept and graded"). The
    # price (entry_odds) and model_prob were already frozen; these two derive
    # the modelled fair price and value edge AT PUBLISH so the claim is stored
    # as a fact, not recomputed from a model that may have moved on. Old legs
    # written before this field carry None.
    entry_fair_odds: Optional[float] = None   # modelled fair price = 1/model_prob at publish
    entry_edge_pct: Optional[float] = None    # value edge claimed = (model_prob*entry_odds-1)*100
    # The same value edge measured against the CLOSING price. entry_edge_pct
    # minus this is how much of the published edge the market erased by close —
    # grading the claim's movement, alongside clv_pct which grades the price.
    closing_edge_pct: Optional[float] = None
    ft_result: Optional[str] = None
    hit: Optional[bool] = None
    stake: Optional[float] = None            # None for Phase 2 paper legs
    phase: str = "phase2_paper"
    notes: str = ""


def implied_prob(decimal_odds: float) -> float:
    return 1.0 / decimal_odds


def fair_odds(model_prob: float) -> Optional[float]:
    """The price the model thinks is fair = 1 / model_prob. None for a
    non-positive probability (nothing to freeze rather than a bogus number)."""
    if not model_prob or model_prob <= 0:
        return None
    return round(1.0 / model_prob, 4)


def value_edge_pct(model_prob: float, decimal_odds: float) -> Optional[float]:
    """The value edge of a price given the model's probability:

        edge% = (model_prob * decimal_odds - 1) * 100

    Positive means the price pays more than the model's fair odds. This is the
    SAME number the board shows as the pick's edge; freezing it at publish is
    what makes the claim gradeable later. None when either input is missing."""
    if not model_prob or model_prob <= 0 or not decimal_odds:
        return None
    return round((model_prob * decimal_odds - 1.0) * 100, 3)


def compute_clv(entry_odds: float, closing_odds: float) -> float:
    """CLV as % edge vs the closing line. POSITIVE means you beat the close.

        CLV% = (entry_odds / closing_odds - 1) * 100

    You beat the close when you took a LONGER price than the market settled
    on: entry 2.10 into a 2.00 close is +5.0%. Entry 2.00 into a 2.10 close is
    -4.8% — the market moved away from you.

    SIGN CORRECTION (2026-08-03): this previously computed
    (closing/entry - 1)*100, which returned NEGATIVE for a leg that beat the
    close while its own docstring claimed positive meant beating it. Because
    phase2_status() gates Phase 3 on `mean_clv > 0`, the effect was that a
    framework consistently beating the closing line could never open the
    capital gate, while one consistently getting worse prices would. Fixed to
    the standard convention with the Architect's approval.
    """
    return round((entry_odds / closing_odds - 1) * 100, 3)


class CLVLog:
    def __init__(self, path: str | Path | None = None):
        # DEFAULT_LOG_PATH is read at call time so a dry run can point it at a
        # scratch copy (run_daily._dry_run_sandbox).
        self.path = Path(path) if path is not None else DEFAULT_LOG_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.legs: list[LoggedLeg] = self._load()

    def _load(self) -> list[LoggedLeg]:
        if not self.path.exists():
            return []
        with open(self.path) as f:
            raw = json.load(f)
        return [LoggedLeg(**r) for r in raw]

    def _save(self) -> None:
        with open(self.path, "w") as f:
            json.dump([asdict(l) for l in self.legs], f, indent=2)

    def log_entry(self, league: str, fixture: str, market: str, model_prob: float,
                  entry_odds: Optional[float], entry_capture_path: str = "CL-LIVE",
                  phase: str = "phase2_paper", stake: Optional[float] = None,
                  match_date: Optional[str] = None) -> LoggedLeg:
        """Record a pick at pick-time. HR46: entry_odds should be captured NOW,
        not reconstructed later — if it's unavailable, pass None and it will
        show as NO DATA — PENDING on the board, never backfilled with a guess."""
        # Capital bright line, enforced on the WRITE PATH rather than in
        # commentary: below Phase 3 a stake cannot reach disk at all.
        assert_paper_only(stake, phase)
        leg = LoggedLeg(
            leg_id=f"{fixture.replace(' ', '_')}_{market.replace(' ', '_')}_{datetime.now(timezone.utc).timestamp():.0f}",
            date_logged=datetime.now(timezone.utc).isoformat(),
            league=league, fixture=fixture, market=market,
            model_prob=model_prob, entry_odds=entry_odds,
            entry_capture_path=entry_capture_path, phase=phase, stake=stake,
            match_date=match_date,
            # Freeze the modelled claim NOW. entry_odds may be None (HR46: no
            # backfilled guess), in which case the edge stays None but the fair
            # price is still recorded from model_prob alone.
            entry_fair_odds=fair_odds(model_prob),
            entry_edge_pct=(value_edge_pct(model_prob, entry_odds)
                            if entry_odds else None),
        )
        self.legs.append(leg)
        self._save()
        return leg

    def log_close(self, leg_id: str, closing_odds: float,
                  closing_capture_path: str = "CL-ARCHIVE") -> LoggedLeg:
        for leg in self.legs:
            if leg.leg_id == leg_id:
                leg.closing_odds = closing_odds
                leg.closing_capture_path = closing_capture_path
                if leg.entry_odds:
                    leg.clv_pct = compute_clv(leg.entry_odds, closing_odds)
                # The model's edge measured against the close. entry_edge_pct
                # minus this is the edge the market erased by close — the claim's
                # movement, not just the price's (clv_pct). model_prob is frozen,
                # so this grades the ORIGINAL claim, never a re-modelled one.
                leg.closing_edge_pct = value_edge_pct(leg.model_prob, closing_odds)
                self._save()
                return leg
        raise KeyError(f"No leg with id {leg_id}")

    def log_batch(self, legs: list[LoggedLeg]) -> int:
        """Append many pre-built legs with a SINGLE disk write.

        log_entry/log_close each call _save(), rewriting the whole JSON — fine
        for one pick at a time, O(n^2) across the thousands of legs a backtest
        produces. Returns the number appended."""
        for leg in legs:
            assert_paper_only(leg.stake, leg.phase)
        self.legs.extend(legs)
        self._save()
        return len(legs)

    def log_result(self, leg_id: str, ft_result: str, hit: bool) -> LoggedLeg:
        for leg in self.legs:
            if leg.leg_id == leg_id:
                leg.ft_result = ft_result
                leg.hit = hit
                self._save()
                return leg
        raise KeyError(f"No leg with id {leg_id}")

    def phase2_status(self) -> dict:
        """Reports honestly against the Phase 3 gate — never rounds up."""
        # Exact match on PAPER_PHASE is what keeps backtest legs (phase
        # "backtest_<run_id>") out of the capital gate.
        legs_with_clv = [l for l in self.legs
                          if l.phase == PAPER_PHASE and l.clv_pct is not None]
        n = len(legs_with_clv)
        mean_clv = round(sum(l.clv_pct for l in legs_with_clv) / n, 3) if n else None
        gate_met = n >= PHASE3_GATE_MIN_LEGS and (mean_clv or 0) > 0
        # Published-edge accounting over the SAME graded legs: what the model
        # claimed at publish (entry_edge_pct), what survived to the close
        # (closing_edge_pct), and the mean decay between them. Lets the record
        # show "we claimed +X%, the market left +Y%" beside the price CLV.
        entry_edges = [l.entry_edge_pct for l in legs_with_clv
                       if l.entry_edge_pct is not None]
        mean_entry_edge = (round(sum(entry_edges) / len(entry_edges), 3)
                           if entry_edges else None)
        decays = [l.entry_edge_pct - l.closing_edge_pct for l in legs_with_clv
                  if l.entry_edge_pct is not None and l.closing_edge_pct is not None]
        mean_edge_decay = round(sum(decays) / len(decays), 3) if decays else None
        return {
            "legs_logged_total": len(self.legs),
            "legs_with_clv": n,
            "gate_requirement": PHASE3_GATE_MIN_LEGS,
            "mean_clv_pct": mean_clv,
            "positive_mean_clv": (mean_clv or 0) > 0,
            "mean_entry_edge_pct": mean_entry_edge,
            "mean_edge_decay_pct": mean_edge_decay,
            "gate_met_pending_architect_signoff": gate_met,
            "note": "CLV logged: ZERO" if n == 0 else f"{n} legs with logged CLV",
        }

    def export_csv(self, path: str) -> None:
        with open(path, "w", newline="") as f:
            if not self.legs:
                return
            writer = csv.DictWriter(f, fieldnames=list(asdict(self.legs[0]).keys()))
            writer.writeheader()
            for leg in self.legs:
                writer.writerow(asdict(leg))
