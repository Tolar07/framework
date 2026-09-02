"""
HEARTBEAT LINEAGE — Architect 2026-08-29 survival/reproduction model.

The heartbeat is modelled as a LIFEFORM under selection pressure, not a flat
daily bet. The Architect's concept:

  - A heartbeat carries a single lineage. Its lifeforce is its bankroll.
  - WIN  -> the lineage REPRODUCES: it spawns up to TWO offspring heartbeats
            the next day (the species branches). Capital compounds.
  - LOSS -> the lineage goes EXTINCT. That branch terminates; its capital is lost.
  - PRESSURE FORCES QUALITY: because death is real (paper-mode, virtual capital),
    the selector must take the highest-edge fixture available or the lineage dies
    off. The survival pressure IS the training signal.

This module manages the lineage population:
  - selection of the day's living heartbeats (from surviving + newly reproduced lineages)
  - recording results and applying the birth/death transition
  - a starvation floor so the species can never fully die while the framework runs
    (the Architect keeps the experiment alive even after a wipeout)

Paper-mode only: no real capital is routed. All bankrolls are virtual.
"""

from __future__ import annotations

import json
import math
import random
import uuid
from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from output.heartbeat import (
    HeartbeatFixture,
    select_top_heartbeats,
    save_heartbeat_record,
    get_heartbeat_stats,
)

# Repo-rooted state files for the lineage population
REPO_ROOT = Path(__file__).parent.parent
LINEAGE_FILE = REPO_ROOT / "data" / "heartbeat" / "lineage.json"


# ----------------------------------------------------------------------------
# Configuration (Architect tuning knobs — paper-mode constants, not protected)
# ----------------------------------------------------------------------------
DEFAULT_STARTING_BANKROLL = 100.0
DEFAULT_STARTING_STAKE = 1.0
KELLY_FRACTION = 0.25          # Quarter-Kelly, inherited from heartbeat_staking
MIN_STAKE = 0.10
MAX_STAKE_PCT = 0.05
OFFSPRING_PER_WIN = 2          # WIN -> two offspring heartbeats (Architect concept)
MAX_LINEAGES = 8              # Hard cap on living lineages to stay runnable
TOP_N_CANDIDATES = 5          # Distinct high-edge fixtures to draw offspring from
STARVATION_FLOOR = 1.0        # If every lineage dies, reseed ONE at this bankroll


# ----------------------------------------------------------------------------
# Data model
# ----------------------------------------------------------------------------
@dataclass
class Lineage:
    """A single heartbeat bloodline with its own bankroll and stake."""
    lineage_id: str
    parent_id: Optional[str]
    generation: int
    bankroll: float
    current_stake: float
    wins: int
    losses: int
    alive: bool
    born_date: str
    last_result: Optional[str] = None
    fixture: Optional[str] = None       # last/current fixture this lineage holds
    pick: Optional[str] = None
    price: Optional[float] = None
    edge: float = 0.0
    probability: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Lineage":
        return cls(**d)


@dataclass
class LineagePopulation:
    """Full lineage state for the framework."""
    lineages: list[Lineage] = field(default_factory=list)
    last_bred_date: Optional[str] = None

    def living(self) -> list[Lineage]:
        return [ln for ln in self.lineages if ln.alive]

    def to_dict(self) -> dict:
        return {
            "lineages": [ln.to_dict() for ln in self.lineages],
            "last_bred_date": self.last_bred_date,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "LineagePopulation":
        return cls(
            lineages=[Lineage.from_dict(x) for x in d.get("lineages", [])],
            last_bred_date=d.get("last_bred_date"),
        )


# ----------------------------------------------------------------------------
# Persistence
# ----------------------------------------------------------------------------
def load_population() -> LineagePopulation:
    """Load lineage population from disk, or seed a genesis lineage."""
    if not LINEAGE_FILE.exists():
        genesis = Lineage(
            lineage_id=_new_id(),
            parent_id=None,
            generation=0,
            bankroll=DEFAULT_STARTING_BANKROLL,
            current_stake=DEFAULT_STARTING_STAKE,
            wins=0, losses=0, alive=True,
            born_date=date.today().isoformat(),
        )
        pop = LineagePopulation(lineages=[genesis])
        save_population(pop)
        return pop
    try:
        data = json.loads(LINEAGE_FILE.read_text(encoding="utf-8"))
        return LineagePopulation.from_dict(data)
    except Exception:
        # Corrupt state -> reseed genesis
        genesis = Lineage(
            lineage_id=_new_id(), parent_id=None, generation=0,
            bankroll=DEFAULT_STARTING_BANKROLL, current_stake=DEFAULT_STARTING_STAKE,
            wins=0, losses=0, alive=True, born_date=date.today().isoformat(),
        )
        pop = LineagePopulation(lineages=[genesis])
        save_population(pop)
        return pop


def save_population(pop: LineagePopulation) -> None:
    """Persist lineage population atomically."""
    LINEAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = LINEAGE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(pop.to_dict(), indent=2), encoding="utf-8")
    tmp.replace(LINEAGE_FILE)


