"""
HEARTBEAT STAKING — Compounding staking logic for heartbeat tracker.

Paper-mode only: this calculates theoretical stake progression for the
single daily heartbeat pick. No real capital is routed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional

from output.heartbeat import get_heartbeat_stats, HeartbeatFixture


@dataclass
class StakeState:
    """Current staking state for heartbeat compounding."""
    current_stake: float
    bankroll: float
    wins: int
    losses: int
    total: int
    win_rate: float
    last_result: Optional[str]  # 'WIN', 'LOSS', or None


# Configuration (paper-mode constants — not protected constants)
DEFAULT_STARTING_BANKROLL = 100.0
DEFAULT_STARTING_STAKE = 1.0
KELLY_FRACTION = 0.25  # Conservative quarter-Kelly
MIN_STAKE = 0.10
MAX_STAKE_PCT = 0.05  # Max 5% of bankroll per bet


def calculate_next_stake(
    current_bankroll: float,
    current_stake: float,
    edge: float,
    probability: float,
    price: float,
    kelly_fraction: float = KELLY_FRACTION
) -> float:
    """
    Calculate next stake using fractional Kelly criterion.

    Kelly % = (bp - q) / b where:
      - b = decimal odds - 1 (net profit per unit staked)
      - p = probability of win
      - q = 1 - p

    We apply a conservative fraction (default 0.25 = quarter-Kelly).
    """
    if price <= 1.0 or probability <= 0.0 or probability >= 1.0:
        return MIN_STAKE

    b = price - 1.0
    p = probability
    q = 1.0 - p

    kelly_pct = (b * p - q) / b
    kelly_pct = max(0.0, kelly_pct)  # No negative Kelly

    fractional_kelly = kelly_pct * kelly_fraction
    stake = current_bankroll * fractional_kelly

    # Clamp to limits
    max_stake = current_bankroll * MAX_STAKE_PCT
    stake = max(MIN_STAKE, min(stake, max_stake))

    return round(stake, 2)


def update_stake_on_result(
    current_bankroll: float,
    current_stake: float,
    result: str,  # 'WIN' or 'LOSS'
    price: float
) -> tuple[float, float]:
    """
    Update bankroll and stake based on result.

    Returns:
        (new_bankroll, new_stake)
    """
    if result == 'WIN':
        profit = current_stake * (price - 1.0)
        new_bankroll = current_bankroll + profit
    elif result == 'LOSS':
        new_bankroll = current_bankroll - current_stake
    else:
        return current_bankroll, current_stake

    # Stake for next bet is recalculated from new bankroll
    # (will be computed fresh on next heartbeat with its edge/prob/price)
    return round(new_bankroll, 2), current_stake


def get_stake_state() -> StakeState:
    """
    Get current staking state from heartbeat history.

    Reconstructs bankroll by replaying all historical results.
    """
    stats = get_heartbeat_stats()

    # Replay history to get current bankroll
    history_file = Path("data/heartbeat/history.jsonl")
    if not history_file.exists():
        return StakeState(
            current_stake=DEFAULT_STARTING_STAKE,
            bankroll=DEFAULT_STARTING_BANKROLL,
            wins=0,
            losses=0,
            total=0,
            win_rate=0.0,
            last_result=None
        )

    bankroll = DEFAULT_STARTING_BANKROLL
    last_result = None
    last_price = 0.0
    last_edge = 0.0
    last_prob = 0.0

    import json
    with history_file.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            record = json.loads(line)
            result = record.get("result")
            price = record.get("price") or 0.0
            edge = record.get("edge") or 0.0
            prob = record.get("probability") or 0.0

            if result in ("WIN", "LOSS"):
                bankroll, _ = update_stake_on_result(bankroll, DEFAULT_STARTING_STAKE, result, price)
                last_result = result
                last_price = price
                last_edge = edge
                last_prob = prob

    # Next stake would be calculated from current bankroll + next heartbeat's edge/prob/price
    current_stake = calculate_next_stake(
        bankroll, DEFAULT_STARTING_STAKE, last_edge, last_prob, last_price
    ) if last_price > 0 else DEFAULT_STARTING_STAKE

    return StakeState(
        current_stake=current_stake,
        bankroll=bankroll,
        wins=stats["wins"],
        losses=stats["losses"],
        total=stats["total"],
        win_rate=stats["win_rate"],
        last_result=last_result
    )


def render_stake_report(state: StakeState, next_heartbeat: Optional[HeartbeatFixture] = None) -> str:
    """Render a stake progression report for Telegram/logging."""
    lines = [
        "💰 HEARTBEAT STAKING REPORT",
        f"📊 Bankroll: {state.bankroll:.2f} (start: {DEFAULT_STARTING_BANKROLL:.2f})",
        f"🎯 Current Stake: {state.current_stake:.2f}",
        f"📈 Record: {state.wins}W - {state.losses}L ({state.win_rate:.0%})",
    ]

    if state.last_result:
        lines.append(f"📍 Last: {state.last_result}")

    if next_heartbeat:
        next_stake = calculate_next_stake(
            state.bankroll, state.current_stake,
            next_heartbeat.edge, next_heartbeat.probability,
            next_heartbeat.price or 0.0
        )
        lines.append(f"🔮 Next Stake (proj.): {next_stake:.2f}")
        lines.append(f"   {next_heartbeat.fixture} — {next_heartbeat.pick} @ {next_heartbeat.price}")

    pnl = state.bankroll - DEFAULT_STARTING_BANKROLL
    pnl_sign = "+" if pnl >= 0 else ""
    lines.append(f"💵 P&L: {pnl_sign}{pnl:.2f}")

    return "\n".join(lines)


def send_loss_alert(heartbeat: HeartbeatFixture, state: StakeState) -> None:
    """
    Send a loss alert via Telegram notify system.
    """
    try:
        from output import notify

        body = (
            f"🚨 HEARTBEAT LOSS ALERT\n\n"
            f"Fixture: {heartbeat.fixture}\n"
            f"Pick: {heartbeat.pick} ({round(heartbeat.probability * 100)}%)\n"
            f"Price: {heartbeat.price}\n"
            f"Edge: {round(heartbeat.edge * 100, 1)}%\n\n"
            f"Stake State After Loss:\n"
            f"  Bankroll: {state.bankroll:.2f}\n"
            f"  Next Stake: {state.current_stake:.2f}\n"
            f"  Record: {state.wins}W-{state.losses}L"
        )

        # Use alert channel (gated by TELEGRAM_ALERTS_ENABLED)
        notify.send_alert(body)
    except Exception:
        # Fail silently — alert is best-effort
        pass


def process_heartbeat_result(
    heartbeat: HeartbeatFixture,
    result: str  # 'WIN' or 'LOSS'
) -> StakeState:
    """
    Process a heartbeat result and return updated stake state.

    This should be called after the match result is known.
    """
    from output.heartbeat import save_heartbeat_record

    # Record result in history
    save_heartbeat_record(heartbeat, result=result)

    # Get updated state
    state = get_stake_state()

    # Send alert on loss
    if result == 'LOSS':
        send_loss_alert(heartbeat, state)

    return state


if __name__ == "__main__":
    # Demo: show current state
    state = get_stake_state()
    print(render_stake_report(state))