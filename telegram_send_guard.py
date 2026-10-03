"""
Telegram send guard for idempotent message delivery in OLP XDV
Prevents duplicate Telegram sends using SHA256 content hashing.
Implements should_send() check to avoid spamming subscribers.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Set
import logging

logger = logging.getLogger(__name__)

# Cache file for tracking sent message hashes
SENT_MESSAGES_CACHE_PATH = Path(__file__).parent.parent / "data" / "cache" / "telegram_sent_messages.json"
# How long to remember sent messages (prevent cache from growing indefinitely)
CACHE_EXPIRY_HOURS = 24


class TelegramSendGuard:
    """Guard against duplicate Telegram sends using content hashing."""

    def __init__(self, cache_path: Path = SENT_MESSAGES_CACHE_PATH):
        self.cache_path = cache_path
        self._sent_hashes: Set[str] = set()
        self._load_cache()

    def _load_cache(self) -> None:
        """Load sent message hashes from cache file."""
        try:
            if self.cache_path.exists():
                with open(self.cache_path, 'r') as f:
                    cache_data = json.load(f)

                # Filter out expired entries
                cutoff_time = datetime.now() - timedelta(hours=CACHE_EXPIRY_HOURS)
                valid_entries = {}

                for msg_hash, timestamp_str in cache_data.items():
                    try:
                        timestamp = datetime.fromisoformat(timestamp_str)
                        if timestamp > cutoff_time:
                            valid_entries[msg_hash] = timestamp_str
                            self._sent_hashes.add(msg_hash)
                    except ValueError:
                        # Skip invalid timestamp entries
                        continue

                # Save cleaned cache
                if len(valid_entries) != len(cache_data):
                    self._save_cache(valid_entries)

                logger.info(f"Loaded {len(self._sent_hashes)} sent message hashes from cache")
            else:
                logger.info("No sent messages cache found, starting fresh")
        except Exception as e:
            logger.warning(f"Failed to load sent messages cache: {e}")
            self._sent_hashes = set()

    def _save_cache(self, cache_data: Dict[str, str] = None) -> None:
        """Save sent message hashes to cache file."""
        try:
            # Ensure cache directory exists
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)

            if cache_data is None:
                # Convert set to dict with current timestamps
                cache_data = {msg_hash: datetime.now().isoformat() for msg_hash in self._sent_hashes}

            with open(self.cache_path, 'w') as f:
                json.dump(cache_data, f, indent=2)

            logger.debug(f"Saved {len(cache_data)} sent message hashes to cache")
        except Exception as e:
            logger.error(f"Failed to save sent messages cache: {e}")

    def _compute_hash(self, content: str) -> str:
        """Compute SHA256 hash of message content."""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def should_send(self, content: str, force_send: bool = False) -> bool:
        """
        Check if a message should be sent based on content hash.

        Args:
            content: The message content to check
            force_send: If True, bypass the guard and always allow sending

        Returns:
            True if message should be sent, False if it's a duplicate
        """
        if force_send:
            logger.debug("Force send enabled, bypassing duplicate check")
            return True

        content_hash = self._compute_hash(content)

        if content_hash in self._sent_hashes:
            logger.info(f"Duplicate message detected (hash: {content_hash[:8]}...), skipping send")
            return False

        # Mark as sent
        self._sent_hashes.add(content_hash)
        self._save_cache()

        logger.debug(f"Message approved for sending (hash: {content_hash[:8]}...)")
        return True

    def mark_as_sent(self, content: str) -> None:
        """Manually mark content as sent (for external sends)."""
        content_hash = self._compute_hash(content)
        self._sent_hashes.add(content_hash)
        self._save_cache()
        logger.debug(f"Manually marked content as sent (hash: {content_hash[:8]}...)")

    def clear_cache(self) -> None:
        """Clear the sent messages cache."""
        self._sent_hashes.clear()
        try:
            if self.cache_path.exists():
                self.cache_path.unlink()
            logger.info("Sent messages cache cleared")
        except Exception as e:
            logger.warning(f"Failed to clear cache file: {e}")


# Global instance for easy access
_telegram_guard = TelegramSendGuard()


def should_send_telegram(content: str, force_send: bool = False) -> bool:
    """
    Convenience function to check if a Telegram message should be sent.

    Args:
        content: The message content to check
        force_send: If True, bypass the guard and always allow sending

    Returns:
        True if message should be sent, False if it's a duplicate
    """
    return _telegram_guard.should_send(content, force_send)


def mark_telegram_as_sent(content: str) -> None:
    """Manually mark Telegram content as sent."""
    _telegram_guard.mark_as_sent(content)


def clear_telegram_send_cache() -> None:
    """Clear the Telegram send cache."""
    _telegram_guard.clear_cache()


if __name__ == "__main__":
    # Test the send guard
    logging.basicConfig(level=logging.INFO)

    guard = TelegramSendGuard()

    # Test message
    test_msg = "##########OLP XDV#########\n==================================\n\n[Date]  Wed 02 Sep 2026   (PICK · win %  ·  alt markets)\n\n[League]  Bundesliga\n   18:30   Hoffenheim v Dortmund\n       O1.5 89%  ·  O2.5 73%  ·  O3.5 45%  ·  BTTS 65%\n   -> Stuttgart to win 68% (EV: -5.0%)"

    # First send should be allowed
    print(f"First send allowed: {guard.should_send(test_msg)}")

    # Second send should be blocked
    print(f"Second send allowed: {guard.should_send(test_msg)}")

    # Different content should be allowed
    different_msg = test_msg.replace("Hoffenheim v Dortmund", "Bayern v Wolfsburg")
    print(f"Different message allowed: {guard.should_send(different_msg)}")

    # Force send should work even for duplicates
    print(f"Force send allowed: {guard.should_send(test_msg, force_send=True)}")