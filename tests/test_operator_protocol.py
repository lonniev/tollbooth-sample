"""OperatorProtocol conformance test.

Verifies that SampleOperator satisfies the runtime-checkable
OperatorProtocol from tollbooth-dpyc.
"""

from __future__ import annotations

from tollbooth.operator_protocol import OperatorProtocol

from tollbooth_sample.server import DOMAIN_CATALOG, SampleOperator


def test_isinstance_check():
    """SampleOperator passes isinstance(obj, OperatorProtocol)."""
    op = SampleOperator()
    assert isinstance(op, OperatorProtocol)


def test_slug():
    """Slug is 'weather'."""
    assert SampleOperator().slug == "weather"


def test_tool_catalog_includes_base():
    """tool_catalog includes base catalog + domain tools."""
    catalog = SampleOperator.tool_catalog()
    names = [t.tool_name for t in catalog]

    # Base catalog tools
    assert "check_balance" in names
    assert "purchase_credits" in names
    assert "check_payment" in names
    assert "service_status" in names
    assert "session_status" in names
    assert "how_to_join" in names

    # Domain tools
    assert "current" in names
    assert "forecast" in names
    assert "historical" in names
    assert "check_price" in names


def test_tool_catalog_includes_domain():
    """Domain catalog entries have correct cost tiers."""
    domain_by_name = {t.tool_name: t for t in DOMAIN_CATALOG}

    assert domain_by_name["current"].cost_tier == "READ"
    assert domain_by_name["forecast"].cost_tier == "WRITE"
    assert domain_by_name["historical"].cost_tier == "HEAVY"
    assert domain_by_name["check_price"].cost_tier == "FREE"
