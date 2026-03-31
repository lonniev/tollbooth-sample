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

from tollbooth import ToolTier
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
        "Paid tools: weather_current (1 sat), weather_forecast (5 sats), "
        "weather_historical (10 sats). Prices are base rates — the "
        "Constraint Engine may apply discounts or surge pricing.\n"
        "Free tools: weather_check_balance, weather_purchase_credits, "
        "weather_check_payment, weather_check_price, weather_service_status, "
        "weather_get_operator_onboarding_status."
    ),
)
tool = make_slug_tool(mcp, "weather")

# ---------------------------------------------------------------------------
# Tool cost map (domain tools only — standard tool costs are in the runtime)
# ---------------------------------------------------------------------------

TOOL_COSTS: dict[str, int] = {
    "current": ToolTier.READ,
    "forecast": ToolTier.WRITE,
    "historical": ToolTier.HEAVY,
}

# ---------------------------------------------------------------------------
# OperatorRuntime — replaces all DPYC boilerplate
# ---------------------------------------------------------------------------

runtime = OperatorRuntime(
    tool_costs=TOOL_COSTS,
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
@runtime.paid_tool("current")
async def current(
    latitude: float, longitude: float, npub: Annotated[str, Field(description="Required. Your Nostr public key (npub1...) for credit billing.")] = "",
) -> dict[str, Any]:
    """Get current weather conditions for a location.

    Returns temperature, wind speed, and weather code from Open-Meteo.
    Cost: 1 api_sat (READ tier).

    Args:
        latitude: Latitude (-90 to 90).
        longitude: Longitude (-180 to 180).
    """
    return await weather.get_current(latitude, longitude)


@tool
@runtime.paid_tool("forecast")
async def forecast(
    latitude: float, longitude: float, days: int = 7, npub: Annotated[str, Field(description="Required. Your Nostr public key (npub1...) for credit billing.")] = "",
) -> dict[str, Any]:
    """Get a multi-day weather forecast for a location.

    Returns daily high/low temperatures and precipitation for 1-16 days.
    Cost: 5 api_sats (WRITE tier).

    Args:
        latitude: Latitude (-90 to 90).
        longitude: Longitude (-180 to 180).
        days: Number of forecast days (1-16, default 7).
    """
    return await weather.get_forecast(latitude, longitude, days)


@tool
@runtime.paid_tool("historical")
async def historical(
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str,
    npub: Annotated[str, Field(description="Required. Your Nostr public key (npub1...) for credit billing.")] = "",
) -> dict[str, Any]:
    """Get historical weather data for a location and date range.

    Returns daily temperature and precipitation from the Open-Meteo archive.
    Cost: 10 api_sats (HEAVY tier).

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
