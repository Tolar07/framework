"""
Tactical engine actions from team-state intelligence (ID417).

WHY
  The engine has promoted-club handling (predict_adjusted) but NO slots for
  low-block / absentees / tier-drop / manager-bounce. team_state (manager,
  squad_hash, derived_formation) is now ingested daily via
  data/api_football_team_state.py and persisted to brain.store team_state.
  This module turns that real data into *tactical adjustments* on the Dixon-Coles
  goal expectancies — conservative, named, auditable, never guessed.

WHAT THIS DOES
  - derived_formation -> a small goal-direction scale. Defensive shapes
    (5-x-x, 4-5-1) shave goal expectancy; attacking shapes (3-4-3, 4-2-4)
    lift it. Unknown shapes -> 1.0 (no adjustment, HR35).
  - squad_hash -> change detection against the prior snapshot. A changed
    squad (transfer window, injury recall) is less cohesive, so the changed
    side's goal expectancy is nudged DOWN a little. No prior -> 1.0.

WHAT THIS DELIBERATELY DOES NOT DO
  - Never fabricates a formation or squad state (HR35): absent data -> 1.0.
  - Never applies a tactical scale without provenance (ID403 F4).
  - Never touches the CLV/legs publish gate or any protected constant.
  - The scales are SMALL by design: a tactical signal is a nudge, not a
    re-rating. The promoted-club level adjustment (predict_adjusted) is the
    heavy lever; this is the fine-tuning on top of real, observed shape.

ID417: consumes team_state rows. The adjustment is applied via
engine.dixon_coles.predict_adjusted (the same scale-home/scale-away path used
for the promoted-club level adjustment), so tactical and promoted adjustments
can never drift apart on the marginals.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# --- Tunable, named, conservative -------------------------------------------
# A tactical shape signal is a NUDGE, not a re-rating. These bounds keep the
# adjustment in the noise floor of the model so it can never silently overturn
# a fitted rating. All are visible here, not buried in a formula.
FORMATION_GOAL_LIFT = 0.04      # attacking shape: +4% goal expectancy
FORMATION_GOAL_SHAVE = 0.04     # defensive shape: -4% goal expectancy
SQUAD_CHANGE_PENALTY = 0.03     # changed squad: -3% goal expectancy (cohesion)

# Formation families. A formation string like "4-3-3" is parsed into its three
# numeric bands; we classify on the defensive-band width (first number = defenders).
#  - Defensive: 5+ defenders, or the explicit low-block 4-5-1 / 4-6-0.
#  - Attacking: 3 defenders with an extra attacker band (4th number >= 3),
#    or the front-foot 4-2-4 / 3-4-3 / 4-3-3 (balanced but attack-leaning).
_DEFENSIVE_FORMATIONS = frozenset({
    "5-3-2", "5-4-1", "5-2-3", "5-3-1-1", "4-5-1", "4-6-0", "6-3-1", "3-5-2",
})
_ATTACKING_FORMATIONS = frozenset({
    "3-4-3", "4-3-3", "4-2-4", "3-4-2-1", "3-4-1-2", "4-1-3-2", "4-2-3-1",
    "4-3-1-2", "3-3-4",
})


@dataclass(frozen=True)
class TacticalAdjustment:
    """The per-fixture tactical nudge, with full provenance.

    scale_home / scale_away are multipliers on the Dixon-Coles goal
    expectancies, consumed by engine.dixon_coles.predict_adjusted.
    1.0 means 'no tactical signal applied' for that side."""
    scale_home: float = 1.0
    scale_away: float = 1.0
    home_note: str = ""
    away_note: str = ""
    provenance: str = "tactical: none"

    @property
    def applied(self) -> bool:
        return self.scale_home != 1.0 or self.scale_away != 1.0


def _formation_direction(formation: Optional[str]) -> Optional[str]:
    """Classify a formation string as 'defensive', 'attacking', or None.

    None means 'no opinion' (unknown / unparseable shape) -> caller applies
    no formation scale (HR35: never guess)."""
    if not formation:
        return None
    f = formation.strip()
    if f in _DEFENSIVE_FORMATIONS:
        return "defensive"
    if f in _ATTACKING_FORMATIONS:
        return "attacking"
    # Fallback parse: first band = defender count.
    parts = [p for p in f.replace("-", " ").split() if p.isdigit()]
    if len(parts) >= 1:
        defenders = int(parts[0])
        if defenders >= 5:
            return "defensive"
        if defenders <= 3 and len(parts) >= 4 and int(parts[3]) >= 3:
            return "attacking"
    return None


def _formation_scale(formation: Optional[str]) -> tuple[float, str]:
    """Return (scale, note) for a formation. scale is 1.0 when no opinion."""
    direction = _formation_direction(formation)
    if direction == "defensive":
        return (1.0 - FORMATION_GOAL_SHAVE,
                f"defensive shape {formation}")
    if direction == "attacking":
        return (1.0 + FORMATION_GOAL_LIFT,
                f"attacking shape {formation}")
    return (1.0, "")


def _squad_change_scale(current_hash: Optional[str],
                        prior_hash: Optional[str]) -> tuple[float, str]:
    """Return (scale, note) for squad turnover detection.

    A changed squad_hash vs the prior snapshot means the composition shifted
    (transfer, recall). New partnerships are less cohesive -> nudge goal
    expectancy down. No prior snapshot or no change -> 1.0 (HR35: no data,
    no penalty)."""
    if not current_hash:
        return 1.0, ""
    if prior_hash and prior_hash != current_hash:
        return (1.0 - SQUAD_CHANGE_PENALTY,
                "squad turnover vs prior snapshot")
    return 1.0, ""


def tactical_for_fixture(
    home_formation: Optional[str] = None,
    away_formation: Optional[str] = None,
    home_squad_hash: Optional[str] = None,
    away_squad_hash: Optional[str] = None,
    home_prior_hash: Optional[str] = None,
    away_prior_hash: Optional[str] = None,
) -> TacticalAdjustment:
    """Build the per-fixture tactical adjustment from team-state fields.

    Each side's scale is the PRODUCT of its formation scale and its squad-change
    scale (both default to 1.0 when no signal). Conservative and multiplicative
    so two small nudges cannot compound into a large one.

    Provenance records which signals fired, for the board / ID403 F4."""
    h_f_scale, h_f_note = _formation_scale(home_formation)
    a_f_scale, a_f_note = _formation_scale(away_formation)
    h_s_scale, h_s_note = _squad_change_scale(home_squad_hash, home_prior_hash)
    a_s_scale, a_s_note = _squad_change_scale(away_squad_hash, away_prior_hash)

    scale_home = round(h_f_scale * h_s_scale, 4)
    scale_away = round(a_f_scale * a_s_scale, 4)

    notes = [n for n in (h_f_note, h_s_note) if n]
    home_note = "; ".join(notes)
    notes = [n for n in (a_f_note, a_s_note) if n]
    away_note = "; ".join(notes)

    prov_parts = []
    if h_f_note or a_f_note:
        prov_parts.append("formation")
    if h_s_note or a_s_note:
        prov_parts.append("squad-change")
    provenance = "tactical: " + (",".join(prov_parts) if prov_parts else "none")

    return TacticalAdjustment(
        scale_home=scale_home, scale_away=scale_away,
        home_note=home_note, away_note=away_note, provenance=provenance)


def load_prior_hashes(brain, home: str, away: str, league: str,
                      as_of: Optional[str] = None) -> tuple[Optional[str], Optional[str]]:
    """Fetch the most recent PRIOR squad_hash for each team from the brain.

    Used for squad-turnover detection. Returns (home_prior, away_prior).
    None for a team with no earlier snapshot (HR35: no penalty applied)."""
    home_prior = away_prior = None
    if brain is None:
        return home_prior, away_prior
    try:
        rows = brain.get_team_state(team=home, league=league, limit=2)
        # get_team_state orders by as_of DESC; index 1 (if present) is the
        # prior snapshot (index 0 is the current one we are comparing against).
        if len(rows) > 1:
            home_prior = rows[1].get("squad_hash")
    except Exception:
        pass
    try:
        rows = brain.get_team_state(team=away, league=league, limit=2)
        if len(rows) > 1:
            away_prior = rows[1].get("squad_hash")
    except Exception:
        pass
    return home_prior, away_prior
