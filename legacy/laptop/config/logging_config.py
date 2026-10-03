"""
Logging configuration for OLP XDV
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class LoggingConfig:
    """Logging-related configuration parameters."""

    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_path: str = "olp_xdv.log"
    max_file_size: int = 10485760  # 10MB
    backup_count: int = 5
    console_enabled: bool = True
    file_enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "level": self.level,
            "format": self.format,
            "file_path": self.file_path,
            "max_file_size": self.max_file_size,
            "backup_count": self.backup_count,
            "console_enabled": self.console_enabled,
            "file_enabled": self.file_enabled
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LoggingConfig":
        """Create configuration from dictionary."""
        return cls(
            level=data.get("level", "INFO"),
            format=data.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"),
            file_path=data.get("file_path", "olp_xdv.log"),
            max_file_size=data.get("max_file_size", 10485760),
            backup_count=data.get("backup_count", 5),
            console_enabled=data.get("console_enabled", True),
            file_enabled=data.get("file_enabled", True)
        )