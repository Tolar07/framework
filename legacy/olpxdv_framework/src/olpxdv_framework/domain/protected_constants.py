"""
Protected Constants Module

This module implements the protected constants pattern from OLP XDV.
These constants are critical for financial safeguards and cannot be modified
without explicit Architect signoff and audit trail.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import ClassVar, Dict, Any, Optional
import logging
from datetime import datetime
import threading

logger = logging.getLogger(__name__)


class ProtectedConstantError(Exception):
    """Raised when attempting to modify a protected constant without authorization"""
    pass


class ArchitectSignoffRequired(Exception):
    """Raised when an operation requires Architect signoff"""
    pass


class ConstantProtectionLevel(Enum):
    """Levels of protection for constants"""
    NORMAL = "normal"              # Can be modified with normal process
    PROTECTED = "protected"        # Requires explicit override
    ARCHITECT_ONLY = "architect_only"  # Only Architect can modify


@dataclass(frozen=True)
class ConstantDefinition:
    """Definition of a protected constant"""
    name: str
    default_value: Any
    protection_level: ConstantProtectionLevel
    description: str
    validation_rules: Dict[str, Any] = field(default_factory=dict)
    last_modified: Optional[datetime] = None
    modified_by: Optional[str] = None


class ProtectedConstants:
    """
    Central registry for all protected constants in the system.

    This class enforces the governance rules around critical constants
    that affect financial decisions, CLV gates, and capital deployment.
    """

    # Registry of all protected constants
    _CONSTANTS: ClassVar[Dict[str, ConstantDefinition]] = {}

    # Lock for thread-safe operations
    _lock: ClassVar[threading.RLock] = threading.RLock()

    # Architecture signoff state
    _ARCHITECT_SIGNOFF: ClassVar[bool] = False
    _ARCHITECT_SIGNOFF_TIMESTAMP: ClassVar[Optional[datetime]] = None
    _ARCHITECT_SIGNOFF_BY: ClassVar[Optional[str]] = None

    # Audit trail for constant modifications
    _AUDIT_TRAIL: ClassVar[list] = []

    @classmethod
    def register_constant(
        cls,
        name: str,
        default_value: Any,
        protection_level: ConstantProtectionLevel,
        description: str,
        validation_rules: Optional[Dict[str, Any]] = None
    ) -> None:
        """Register a new protected constant"""
        with cls._lock:
            if name in cls._CONSTANTS:
                raise ValueError(f"Constant {name} already registered")

            cls._CONSTANTS[name] = ConstantDefinition(
                name=name,
                default_value=default_value,
                protection_level=protection_level,
                description=description,
                validation_rules=validation_rules or {}
            )
            logger.info(f"Registered protected constant: {name} (level: {protection_level.value})")

    @classmethod
    def get(cls, name: str) -> Any:
        """Get the value of a protected constant"""
        with cls._lock:
            if name not in cls._CONSTANTS:
                raise KeyError(f"Constant {name} not registered")

            return cls._CONSTANTS[name].default_value

    @classmethod
    def set(cls, name: str, value: Any, authorized_by: str,
           architect_signoff: bool = False) -> None:
        """
        Set a protected constant value with governance checks.

        Args:
            name: Name of the constant
            value: New value
            authorized_by: Identifier of the entity making the change
            architect_signoff: Whether Architect signoff is provided

        Raises:
            ProtectedConstantError: If modification is not authorized
            ArchitectSignoffRequired: If Architect signoff is required but not provided
        """
        with cls._lock:
            if name not in cls._CONSTANTS:
                raise KeyError(f"Constant {name} not registered")

            constant = cls._CONSTANTS[name]

            # Check protection level
            if constant.protection_level == ConstantProtectionLevel.ARCHITECT_ONLY:
                if not architect_signoff or not cls._ARCHITECT_SIGNOFF:
                    raise ArchitectSignoffRequired(
                        f"Constant {name} requires Architect signoff. "
                        f"Current signoff status: {cls._ARCHITECT_SIGNOFF}"
                    )

            # Validate against rules
            cls._validate_value(name, value, constant.validation_rules)

            # Record the change
            old_value = constant.default_value
            constant.default_value = value
            constant.last_modified = datetime.utcnow()
            constant.modified_by = authorized_by

            # Add to audit trail
            audit_entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "constant": name,
                "old_value": str(old_value),
                "new_value": str(value),
                "modified_by": authorized_by,
                "architect_signoff": architect_signoff,
                "protection_level": constant.protection_level.value
            }
            cls._AUDIT_TRAIL.append(audit_entry)

            logger.warning(
                f"PROTECTED CONSTANT MODIFIED: {name} = {value} "
                f"(by: {authorized_by}, architect_signoff: {architect_signoff})"
            )

    @classmethod
    def _validate_value(cls, name: str, value: Any, rules: Dict[str, Any]) -> None:
        """Validate a value against registered rules"""
        if not rules:
            return

        if "type" in rules:
            expected_type = rules["type"]
            if not isinstance(value, expected_type):
                raise ProtectedConstantError(
                    f"Constant {name} must be of type {expected_type.__name__}, "
                    f"got {type(value).__name__}"
                )

        if "min" in rules and value < rules["min"]:
            raise ProtectedConstantError(
                f"Constant {name} value {value} below minimum {rules['min']}"
            )

        if "max" in rules and value > rules["max"]:
            raise ProtectedConstantError(
                f"Constant {name} value {value} exceeds maximum {rules['max']}"
            )

        if "allowed_values" in rules and value not in rules["allowed_values"]:
            raise ProtectedConstantError(
                f"Constant {name} value {value} not in allowed values: "
                f"{rules['allowed_values']}"
            )

    @classmethod
    def set_architect_signoff(cls, granted: bool, authorized_by: str) -> None:
        """
        Set the Architect signoff state.

        This is a critical operation that enables/disables modification
        of ARCHITECT_ONLY constants.
        """
        with cls._lock:
            cls._ARCHITECT_SIGNOFF = granted
            cls._ARCHITECT_SIGNOFF_TIMESTAMP = datetime.utcnow()
            cls._ARCHITECT_SIGNOFF_BY = authorized_by

            audit_entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "action": "ARCHITECT_SIGNOFF_CHANGE",
                "granted": granted,
                "authorized_by": authorized_by,
                "protection_level": "CRITICAL"
            }
            cls._AUDIT_TRAIL.append(audit_entry)

            logger.critical(
                f"ARCHITECT_SIGNOFF {'GRANTED' if granted else 'REVOKED'} "
                f"by {authorized_by} at {cls._ARCHITECT_SIGNOFF_TIMESTAMP}"
            )

    @classmethod
    def get_architect_signoff_status(cls) -> Dict[str, Any]:
        """Get current Architect signoff status"""
        return {
            "active": cls._ARCHITECT_SIGNOFF,
            "timestamp": cls._ARCHITECT_SIGNOFF_TIMESTAMP.isoformat()
            if cls._ARCHITECT_SIGNOFF_TIMESTAMP else None,
            "authorized_by": cls._ARCHITECT_SIGNOFF_BY
        }

    @classmethod
    def get_audit_trail(cls, limit: int = 100) -> list:
        """Get the audit trail of constant modifications"""
        return cls._AUDIT_TRAIL[-limit:]

    @classmethod
    def get_all_constants(cls) -> Dict[str, Dict[str, Any]]:
        """Get all registered constants with their metadata"""
        return {
            name: {
                "value": const.default_value,
                "protection_level": const.protection_level.value,
                "description": const.description,
                "last_modified": const.last_modified.isoformat()
                if const.last_modified else None,
                "modified_by": const.modified_by
            }
            for name, const in cls._CONSTANTS.items()
        }


# Register all OLP XDV protected constants
def register_olpxdv_constants() -> None:
    """Register all OLP XDV protected constants"""

    # ARCHITECT_SIGNOFF - Master gate for all protected operations
    ProtectedConstants.register_constant(
        name="ARCHITECT_SIGNOFF",
        default_value=False,
        protection_level=ConstantProtectionLevel.ARCHITECT_ONLY,
        description="Master gate - enables modification of other protected constants",
        validation_rules={"type": bool}
    )

    # CLV Gate constants
    ProtectedConstants.register_constant(
        name="CLV_MIN_LEGS",
        default_value=30,
        protection_level=ConstantProtectionLevel.ARCHITECT_ONLY,
        description="Minimum number of legs required for CLV gate to pass",
        validation_rules={"type": int, "min": 10, "max": 100}
    )

    ProtectedConstants.register_constant(
        name="CLV_MEAN_THRESHOLD",
        default_value=0.0,
        protection_level=ConstantProtectionLevel.ARCHITECT_ONLY,
        description="Mean CLV must be >= this threshold (in percentage)",
        validation_rules={"type": (int, float, Decimal), "min": -10.0, "max": 50.0}
    )

    ProtectedConstants.register_constant(
        name="CLV_WINDOW_HOURS",
        default_value=24,
        protection_level=ConstantProtectionLevel.PROTECTED,
        description="Hours before kickoff to capture closing lines",
        validation_rules={"type": int, "min": 1, "max": 168}
    )

    # Capital Deployment constants
    ProtectedConstants.register_constant(
        name="MAX_KELLY_FRACTION",
        default_value=Decimal('0.25'),
        protection_level=ConstantProtectionLevel.ARCHITECT_ONLY,
        description="Maximum Kelly fraction for stake sizing",
        validation_rules={"type": (float, Decimal), "min": 0.0, "max": 1.0}
    )

    ProtectedConstants.register_constant(
        name="MAX_DAILY_EXPOSURE",
        default_value=Decimal('1000.0'),
        protection_level=ConstantProtectionLevel.ARCHITECT_ONLY,
        description="Maximum daily capital exposure in units",
        validation_rules={"type": (float, Decimal), "min": 0.0}
    )

    ProtectedConstants.register_constant(
        name="MAX_SINGLE_BET_EXPOSURE",
        default_value=Decimal('100.0'),
        protection_level=ConstantProtectionLevel.ARCHITECT_ONLY,
        description="Maximum single bet exposure in units",
        validation_rules={"type": (float, Decimal), "min": 0.0}
    )

    # Client Publish Gate
    ProtectedConstants.register_constant(
        name="CLIENT_PUBLISH_ENABLED",
        default_value=False,
        protection_level=ConstantProtectionLevel.ARCHITECT_ONLY,
        description="Enable publishing to client channels (Telegram, Web)",
        validation_rules={"type": bool}
    )

    ProtectedConstants.register_constant(
        name="MIN_EDGE_FOR_PUBLISH",
        default_value=Decimal('0.03'),  # 3% minimum edge
        protection_level=ConstantProtectionLevel.ARCHITECT_ONLY,
        description="Minimum expected edge (MES) for publishing",
        validation_rules={"type": (float, Decimal), "min": 0.0, "max": 1.0}
    )

    # Model Reuse Gate
    ProtectedConstants.register_constant(
        name="MODEL_REUSE_DAYS",
        default_value=7,
        protection_level=ConstantProtectionLevel.PROTECTED,
        description="Days before model coefficients can be reused",
        validation_rules={"type": int, "min": 1, "max": 30}
    )

    # Schema Refusal Gate
    ProtectedConstants.register_constant(
        name="STRICT_SCHEMA_MODE",
        default_value=True,
        protection_level=ConstantProtectionLevel.PROTECTED,
        description="Reject data that doesn't match expected schema",
        validation_rules={"type": bool}
    )

    # All Fixtures Eligibility (replaces softness tier)
    ProtectedConstants.register_constant(
        name="ALL_FIXTURES_ELIGIBLE",
        default_value=True,
        protection_level=ConstantProtectionLevel.ARCHITECT_ONLY,
        description="All fixtures eligible regardless of league tier",
        validation_rules={"type": bool}
    )

    # ID405 Override (Away wins gate)
    ProtectedConstants.register_constant(
        name="ID405_ALLOW_AWAY_WINS",
        default_value=True,
        protection_level=ConstantProtectionLevel.ARCHITECT_ONLY,
        description="Allow away win recommendations (ID405 override active)",
        validation_rules={"type": bool}
    )

    # Phase configuration
    ProtectedConstants.register_constant(
        name="CURRENT_PHASE",
        default_value=3,
        protection_level=ConstantProtectionLevel.ARCHITECT_ONLY,
        description="Current phase of the framework (1=paper, 2=calibration, 3=live)",
        validation_rules={"type": int, "allowed_values": [1, 2, 3]}
    )

    ProtectedConstants.register_constant(
        name="PAPER_ONLY_BELOW_PHASE",
        default_value=3,
        protection_level=ConstantProtectionLevel.ARCHITECT_ONLY,
        description="Phase below which only paper trading is allowed",
        validation_rules={"type": int, "allowed_values": [1, 2, 3]}
    )

    # Booking/Betting constants
    ProtectedConstants.register_constant(
        name="BOOKING_CODE_EXPIRY_MINUTES",
        default_value=60,
        protection_level=ConstantProtectionLevel.PROTECTED,
        description="Minutes until booking codes expire",
        validation_rules={"type": int, "min": 5, "max": 1440}
    )

    ProtectedConstants.register_constant(
        name="SPORTYBET_MAX_ODDS",
        default_value=Decimal('50.0'),
        protection_level=ConstantProtectionLevel.PROTECTED,
        description="Maximum odds SportyBet will accept",
        validation_rules={"type": (float, Decimal), "min": 1.0}
    )

    # Fabrication Detection
    ProtectedConstants.register_constant(
        name="FABRICATION_DETECTION_ENABLED",
        default_value=True,
        protection_level=ConstantProtectionLevel.ARCHITECT_ONLY,
        description="Enable fabrication detection (FAB-001..004)",
        validation_rules={"type": bool}
    )

    ProtectedConstants.register_constant(
        name="FABRICATION_THRESHOLD",
        default_value=Decimal('0.95'),
        protection_level=ConstantProtectionLevel.PROTECTED,
        description="Confidence threshold for fabrication flagging",
        validation_rules={"type": (float, Decimal), "min": 0.5, "max": 1.0}
    )

    # Knowledge Persistence
    ProtectedConstants.register_constant(
        name="KNOWLEDGE_RELEVANCE_HALF_LIFE_DAYS",
        default_value=30,
        protection_level=ConstantProtectionLevel.PROTECTED,
        description="Half-life for knowledge relevance decay",
        validation_rules={"type": int, "min": 1, "max": 365}
    )

    ProtectedConstants.register_constant(
        name="VAULT_MEMORY_SYNC_INTERVAL_MINUTES",
        default_value=30,
        protection_level=ConstantProtectionLevel.PROTECTED,
        description="Minutes between vault-memory sync operations",
        validation_rules={"type": int, "min": 5, "max": 1440}
    )

    # Risk Management
    ProtectedConstants.register_constant(
        name="MAX_DRAWDOWN_PERCENTAGE",
        default_value=Decimal('20.0'),
        protection_level=ConstantProtectionLevel.ARCHITECT_ONLY,
        description="Maximum drawdown percentage before stopping",
        validation_rules={"type": (float, Decimal), "min": 0.0, "max": 100.0}
    )

    ProtectedConstants.register_constant(
        name="MIN_SAMPLE_SIZE_FOR_CLV",
        default_value=50,
        protection_level=ConstantProtectionLevel.ARCHITECT_ONLY,
        description="Minimum sample size for statistical CLV significance",
        validation_rules={"type": int, "min": 30, "max": 1000}
    )

    # Whitelisted leagues (optional filter)
    ProtectedConstants.register_constant(
        name="WHITELISTED_LEAGUES",
        default_value=[],
        protection_level=ConstantProtectionLevel.PROTECTED,
        description="Optional list of whitelisted league names for filtering",
        validation_rules={"type": list}
    )


# Initialize constants on module load
register_olpxdv_constants()


# Convenience accessor functions
def get_architect_signoff() -> bool:
    """Get current Architect signoff status"""
    return ProtectedConstants.get_architect_signoff_status()["active"]


def get_clv_min_legs() -> int:
    """Get minimum legs for CLV gate"""
    return ProtectedConstants.get("CLV_MIN_LEGS")


def get_clv_mean_threshold() -> Decimal:
    """Get mean CLV threshold"""
    return Decimal(str(ProtectedConstants.get("CLV_MEAN_THRESHOLD")))


def get_max_kelly_fraction() -> Decimal:
    """Get maximum Kelly fraction"""
    return Decimal(str(ProtectedConstants.get("MAX_KELLY_FRACTION")))


def get_current_phase() -> int:
    """Get current framework phase"""
    return ProtectedConstants.get("CURRENT_PHASE")


def is_paper_only() -> bool:
    """Check if system is in paper-only mode"""
    return get_current_phase() < ProtectedConstants.get("PAPER_ONLY_BELOW_PHASE")


def is_client_publish_enabled() -> bool:
    """Check if client publishing is enabled"""
    return ProtectedConstants.get("CLIENT_PUBLISH_ENABLED")


def all_fixtures_eligible() -> bool:
    """Check if all fixtures are eligible (no tier restrictions)"""
    return ProtectedConstants.get("ALL_FIXTURES_ELIGIBLE")


def is_fabrication_detection_enabled() -> bool:
    """Check if fabrication detection is enabled"""
    return ProtectedConstants.get("FABRICATION_DETECTION_ENABLED")


def get_fabrication_threshold() -> Decimal:
    """Get fabrication detection confidence threshold"""
    return Decimal(str(ProtectedConstants.get("FABRICATION_THRESHOLD")))


def get_knowledge_relevance_half_life_days() -> int:
    """Get knowledge relevance half-life in days"""
    return ProtectedConstants.get("KNOWLEDGE_RELEVANCE_HALF_LIFE_DAYS")


def get_vault_memory_sync_interval_minutes() -> int:
    """Get vault-memory sync interval in minutes"""
    return ProtectedConstants.get("VAULT_MEMORY_SYNC_INTERVAL_MINUTES")


def get_booking_code_expiry_minutes() -> int:
    """Get booking code expiry in minutes"""
    return ProtectedConstants.get("BOOKING_CODE_EXPIRY_MINUTES")


def get_sportybet_max_odds() -> Decimal:
    """Get SportyBet maximum odds"""
    return Decimal(str(ProtectedConstants.get("SPORTYBET_MAX_ODDS")))


def get_whitelisted_leagues() -> list:
    """Get whitelisted leagues"""
    return ProtectedConstants.get("WHITELISTED_LEAGUES", [])


def id405_allow_away_wins() -> bool:
    """Check if ID405 away wins gate is active"""
    return ProtectedConstants.get("ID405_ALLOW_AWAY_WINS")


def get_max_drawdown_percentage() -> Decimal:
    """Get maximum drawdown percentage"""
    return Decimal(str(ProtectedConstants.get("MAX_DRAWDOWN_PERCENTAGE")))


def get_min_sample_size_for_clv() -> int:
    """Get minimum sample size for CLV statistical significance"""
    return ProtectedConstants.get("MIN_SAMPLE_SIZE_FOR_CLV")


def get_max_daily_exposure() -> Decimal:
    """Get maximum daily exposure"""
    return Decimal(str(ProtectedConstants.get("MAX_DAILY_EXPOSURE")))


def get_max_single_bet_exposure() -> Decimal:
    """Get maximum single bet exposure"""
    return Decimal(str(ProtectedConstants.get("MAX_SINGLE_BET_EXPOSURE")))


def get_min_edge_for_publish() -> Decimal:
    """Get minimum edge for publish"""
    return Decimal(str(ProtectedConstants.get("MIN_EDGE_FOR_PUBLISH")))