def _new_id() -> str:
    return "ln_" + uuid.uuid4().hex[:10]


# ----------------------------------------------------------------------------
# Daily heartbeat selection for living lineages
# ----------------------------------------------------------------------------
def select_daily_heartbeats(
    board: list,
    target_date: str = None,
    odds_index: Optional[dict] = None,
    top_n: int = TOP_N_CANDIDATES,
    min_edge: float = 0.0,
) -> list[HeartbeatFixture]:
    """
    Build the day's heartbeats from the living lineages + top edge candidates.

    Each living lineage gets ONE heartbeat. To maximise survival pressure and
    diversity, we assign the highest-edge distinct fixtures to the living
    lineages, preferring to give the strongest lineage the strongest fixture.

    Returns HeartbeatFixture list (one per living lineage), empty if no living
    lineages (caller should reseed via the starvation floor).
    """
    pop = load_population()
    living = pop.living()

    if not living:
        # Starvation floor: reseed a single genesis lineage so the species
        # survives while the framework runs.
        genesis = Lineage(
            lineage_id=_new_id(), parent_id=None, generation=0,
            bankroll=STARVATION_FLOOR, current_stake=DEFAULT_STARTING_STAKE,
            wins=0, losses=0, alive=True, born_date=date.today().isoformat(),
        )
        pop.lineages.append(genesis)
        save_population(pop)
        living = [genesis]

    candidates = select_top_heartbeats(
        board, target_date=target_date, odds_index=odds_index,
        top_n=max(top_n, len(living)), min_edge=min_edge,
    )

    # Assign candidates to lineages: strongest lineage -> strongest fixture.
    living_sorted = sorted(living, key=lambda ln: ln.bankroll, reverse=True)
    heartbeats: list[HeartbeatFixture] = []
    for i, lineage in enumerate(living_sorted):
        if i < len(candidates):
            hb = candidates[i]
            # Tag lineage onto the fixture so results can be routed back
            hb.lineage_id = lineage.lineage_id  # type: ignore[attr-defined]
            hb.generation = lineage.generation  # type: ignore[attr-defined]
            heartbeats.append(hb)
        # If fewer candidates than lineages, surviving lineages simply skip a day
    return heartbeats


# ----------------------------------------------------------------------------
# Result processing — birth / death transition
# ----------------------------------------------------------------------------
def record_heartbeat_result(
    heartbeat: HeartbeatFixture,
    result: str,  # 'WIN' or 'LOSS'
    target_date: str = None,
) -> LineagePopulation:
    """
    Apply a heartbeat result to its lineage and run the reproduction/extinction
    transition.

    WIN  -> lineage bankroll grows (fractional Kelly payout); on the NEXT breeding
            cycle it will reproduce into up to OFFSPRING_PER_WIN offspring.
    LOSS -> lineage bankroll loses its stake; if bankroll hits 0 it goes extinct.

    Returns the updated population (also persisted).
    """
    pop = load_population()
    lineage_id = getattr(heartbeat, "lineage_id", None)
    lineage = next((ln for ln in pop.lineages if ln.lineage_id == lineage_id), None)

    if lineage is None:
        # Lineage not tracked (e.g. legacy single-heartbeat record). Attach result
        # to first living lineage or create one.
        living = pop.living()
        lineage = living[0] if living else Lineage(
            lineage_id=_new_id(), parent_id=None, generation=0,
            bankroll=DEFAULT_STARTING_BANKROLL, current_stake=DEFAULT_STARTING_STAKE,
            wins=0, losses=0, alive=True, born_date=date.today().isoformat(),
        )
        if lineage not in pop.lineages:
            pop.lineages.append(lineage)

    price = heartbeat.price or 0.0
    if result == "WIN":
        profit = lineage.current_stake * (price - 1.0)
        lineage.bankroll = round(lineage.bankroll + profit, 2)
        lineage.wins += 1
    elif result == "LOSS":
        lineage.bankroll = round(lineage.bankroll - lineage.current_stake, 2)
        lineage.losses += 1
        if lineage.bankroll <= 0.0:
            lineage.alive = False  # EXTINCTION
    else:
        # Unknown result — no transition
        lineage.last_result = result
        save_population(pop)
        return pop

    lineage.last_result = result
    lineage.fixture = heartbeat.fixture
    lineage.pick = heartbeat.pick
    lineage.price = price
    lineage.edge = heartbeat.edge
    lineage.probability = heartbeat.probability

    save_population(pop)
    return pop


