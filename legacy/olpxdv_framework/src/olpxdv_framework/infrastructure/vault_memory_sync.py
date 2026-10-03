"""
Vault-Memory Synchronization for OLP XDV Framework.

Python wrapper around the Node.js vault-memory synchronization script.
Provides async interface for bidirectional synchronization between
the canonical vault (git-tracked) and the agent memory system.
"""

from __future__ import annotations
import asyncio
import logging
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    """Result of a vault-memory synchronization operation."""
    vault_to_memory: int
    memory_to_vault: int
    duration: float
    success: bool
    error: Optional[str] = None


class VaultMemorySync:
    """
    Wrapper for the vault-memory synchronization script.

    Provides async interface to run the Node.js synchronization script
    and parse its results.
    """

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        # Find the Node.js script
        project_root = Path(__file__).parent.parent.parent.parent
        self.script_path = project_root / "scripts" / "vault-memory-sync.js"
        self.logger.info(f"Vault-memory sync script: {self.script_path}")

    async def sync_vault_to_memory(self) -> SyncResult:
        """Synchronize vault to memory (one-way)."""
        return await self._run_sync("vault-to-memory")

    async def sync_memory_to_vault(self) -> SyncResult:
        """Synchronize memory to vault (one-way)."""
        return await self._run_sync("memory-to-vault")

    async def sync_bidirectional(self) -> SyncResult:
        """Perform bidirectional synchronization."""
        return await self._run_sync("bidirectional")

    async def _run_sync(self, direction: str) -> SyncResult:
        """
        Run the synchronization script with the given direction.

        Args:
            direction: One of 'vault-to-memory', 'memory-to-vault', 'bidirectional'

        Returns:
            SyncResult with operation details
        """
        try:
            self.logger.info(f"Running vault-memory sync: {direction}")

            # Run the Node.js script
            process = await asyncio.create_subprocess_exec(
                "node",
                str(self.script_path),
                direction,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            stdout_str = stdout.decode("utf-8") if stdout else ""
            stderr_str = stderr.decode("utf-8") if stderr else ""

            if process.returncode != 0:
                error_msg = f"Sync script failed with exit code {process.returncode}: {stderr_str}"
                self.logger.error(error_msg)
                return SyncResult(
                    vault_to_memory=0,
                    memory_to_vault=0,
                    duration=0.0,
                    success=False,
                    error=error_msg
                )

            # Parse output for sync statistics
            vault_to_memory = 0
            memory_to_vault = 0
            duration = 0.0

            # Parse the log output
            for line in stdout_str.split('\n'):
                if 'synchronized' in line.lower() and 'vault' in line.lower() and 'memory' in line.lower():
                    # Try to extract numbers
                    import re
                    numbers = re.findall(r'\d+', line)
                    if 'vault' in line.lower() and 'memory' in line.lower():
                        if numbers:
                            vault_to_memory = int(numbers[0])
                            if len(numbers) > 1:
                                memory_to_vault = int(numbers[1])
                    elif 'memory' in line.lower() and 'vault' in line.lower():
                        if numbers:
                            memory_to_vault = int(numbers[0])
                elif 'completed in' in line.lower():
                    # Extract duration
                    import re
                    duration_match = re.search(r'(\d+\.?\d*)s', line)
                    if duration_match:
                        duration = float(duration_match.group(1))

            self.logger.info(f"Sync completed: vault→memory={vault_to_memory}, memory→vault={memory_to_vault}, duration={duration}s")

            return SyncResult(
                vault_to_memory=vault_to_memory,
                memory_to_vault=memory_to_vault,
                duration=duration,
                success=True
            )

        except FileNotFoundError:
            error_msg = f"Node.js or sync script not found: {self.script_path}"
            self.logger.error(error_msg)
            return SyncResult(
                vault_to_memory=0,
                memory_to_vault=0,
                duration=0.0,
                success=False,
                error=error_msg
            )
        except Exception as e:
            error_msg = f"Error running sync script: {e}"
            self.logger.error(error_msg, exc_info=True)
            return SyncResult(
                vault_to_memory=0,
                memory_to_vault=0,
                duration=0.0,
                success=False,
                error=error_msg
            )


# Global sync instance
_vault_memory_sync: Optional[VaultMemorySync] = None


def get_vault_memory_sync() -> VaultMemorySync:
    """Get the global vault-memory sync instance."""
    global _vault_memory_sync
    if _vault_memory_sync is None:
        _vault_memory_sync = VaultMemorySync()
    return _vault_memory_sync


async def sync_bidirectional() -> SyncResult:
    """Convenience function for bidirectional sync."""
    sync = get_vault_memory_sync()
    return await sync.sync_bidirectional()


async def sync_vault_to_memory() -> SyncResult:
    """Convenience function for vault-to-memory sync."""
    sync = get_vault_memory_sync()
    return await sync.sync_vault_to_memory()


async def sync_memory_to_vault() -> SyncResult:
    """Convenience function for memory-to-vault sync."""
    sync = get_vault_memory_sync()
    return await sync.sync_memory_to_vault()


# For direct script execution
async def main():
    """Main entry point for direct execution."""
    import argparse

    parser = argparse.ArgumentParser(description="Vault-Memory Synchronization")
    parser.add_argument(
        "direction",
        choices=["vault-to-memory", "memory-to-vault", "bidirectional"],
        default="bidirectional",
        nargs="?",
        help="Sync direction"
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    result = await _run_sync(args.direction)

    if result.success:
        print(f"Sync successful: vault→memory={result.vault_to_memory}, "
              f"memory→vault={result.memory_to_vault}, duration={result.duration:.2f}s")
        sys.exit(0)
    else:
        print(f"Sync failed: {result.error}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())