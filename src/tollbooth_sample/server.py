"""Tollbooth Sample — Educational Weather Stats MCP Server.

This server demonstrates Tollbooth DPYC monetization with a real-world
weather API (Open-Meteo).  It implements OperatorProtocol from
tollbooth-dpyc and optionally activates the Constraint Engine for
dynamic pricing (free trials, happy hours, temporal windows).

Run locally:
    python -m tollbooth_sample.server

Deploy on FastMCP Cloud:
    See .fastmcp.yaml
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastmcp import FastMCP

from datetime import datetime, timezone

from tollbooth import (
    BTCPayClient,
    BTCPayError,
    ConstraintGate,
    ECOSYSTEM_LINKS,
    LedgerCache,
    NeonVault,
    ToolTier,
    TollboothConfig,
)
from tollbooth.actor_types import ToolPath, ToolPathInfo
from tollbooth.operator_protocol import (
    OPERATOR_BASE_CATALOG,
    OPERATOR_OBSOLETE_PRACTICES,
    OperatorProtocol,
)
from tollbooth.slug_tools import make_slug_tool
from tollbooth.tools import credits

from tollbooth_sample import __version__
from tollbooth_sample.config import Settings, get_settings
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
        "Paid tools: weather_current (1 sat), weather_forecast (5 sats), "
        "weather_historical (10 sats). Prices are base rates — the "
        "Constraint Engine may apply discounts (happy hour, loyalty, free "
        "trial) or surge pricing based on global demand.\n"
        "Free tools: weather_check_balance, weather_purchase_credits, "
        "weather_check_payment, weather_check_price, weather_service_status."
    ),
)
tool = make_slug_tool(mcp, "weather")

# ---------------------------------------------------------------------------
# Tool cost map
# ---------------------------------------------------------------------------

TOOL_COSTS: dict[str, int] = {
    "current": ToolTier.READ,
    "forecast": ToolTier.WRITE,
    "historical": ToolTier.HEAVY,
    "check_balance": ToolTier.FREE,
    "purchase_credits": ToolTier.FREE,
    "check_payment": ToolTier.FREE,
    "check_price": ToolTier.FREE,
    "service_status": ToolTier.FREE,
    "account_statement": ToolTier.FREE,
    "account_statement_infographic": ToolTier.READ,
    "restore_credits": ToolTier.FREE,
    "session_status": ToolTier.FREE,
    "request_credential_channel": ToolTier.FREE,
    "receive_credentials": ToolTier.FREE,
    "forget_credentials": ToolTier.FREE,
    "get_pricing_model": ToolTier.FREE,
    "set_pricing_model": ToolTier.RESTRICTED,
    "list_constraint_types": ToolTier.FREE,
}

# ---------------------------------------------------------------------------
# Domain-specific tool catalog entries
# ---------------------------------------------------------------------------

DOMAIN_CATALOG: list[ToolPathInfo] = [
    ToolPathInfo(
        tool_name="current",
        path=ToolPath.COLD,
        requires_auth=True,
        cost_tier="READ",
        agent_hint="Current weather conditions for a lat/lon location.",
    ),
    ToolPathInfo(
        tool_name="forecast",
        path=ToolPath.COLD,
        requires_auth=True,
        cost_tier="WRITE",
        agent_hint="Multi-day weather forecast (1-16 days) for a lat/lon location.",
    ),
    ToolPathInfo(
        tool_name="historical",
        path=ToolPath.COLD,
        requires_auth=True,
        cost_tier="HEAVY",
        agent_hint="Historical weather data for a date range at a lat/lon location.",
    ),
    ToolPathInfo(
        tool_name="check_price",
        path=ToolPath.HOT,
        requires_auth=False,
        cost_tier="FREE",
        agent_hint="Preview the effective cost of a tool (shows constraint effects).",
    ),
]

# ---------------------------------------------------------------------------
# SampleOperator — satisfies OperatorProtocol
# ---------------------------------------------------------------------------


class SampleOperator:
    """Weather Stats operator implementing the DPYC OperatorProtocol.

    This class is the single source of truth for Protocol conformance.
    The @tool-decorated FastMCP functions below delegate to its methods.
    """

    @property
    def slug(self) -> str:
        return "weather"

    @classmethod
    def tool_catalog(cls) -> list[ToolPathInfo]:
        return OPERATOR_BASE_CATALOG + DOMAIN_CATALOG

    # ── Hot-path (local ledger) ───────────────────────────────────

    async def check_balance(self, npub: str) -> dict[str, Any]:
        cache = _get_ledger_cache()
        settings = get_settings()
        return await credits.check_balance_tool(
            cache,
            npub,
            default_credit_ttl_seconds=settings.credit_ttl_seconds,
        )

    async def account_statement(self, npub: str) -> dict[str, Any]:
        cache = _get_ledger_cache()
        return await credits.account_statement_tool(cache, npub)

    async def account_statement_infographic(
        self, npub: str
    ) -> dict[str, Any]:
        cache = _get_ledger_cache()
        data = await credits.account_statement_tool(cache, npub)
        return {"success": True, "statement": data}

    async def restore_credits(
        self, npub: str, invoice_id: str
    ) -> dict[str, Any]:
        btcpay = _get_btcpay()
        cache = _get_ledger_cache()
        settings = get_settings()
        return await credits.restore_credits_tool(
            btcpay,
            cache,
            npub,
            invoice_id,
            default_credit_ttl_seconds=settings.credit_ttl_seconds,
        )

    async def service_status(self) -> dict[str, Any]:
        settings = get_settings()
        gate = _get_gate()
        return {
            "success": True,
            "service": "tollbooth-sample",
            "version": __version__,
            "slug": self.slug,
            "constraints_enabled": gate.enabled if gate else False,
            "btcpay_configured": settings.btcpay_host is not None,
            "vault_configured": settings.neon_database_url is not None,
            "seed_balance_sats": settings.seed_balance_sats,
            "tool_costs": {k: int(v) for k, v in TOOL_COSTS.items() if v > 0},
            "ecosystem_links": ECOSYSTEM_LINKS,
        }

    # ── Hot-path (Secure Courier) ─────────────────────────────────

    async def session_status(self) -> dict[str, Any]:
        user_id = _get_current_user_id()
        if not user_id:
            return {
                "success": True,
                "mode": "stdio",
                "message": "Running in local development mode — no gating.",
            }
        npub = _dpyc_sessions.get(user_id)
        return {
            "success": True,
            "mode": "multi-tenant",
            "userId": user_id,
            "hasSession": npub is not None,
            "dpyc_npub": npub,
            "obsolete_practices": [
                {"pattern": p.pattern, "replaced_by": p.replaced_by}
                for p in OPERATOR_OBSOLETE_PRACTICES
            ],
        }

    async def request_credential_channel(
        self, service: str, greeting: str, recipient_npub: str | None,
    ) -> dict[str, Any]:
        courier = _get_courier_service()
        if courier is None:
            return {
                "success": False,
                "error": (
                    "Secure Courier not configured. "
                    "Set TOLLBOOTH_NOSTR_OPERATOR_NSEC to enable."
                ),
            }
        try:
            return await courier.open_channel(
                service,
                greeting=greeting or (
                    "Hi — I'm Tollbooth Sample, an educational weather stats "
                    "MCP service. You (or your AI agent) requested a credential channel."
                ),
                recipient_npub=recipient_npub,
            )
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def receive_credentials(
        self, sender_npub: str, service: str, credential_card: str,
    ) -> dict[str, Any]:
        courier = _get_courier_service()
        if courier is None:
            return {
                "success": False,
                "error": "Secure Courier not configured.",
            }
        try:
            if credential_card:
                return await courier.redeem_card(credential_card, service=service)
            if not sender_npub:
                return {
                    "success": False,
                    "error": "Either sender_npub or credential_card is required.",
                }
            return await courier.receive(
                sender_npub, service=service, caller_id=_get_current_user_id(),
            )
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def forget_credentials(
        self, sender_npub: str, service: str,
    ) -> dict[str, Any]:
        courier = _get_courier_service()
        if courier is None:
            return {"success": False, "error": "Secure Courier not configured."}
        return await courier.forget(
            sender_npub, service=service, caller_id=_get_current_user_id(),
        )

    # ── Cold-path (BTCPay via Authority) ──────────────────────────

    async def purchase_credits(
        self, npub: str, amount_sats: int, certificate: str
    ) -> dict[str, Any]:
        btcpay = _get_btcpay()
        cache = _get_ledger_cache()
        settings = get_settings()
        authority_npub = await _resolve_authority_npub()

        # Fire-and-forget invoice DM — courier may not be available
        invoice_dm_cb = None
        try:
            courier = _get_courier_service()
            if courier is not None and courier.enabled:
                async def _send_invoice_dm(msg: str) -> None:
                    courier.exchange.send_dm(npub, msg)
                invoice_dm_cb = _send_invoice_dm
        except Exception:
            pass  # courier unavailable — skip DM

        return await credits.purchase_credits_tool(
            btcpay,
            cache,
            npub,
            amount_sats,
            certificate,
            authority_npub,
            default_credit_ttl_seconds=settings.credit_ttl_seconds,
            invoice_dm_callback=invoice_dm_cb,
        )

    async def check_payment(
        self, npub: str, invoice_id: str
    ) -> dict[str, Any]:
        btcpay = _get_btcpay()
        cache = _get_ledger_cache()
        settings = get_settings()
        return await credits.check_payment_tool(
            btcpay,
            cache,
            npub,
            invoice_id,
            default_credit_ttl_seconds=settings.credit_ttl_seconds,
        )

    # ── Cold-path (delegates to Authority) ────────────────────────

    async def certify_credits(
        self, operator_id: str, amount_sats: int
    ) -> dict[str, Any]:
        try:
            from tollbooth.authority_client import (
                AuthorityCertifier,
                AuthorityCertifyError,
            )

            url = await _resolve_authority_service_url()
            return await AuthorityCertifier(url).certify(amount_sats)
        except Exception as e:
            return {"success": False, "error": f"Certification failed: {e}"}

    async def register_operator(self, npub: str) -> dict[str, Any]:
        return await _call_oracle("request_citizenship", {"npub": npub})

    async def operator_status(self) -> dict[str, Any]:
        return {"success": True, "message": "Use service_status for this operator."}

    # ── Cold-path (delegates to Oracle) ───────────────────────────

    async def lookup_member(self, npub: str) -> dict[str, Any] | str:
        return await _call_oracle("lookup_member", {"npub": npub})

    async def how_to_join(self) -> str:
        result = await _call_oracle("how_to_join")
        return result.get("text", str(result)) if isinstance(result, dict) else result

    async def get_tax_rate(self) -> dict[str, Any]:
        return await _call_oracle("get_tax_rate")

    async def about(self) -> str:
        result = await _call_oracle("about")
        return result.get("text", str(result)) if isinstance(result, dict) else result

    async def network_advisory(self) -> str:
        result = await _call_oracle("network_advisory")
        return result.get("text", str(result)) if isinstance(result, dict) else result


# ---------------------------------------------------------------------------
# Module-level singletons
# ---------------------------------------------------------------------------

_operator: SampleOperator | None = None
_ledger_cache: LedgerCache | None = None
_btcpay_client: BTCPayClient | None = None
_gate: ConstraintGate | None = None
_gate_initialized: bool = False
_dpyc_sessions: dict[str, str] = {}  # horizon_id → npub


def _get_operator() -> SampleOperator:
    global _operator
    if _operator is None:
        _operator = SampleOperator()
    return _operator


def _get_current_user_id() -> str | None:
    """Return the FastMCP Cloud user ID, or None in STDIO mode."""
    try:
        from fastmcp.server.dependencies import get_http_headers

        headers = get_http_headers(include_all=True)
        return headers.get("fastmcp-cloud-user")
    except Exception:
        return None


_cached_operator_npub: str | None = None


def _get_operator_npub() -> str:
    global _cached_operator_npub
    if _cached_operator_npub is not None:
        return _cached_operator_npub
    from pynostr.key import PrivateKey

    settings = get_settings()
    nsec = settings.tollbooth_nostr_operator_nsec
    if not nsec:
        raise RuntimeError(
            "Operator misconfigured: TOLLBOOTH_NOSTR_OPERATOR_NSEC not set."
        )
    pk = PrivateKey.from_nsec(nsec)
    _cached_operator_npub = pk.public_key.bech32()
    return _cached_operator_npub


def _get_commerce_vault() -> NeonVault:
    settings = get_settings()
    if not settings.neon_database_url:
        raise ValueError(
            "Commerce vault not configured. Set NEON_DATABASE_URL to enable credits."
        )
    vault = NeonVault(database_url=settings.neon_database_url)
    asyncio.ensure_future(vault.ensure_schema())
    return vault


def _get_ledger_cache() -> LedgerCache:
    global _ledger_cache
    if _ledger_cache is not None:
        return _ledger_cache
    vault = _get_commerce_vault()
    _ledger_cache = LedgerCache(vault)
    asyncio.ensure_future(_ledger_cache.start_background_flush())
    return _ledger_cache


def _get_btcpay() -> BTCPayClient:
    global _btcpay_client
    if _btcpay_client is not None:
        return _btcpay_client
    settings = get_settings()
    if not all([settings.btcpay_host, settings.btcpay_api_key, settings.btcpay_store_id]):
        raise ValueError(
            "BTCPay not configured. Set BTCPAY_HOST, BTCPAY_API_KEY, BTCPAY_STORE_ID."
        )
    _btcpay_client = BTCPayClient(
        host=settings.btcpay_host,
        api_key=settings.btcpay_api_key,
        store_id=settings.btcpay_store_id,
    )
    return _btcpay_client


# ---------------------------------------------------------------------------
# Pricing model store singleton
# ---------------------------------------------------------------------------

_pricing_store: Any = None


def _get_pricing_store() -> Any:
    global _pricing_store
    if _pricing_store is not None:
        return _pricing_store
    from tollbooth.pricing_store import PricingModelStore

    vault = _get_commerce_vault()
    _pricing_store = PricingModelStore(neon_vault=vault)
    import asyncio

    try:
        asyncio.ensure_future(_pricing_store.ensure_schema())
    except RuntimeError:
        pass
    return _pricing_store


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


_courier_service = None

_DEFAULT_RELAY = "wss://nostr.wine"
_FALLBACK_POOL = [
    "wss://relay.primal.net",
    "wss://relay.damus.io",
    "wss://nos.lol",
    "wss://relay.nostr.band",
]


def _get_courier_service():
    """Return the SecureCourierService singleton, or None if not configured.

    Constructs a minimal courier with no credential templates — this service
    has no patron secrets to exchange (Open-Meteo is free/keyless).  The
    courier is still useful for ``send_dm()`` (e.g. invoice DM delivery).
    """
    global _courier_service
    if _courier_service is not None:
        return _courier_service

    try:
        from tollbooth.nostr_diagnostics import probe_relay_liveness
        from tollbooth.secure_courier import SecureCourierService
    except ImportError:
        return None

    settings = get_settings()
    if not settings.tollbooth_nostr_operator_nsec:
        return None

    # Resolve relays — probe default, fall back to pool
    relays = [_DEFAULT_RELAY]
    results = probe_relay_liveness(relays, timeout=5)
    live = [r["relay"] for r in results if r["connected"]]
    if not live:
        fallback_results = probe_relay_liveness(_FALLBACK_POOL, timeout=5)
        live = [r["relay"] for r in fallback_results if r["connected"]]
    if not live:
        live = relays + _FALLBACK_POOL

    _courier_service = SecureCourierService(
        operator_nsec=settings.tollbooth_nostr_operator_nsec,
        relays=live,
        templates={},  # No credential exchange — weather API needs no patron secrets
    )
    return _courier_service


async def _resolve_authority_npub() -> str:
    from tollbooth import resolve_authority_npub

    return await resolve_authority_npub()


async def _resolve_authority_service_url() -> str:
    from tollbooth import resolve_authority_service

    return await resolve_authority_service()


async def _call_oracle(
    tool_name: str, arguments: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Delegate a tool call to the DPYC Oracle."""
    try:
        from tollbooth.oracle_client import OracleClient, OracleClientError
        from tollbooth import resolve_oracle_service

        oracle_url = await resolve_oracle_service()
        return await OracleClient(oracle_url).call_tool(tool_name, arguments)
    except Exception as e:
        return {"success": False, "error": f"Oracle delegation failed: {e}"}