def breed_next_generation(board: list, target_date: str = None,
                          odds_index: Optional[dict] = None) -> LineagePopulation:
    """
    Reproduce living lineages into the next day's population.

    For each living lineage:
      - WIN last -> spawn up to OFFSPRING_PER_WIN children (split bankroll),
                    parent retires (its bloodline continues through children).
      - LOSS last -> already extinct or stays (no spawn).
      - No result yet -> carries forward as-is (still alive, same bankroll).

    Starvation floor: if no lineages remain alive, reseed one genesis lineage.
    """
    pop = load_population()
    today = target_date or date.today().isoformat()

    if pop.last_bred_date == today:
        return pop  # already bred for today

    new_lineages: list[Lineage] = []
    for ln in pop.lineages:
        if not ln.alive:
            continue  # extinct lineages do not reproduce
        if ln.last_result == "WIN":
            # REPRODUCE: split bankroll across offspring
            n = min(OFFSPRING_PER_WIN, MAX_LINEAGES - len(new_lineages))
            if n <= 0:
                # Population cap reached — parent carries forward alone
                ln.generation += 1
                new_lineages.append(ln)
                continue
            share = ln.bankroll / n
            for _ in range(n):
                child = Lineage(
                    lineage_id=_new_id(),
                    parent_id=ln.lineage_id,
                    generation=ln.generation + 1,
                    bankroll=round(share, 2),
                    current_stake=DEFAULT_STARTING_STAKE,
                    wins=0, losses=0, alive=True,
                    born_date=today,
                )
                new_lineages.append(child)
            # Parent retires; bloodline continues via children
        else:
            # LOSS or no-result: carry forward unchanged
            new_lineages.append(ln)

    # Cap population
    if len(new_lineages) > MAX_LINEAGES:
        new_lineages = new_lineages[:MAX_LINEAGES]

    if not new_lineages:
        # STARVATION FLOOR — keep the species alive
        new_lineages.append(Lineage(
            lineage_id=_new_id(), parent_id=None, generation=0,
            bankroll=STARVATION_FLOOR, current_stake=DEFAULT_STARTING_STAKE,
            wins=0, losses=0, alive=True, born_date=today,
        ))

    pop.lineages = new_lineages
    pop.last_bred_date = today
    save_population(pop)
    return pop


# ----------------------------------------------------------------------------
# Reporting
# ----------------------------------------------------------------------------
def _safe_render(text: str) -> str:
    """Replace emoji with ASCII for Windows compatibility."""
    return (text
        .replace('🧬', '[DNA]')
        .replace('🌿', '[ALIVE]')
        .replace('💀', '[EXTINCT]')
        .replace('💰', '[$]')
        .replace('💵', '[$]')
        .replace('🎯', '[S]')
    )


def render_lineage_report(pop: Optional[LineagePopulation] = None) -> str:
    """Render a lineage survival report for Telegram / logging."""
    pop = pop or load_population()
    living = pop.living()
    extinct = [ln for ln in pop.lineages if not ln.alive]
    total_bankroll = sum(ln.bankroll for ln in living)

    lines = [
        _safe_render("🧬 HEARTBEAT LINEAGE REPORT"),
        _safe_render(f"🌿 Living lineages: {len(living)}   💀 Extinct: {len(extinct)}"),
        _safe_render(f"💰 Total lifeforce (bankroll): {total_bankroll:.2f}"),
    ]
    for ln in sorted(living, key=lambda x: x.bankroll, reverse=True):
        tag = f"G{ln.generation}"
        par = f"<-{ln.parent_id[:6]}" if ln.parent_id else "GENESIS"
        lines.append(
            _safe_render(
                f"  {ln.lineage_id[:8]} {tag} {par} | [$]{ln.bankroll:.2f} "
                f"[S]{ln.current_stake:.2f} | {ln.wins}W-{ln.losses}L"
                + (f" | {ln.fixture} - {ln.pick}" if ln.fixture else "")
            )
        )
    return "\n".join(lines)


# ----------------------------------------------------------------------------
# CLI / entrypoint for outcome monitor
# ----------------------------------------------------------------------------
def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Heartbeat lineage survival engine.")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("report", help="Print current lineage report")
    sub.add_parser("breed", help="Breed next generation (reproduce winners)")

    res = sub.add_parser("result", help="Record a heartbeat result")
    res.add_argument("--fixture", required=True)
    res.add_argument("--pick", required=True)
    res.add_argument("--price", type=float, default=0.0)
    res.add_argument("--edge", type=float, default=0.0)
    res.add_argument("--prob", type=float, default=0.0)
    res.add_argument("--lineage", default=None)
    res.add_argument("--result", choices=["WIN", "LOSS"], required=True)

    args = parser.parse_args()

    if args.cmd == "report":
        print(render_lineage_report())
        return 0
    if args.cmd == "breed":
        pop = breed_next_generation([])
        print(render_lineage_report(pop))
        return 0
    if args.cmd == "result":
        hb = HeartbeatFixture(
            fixture=args.fixture, kickoff_time="??:??", league="Unknown",
            pick=args.pick, probability=args.prob, edge=args.edge,
            market_type="OTHER", price=args.price,
        )
        if args.lineage:
            hb.lineage_id = args.lineage  # type: ignore[attr-defined]
        record_heartbeat_result(hb, args.result)
        print(render_lineage_report())
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
