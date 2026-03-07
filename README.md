# tollbooth-sample

Educational Weather Stats MCP Service — a working template for building
Tollbooth DPYC monetized API services with Bitcoin Lightning micropayments.

This service wraps the free [Open-Meteo](https://open-meteo.com) weather API
and gates paid tool calls through the [Tollbooth](https://github.com/lonniev/tollbooth-dpyc)
credit system. It demonstrates debit/rollback economics, OperatorProtocol
conformance, and optional ConstraintGate dynamic pricing.

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

3. **ToolTier pricing** — Every tool has a fixed cost tier:

   | Tier   | Cost      | Use case                    |
   |--------|-----------|-----------------------------|
   | FREE   | 0 sats    | Balance checks, status      |
   | READ   | 1 sat     | Simple lookups              |
   | WRITE  | 5 sats    | Multi-step operations       |
   | HEAVY  | 10 sats   | Expensive queries           |

4. **Rollback on failure** — If the downstream API fails after a debit,
   credits are automatically rolled back via a compensating tranche. The
   user never pays for a failed call.

5. **Honor Chain** — The DPYC ecosystem is a voluntary community:
   - **Citizens** — Users who consume API services
   - **Operators** — Developers who run MCP services (like this one)
   - **Authorities** — Certify operators and collect a small tax on purchases
   - **First Curator** — The root of the chain, mints the initial cert-sat supply

## How Tollbooth Monetization Works

### The debit/rollback pattern

Every paid tool follows this pattern:

```python
@tool
async def current(latitude: float, longitude: float) -> dict:
    # 1. Debit credits (checks balance, applies constraints)
    err = await _debit_or_error("current")
    if err:
        return err

    # 2. Call the real API
    try:
        result = await weather.get_current(latitude, longitude)
        return await _with_warning(result)
    except Exception as e:
        # 3. Rollback on failure — user doesn't pay for broken calls
        await _rollback_debit("current")
        return {"success": False, "error": str(e)}
```

### The `_debit_or_error` flow

```
Tool call arrives
    │
    ▼
Cost = 0? ──yes──► Proceed (free tool)
    │
    no
    │
    ▼
STDIO mode? ──yes──► Proceed (local dev, no gating)
    │
    no
    │
    ▼
ConstraintGate active? ──yes──► Evaluate constraints
    │                              │
    no                        May discount, deny, or pass through
    │                              │
    ▼                              ▼
Debit from ledger ◄────── Effective cost
    │
    ▼
Balance sufficient? ──no──► Return error
    │
    yes
    │
    ▼
Proceed with tool execution
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
   - `NEON_DATABASE_URL` — Postgres connection string for credit ledgers
   - `BTCPAY_HOST`, `BTCPAY_API_KEY`, `BTCPAY_STORE_ID` — Lightning payments
   - `TOLLBOOTH_NOSTR_OPERATOR_NSEC` — Nostr key for Secure Courier
   - (Optional) `CONSTRAINTS_ENABLED=true` + `CONSTRAINTS_CONFIG=...`

### Run tests

```bash
pip install -e ".[dev]"
pytest -v
```

## Tool Reference

| MCP tool name              | Cost     | Description                           |
|----------------------------|----------|---------------------------------------|
| `weather_current`          | 1 sat    | Current weather for lat/lon           |
| `weather_forecast`         | 5 sats   | Multi-day forecast (1-16 days)        |
| `weather_historical`       | 10 sats  | Historical weather for a date range   |
| `weather_check_balance`    | Free     | Check credit balance                  |
| `weather_purchase_credits` | Free     | Buy credits via Lightning             |
| `weather_check_payment`    | Free     | Check invoice status                  |
| `weather_check_price`      | Free     | Preview cost (shows constraint effects)|
| `weather_service_status`   | Free     | Health + constraint config summary    |
| `weather_how_to_join`      | Free     | DPYC onboarding instructions          |
| `weather_get_tax_rate`     | Free     | Current certification tax rate        |
| `weather_lookup_member`    | Free     | Look up a DPYC member                |
| `weather_about`            | Free     | DPYC ecosystem description            |
| `weather_network_advisory` | Free     | Active network advisories             |

## DPYC Ecosystem

- [dpyc-community](https://github.com/lonniev/dpyc-community) — Registry + governance
- [tollbooth-dpyc](https://github.com/lonniev/tollbooth-dpyc) — Python SDK for Tollbooth monetization
- [tollbooth-authority](https://github.com/lonniev/tollbooth-authority) — Authority MCP service
- [thebrain-mcp](https://github.com/lonniev/thebrain-mcp) — Personal Brain MCP service
- [excalibur-mcp](https://github.com/lonniev/excalibur-mcp) — Twitter MCP service
- [dpyc-oracle](https://github.com/lonniev/dpyc-oracle) — Community concierge

## License

Apache-2.0
