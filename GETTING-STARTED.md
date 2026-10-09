# Getting Started as a Tollbooth Operator

A step-by-step guide for Lightning Node entrepreneurs who want to
monetize an MCP service using the DPYC Tollbooth protocol.

Tool names below carry this sample's `weather_` slug. Your service's own
slug replaces it.

## What you need

| Prerequisite | Why | How to get one |
|---|---|---|
| **Nostr keypair** | Your secure DPYC identity (`npub`/`nsec`) | `nak key generate` or any Nostr client (Damus, Amethyst, etc.) |
| **A Nostr client holding that key** | You reply to your own service's Secure Courier DM as the operator | Any client that sends encrypted DMs, or Pricing Studio |
| **A BTCPay Server store** | Creates the Lightning invoices your patrons pay | Your own server, or a store on one somebody hosts for you. You supply its host, an API key and the store ID |
| **A sponsor Authority** | Certifies your credit sales and provisions your database | Chosen in step 2, joined in step 5 |

You do **not** provision a database. Your Authority creates a
per-operator Neon Postgres schema with its own LOGIN role when it adopts
you, and your service finds it by itself.

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
- The **npub** to name yourself to your Authority and to your own service
- The **nsec** as the `TOLLBOOTH_NOSTR_OPERATOR_NSEC` env var

## 2. Choose a sponsor Authority

Authorities are the institutional backbone of the DPYC ecosystem. They
certify Operators, collect a certification fee on credit purchases
(default 2%, minimum 10 sats), and sign Nostr event certificates that
prove an Operator has paid before collecting a fare.

