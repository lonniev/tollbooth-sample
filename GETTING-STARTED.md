# Getting Started as a Tollbooth Operator

A step-by-step guide for Lightning Node entrepreneurs who want to
monetize an MCP service using the DPYC Tollbooth protocol.

## What you need

| Prerequisite | Why | How to get one |
|---|---|---|
| **Nostr keypair** | Your Honor Chain identity (`npub`/`nsec`) | `nak key generate` or any Nostr client (Damus, Amethyst, etc.) |
| **Lightning wallet** | Receive sats from your patrons | Alby, Zeus, Phoenix, or any BOLT11-capable wallet |
| **BTCPay credentials** | Create Lightning invoices for credit purchases | Self-hosted or provisioned by your sponsor Authority |
| **Neon Postgres database** | Persistent credit ledgers | Free tier at [neon.tech](https://neon.tech) |

You do **not** need to run your own Lightning node. A Lightning address
from any wallet provider is sufficient.

## 1. Generate a Nostr keypair

Your Nostr keypair is your identity in the DPYC ecosystem. The `npub`
(public key) identifies you on the Honor Chain. The `nsec` (secret key)
signs Secure Courier DMs and proves ownership.

```bash
# Using the nak CLI (https://github.com/fiatjaf/nak)
nak key generate
```

Save both the `npub` and `nsec`. You will need:
- The **npub** for community registration
- The **nsec** as the `TOLLBOOTH_NOSTR_OPERATOR_NSEC` env var

## 2. Find a sponsor Authority

Authorities are the institutional backbone of the DPYC ecosystem. They
certify Operators, collect a small certification fee on credit purchases
(default 2%, minimum 10 sats), and sign Nostr event certificates that
prove an Operator is registered.

To find an active Authority, ask the DPYC Oracle:

```
Call: weather_how_to_join
```

Your sponsor Authority will:
- Register you in the [dpyc-community](https://github.com/lonniev/dpyc-community) registry
- Provision a BTCPay store (or help you connect your own)
- Provide the `BTCPAY_HOST`, `BTCPAY_API_KEY`, and `BTCPAY_STORE_ID` for your service

> **How Authorities are registered:** Authorities self-register via a
> Nostr DM challenge-response protocol with the Prime Authority.
> Operators do not need to understand this process -- you simply reference
> your Authority by its registered `npub`, and the DPYC registry handles
> service discovery at runtime.

## 3. Register as an Operator

Your sponsor Authority registers your `npub` in the dpyc-community
registry. The registry entry looks like:

```json
{
  "npub": "npub1your...",
  "role": "operator",
  "status": "active",
  "display_name": "my-weather-service",
  "services": [
    {
      "name": "my-service",
      "url": "https://my-service.fastmcp.app/mcp",
      "description": "What my service does"
    }
  ],
  "upstream_authority_npub": "npub1authority..."
}
```

The `upstream_authority_npub` field links you to your Authority. At
runtime, `tollbooth-dpyc` resolves your Authority's service URL from
this registry entry automatically -- no hardcoded Authority URL needed.

## 4. Configure environment variables

Set these env vars for your deployment:

| Variable | Required | Description |
|---|---|---|
| `NEON_DATABASE_URL` | Yes | Postgres connection string for credit ledgers |
| `BTCPAY_HOST` | Yes | BTCPay Server hostname (e.g. `btcpay.example.com`) |
| `BTCPAY_API_KEY` | Yes | Scoped API key for your BTCPay store |
| `BTCPAY_STORE_ID` | Yes | Your BTCPay store ID |
| `TOLLBOOTH_NOSTR_OPERATOR_NSEC` | Yes | Your Nostr secret key (enables Secure Courier + identity) |
| `SEED_BALANCE_SATS` | No | Free credits for new users (default: 25) |
| `CREDIT_TTL_SECONDS` | No | Credit expiry in seconds (default: 604800 = 7 days) |
| `CONSTRAINTS_ENABLED` | No | Enable the Constraint Engine (`true`/`false`) |
| `CONSTRAINTS_CONFIG` | No | JSON constraint configuration |

> **No Authority URL env var.** Your Authority's service URL is resolved
> from the dpyc-community registry at runtime, based on the
> `upstream_authority_npub` in your registry entry. This means you can
> switch Authorities by updating the registry -- no env var changes or
> restarts needed.

## 5. Install and wire up tollbooth-dpyc

```bash
pip install "tollbooth-dpyc[nostr]>=0.1.78"
```

The `[nostr]` extra installs Secure Courier dependencies for Nostr DM
credential exchange.

### Minimal server skeleton

```python
from fastmcp import FastMCP
from tollbooth import LedgerCache, NeonVault, BTCPayClient, ToolTier
from tollbooth.tools import credits

mcp = FastMCP("my-service")

# ... configure vault, ledger, btcpay from env vars ...

@mcp.tool
async def my_paid_tool(query: str) -> dict:
    """A tool that costs 1 api_sat."""
    # Debit
    if not await ledger.debit(npub, "my_paid_tool", ToolTier.READ):
        return {"error": "Insufficient balance"}
    # Do work
    try:
        result = do_something(query)
        return {"success": True, "data": result}
    except Exception as e:
        # Rollback on failure
        ledger_entry = await ledger.get(npub)
        ledger_entry.rollback_debit("my_paid_tool", ToolTier.READ)
        ledger.mark_dirty(npub)
        return {"error": str(e)}
```

See this repository's [`server.py`](src/tollbooth_sample/server.py) for
a complete working example with all credit tools, Oracle delegation, and
the Constraint Engine.

## 6. Deploy

### FastMCP Cloud (recommended)

1. Push your repo to GitHub
2. Connect it on [FastMCP Cloud](https://app.fastmcp.cloud)
3. Set your env vars in the dashboard
4. Your MCP service is live with a stable URL

### Self-hosted

Run directly:

```bash
python -m my_service.server
```

Or via Docker, systemd, etc. Ensure the env vars are set in your
runtime environment.

## 7. Register your first patron

Once deployed, your patrons onboard via Secure Courier (Nostr DM
credential exchange). The flow:

1. Patron generates a Nostr keypair
2. Patron (or their AI agent) calls `my_service_session_status` to check state
3. If no session, patron calls `my_service_request_credential_channel` with their npub
4. Patron receives a DM and replies with credentials
5. Patron calls `my_service_receive_credentials` to activate

> **You register patrons on their behalf.** Citizens are registered in
> the dpyc-community registry by their Operator. Patrons do not contact
> the Authority -- that is exclusively your relationship.

## Using a sponsor's BTCPay Server

The lowest-friction path: your sponsor Authority creates a scoped store
on their BTCPay instance. You provide only a Lightning address as the
payout destination. The Authority gives you:

- `BTCPAY_HOST` — their BTCPay server
- `BTCPAY_STORE_ID` — your dedicated store
- `BTCPAY_API_KEY` — scoped to your store only

Sats from patron purchases route to your Lightning wallet via BTCPay's
automated payout system. The Authority's certification fee (default 2%,
minimum 10 sats) is deducted at purchase time via the certification fee
cascade -- you never handle the fee manually.

## Self-hosted BTCPay (advanced)

If you prefer full control:

1. Deploy [BTCPay Server](https://btcpayserver.org) on your own infrastructure
2. Create a store and connect your Lightning node
3. Generate an API key with invoice permissions
4. Use your own `BTCPAY_HOST`, `BTCPAY_STORE_ID`, `BTCPAY_API_KEY`

Everything else works the same -- the certification fee cascade routes
through the Authority regardless of who hosts the BTCPay instance.

## The certification fee cascade

When a patron calls `purchase_credits`:

1. Your service auto-requests a certificate from your Authority (MCP-to-MCP)
2. The Authority deducts its certification fee (default 2%, min 10 sats) from its own pre-funded balance with the Prime Authority
3. The Authority returns a signed certificate
4. Your service creates a BTCPay invoice for the **full amount** the patron requested
5. Patron pays, credits land in their ledger

The patron pays exactly what they asked for. The certification fee is an
Operator cost, paid from the Operator's pre-funded balance with the
Authority. This eliminates any visible tax from the patron's perspective.

## Quick reference

| Role | Registers with | Pays fees to | Registers others |
|---|---|---|---|
| **Citizen** (patron) | Operator | Operator (tool costs) | -- |
| **Operator** (you) | Authority | Authority (cert fee) | Citizens |
| **Authority** | Prime Authority | Prime (cert fee) | Operators |

## Links

- [tollbooth-dpyc](https://github.com/lonniev/tollbooth-dpyc) — Python SDK
- [dpyc-community](https://github.com/lonniev/dpyc-community) — Registry + governance
- [tollbooth-authority](https://github.com/lonniev/tollbooth-authority) — Authority MCP service
- [dpyc-oracle](https://github.com/lonniev/dpyc-oracle) — Community concierge
- [DPYC Oracle `how_to_join`](https://github.com/lonniev/dpyc-oracle) — Full onboarding instructions
