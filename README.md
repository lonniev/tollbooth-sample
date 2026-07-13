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

**Version:** 0.3.1

## Build your own operator — the `bootstrap-dpyc-operator` skill

This repo doubles as a **Claude Code plugin**. The `bootstrap-dpyc-operator` skill turns your
**existing REST API, stdio MCP, or HTTP MCP** into a monetized DPYC Operator MCP: it clones this
template live, wraps your domain logic, and generates a deploy-ready project. You keep writing
business logic — the SDK handles payments, identity, vault, audit, and pricing.

Install it in Claude Code:

```
/plugin marketplace add lonniev/tollbooth-sample
/plugin install bootstrap-dpyc-operator@tollbooth-dpyc
```

Then ask Claude to *"make my API a paid DPYC operator"* — the skill activates automatically by
its description. It never touches your original code (it emits a sibling `<slug>-mcp/` project)
and reads this repo's live wheel pin on every run, so it can't go stale.

See [`skills/bootstrap-dpyc-operator/`](skills/bootstrap-dpyc-operator/) for the skill and its
reference guides (canonical pattern, source adapters, sessions & vaults, onboarding checklist).

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

5. **Social Contract** — The DPYC ecosystem is a voluntary community bound
   by transparent, auditable economic rules, with a Certification Chain that
   cascades trust from the root:
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

# Delegate all standard DPYC tools to the wheel.
# register_standard_tools returns the slug-prefixed @tool decorator —
# use it for the operator's own paid tools below.
tool = register_standard_tools(mcp, "weather", runtime, ...)

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

**`register_standard_tools(mcp, "weather", runtime, …)`** — Registers all
standard DPYC tools (balance, purchase, payment, pricing, Secure Courier,
Oracle, constraints) from the tollbooth-dpyc wheel, mounts oracle
delegations under `<slug>_oracle_*`, and **returns** the slug-prefixed
`@tool` decorator. Capture the return so you can use the same decorator
for your own paid tools — every wire-exposed name on this operator then
shares one slug prefix.

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

### Deploy on Prefect Horizon

The hosting platform is **Prefect Horizon** (FastMCP is the runtime/framework
the server is built on).

1. Push to GitHub
2. Connect the repo on Prefect Horizon
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
| `weather_request_adoption` | free     | Request adoption by an Authority (deferred-courtship onboarding) |
| `weather_check_price`      | free     | Preview cost (shows constraint effects)|
| `weather_service_status`   | free     | Health + constraint config summary    |
| `weather_how_to_join`      | free     | DPYC onboarding instructions          |
| `weather_get_tax_rate`     | free     | Current certification tax rate        |
| `weather_lookup_member`    | free     | Look up a DPYC member                |
| `weather_about`            | free     | DPYC ecosystem description            |
| `weather_network_advisory` | free     | Active network advisories             |

## DPYC Ecosystem

**Core**

- [tollbooth-dpyc](https://github.com/lonniev/tollbooth-dpyc) — Python SDK (vault, auth, pricing, Lightning, Nostr identity)
- [dpyc-community](https://github.com/lonniev/dpyc-community) — Governance registry: membership, advisories, threat model
- [dpyc-oracle](https://github.com/lonniev/dpyc-oracle) — Community concierge (free onboarding + member lookup)
- [tollbooth-authority](https://github.com/lonniev/tollbooth-authority) — Certification backbone (Schnorr-signed certificates)
- [tollbooth-sample](https://github.com/lonniev/tollbooth-sample) — Sample Operator (this canonical template)
- [tollbooth-pricing-studio](https://github.com/lonniev/tollbooth-pricing-studio) — iOS pricing-model editor / operator console

**Operators**

- [cypher-mcp](https://github.com/lonniev/cypher-mcp) — Monetized graph answers: named Cypher templates over Neo4j/AuraDB
- [schwab-mcp](https://github.com/lonniev/schwab-mcp) — Charles Schwab brokerage data
- [thebrain-mcp](https://github.com/lonniev/thebrain-mcp) — TheBrain personal knowledge graph
- [excalibur-mcp](https://github.com/lonniev/excalibur-mcp) — X/Twitter posting
- [taxsort-mcp](https://github.com/lonniev/taxsort-mcp) — Tax classification + Cloudflare Pages UI
- [optionality-mcp](https://github.com/lonniev/optionality-mcp) — Options analytics (brokerage-data operator)

**Advocates & utilities**

- [tollbooth-oauth2-collector](https://github.com/lonniev/tollbooth-oauth2-collector) — OAuth2 callback handler (advocate service)
- [tollbooth-shortlinks](https://github.com/lonniev/tollbooth-shortlinks) — URL shortener utility

## License

Apache-2.0
