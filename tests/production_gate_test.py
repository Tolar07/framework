"""
Tests for the --only-production delivery gate in run_daily.

Offline, plain-script style. _has_production decides whether a run's board is
worth pushing to Telegram: a deploy-eligible pick or a newly logged paper leg
counts as production; an empty NO-DATA slate does not.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from run_daily import _has_production


class _BF:
    """Minimal stand-in for a BoardFixture — only the field the gate reads."""
    def __init__(self, on_deploy_shortlist: bool):
        self.on_deploy_shortlist = on_deploy_shortlist


def test_empty_slate_is_not_production() -> None:
    board = [_BF(False), _BF(False)]
    assert _has_production(board, logged_count=0) is False
    assert _has_production([], logged_count=0) is False


def test_deploy_eligible_pick_is_production() -> None:
    board = [_BF(False), _BF(True)]
    assert _has_production(board, logged_count=0) is True


def test_new_leg_is_production_even_without_shortlist() -> None:
    board = [_BF(False)]
    assert _has_production(board, logged_count=1) is True


def test_delivery_decision_matrix() -> None:
    # deliver_now = send and (produced or not only_production) — mirror the gate.
    def deliver_now(send, only_production, produced):
        return send and (produced or not only_production)

    assert deliver_now(True, True, True) is True      # production-only, produced -> send
    assert deliver_now(True, True, False) is False     # production-only, empty -> hold
    assert deliver_now(True, False, False) is True     # send-always, empty -> send
    assert deliver_now(False, True, True) is False     # --no-send wins regardless


def main() -> None:
    test_empty_slate_is_not_production()
    test_deploy_eligible_pick_is_production()
    test_new_leg_is_production_even_without_shortlist()
    test_delivery_decision_matrix()
    print("production_gate_test: OK")


if __name__ == "__main__":
    main()
