# Getting Started as a Tollbooth Operator

A step-by-step guide for Lightning Node entrepreneurs who want to
monetize an MCP service using the DPYC Tollbooth protocol.

## What you need

| Prerequisite | Why | How to get one |
|---|---|---|
| **Nostr keypair** | Your secure DPYC identity (`npub`/`nsec`) | `nak key generate` or any Nostr client (Damus, Amethyst, etc.) |
| **Lightning wallet** | Receive sats from your patrons | Alby, Zeus, Phoenix, or any BOLT11-capable wallet |
| **BTCPay credentials** | Create Lightning invoices for credit purchases | Provisioned by your sponsor Authority (or self-hosted), delivered via Secure Courier |
| **Neon Postgres schema** | Persistent credit ledgers | Provisioned automatically by your sponsor Authority — a per-operator schema with its own LOGIN role; you never handle a connection string |

You do **not** need to run your own Lightning node. A Lightning address
from any wallet provider is sufficient.

## 1. Generate a Nostr keypair

Your Nostr keypair is your identity in the DPYC ecosystem. The `npub`
(public key) is your secure DPYC identity — what other actors see and
verify. The `nsec` (secret key) signs Secure Courier DMs and proves
ownership.

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
- Provision your per-operator Neon schema with its own LOGIN role — wired to your
  operator automatically during onboarding; you never set or receive a `NEON_DATABASE_URL`
- Provision a BTCPay store (or help you connect your own)
- Deliver your `btcpay_host`, `btcpay_api_key`, and `btcpay_store_id` via Secure Courier

Your ad valorem certification fee on each credit purchase compensates
the Authority for these services — Neon persistence, certificate
signing, BTCPay hosting (when offered), and the registry membership
that makes your service discoverable.

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
      "url": "https://<your-deployment-host>/mcp",
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

The deploy-time secret contract is **one env var**:

| Variable | Required | Description |
|---|---|---|
| `TOLLBOOTH_NOSTR_OPERATOR_NSEC` | Yes | Your Nostr secret key — bootstraps your identity, signs Secure Courier DMs, and derives the AES-256-GCM key that encrypts your vault at rest. This is the **only** secret that lives in env. |

Optional knobs (also env-driven):

| Variable | Description |
|---|---|
| `TOLLBOOTH_NOSTR_RELAYS` | Comma-separated relay set for Secure Courier DMs. Defaults to a sensible set if omitted. |
| `SEED_BALANCE_SATS` | Free credits for new users (default: 25) |
| `CREDIT_TTL_SECONDS` | Credit expiry in seconds (default: 604800 = 7 days) |
| `CONSTRAINTS_ENABLED` | Enable the Constraint Engine (`true`/`false`) |
| `CONSTRAINTS_CONFIG` | JSON constraint configuration |

> **Your BTCPay secrets arrive via Secure Courier.** Your `btcpay_host`,
> `btcpay_api_key`, and `btcpay_store_id` are NOT env vars on your
> operator MCP. After deploy, your Authority delivers them as an
> encrypted Nostr DM to your operator npub. Your MCP receives the DM via
> the wheel's `receive_credentials` tool and stores the values in its
> vault, encrypted at rest with the key derived from your nsec. Rotating
> BTCPay credentials later? Same flow — no env var change, no redeploy.

> **Your Neon schema is wired automatically.** The per-operator Postgres
> schema your Authority provisions is connected to your operator during
> onboarding — you never set a `NEON_DATABASE_URL` env var or receive a
> connection string. Persistence Just Works once you're registered.

> **No Authority URL env var either.** Your Authority's service URL is
> resolved from the dpyc-community registry at runtime, based on the
> `upstream_authority_npub` in your registry entry. Switch Authorities
> by updating the registry — no env var changes or restarts.

## 5. Install and wire up tollbooth-dpyc

Pin the wheel **exactly** — match the version this repo pins in its
[`pyproject.toml`](pyproject.toml):

```bash
pip install "tollbooth-dpyc[nostr]==0.62.4"
```

The `[nostr]` extra installs Secure Courier dependencies for Nostr DM
credential exchange. (If your operator runs long async jobs, use the
`[nostr,prefect]` extra instead.)

### Minimal server skeleton

You do **not** hand-write debit, rollback, or balance plumbing. The
`OperatorRuntime` owns all of it — you declare your tool identities, hand
them to the runtime, and wrap each domain function in a single decorator:

