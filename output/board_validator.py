"""
BOARD VALIDATOR — Filters board fixtures for Telegram delivery and THE CALL.

Two bugs this fixes (Architect 2026-09-01):
1. Negative EV picks were appearing in "RECOMMENDED — THE CALL" (violating the
   "wide eyes, narrow hands" design — narrow hands means ONLY positive-edge
   picks reach the call).
2. A self-flagged implausible pick (ID403.1 V5 divergence) appeared in the
   recommended table without visible warning flags.

This module provides:
- `validate_the_call(board)` — filters a board to only positive-EV,
  non-divergence-flagged fixtures for THE CALL table and compact Telegram output.
- `chunk_for_telegram(text, limit=4096)` — proper Telegram chunking on line
  boundaries with fence balancing, replacing notify._chunk() which split on
  blank lines and could break mid-table.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, List, Tuple


def validate_the_call(board: List[BoardFixture]) -> List[BoardFixture]:
    """
    Filter board fixtures for THE CALL — the "narrow hands" shortlist.

    Only fixtures that satisfy ALL of:
      - Has model probabilities (bf.probs is not None)
      - Has a best_market with a live price (bf.best_price is not None)
      - Positive expected value (bf.best_mes_ev > 0)
      - No engine divergence flag (bf.engine_divergence is None)
      - No goals divergence flag (bf.goals_divergence is None)
      - No ID403.1 V5 divergence flag (bf.best_mes_ev is not None and
        abs(bf.best_mes_ev) < 0.15 — the implausible EV threshold)

    Returns a new list containing only fixtures that pass all gates.
    This is the "wide eyes, narrow hands" filter — the board sees everything,
    THE CALL only sees the clean positive-edge picks.
    """
    filtered = []
    for bf in board:
        if bf.probs is None:
            continue
        if bf.best_market is None or bf.best_price is None:
            continue
        if bf.best_mes_ev is None or bf.best_mes_ev <= 0:
            continue
        if bf.engine_divergence is not None:
            continue
        if bf.goals_divergence is not None:
            continue
        # ID403.1 V5 implausible EV gate (extension beyond ratified V5)
        if bf.best_mes_ev is not None and abs(bf.best_mes_ev) >= 0.15:
            continue
        filtered.append(bf)
    return filtered


def _balance_fences(chunk: str) -> str:
    """Close a code fence left open at the end of a chunk.

    Splitting mid-fence leaves one message with an unclosed ``` and the next
    with an orphan closer. Both then render as broken plain text and the whole
    point of the table — aligned columns — is lost."""
    FENCE = "```"
    return chunk + f"\n{FENCE}" if chunk.count(FENCE) % 2 else chunk


def chunk_for_telegram(text: str, limit: int = 4096) -> List[str]:
    """
    Split text into Telegram-safe chunks on LINE boundaries.

    Key differences from notify._chunk():
    - Splits on '\n' (line boundaries), never mid-line
    - Keeps code fences balanced (opens/closes ``` per chunk)
    - Guarantees each chunk <= limit (Telegram hard limit is 4096)
    - Never splits a table row — each line is atomic

    This ensures TABLE 1 (layer 2 grid), TABLE 2 (deploy singles),
    TABLE 3 (accas), TABLE 4 (the pick) all render as complete tables
    on the phone, never truncated mid-row.

    Args:
        text: Full board text to chunk
        limit: Max characters per chunk (default 4096, Telegram hard limit)

    Returns:
        List of chunk strings, each <= limit, fences balanced.
    """
    if len(text) <= limit:
        return [text]

    chunks: List[str] = []
    current: str = ""
    in_fence: bool = False
    FENCE = "```"

    for line in text.split("\n"):
        # Room for a closing fence if we're inside one
        room = limit - (len(FENCE) + 1 if in_fence else 0)
        if len(current) + len(line) + 1 > room and current:
            # Close the current chunk with balanced fences
            if in_fence:
                current = current.rstrip() + f"\n{FENCE}"
            chunks.append(current.rstrip())
            current = f"{FENCE}\n" if in_fence else ""
        current += line + "\n"
        if line.strip() == FENCE:
            in_fence = not in_fence

    if current.strip():
        if in_fence:
            current = current.rstrip() + f"\n{FENCE}"
        chunks.append(current.rstrip())

    return chunks


def filter_board_for_telegram(board: List[BoardFixture], target_date: Optional[str] = None) -> List[BoardFixture]:
    """
    Filter board for compact Telegram heartbeat output (compact=True path).

    This is a lighter filter than validate_the_call() — it keeps all rated
    fixtures (probs not None) for the league-grouped heartbeat format,
    but drops unrated fixtures entirely (HR35: never fabricate, but also
    don't pollute the phone with NO DATA rows).

    Args:
        board: Full board fixture list
        target_date: Optional ISO date string to filter by kickoff_date

    Returns:
        Filtered list suitable for render_compact_heartbeat()
    """
    from datetime import date
    if target_date is None:
        target_date = date.today().isoformat()

    filtered = [bf for bf in board if bf.probs is not None and bf.kickoff_date == target_date]
    return filtered