To find one, ask the DPYC Oracle, or browse
[`members/authorities`](https://github.com/lonniev/dpyc-community/tree/main/members/authorities)
in the community registry:

```
Call: weather_oracle_how_to_join
```

Note the Authority's `npub`. You name it in step 5.

When an Authority adopts you, it does three things:
- Creates your ledger row, so you can hold a certification balance with it
- Provisions your per-operator Neon schema with its own LOGIN role
- Registers you in the [dpyc-community](https://github.com/lonniev/dpyc-community) registry

It does **not** provision a BTCPay store and it hands you no env vars.

> **How Authorities are registered:** Authorities self-register via a
> Nostr DM challenge-response protocol with the Prime Authority.
> Operators do not need to understand this process -- you simply name
> your Authority by its registered `npub`, and the DPYC registry handles
> service discovery at runtime.

## 3. Install and wire up tollbooth-dpyc

Pin the wheel **exactly**, to the version this repo pins in its
[`pyproject.toml`](pyproject.toml):

```bash
pip install "tollbooth-dpyc[nostr]==<the version pinned in pyproject.toml>"
```

The `[nostr]` extra installs Secure Courier dependencies for Nostr DM
credential exchange.

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

## 4. Deploy with one env var

The deploy-time secret contract is **one env var**:

| Variable | Required | Description |
|---|---|---|
| `TOLLBOOTH_NOSTR_OPERATOR_NSEC` | Yes | Your Nostr secret key — bootstraps your identity, signs Secure Courier DMs, and derives the AES-256-GCM key that encrypts your vault at rest. This is the **only** secret that lives in env. |

The operator runtime reads nothing else from the environment:

- **No database URL.** Your Authority publishes your Neon connection to
  Nostr relays, encrypted to your npub. Your service reads it on cold
  start using only its nsec.
- **No BTCPay variables.** You deliver those over Secure Courier in step 6.
- **No Authority URL.** It is resolved from the registry at runtime, from
  the `upstream_authority_npub` in your registry entry.
- **No relay list.** The relay set comes from the DPYC Oracle.
- **No pricing, expiry or constraint variables.** Prices, credit expiry
  and constraints all live in your pricing model, which you edit with
  `weather_set_pricing_model` or Pricing Studio.

### Horizon (recommended)

Build it with FastMCP; run it on **Horizon** — the MCP gateway and
governance layer from the team behind FastMCP and Prefect.

1. Push your repo to GitHub
2. Connect it on [Horizon](https://prefect.horizon.io)
3. Set `TOLLBOOTH_NOSTR_OPERATOR_NSEC` in the dashboard
4. Your MCP service is live with a stable URL

### Self-hosted

Run directly:

```bash
python -m my_service.server
```

Or via Docker, systemd, etc. Ensure the env var is set in your runtime
environment.

A freshly deployed service has an identity and nothing else.
`weather_session_status` reports `not_registered` until an Authority
adopts it.

## 5. Get adopted by your Authority

Adoption is what gives your service a database and a place in the
registry. You ask from your own service; the Authority's owner decides.

1. Call `weather_request_adoption` on **your own** MCP:
   - `authority_npub` — the Authority you chose in step 2
   - `service_url` — your MCP endpoint
   - `dpop_token` — proof that you hold the operator nsec: a kind-27235
     Nostr event signed by your operator key, whose `u` tag holds this
     tool's exact name, with empty content and a `created_at` within 60
     seconds. Only the operator can make this call.
2. Your service delivers the request to the Authority, MCP to MCP. The
   Authority records it as pending and notifies its owner.
3. The owner approves it on their own time (`approve_adoption`).
4. Poll `weather_adoption_status(authority_npub=…)` for
   `pending` / `approved` / `rejected` / `provisioned`.

On approval the Authority provisions your Neon schema, publishes the
connection to Nostr relays as an event encrypted to your npub, and
registers you through the Oracle. Your registry entry looks like:

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

Your service picks the connection up by itself and `weather_session_status`
turns `ready`. You never set a connection string.

> **The other path.** An Authority owner can adopt you in one call with
> the Authority's `register_operator`, which takes two proofs at once:
> yours and the Authority's own. The effect is identical.

## 6. Deliver your BTCPay credentials to your own service

Your service cannot create invoices until it holds `btcpay_host`,
`btcpay_api_key` and `btcpay_store_id`. **You** deliver them, to **your
own** MCP, over Secure Courier. Your Authority is not involved.

`weather_get_operator_onboarding_status` shows what is still missing.

1. Call `weather_request_credential_channel(sender_npub=<your operator
   npub>, service="tollbooth-sample-operator")`. Your service sends a
   welcome DM to that npub with the fields to fill in, and the call
   returns a `dpop_token` — the session phrase for this channel.
2. Open the DM in a Nostr client that holds your operator key. Reply with
   the three values, keeping the `dpop_token` line exactly as shown, and
   send the reply through the `rendezvous_relay` the DM names.
3. Call `weather_receive_credentials(sender_npub=<your operator npub>,
   service="tollbooth-sample-operator", dpop_token=<the session phrase>)`
   **once**, after you have replied. Each call drains the mailbox, so do
   not poll.

The values are stored in your vault, encrypted with the AES-256-GCM key
derived from your nsec, and the response never echoes them. Once all
three are present they are checked; a malformed set is wiped and a DM
tells you what to correct. The payment client is rebuilt from the new
values with no restart.

Rotating later, for a new store or a new API key, is the same three
calls. No env var changes and no redeploy.

> **Why courier and not env?** Env vars are visible to the deployment
> platform, leak into shell history and process listings, and require
> a redeploy to rotate. Secure Courier sends credentials only to the
> nsec that can decrypt them, stores them encrypted at rest, and
> rotates without redeploy. The cost is one extra MCP round-trip; the
> reward is no plaintext credentials anywhere outside your vault.

## 7. Fund your certification balance

Every credit purchase by a patron is certified by your Authority, and the
certification fee is debited from **your** balance at that Authority. When
that balance reaches zero, patron top-ups cannot be certified and
`purchase_credits` tells the patron to try again later.

1. Call `purchase_credits` on the **Authority's** MCP for the sats you
   want to pre-fund. It returns a Lightning invoice.
2. Pay it, then call the Authority's `check_payment`.
3. `weather_check_authority_balance` on your own service shows what is left.

## 8. Serve your first patron

A patron needs a Nostr npub and nothing else. This sample asks patrons
for no credentials.

1. Patron (or their AI agent) calls
   `weather_request_npub_proof(patron_npub=…)`. Your service sends them a
   challenge DM.
2. Patron replies to it from their Nostr client.
3. Patron calls `weather_receive_npub_proof(patron_npub=…, dpop_token=…)`
   once. It returns a new `dpop_token`, a proof grant your service signed.
4. Patron calls `weather_purchase_credits(npub, dpop_token, amount_sats)`,
   pays the Lightning invoice, and calls `weather_check_payment`.
5. Patron calls paid tools, passing `npub` and `dpop_token` each time.
   Each call debits their pre-funded balance. No popups, no interruptions.

The paid-tool path checks two things: the proof and the balance. It does
not look the patron up in the community registry, and this runtime
registers nobody on a patron's behalf.

> **If your service needs a secret from each patron** (an upstream API
> key, say), pass a `patron_credential_template` to `OperatorRuntime`.
> That adds `request_patron_credentials` and `receive_patron_credentials`,
> the same Secure Courier exchange with the patron replying. A service
> whose upstream uses OAuth2 passes an `oauth_provider` instead.

## Where the BTCPay store comes from

The runtime needs three values and does not care who runs the server:

1. A [BTCPay Server](https://btcpayserver.org) you can reach — your own,
   or one where somebody has given you a store
2. A store on it with a working Lightning connection
3. An API key that can create invoices for that store

Nothing in the protocol provisions a store for you. If your sponsor or
anyone else hosts one for you, that is an arrangement between the two of
you; they hand you the three values and you deliver them in step 6
exactly as you would your own.

The certification fee cascade routes through your Authority regardless of
who hosts the BTCPay instance.

## The certification fee cascade

When a patron calls `purchase_credits`:

1. Your service requests a certificate from your Authority (MCP-to-MCP)
2. The Authority debits its certification fee (default 2%, min 10 sats) from **your** pre-funded balance with it
3. The Authority returns a signed certificate
4. Your service creates a BTCPay invoice for the **full amount** the patron requested
5. Patron pays, credits land in their ledger

The patron pays exactly what they asked for. The certification fee is an
Operator cost, paid from the balance you funded in step 7. This
eliminates any visible tax from the patron's perspective.

## Quick reference

| Role | Joins by | Pays |
|---|---|---|
| **Patron** | Proving an npub to the Operator — no registration | The Operator, per tool call, from pre-funded credits |
| **Operator** (you) | Adoption by an Authority | The Authority, a certification fee on each credit sale |
| **Authority** | Registration with the Prime Authority | Its upstream, a certification fee |

## Links

- [tollbooth-dpyc](https://github.com/lonniev/tollbooth-dpyc) — Python SDK
- [dpyc-community](https://github.com/lonniev/dpyc-community) — Registry + governance
- [tollbooth-authority](https://github.com/lonniev/tollbooth-authority) — Authority MCP service
- [dpyc-oracle](https://github.com/lonniev/dpyc-oracle) — Community concierge
- [DPYC Oracle `how_to_join`](https://github.com/lonniev/dpyc-oracle) — Full onboarding instructions
