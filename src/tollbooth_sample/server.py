"""Tollbooth Sample — Educational Weather Stats MCP Server.

This server demonstrates Tollbooth DPYC monetization with a real-world
weather API (Open-Meteo).  Standard DPYC tools (check_balance,
purchase_credits, Secure Courier, Oracle, pricing, constraints) are
provided by ``register_standard_tools`` from the tollbooth-dpyc wheel.
Only domain-specific weather tools are defined here.

Run locally:
    python -m tollbooth_sample.server

Deploy on FastMCP Cloud:
    See .fastmcp.yaml
"""

from __future__ import annotations

import logging
from typing import Annotated, Any

from pydantic import Field

from fastmcp import FastMCP

from tollbooth.tool_identity import ToolIdentity, STANDARD_IDENTITIES, capability_uuid
from tollbooth.runtime import OperatorRuntime, register_standard_tools
from tollbooth.credential_templates import CredentialTemplate, FieldSpec
from tollbooth.slug_tools import make_slug_tool

from tollbooth_sample import __version__

from tollbooth_sample import weather

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FastMCP app + slug decorator
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "tollbooth-sample",
    instructions=(
        "Weather Stats MCP Service — powered by Open-Meteo and monetized "
        "via Tollbooth DPYC Bitcoin Lightning micropayments.\n\n"
        "## Onboarding\n"
        "Call weather_get_operator_onboarding_status to check configuration readiness.\n"
        "1. Register with an Authority (provides Neon database automatically)\n"
        "2. Deliver operator secrets via Secure Courier:\n"
        "   - btcpay_host, btcpay_api_key, btcpay_store_id\n"
        "   Call weather_request_credential_channel to start.\n"
        "3. Once configured, the operator serves paid weather queries.\n\n"
        "## Pricing\n"
        "Tool prices are set dynamically by the operator's pricing model. "
        "Use `weather_check_price` to preview costs and `weather_check_balance` "
        "to see your balance. The Constraint Engine may apply discounts or "
        "surge pricing."
    ),
)
tool = make_slug_tool(mcp, "weather")

# ---------------------------------------------------------------------------
# Tool registry (domain tools only — standard identities are in the wheel)
# ---------------------------------------------------------------------------

_DOMAIN_TOOLS = [
    ToolIdentity(
        capability="get_current_weather",
        category="read",
        intent="Get current weather conditions",
    ),
    ToolIdentity(
        capability="get_weather_forecast",
        category="write",
        intent="Get weather forecast",
    ),
    ToolIdentity(
        capability="get_historical_weather",
        category="heavy",
        intent="Get historical weather data",
    ),
]

TOOL_REGISTRY: dict[str, ToolIdentity] = {ti.tool_id: ti for ti in _DOMAIN_TOOLS}

# ---------------------------------------------------------------------------
# OperatorRuntime — replaces all DPYC boilerplate
# ---------------------------------------------------------------------------

runtime = OperatorRuntime(
    tool_registry={**STANDARD_IDENTITIES, **TOOL_REGISTRY},
    operator_credential_template=CredentialTemplate(
        service="tollbooth-sample-operator",
        version=2,
        description="Operator credentials for BTCPay Lightning payments",
        fields={
            "btcpay_host": FieldSpec(
                required=True, sensitive=True,
                description=(
                    "The URL of your BTCPay Server instance "
                    "(e.g. https://btcpay.example.com)."
                ),
            ),
            "btcpay_api_key": FieldSpec(
                required=True, sensitive=True,
                description=(
                    "Your BTCPay Server API key. Generate one in "
                    "BTCPay under Account > Manage Account > API Keys."
                ),
            ),
            "btcpay_store_id": FieldSpec(
                required=True, sensitive=True,
                description=(
                    "Your BTCPay Store ID. Find it in BTCPay "
                    "under Stores > Settings > General."
                ),
            ),
        },
    ),
    operator_credential_greeting=(
        "Hi — I'm Tollbooth Sample, an educational weather stats "
        "MCP service. You (or your AI agent) requested a credential channel."
    ),
    service_name="Tollbooth Sample",
)

# ---------------------------------------------------------------------------
# Register all standard DPYC tools from the wheel
# ---------------------------------------------------------------------------

register_standard_tools(
    mcp,
    "weather",
    runtime,
    service_name="tollbooth-sample",
    service_version=__version__,
)


# ---------------------------------------------------------------------------
# Domain-specific MCP tools
# ---------------------------------------------------------------------------


@tool
@runtime.paid_tool(capability_uuid("get_current_weather"))
async def current(
    latitude: float, longitude: float, npub: Annotated[str, Field(description="Required. Your Nostr public key (npub1...) for credit billing.")] = "",
) -> dict[str, Any]:
    """Get current weather conditions for a location.

    Returns temperature, wind speed, and weather code from Open-Meteo.

    Args:
        latitude: Latitude (-90 to 90).
        longitude: Longitude (-180 to 180).
    """
    return await weather.get_current(latitude, longitude)


@tool
@runtime.paid_tool(capability_uuid("get_weather_forecast"))
async def forecast(
    latitude: float, longitude: float, days: int = 7, npub: Annotated[str, Field(description="Required. Your Nostr public key (npub1...) for credit billing.")] = "",
) -> dict[str, Any]:
    """Get a multi-day weather forecast for a location.

    Returns daily high/low temperatures and precipitation for 1-16 days.

    Args:
        latitude: Latitude (-90 to 90).
        longitude: Longitude (-180 to 180).
        days: Number of forecast days (1-16, default 7).
    """
    return await weather.get_forecast(latitude, longitude, days)


@tool
@runtime.paid_tool(capability_uuid("get_historical_weather"))
async def historical(
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str,
    npub: Annotated[str, Field(description="Required. Your Nostr public key (npub1...) for credit billing.")] = "",
) -> dict[str, Any]:
    """Get historical weather data for a location and date range.

    Returns daily temperature and precipitation from the Open-Meteo archive.

    Args:
        latitude: Latitude (-90 to 90).
        longitude: Longitude (-180 to 180).
        start_date: Start date (YYYY-MM-DD).
        end_date: End date (YYYY-MM-DD).
    """
    return await weather.get_historical(
        latitude, longitude, start_date, end_date,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Main entry point for the server."""
    from tollbooth import validate_operator_tools

    missing = validate_operator_tools(mcp, "weather")
    if missing:
        import sys

        print(
            f"\u26a0 Missing base-catalog tools: {', '.join(missing)}",
            file=sys.stderr,
        )
    mcp.run()


if __name__ == "__main__":
    main()