async def _ensure_dpyc_session() -> str:
    """Return the patron's npub, raising ValueError if unavailable."""
    user_id = _get_current_user_id()
    if not user_id:
        raise ValueError("No user identity — running in STDIO mode.")
    npub = _dpyc_sessions.get(user_id)
    if npub:
        return npub
    # Auto-restore from vault would go here in a production deployment.
    raise ValueError(
        "No DPYC session. Call session_status for onboarding steps."
    )


# ---------------------------------------------------------------------------
# Debit / rollback helpers
# ---------------------------------------------------------------------------


def _demand_window_key() -> str:
    """Compute the current hourly demand window key (e.g. '2026-03-05T14:00')."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:00")


async def _get_global_demand(tool_name: str) -> dict[str, int]:
    """Read global demand for *tool_name* from Neon.  Returns {tool: count}.

    On error or when vault is unconfigured, returns empty dict (base pricing).
    """
    try:
        vault = _get_commerce_vault()
        count = await vault.get_demand(tool_name, _demand_window_key())
        return {tool_name: count}
    except Exception:
        return {}


def _fire_and_forget_demand_increment(tool_name: str) -> None:
    """Increment the demand counter for *tool_name* — async, non-blocking."""
    async def _increment() -> None:
        try:
            vault = _get_commerce_vault()
            await vault.increment_demand(tool_name, _demand_window_key())
        except Exception:
            pass  # best-effort; stale counts just mean slightly off pricing

    asyncio.create_task(_increment())


async def _debit_or_error(tool_name: str) -> dict[str, Any] | None:
    """Check balance and debit credits for a paid tool call.

    Returns None on success (proceed with execution).
    Returns an error dict if insufficient balance or no session.
    Skips gating entirely in STDIO mode or when vault is unconfigured.

    RESTRICTED tools (cost == ToolTier.RESTRICTED) are operator-only:
    allowed at cost 0 if the caller's npub matches the operator npub,
    rejected otherwise.  STDIO mode bypasses the restriction.
    """
    cost = TOOL_COSTS.get(tool_name, 0)

    # RESTRICTED tier: operator-only access gate
    if cost == ToolTier.RESTRICTED:
        user_id = _get_current_user_id()
        if not user_id:
            return None  # STDIO mode — allow
        try:
            caller_npub = await _ensure_dpyc_session()
        except ValueError as e:
            return {"success": False, "error": str(e)}
        if caller_npub != _get_operator_npub():
            return {
                "success": False,
                "error": "This tool is restricted to the operator.",
            }
        return None  # operator — allow at cost 0

    if cost == 0:
        return None

    # STDIO mode — no gating
    if not _get_current_user_id():
        return None

    try:
        npub = await _ensure_dpyc_session()
        cache = _get_ledger_cache()
    except ValueError as e:
        return {"success": False, "error": str(e)}

    # ConstraintGate may modify the cost or deny the call
    gate = _get_gate()
    if gate and gate.enabled:
        ledger = await cache.get(npub)
        demand = await _get_global_demand(tool_name)
        denial, effective_cost = gate.check(
            tool_name=tool_name,
            base_cost=cost,
            ledger=ledger,
            npub=npub,
            global_demand=demand,
        )
        if denial is not None:
            return denial
        cost = effective_cost

    # If constraint reduced cost to zero, skip debit
    if cost == 0:
        return None

    if not await cache.debit(npub, tool_name, cost):
        ledger = await cache.get(npub)
        return {
            "success": False,
            "error": (
                f"Insufficient balance ({ledger.balance_api_sats} api_sats) "
                f"for {tool_name} ({cost} api_sats). "
                f"Use weather_purchase_credits to add funds."
            ),
        }

    # Successful debit — increment global demand counter (fire-and-forget)
    _fire_and_forget_demand_increment(tool_name)

    return None


async def _rollback_debit(tool_name: str) -> None:
    """Undo a debit if the downstream API call fails."""
    cost = TOOL_COSTS.get(tool_name, 0)
    if cost <= 0 or not _get_current_user_id():
        return
    try:
        npub = await _ensure_dpyc_session()
        cache = _get_ledger_cache()
        ledger = await cache.get(npub)
        ledger.rollback_debit(tool_name, cost)
        cache.mark_dirty(npub)
    except Exception:
        logger.exception("Rollback failed for %s", tool_name)


async def _with_warning(result: dict[str, Any]) -> dict[str, Any]:
    """Append low_balance_warning to the result if balance is running low."""
    if not _get_current_user_id():
        return result
    try:
        npub = await _ensure_dpyc_session()
        cache = _get_ledger_cache()
        warning = credits.compute_low_balance_warning(await cache.get(npub))
        if warning:
            result["low_balance_warning"] = warning
    except Exception:
        pass
    return result


# ---------------------------------------------------------------------------
# MCP tool registrations — delegate to SampleOperator
# ---------------------------------------------------------------------------

# ── Weather domain tools ──────────────────────────────────────────


@tool
async def current(latitude: float, longitude: float) -> dict[str, Any]:
    """Get current weather conditions for a location.

    Returns temperature, wind speed, and weather code from Open-Meteo.
    Cost: 1 api_sat (READ tier).

    Args:
        latitude: Latitude (-90 to 90).
        longitude: Longitude (-180 to 180).
    """
    err = await _debit_or_error("current")
    if err:
        return err
    try:
        result = await weather.get_current(latitude, longitude)
        return await _with_warning(result)
    except Exception as e:
        await _rollback_debit("current")
        return {"success": False, "error": str(e)}


@tool
async def forecast(
    latitude: float, longitude: float, days: int = 7
) -> dict[str, Any]:
    """Get a multi-day weather forecast for a location.

    Returns daily high/low temperatures and precipitation for 1-16 days.
    Cost: 5 api_sats (WRITE tier).

    Args:
        latitude: Latitude (-90 to 90).
        longitude: Longitude (-180 to 180).
        days: Number of forecast days (1-16, default 7).
    """
    err = await _debit_or_error("forecast")
    if err:
        return err
    try:
        result = await weather.get_forecast(latitude, longitude, days)
        return await _with_warning(result)
    except Exception as e:
        await _rollback_debit("forecast")
        return {"success": False, "error": str(e)}


@tool
async def historical(
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str,
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
    err = await _debit_or_error("historical")
    if err:
        return err
    try:
        result = await weather.get_historical(latitude, longitude, start_date, end_date)
        return await _with_warning(result)
    except Exception as e:
        await _rollback_debit("historical")
        return {"success": False, "error": str(e)}


# ── Price preview ─────────────────────────────────────────────────


@tool
async def check_price(tool_name: str) -> dict[str, Any]:
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
        # Show what constraints would do (without actually debiting)
        try:
            npub = await _ensure_dpyc_session()
            cache = _get_ledger_cache()
            ledger = await cache.get(npub)
            demand = await _get_global_demand(tool_name)
            denial, effective = gate.check(
                tool_name=tool_name,
                base_cost=int(base_cost),
                ledger=ledger,
                npub=npub,
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


# ── Standard credit tools ─────────────────────────────────────────


@tool
async def check_balance() -> dict[str, Any]:
    """Check your current credit balance, tier info, and usage summary.

    Free — no credits required.
    """
    op = _get_operator()
    try:
        npub = await _ensure_dpyc_session()
    except ValueError as e:
        return {"success": False, "error": str(e)}
    return await op.check_balance(npub)


@tool
async def purchase_credits(amount_sats: int = 1000) -> dict[str, Any]:
    """Buy credits via Bitcoin Lightning.

    Creates a Lightning invoice. Pay it with any Lightning wallet, then
    call weather_check_payment to confirm. Minimum 110 sats (100 net +
    10 sat Authority certification fee).

    Free — no credits required to call.

    Args:
        amount_sats: Number of satoshis to purchase (default 1000).
    """
    op = _get_operator()
    try:
        npub = await _ensure_dpyc_session()
    except ValueError as e:
        return {"success": False, "error": str(e)}

    # Auto-certify via Authority
    try:
        from tollbooth.authority_client import AuthorityCertifier

        authority_url = await _resolve_authority_service_url()
        cert_result = await AuthorityCertifier(authority_url).certify(amount_sats)
        certificate = cert_result.get("certificate", "")
    except Exception as e:
        return {"success": False, "error": f"Authority certification failed: {e}"}

    try:
        return await op.purchase_credits(npub, amount_sats, certificate)
    except ValueError as e:
        return {"success": False, "error": str(e)}


@tool
async def check_payment(invoice_id: str) -> dict[str, Any]:
    """Check the payment status of a Lightning invoice.

    Call after paying the invoice from weather_purchase_credits.
    On settlement, credits are added to your balance automatically.

    Free — no credits required.

    Args:
        invoice_id: The BTCPay invoice ID from purchase_credits.
    """
    op = _get_operator()
    try:
        npub = await _ensure_dpyc_session()
    except ValueError as e:
        return {"success": False, "error": str(e)}
    try:
        return await op.check_payment(npub, invoice_id)
    except ValueError as e:
        return {"success": False, "error": str(e)}


@tool
async def service_status() -> dict[str, Any]:
    """Check the health and configuration of this weather service.

    Free — no authentication or credits required.
    """
    return await _get_operator().service_status()


# ── Oracle delegation tools ───────────────────────────────────────


@tool
async def how_to_join() -> dict[str, Any]:
    """Get DPYC onboarding instructions from the community Oracle.

    Free — no authentication or credits required.
    """
    return await _call_oracle("how_to_join")


@tool
async def get_tax_rate() -> dict[str, Any]:
    """Get the current DPYC certification tax rate from the Oracle.

    Free — no authentication or credits required.
    """
    return await _call_oracle("get_tax_rate")


@tool
async def lookup_member(npub: str) -> dict[str, Any]:
    """Look up a DPYC community member by their Nostr npub.

    Can look up any role's npub — citizen, operator, or authority.
    Free — no authentication or credits required.

    Args:
        npub: The Nostr public key (bech32 npub format) to look up.
    """
    return await _call_oracle("lookup_member", {"npub": npub})


@tool
async def about() -> dict[str, Any]:
    """Describe the DPYC ecosystem via the community Oracle.

    Free — no authentication or credits required.
    """
    return await _call_oracle("about")


@tool
async def network_advisory() -> dict[str, Any]:
    """Get active network advisories from the DPYC Oracle.

    Free — no authentication or credits required.
    """
    return await _call_oracle("network_advisory")


# ---------------------------------------------------------------------------
# Pricing CRUD tools
# ---------------------------------------------------------------------------


@tool
async def get_pricing_model() -> dict[str, Any]:
    """Get the active pricing model for this operator. Free."""
    try:
        store = _get_pricing_store()
        operator = _get_operator_npub()
    except (ValueError, RuntimeError) as e:
        return {"status": "error", "error": str(e)}
    from tollbooth.tools.pricing import get_pricing_model_tool

    return await get_pricing_model_tool(store, operator)


@tool
async def set_pricing_model(model_json: str) -> dict[str, Any]:
    """Set or update the active pricing model. Restricted — operator only."""
    err = await _debit_or_error("set_pricing_model")
    if err:
        return err
    try:
        store = _get_pricing_store()
        operator = _get_operator_npub()
    except (ValueError, RuntimeError) as e:
        return {"status": "error", "error": str(e)}

    # Verify caller is the operator (skip in STDIO mode)
    user_id = _get_current_user_id()
    if user_id is not None:
        try:
            caller_npub = await _ensure_dpyc_session()
        except ValueError as e:
            return {"status": "error", "error": str(e)}
        if caller_npub != operator:
            return {"status": "error", "error": "Only the operator can modify pricing"}

    from tollbooth.tools.pricing import set_pricing_model_tool

    return await set_pricing_model_tool(store, operator, model_json)


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
