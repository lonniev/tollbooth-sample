"""Tollbooth Sample — Educational Weather Stats MCP Server.

This server demonstrates Tollbooth DPYC monetization with a real-world
weather API (Open-Meteo).  Standard DPYC tools (check_balance,
purchase_credits, Secure Courier, Oracle, pricing) are provided by
``register_standard_tools`` from the tollbooth-dpyc wheel.  Only
domain-specific weather tools are defined here.

Run locally:
    python -m tollbooth_sample.server

Deploy on FastMCP Cloud:
    See .fastmcp.yaml
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any

from fastmcp import FastMCP

from tollbooth import (
    BTCPayClient,
    ConstraintGate,
    ECOSYSTEM_LINKS,
    ToolTier,
)
from tollbooth.runtime import OperatorRuntime, register_standard_tools, resolve_npub
from tollbooth.credential_templates import CredentialTemplate, FieldSpec
from tollbooth.slug_tools import make_slug_tool
from tollbooth.tools import credits

from tollbooth_sample import __version__
from tollbooth_sample.config import Settings, get_settings
from tollbooth_sample import weather

logger = logging.getLogger(__name__)

# Process identity — set once at module load, survives for process lifetime
_process_boot_time = datetime.now(timezone.utc)

# ---------------------------------------------------------------------------
# FastMCP app + slug decorator
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "tollbooth-sample",
    instructions=(
        "Weather Stats MCP Service — powered by Open-Meteo and monetized "
        "via Tollbooth DPYC Bitcoin Lightning micropayments.\n\n"
        "## Onboarding\n"
        "Call weather_get_onboarding_status to check configuration readiness.\n"
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
        "weather_get_onboarding_status."
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
    "check_price": ToolTier.FREE,
    "list_constraint_types": ToolTier.FREE,
}

CREDENTIAL_SERVICE = "tollbooth-sample-operator"

# ---------------------------------------------------------------------------
# OperatorRuntime — replaces all DPYC boilerplate
# ---------------------------------------------------------------------------

runtime = OperatorRuntime(
    tool_costs=TOOL_COSTS,
    credential_service=CREDENTIAL_SERVICE,
    credential_template=CredentialTemplate(
        service="tollbooth-sample",
        version=1,
        description="Operator credentials for BTCPay Lightning payments",
        fields={
            "btcpay_host": FieldSpec(required=True, sensitive=True),
            "btcpay_api_key": FieldSpec(required=True, sensitive=True),
            "btcpay_store_id": FieldSpec(required=True, sensitive=True),
        },
    ),
)

# ---------------------------------------------------------------------------
# Register all 20 standard DPYC tools from the wheel
# ---------------------------------------------------------------------------

register_standard_tools(
    mcp,
    "weather",
    runtime,
    settings_fn=get_settings,
    service_name="tollbooth-sample",
    service_version=__version__,
)

# ---------------------------------------------------------------------------
# Module-level singletons (domain-specific only)
# ---------------------------------------------------------------------------

_btcpay_client: BTCPayClient | None = None
_gate: ConstraintGate | None = None
_gate_initialized: bool = False


def _get_current_user_id() -> str | None:
    """Return the FastMCP Cloud user ID, or None in STDIO mode."""
    try:
        from fastmcp.server.dependencies import get_http_headers

        headers = get_http_headers(include_all=True)
        return headers.get("fastmcp-cloud-user")
    except Exception:
        return None


async def _ensure_btcpay() -> BTCPayClient:
    """Load BTCPay config from credential vault (primary) or env vars (legacy)."""
    global _btcpay_client
    if _btcpay_client is not None:
        return _btcpay_client

    creds = await runtime.load_credentials(
        ["btcpay_host", "btcpay_api_key", "btcpay_store_id"]
    )

    host = creds.get("btcpay_host")
    api_key = creds.get("btcpay_api_key")
    store_id = creds.get("btcpay_store_id")

    if not all([host, api_key, store_id]):
        raise ValueError(
            "BTCPay not configured. Deliver btcpay_host, btcpay_api_key, "
            "btcpay_store_id via Secure Courier (request_credential_channel)."
        )

    _btcpay_client = BTCPayClient(host=host, api_key=api_key, store_id=store_id)
    return _btcpay_client


def _get_gate() -> ConstraintGate | None:
    """Return the ConstraintGate singleton, or None if constraints are off."""
    global _gate, _gate_initialized
    if _gate_initialized:
        return _gate
    settings = get_settings()
    config = settings.to_tollbooth_config()
    if config.constraints_enabled:
        _gate = ConstraintGate(config)
    _gate_initialized = True
    return _gate


# ---------------------------------------------------------------------------
# Demand tracking helpers (domain-specific, uses runtime.vault())
# ---------------------------------------------------------------------------


def _demand_window_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:00")


async def _get_global_demand(tool_name: str) -> dict[str, int]:
    try:
        vault = await runtime.vault()
        count = await vault.get_demand(tool_name, _demand_window_key())
        return {tool_name: count}
    except Exception:
        return {}


def _fire_and_forget_demand_increment(tool_name: str) -> None:
    async def _increment() -> None:
        try:
            vault = await runtime.vault()
            await vault.increment_demand(tool_name, _demand_window_key())
        except Exception:
            pass

    asyncio.create_task(_increment())


# ---------------------------------------------------------------------------
# Low-balance warning helper
# ---------------------------------------------------------------------------


async def _with_warning(result: dict[str, Any], npub: str = "") -> dict[str, Any]:
    """Append low_balance_warning to the result if balance is running low."""
    if not _get_current_user_id():
        return result
    try:
        npub = resolve_npub(npub)
        cache = await runtime.ledger_cache()
        warning = credits.compute_low_balance_warning(await cache.get(npub))
        if warning:
            result["low_balance_warning"] = warning
    except Exception:
        pass
    return result


# ---------------------------------------------------------------------------
# Domain-specific MCP tools
# ---------------------------------------------------------------------------


@tool
async def current(latitude: float, longitude: float, npub: str = "") -> dict[str, Any]:
    """Get current weather conditions for a location.

    Returns temperature, wind speed, and weather code from Open-Meteo.
    Cost: 1 api_sat (READ tier).

    Args:
        latitude: Latitude (-90 to 90).
        longitude: Longitude (-180 to 180).
    """
    err = await runtime.debit_or_error("current", npub)
    if err:
        return err
    try:
        result = await weather.get_current(latitude, longitude)
        return await _with_warning(result, npub=npub)
    except Exception as e:
        await runtime.rollback_debit("current", npub)
        return {"success": False, "error": str(e)}


@tool
async def forecast(
    latitude: float, longitude: float, days: int = 7, npub: str = ""
) -> dict[str, Any]:
    """Get a multi-day weather forecast for a location.

    Returns daily high/low temperatures and precipitation for 1-16 days.
    Cost: 5 api_sats (WRITE tier).

    Args:
        latitude: Latitude (-90 to 90).
        longitude: Longitude (-180 to 180).
        days: Number of forecast days (1-16, default 7).
    """
    err = await runtime.debit_or_error("forecast", npub)
    if err:
        return err
    try:
        result = await weather.get_forecast(latitude, longitude, days)
        return await _with_warning(result, npub=npub)
    except Exception as e:
        await runtime.rollback_debit("forecast", npub)
        return {"success": False, "error": str(e)}


@tool
async def historical(
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str,
    npub: str = "",
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
    err = await runtime.debit_or_error("historical", npub)
    if err:
        return err
    try:
        result = await weather.get_historical(latitude, longitude, start_date, end_date)
        return await _with_warning(result, npub=npub)
    except Exception as e:
        await runtime.rollback_debit("historical", npub)
        return {"success": False, "error": str(e)}


@tool
async def check_price(tool_name: str, npub: str = "") -> dict[str, Any]:
    """Preview the effective cost of a tool call.

    Shows the base cost and any constraint effects (discounts, free trials).
    Free — no credits required.

    Args:
        tool_name: The tool to check (e.g. "current", "forecast", "historical").
    """
    base_cost = TOOL_COSTS.get(tool_name)
    if base_cost is None:
        return {
            "success": False,
            "error": f"Unknown tool: {tool_name}. Valid: {list(TOOL_COSTS.keys())}",
        }

    result: dict[str, Any] = {
        "success": True,
        "tool_name": tool_name,
        "base_cost_api_sats": int(base_cost),
        "effective_cost_api_sats": int(base_cost),
        "constraints_enabled": False,
        "constraint_effects": [],
    }

    gate = _get_gate()
    if gate and gate.enabled and base_cost > 0:
        result["constraints_enabled"] = True
        try:
            resolved = resolve_npub(npub)
            cache = await runtime.ledger_cache()
            ledger = await cache.get(resolved)
            demand = await _get_global_demand(tool_name)
            denial, effective = gate.check(
                tool_name=tool_name,
                base_cost=int(base_cost),
                ledger=ledger,
                npub=resolved,
                global_demand=demand,
            )
            if demand.get(tool_name, 0) > 0:
                result["current_demand"] = demand[tool_name]
            if denial:
                result["effective_cost_api_sats"] = 0
                result["constraint_effects"].append(
                    {"type": "denied", "reason": denial.get("constraint_reason", "blocked")}
                )
            else:
                result["effective_cost_api_sats"] = effective
                if effective != base_cost:
                    result["constraint_effects"].append(
                        {"type": "discount", "from": int(base_cost), "to": effective}
                    )
        except ValueError:
            result["constraint_effects"].append(
                {"type": "info", "message": "Session required for constraint evaluation."}
            )

    return result


@tool
async def list_constraint_types() -> dict[str, Any]:
    """List all available constraint types and their parameter schemas.

    Returns the type, category, description, and parameter specs for
    every constraint that can be used in a pricing pipeline.

    Free — no credits required.
    """
    from tollbooth.tools.pricing import list_constraint_types as _list

    return {"status": "ok", "constraint_types": _list()}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Main entry point for the server."""
    from tollbooth import validate_operator_tools

    missing = validate_operator_tools(mcp, "weather")
    if missing:
        import sys

        print(f"\u26a0 Missing base-catalog tools: {', '.join(missing)}", file=sys.stderr)
    mcp.run()


if __name__ == "__main__":
    main()
