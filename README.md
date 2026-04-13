# tollbooth-sample

Educational Weather Stats MCP Service — the reference implementation for building
Tollbooth DPYC monetized API services with Bitcoin Lightning micropayments.

This service wraps the free [Open-Meteo](https://open-meteo.com) weather API
and gates paid tool calls through the [Tollbooth](https://github.com/lonniev/tollbooth-dpyc)
credit system using the `@runtime.paid_tool()` decorator. Domain tools contain
only business logic; debit, rollback, balance warnings, and constraint evaluation
are handled automatically by the `OperatorRuntime`. Standard DPYC tools
(balance, purchase, Secure Courier, Oracle, pricing, constraints) are delegated
to the wheel via `register_standard_tools()`.

**Version:** 0.2.0

## The DPYC Economy

**DPYC** stands for **Don't Pester Your Customer**. It's a philosophy and
protocol for API monetization that eliminates mid-session payment popups,
subscription nag screens, and KYC friction.

### How it works

1. **Pre-funded balances** — Users buy credits via Bitcoin Lightning *before*
   using tools. Each tool call silently debits from their balance. No
   interruptions, no "please upgrade" modals.

2. **Nostr keypair identity** — Users are identified by a Nostr public key
   (`npub`), not an email or password. One keypair per role, managed by the
   user. No account creation forms.

3. **UUID-keyed tool identity** — Every tool is a `ToolIdentity` object with
   a deterministic UUID v5 derived from a capability name. Pricing hints come
   from the `category` field:

   | Category | Pricing hint | Use case                    |
   |----------|--------------|-----------------------------|
   | `free`   | 0 sats       | Balance checks, status      |
   | `read`   | 1 sat        | Simple lookups              |
   | `write`  | 5 sats       | Multi-step operations       |
   | `heavy`  | 10 sats      | Expensive queries           |

   Actual prices are set dynamically by the operator's pricing model in Neon.

4. **Rollback on failure** — If the downstream API fails after a debit,
   credits are automatically rolled back via a compensating tranche. The
   user never pays for a failed call.

5. **Honor Chain** — The DPYC ecosystem is a voluntary community:
   - **Citizens** — Users who consume API services
   - **Operators** — Developers who run MCP services (like this one)
   - **Authorities** — Certify operators and collect a small tax on purchases
   - **First Curator** — The root of the chain, mints the initial cert-sat supply

## How Tollbooth Monetization Works

### ToolIdentity and `capability_uuid()`

Each domain tool is registered as a `ToolIdentity` with a capability name,
category (pricing hint), and intent description. The `capability_uuid()`
function derives a deterministic UUID v5 from the capability name, which the
`@runtime.paid_tool()` decorator uses to look up pricing and track usage:

```python
from tollbooth.tool_identity import ToolIdentity, STANDARD_IDENTITIES, capability_uuid
from tollbooth.runtime import OperatorRuntime, register_standard_tools
from tollbooth.credential_templates import CredentialTemplate, FieldSpec
from tollbooth.credential_validators import validate_btcpay_creds
from tollbooth.slug_tools import make_slug_tool

# 1. Define domain tool identities
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
```

### The `@runtime.paid_tool()` decorator

Every paid tool is a single decorator away from full DPYC monetization.
The decorator takes the UUID of the tool identity (via `capability_uuid()`),
handles debit, balance checks, constraint evaluation, rollback on failure,
and low-balance warnings automatically. Your tool function contains only
domain logic:

```python
from typing import Annotated, Any
from pydantic import Field
from fastmcp import FastMCP

mcp = FastMCP("tollbooth-sample", ...)
tool = make_slug_tool(mcp, "weather")

# Create the runtime with merged standard + domain identities
runtime = OperatorRuntime(
    tool_registry={**STANDARD_IDENTITIES, **TOOL_REGISTRY},
    operator_credential_template=CredentialTemplate(
        service="tollbooth-sample-operator",
        version=2,
        description="Operator credentials for BTCPay Lightning payments",
        fields={
            "btcpay_host": FieldSpec(required=True, sensitive=True, ...),
            "btcpay_api_key": FieldSpec(required=True, sensitive=True, ...),
            "btcpay_store_id": FieldSpec(required=True, sensitive=True, ...),
        },
    ),
    credential_validator=validate_btcpay_creds,
    ...
)

# Delegate all standard DPYC tools to the wheel
register_standard_tools(mcp, "weather", runtime, ...)

# Decorate each paid domain tool
@tool
@runtime.paid_tool(capability_uuid("get_current_weather"))
async def current(
    latitude: float,
    longitude: float,
    npub: Annotated[str, Field(
        description="Required. Your Nostr public key (npub1...) for credit billing."
    )] = "",
    proof: str = "",
) -> dict[str, Any]:
    """Get current weather conditions for a location.

    Returns temperature, wind speed, and weather code from Open-Meteo.
    """
    return await weather.get_current(latitude, longitude)
```

That is the complete paid tool. No manual debit calls, no try/except
rollback blocks, no balance-warning plumbing. The decorator:

- Looks up the tool's pricing from the `ToolIdentity` registry by UUID
- Extracts `npub` from the function arguments for billing
- Validates `proof` for operator proof verification
- Debits before calling your function (respecting ConstraintGate discounts)
- Rolls back automatically if your function raises an exception
- Appends a low-balance warning to the response when funds are running low
- Skips all gating in STDIO mode so local development works without credits

### Key patterns

**`make_slug_tool(mcp, "weather")`** — Creates a `@tool` decorator that
automatically prefixes all tool names with `weather_`. This keeps the MCP
namespace clean when multiple operators share a host.

**`register_standard_tools()`** — Registers all standard DPYC tools
(balance, purchase, payment, pricing, Secure Courier, Oracle, constraints)
from the tollbooth-dpyc wheel. Domain operators never define these manually.

**`validate_btcpay_creds`** — Credential validator that checks BTCPay
credentials at receive time, not at first use. Invalid credentials are
rejected immediately during the Secure Courier exchange.

**`CredentialTemplate`** — Declares the operator's required secrets
(BTCPay host, API key, store ID) so the Secure Courier flow can prompt
for the right fields and validate them on delivery.

### The `npub` and `proof` parameters

Every paid tool must accept `npub` and `proof` keyword arguments. The
`npub` tells the runtime which patron to bill; `proof` carries the
operator proof for verification:

```python
npub: Annotated[str, Field(
    description="Required. Your Nostr public key (npub1...) for credit billing."
)] = ""
proof: str = ""
```

The defaults of `""` keep both parameters optional in STDIO/dev mode.

### What the runtime handles under the hood

```
Tool call arrives
    |
    v
@runtime.paid_tool(capability_uuid("get_current_weather"))
    |
    +-- UUID lookup in tool_registry -> ToolIdentity + pricing
    +-- npub + proof extraction from kwargs
    +-- STDIO mode? --yes--> Skip gating, call function directly
    |
    +-- ConstraintGate evaluation (discounts, surge, supply caps)
    +-- Balance check + debit
    |       |
    |       insufficient --> Return error (no function call)
    |
    +-- Call your function
    |       |
    |       exception --> Automatic rollback, return error
    |
    +-- Append low-balance warning if needed
    |
    v
Return result to caller
```

## Constraint Engine

The ConstraintGate is an opt-in dynamic pricing layer. Enable it by setting:

```bash
CONSTRAINTS_ENABLED=true
CONSTRAINTS_CONFIG='{"tool_constraints": {...}}'
```

Supported constraint types:

| Type              | Effect                                            |
|-------------------|---------------------------------------------------|
| `free_trial`      | First N calls are free                            |
| `happy_hour`      | Discount during specific hours                    |
| `temporal_window` | Allow calls only during a time window             |
| `finite_supply`   | Cap total invocations globally                    |
| `loyalty_discount`| Discount after spending N sats                    |
| `bulk_bonus`      | Discount after N invocations                      |

Use `weather_check_price` to preview constraint effects without spending credits.

See [`constraints/example_basic.json`](constraints/example_basic.json) and
[`constraints/example_advanced.json`](constraints/example_advanced.json)
for configuration examples.

## Becoming an Operator

New to Tollbooth? See **[GETTING-STARTED.md](GETTING-STARTED.md)** for a
step-by-step guide covering Nostr keypair setup, Authority enrollment,
BTCPay configuration, and deploying your first monetized MCP service.

## Quick Start

### Local development (no gating)

```bash
git clone https://github.com/lonniev/tollbooth-sample.git
cd tollbooth-sample
pip install -e ".[dev]"
python -m tollbooth_sample.server
```

In STDIO mode, all tools work without credits — great for development.

### Deploy on FastMCP Cloud

1. Push to GitHub
2. Connect the repo on [FastMCP Cloud](https://app.fastmcp.cloud)
3. Set environment variables:
   - `TOLLBOOTH_NOSTR_OPERATOR_NSEC` — Nostr key for identity bootstrap
     (the only env var required to boot; all other secrets are delivered
     via Secure Courier credential templates)
   - (Optional) `CONSTRAINTS_ENABLED=true` + `CONSTRAINTS_CONFIG=...`

### Run tests

```bash
pip install -e ".[dev]"
pytest -v
```

## Tool Reference

| MCP tool name              | Cost     | Description                           |
|----------------------------|----------|---------------------------------------|
| `weather_current`          | read     | Current weather for lat/lon           |
| `weather_forecast`         | write    | Multi-day forecast (1-16 days)        |
| `weather_historical`       | heavy    | Historical weather for a date range   |
| `weather_check_balance`    | free     | Check credit balance                  |
| `weather_purchase_credits` | free     | Buy credits via Lightning             |
| `weather_check_payment`    | free     | Check invoice status                  |
| `weather_check_price`      | free     | Preview cost (shows constraint effects)|
| `weather_service_status`   | free     | Health + constraint config summary    |
| `weather_how_to_join`      | free     | DPYC onboarding instructions          |
| `weather_get_tax_rate`     | free     | Current certification tax rate        |
| `weather_lookup_member`    | free     | Look up a DPYC member                |
| `weather_about`            | free     | DPYC ecosystem description            |
| `weather_network_advisory` | free     | Active network advisories             |

## DPYC Ecosystem

- [dpyc-community](https://github.com/lonniev/dpyc-community) — Registry + governance
- [tollbooth-dpyc](https://github.com/lonniev/tollbooth-dpyc) — Python SDK for Tollbooth monetization
- [tollbooth-authority](https://github.com/lonniev/tollbooth-authority) — Authority MCP service
- [thebrain-mcp](https://github.com/lonniev/thebrain-mcp) — Personal Brain MCP service
- [excalibur-mcp](https://github.com/lonniev/excalibur-mcp) — Twitter MCP service
- [dpyc-oracle](https://github.com/lonniev/dpyc-oracle) — Community concierge

## License

Apache-2.0