```python
from typing import Annotated, Any
from pydantic import Field
from fastmcp import FastMCP

from tollbooth.tool_identity import ToolIdentity, STANDARD_IDENTITIES
from tollbooth.runtime import OperatorRuntime, register_standard_tools
from tollbooth.credential_templates import CredentialTemplate, FieldSpec
from tollbooth.credential_validators import validate_btcpay_creds

import my_service  # your pure-domain-logic module (no npub, no billing)

# Frozen UUID — minted once at a REPL (capability_uuid("my_paid_tool") or
# uuid.uuid4()), then pasted as a literal and never recomputed.
MY_PAID_TOOL_UUID = "…paste-your-uuid-here…"

_DOMAIN_TOOLS = [
    ToolIdentity(
        tool_id=MY_PAID_TOOL_UUID,
        capability="my_paid_tool",
        category="read",          # read | write | heavy → pricing tier
        intent="What this tool does",
    ),
]
TOOL_REGISTRY = {ti.tool_id: ti for ti in _DOMAIN_TOOLS}

mcp = FastMCP("my-service", instructions="…")

runtime = OperatorRuntime(
    tool_registry={**STANDARD_IDENTITIES, **TOOL_REGISTRY},
    operator_credential_template=CredentialTemplate(
        service="my-service-operator",
        version=2,
        description="Operator credentials for BTCPay Lightning payments",
        fields={
            "btcpay_host":     FieldSpec(required=True, sensitive=True),
            "btcpay_api_key":  FieldSpec(required=True, sensitive=True),
            "btcpay_store_id": FieldSpec(required=True, sensitive=True),
        },
    ),
    credential_validator=validate_btcpay_creds,
    service_name="My Service",
)

# Registers every standard DPYC tool (balance, purchase, Secure Courier,
# Oracle, pricing, constraints) and returns the slug-prefixed @tool decorator.
tool = register_standard_tools(mcp, "my", runtime, service_name="my-service")

@tool
@runtime.paid_tool(MY_PAID_TOOL_UUID)
async def my_paid_tool(
    query: str,
    npub: Annotated[str, Field(
        description="Required. Your Nostr public key (npub1...) for credit billing."
    )] = "",
    dpop_token: str = "",
) -> dict[str, Any]:
    """A paid tool — the decorator handles debit, rollback, and warnings."""
    return await my_service.do_something(query)
```

That is the complete paid tool: no manual `debit`/`rollback` calls. See
this repository's [`server.py`](src/tollbooth_sample/server.py) for the
full working example (three paid tools, Oracle delegation, the Constraint
Engine) and the [README](README.md#how-tollbooth-monetization-works) for a
deeper walk-through.

## 6. Deploy

### Horizon (recommended)

Build it with FastMCP; run it on **Horizon** — the MCP gateway and
governance layer from the team behind FastMCP and Prefect.

1. Push your repo to GitHub
2. Connect it on [Horizon](https://prefect.horizon.io)
3. Set your env vars in the dashboard
4. Your MCP service is live with a stable URL

### Self-hosted

Run directly:

```bash
python -m my_service.server
```

Or via Docker, systemd, etc. Ensure the env vars are set in your
runtime environment.

## 7. Receive your operator credentials via Secure Courier

With your MCP up but vault still empty, your sponsor Authority delivers
your `btcpay_host`, `btcpay_api_key`, and `btcpay_store_id` as an
encrypted Nostr DM addressed to your operator npub. (Your Neon schema is
already wired automatically — it is not part of this exchange.) You — the
human — drive the intake from any MCP client (Pricing Studio, Claude
Desktop, Claude Code, etc.):

1. Call `request_credential_channel(npub=<your_operator_npub>)` on the
   Authority's MCP. This signals the Authority to mint and send the DM.
2. Wait for the Authority's DM to land on your relay set.
3. Call `receive_credentials(npub=<your_operator_npub>)` on **your own**
   MCP (the operator service you just deployed). The wheel polls the
   relays, finds the Authority-signed DM, validates the signature,
   decrypts, and stores each field in your vault encrypted with the
   AES-256-GCM key derived from your nsec.

After this round trip your operator MCP has the BTCPay credentials it
needs to mint Lightning invoices — and, with the Authority-provisioned
Neon schema already wired, it can persist patron ledgers — all without
touching env vars or redeploying.

Rotating credentials later (new BTCPay store, Authority change) follows
the exact same flow.

> **Why courier and not env?** Env vars are visible to the deployment
> platform, leak into shell history and process listings, and require
> a redeploy to rotate. Secure Courier sends credentials only to the
> nsec that can decrypt them, stores them encrypted at rest, and
> rotates without redeploy. The cost is one extra MCP round-trip; the
> reward is no plaintext credentials anywhere outside your vault.

## 8. Register your first patron

Once deployed and onboarded, your patrons use the same Secure Courier
mechanism — now with you on the receiving end. The flow:

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
