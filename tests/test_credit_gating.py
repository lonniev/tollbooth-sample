"""Unit tests for the debit/rollback and constraint gating logic."""

from __future__ import annotations

import pytest

from tollbooth import ToolTier, UserLedger
from tollbooth_sample.server import TOOL_COSTS


def test_tool_costs_match_tiers():
    """TOOL_COSTS values align with ToolTier enum members."""
    assert TOOL_COSTS["current"] == ToolTier.READ == 1
    assert TOOL_COSTS["forecast"] == ToolTier.WRITE == 5
    assert TOOL_COSTS["historical"] == ToolTier.HEAVY == 10
    assert TOOL_COSTS["check_balance"] == ToolTier.FREE == 0
    assert TOOL_COSTS["purchase_credits"] == ToolTier.FREE == 0
    assert TOOL_COSTS["check_payment"] == ToolTier.FREE == 0
    assert TOOL_COSTS["check_price"] == ToolTier.FREE == 0
    assert TOOL_COSTS["service_status"] == ToolTier.FREE == 0


def test_debit_success(funded_ledger: UserLedger):
    """Debit succeeds when balance is sufficient."""
    assert funded_ledger.balance_api_sats == 100
    ok = funded_ledger.debit("current", ToolTier.READ)
    assert ok is True
    assert funded_ledger.balance_api_sats == 99


def test_debit_insufficient(empty_ledger: UserLedger):
    """Debit fails on zero balance."""
    ok = empty_ledger.debit("current", ToolTier.READ)
    assert ok is False
    assert empty_ledger.balance_api_sats == 0


def test_rollback_restores_balance(funded_ledger: UserLedger):
    """Rollback creates a compensating tranche."""
    funded_ledger.debit("forecast", ToolTier.WRITE)
    assert funded_ledger.balance_api_sats == 95

    funded_ledger.rollback_debit("forecast", ToolTier.WRITE)
    assert funded_ledger.balance_api_sats == 100


def test_heavy_tool_cost(funded_ledger: UserLedger):
    """HEAVY tier costs 10 api_sats per call."""
    funded_ledger.debit("historical", ToolTier.HEAVY)
    assert funded_ledger.balance_api_sats == 90


def test_free_tools_dont_debit(funded_ledger: UserLedger):
    """FREE tier tools cost nothing — balance stays the same."""
    initial = funded_ledger.balance_api_sats
    for tool_name in ("check_balance", "purchase_credits", "check_payment", "service_status"):
        cost = TOOL_COSTS[tool_name]
        assert cost == 0, f"{tool_name} should be free"
    assert funded_ledger.balance_api_sats == initial


def test_constraint_gate_disabled_by_default():
    """ConstraintGate returns base cost when disabled."""
    from tollbooth import ConstraintGate, TollboothConfig

    config = TollboothConfig(constraints_enabled=False)
    gate = ConstraintGate(config)

    assert not gate.enabled

    ledger = UserLedger()
    ledger.credit_deposit(100, "inv-1")
    denial, effective = gate.check("current", ToolTier.READ, ledger)
    assert denial is None
    assert effective == ToolTier.READ


def test_constraint_gate_with_free_trial():
    """ConstraintGate applies free trial (cost → 0) when enabled."""
    import json

    from tollbooth import ConstraintGate, TollboothConfig

    config_json = json.dumps({
        "tool_constraints": {
            "current": {
                "constraints": [
                    {"type": "free_trial", "first_n_free": 5}
                ]
            }
        }
    })
    config = TollboothConfig(
        constraints_enabled=True,
        constraints_config=config_json,
    )
    gate = ConstraintGate(config)
    assert gate.enabled

    ledger = UserLedger()
    ledger.credit_deposit(100, "inv-1")

    # First call should be free (within trial)
    denial, effective = gate.check(
        "current", ToolTier.READ, ledger, invocation_count=0
    )
    assert denial is None
    assert effective == 0
