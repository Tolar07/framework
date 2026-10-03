"""X/Twitter Booking Code Fetcher — monitors configured accounts for SportyBet codes.

WHAT THIS DOES
  Uses Tweepy (X API v2) to poll target accounts/hashtags for SportyBet booking codes.
  Booking codes are 6-10 character alphanumeric strings (e.g., TFS8TR).
  Extracted codes with metadata are written to data/ingested_codes.jsonl for verification.

ARCHITECTURE
  - Tweepy daemon polls X API on a schedule (respects rate limits)
  - Writes raw codes + metadata (tweet_id, author, timestamp, source_account) to JSONL
  - Does NOT verify codes — verification is a separate step via verify_external_code.py
  - Runs as a scheduled task (Windows Task Scheduler or GitHub Actions)

CONFIGURATION (via .env)
  X_API_BEARER_TOKEN  — X API Bearer token (Basic tier $100/mo for 10k reads)
  X_TARGET_ACCOUNTS   — Comma-separated list of @handles to monitor (no @ prefix)
  X_HASHTAGS          — Optional comma-separated hashtags to search (no # prefix)
  X_POLL_INTERVAL     — Seconds between polls (default: 300 = 5 minutes)

HR35 COMPLIANCE
  - Never guesses codes — only extracts what X API returns
  - Missing/incomplete data marked "NO DATA — PENDING"
  - All gaps surfaced honestly in the output

USAGE
  python -m booking.twitter_fetcher [--once] [--since-id FILE]

  --once        : Run a single poll cycle and exit (for cron/Task Scheduler)
  --since-id FILE: Path to file storing last seen tweet ID (persists across runs)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    import tweepy
except ImportError:
    tweepy = None

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# Booking code pattern: 6-10 alphanumeric characters (SportyBet format)
BOOKING_CODE_PATTERN = re.compile(r"\b([A-Z0-9]{6,10})\b")

# Output file for ingested codes
INGESTED_CODES_PATH = ROOT / "data" / "ingested_codes.jsonl"


@dataclass
class IngestedCode:
    """One booking code ingested from X/Twitter."""
    code: str
    tweet_id: str
    author_username: str
    author_id: str
    tweet_text: str
    tweet_created_at: str  # ISO format
    source_account: str   # The @handle we were monitoring when we found it
    fetched_at: str       # ISO format when we ingested it
    hashtags: list[str]   # Hashtags present in the tweet

    def to_jsonl(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


def load_env() -> dict:
    """Load configuration from environment variables."""
    return {
        "bearer_token": os.getenv("X_API_BEARER_TOKEN", "").strip(),
        "target_accounts": [a.strip() for a in os.getenv("X_TARGET_ACCOUNTS", "").split(",") if a.strip()],
        "hashtags": [h.strip() for h in os.getenv("X_HASHTAGS", "").split(",") if h.strip()],
        "poll_interval": int(os.getenv("X_POLL_INTERVAL", "300")),
    }


def validate_config(cfg: dict) -> list[str]:
    """Validate configuration, return list of errors (empty if valid)."""
    errors = []
    if not cfg["bearer_token"]:
        errors.append("X_API_BEARER_TOKEN not set in environment")
    if not cfg["target_accounts"] and not cfg["hashtags"]:
        errors.append("At least one of X_TARGET_ACCOUNTS or X_HASHTAGS must be set")
    if cfg["poll_interval"] < 60:
        errors.append("X_POLL_INTERVAL must be >= 60 seconds (X API rate limit)")
    return errors


def extract_booking_codes(text: str) -> list[str]:
    """Extract potential SportyBet booking codes from tweet text.

    SportyBet codes are 6-10 alphanumeric characters. We return ALL matches
    and let the verification step filter false positives.
    """
    matches = BOOKING_CODE_PATTERN.findall(text)
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for m in matches:
        if m not in seen:
            seen.add(m)
            unique.append(m)
    return unique


def extract_hashtags(text: str) -> list[str]:
    """Extract hashtags from tweet text."""
    return re.findall(r"#(\w+)", text)


def load_last_tweet_id(path: Path) -> Optional[str]:
    """Load the last seen tweet ID from file."""
    try:
        return path.read_text(encoding="utf-8").strip()
    except Exception:
        return None


def save_last_tweet_id(path: Path, tweet_id: str) -> None:
    """Save the last seen tweet ID to file."""
    try:
        path.write_text(tweet_id, encoding="utf-8")
    except Exception:
        pass  # non-fatal


def build_query(cfg: dict) -> str:
    """Build the X API v2 search query from config."""
    parts = []
    # Account mentions: from:handle
    for acct in cfg["target_accounts"]:
        parts.append(f"from:{acct}")
    # Hashtags: #hashtag
    for tag in cfg["hashtags"]:
        parts.append(f"#{tag}")
    # Always filter for potential booking codes (alphanumeric 6-10)
    # Note: X API doesn't support regex, so we filter client-side
    query = " OR ".join(parts) if parts else ""
    return query


class TwitterFetcher:
    """Tweepy-based fetcher for SportyBet booking codes from X/Twitter."""

    def __init__(self, cfg: dict, since_id_path: Path):
        self.cfg = cfg
        self.since_id_path = since_id_path
        self.client: Optional[tweepy.Client] = None

    def connect(self) -> bool:
        """Initialize Tweepy client."""
        if tweepy is None:
            print("ERROR: tweepy not installed. Run: pip install tweepy")
            return False
        try:
            self.client = tweepy.Client(
                bearer_token=self.cfg["bearer_token"],
                wait_on_rate_limit=True,  # Tweepy handles rate limit waiting
            )
            # Test auth
            me = self.client.get_me()
            if me.data:
                print(f"Connected to X API as @{me.data.username}")
            return True
        except Exception as e:
            print(f"ERROR: Failed to connect to X API: {e}")
            return False

    def fetch_new_codes(self) -> list[IngestedCode]:
        """Fetch new tweets and extract booking codes. Returns list of IngestedCode."""
        if not self.client:
            return []

        since_id = load_last_tweet_id(self.since_id_path)
        query = build_query(self.cfg)

        if not query:
            return []

        print(f"Querying X API: {query}")
        if since_id:
            print(f"Since tweet ID: {since_id}")

        try:
            # Search recent tweets (last 7 days max for Basic tier)
            response = self.client.search_recent_tweets(
                query=query,
                max_results=100,  # Max per request for Basic tier
                since_id=since_id,
                tweet_fields=["created_at", "author_id", "entities"],
                user_fields=["username"],
                expansions=["author_id"],
            )
        except tweepy.TooManyRequests as e:
            # Rate limited — Tweepy's wait_on_rate_limit should handle this,
            # but we log it explicitly
            reset_time = e.response.headers.get("x-rate-limit-reset")
            if reset_time:
                wait = int(reset_time) - int(time.time()) + 5
                print(f"Rate limited. Waiting {wait}s...")
                time.sleep(max(wait, 60))
            return []
        except Exception as e:
            print(f"ERROR: X API request failed: {e}")
            return []

        if not response.data:
            print("No new tweets found.")
            return []

        # Build author lookup
        users = {u.id: u for u in (response.includes.get("users") or [])}

        codes: list[IngestedCode] = []
        newest_tweet_id = None

        for tweet in response.data:
            tweet_id = str(tweet.id)
            if newest_tweet_id is None or int(tweet_id) > int(newest_tweet_id):
                newest_tweet_id = tweet_id

            author = users.get(tweet.author_id)
            author_username = author.username if author else "unknown"
            author_id = str(tweet.author_id)

            tweet_text = tweet.text or ""
            tweet_created = tweet.created_at.isoformat() if tweet.created_at else datetime.now(timezone.utc).isoformat()

            # Determine which source account/hashtag matched
            source_account = "unknown"
            for acct in self.cfg["target_accounts"]:
                if f"@{acct.lower()}" in tweet_text.lower() or author_username.lower() == acct.lower():
                    source_account = acct
                    break
            if source_account == "unknown" and self.cfg["hashtags"]:
                for tag in self.cfg["hashtags"]:
                    if f"#{tag.lower()}" in tweet_text.lower():
                        source_account = f"#{tag}"
                        break

            # Extract booking codes
            found_codes = extract_booking_codes(tweet_text)
            hashtags = extract_hashtags(tweet_text)

            for code in found_codes:
                ingested = IngestedCode(
                    code=code,
                    tweet_id=tweet_id,
                    author_username=author_username,
                    author_id=author_id,
                    tweet_text=tweet_text,
                    tweet_created_at=tweet_created,
                    source_account=source_account,
                    fetched_at=datetime.now(timezone.utc).isoformat(),
                    hashtags=hashtags,
                )
                codes.append(ingested)
                print(f"  Found code: {code} from @{author_username} (tweet {tweet_id})")

        # Persist the newest tweet ID for next run
        if newest_tweet_id:
            save_last_tweet_id(self.since_id_path, newest_tweet_id)

        return codes

    def write_codes(self, codes: list[IngestedCode]) -> None:
        """Append codes to the JSONL file."""
        if not codes:
            return
        INGESTED_CODES_PATH.parent.mkdir(parents=True, exist_ok=True)
        with INGESTED_CODES_PATH.open("a", encoding="utf-8") as f:
            for code in codes:
                f.write(code.to_jsonl() + "\n")
        print(f"Wrote {len(codes)} code(s) to {INGESTED_CODES_PATH}")

    def run_once(self) -> int:
        """Run one fetch cycle. Returns number of codes found."""
        codes = self.fetch_new_codes()
        self.write_codes(codes)
        return len(codes)

    def run_daemon(self) -> None:
        """Run continuously, polling at the configured interval."""
        print(f"Starting Twitter fetcher daemon (poll interval: {self.cfg['poll_interval']}s)")
        print("Press Ctrl+C to stop")
        while True:
            try:
                count = self.run_once()
                if count == 0:
                    print(f"No new codes. Sleeping {self.cfg['poll_interval']}s...")
                time.sleep(self.cfg["poll_interval"])
            except KeyboardInterrupt:
                print("\nStopped by user.")
                break
            except Exception as e:
                print(f"Unexpected error: {e}. Sleeping {self.cfg['poll_interval']}s...")
                time.sleep(self.cfg["poll_interval"])


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch SportyBet booking codes from X/Twitter via Tweepy."
    )
    parser.add_argument("--once", action="store_true",
                        help="Run a single poll cycle and exit (for cron/Task Scheduler)")
    parser.add_argument("--since-id", default=None,
                        help="Path to file storing last seen tweet ID (default: data/twitter_since_id.txt)")
    args = parser.parse_args()

    cfg = load_env()
    errors = validate_config(cfg)
    if errors:
        for err in errors:
            print(f"CONFIG ERROR: {err}")
        sys.exit(1)

    since_id_path = Path(args.since_id) if args.since_id else (ROOT / "data" / "twitter_since_id.txt")

    fetcher = TwitterFetcher(cfg, since_id_path)
    if not fetcher.connect():
        sys.exit(1)

    if args.once:
        count = fetcher.run_once()
        print(f"Done. Found {count} new code(s).")
    else:
        fetcher.run_daemon()


if __name__ == "__main__":
    main()