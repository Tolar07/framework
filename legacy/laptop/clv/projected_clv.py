"""
Projected CLV Logger — records projected CLV at selection time.

This module captures the projected CLV (Closing Line Value) when a leg is selected
for the production bet, before the match kicks off. It allows comparison of
projected CLV vs actual CLV post-settlement, providing insight into whether
the model's edge estimates are accurate predictors of closing line movement.

Projected CLV = (model_prob / implied_prob - 1) * 100

This is distinct from actual CLV which uses entry_odds vs closing_odds:
Actual CLV = (entry_odds / closing_odds - 1) * 100
"""
from __future__ import annotations
import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


DEFAULT_PROJECTED_LOG_PATH = Path(__file__).parent / "projected_clv_log.json"


@dataclass
class ProjectedCLVLeg:
    """A projected CLV record at selection time."""
    fixture: str
    market_key: str
    entry_odds: float
    model_prob: float
    implied_prob: float
    projected_clv_pct: float
    date_logged: str
    # Optional: link to actual CLV log leg_id when it gets created
    actual_leg_id: Optional[str] = None


class ProjectedCLVLog:
    def __init__(self, path: str | Path = DEFAULT_PROJECTED_LOG_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.legs: list[ProjectedCLVLeg] = self._load()

    def _load(self) -> list[ProjectedCLVLeg]:
        if not self.path.exists():
            return []
        with open(self.path) as f:
            raw = json.load(f)
        return [ProjectedCLVLeg(**r) for r in raw]

    def _save(self) -> None:
        with open(self.path, "w") as f:
            json.dump([asdict(l) for l in self.legs], f, indent=2)

    def log(self, fixture: str, market_key: str, entry_odds: float,
            model_prob: float, implied_prob: float, projected_clv_pct: float) -> ProjectedCLVLeg:
        """Record a projected CLV at selection time."""
        leg = ProjectedCLVLeg(
            fixture=fixture,
            market_key=market_key,
            entry_odds=entry_odds,
            model_prob=model_prob,
            implied_prob=implied_prob,
            projected_clv_pct=projected_clv_pct,
            date_logged=datetime.now(timezone.utc).isoformat(),
        )
        self.legs.append(leg)
        self._save()
        return leg

    def link_to_actual(self, fixture: str, market_key: str, actual_leg_id: str) -> bool:
        """Link a projected CLV entry to its actual CLV leg after settlement."""
        for leg in self.legs:
            if leg.fixture == fixture and leg.market_key == market_key and leg.actual_leg_id is None:
                leg.actual_leg_id = actual_leg_id
                self._save()
                return True
        return False

    def get_summary(self) -> dict:
        """Summary stats for projected vs actual CLV comparison."""
        if not self.legs:
            return {"total": 0, "linked": 0, "mean_projected_clv": None}
        linked = [l for l in self.legs if l.actual_leg_id is not None]
        return {
            "total": len(self.legs),
            "linked": len(linked),
            "mean_projected_clv": round(sum(l.projected_clv_pct for l in self.legs) / len(self.legs), 3),
            "mean_projected_clv_linked": round(sum(l.projected_clv_pct for l in linked) / len(linked), 3) if linked else None,
        }


def log_projected_clv(fixture: str, market_key: str, entry_odds: float,
                      model_prob: float, implied_prob: float, projected_clv_pct: float) -> ProjectedCLVLeg:
    """Convenience function to log a projected CLV entry."""
    log = ProjectedCLVLog()
    return log.log(fixture, market_key, entry_odds, model_prob, implied_prob, projected_clv_pct)


if __name__ == "__main__":
    """CLI for projected CLV log."""
    import argparse
    ap = argparse.ArgumentParser(description="Projected CLV Log - status and analysis")
    ap.add_argument("--status", action="store_true", help="print projected CLV log summary")
    a = ap.parse_args()

    log = ProjectedCLVLog()
    if a.status:
        summary = log.get_summary()
        for k, v in summary.items():
            print(f"  {k}: {v}")
    else:
        ap.print_help()