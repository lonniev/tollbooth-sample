# The canonical operator pattern

Distilled from `tollbooth-sample/src/tollbooth_sample/server.py`. Always read the live file
too — this is a map, not a substitute.

## Anatomy of `server.py`

```python
from fastmcp import FastMCP
from tollbooth.tool_identity import ToolIdentity, STANDARD_IDENTITIES, capability_uuid
from tollbooth.runtime import OperatorRuntime, register_standard_tools
from tollbooth.credential_templates import CredentialTemplate, FieldSpec
from tollbooth.credential_validators import validate_btcpay_creds

# 1. The FastMCP app, with patron-facing instructions.
mcp = FastMCP("<slug>-mcp", instructions="...onboarding + pricing blurb...")

# 2. Domain tool identities. Each tool_id is a FROZEN, OPAQUE UUID literal, minted ONCE
#    at tool birth and then never changed. Generate the starting value once at a REPL:
#        >>> from tollbooth.tool_identity import capability_uuid
#        >>> capability_uuid("get_current_weather")   # or uuid.uuid4() — equally fine
#    then paste the RESULT as a constant. capability_uuid is only a seed helper (the wheel
#    never calls it at runtime); pasting the literal means renaming `capability` later does
#    NOT change the identity, so the tool keeps its pricing rows in Neon.
GET_CURRENT_WEATHER_UUID = "b7327eb8-92b4-5252-84e0-ba3f437a16ed"  # frozen literal

_DOMAIN_TOOLS = [
    ToolIdentity(
        tool_id=GET_CURRENT_WEATHER_UUID,
        capability="get_current_weather",
        category="read",          # read | write | heavy
        intent="Get current weather conditions",
    ),
    # ...one per paid tool...
]
TOOL_REGISTRY = {ti.tool_id: ti for ti in _DOMAIN_TOOLS}

# 3. The runtime. It provides ALL DPYC machinery: vault, auth, pricing, payments, audit.
runtime = OperatorRuntime(
    tool_registry={**STANDARD_IDENTITIES, **TOOL_REGISTRY},
    operator_credential_template=CredentialTemplate(
        service="<slug>-operator",
        version=2,
        description="Operator credentials for BTCPay Lightning payments",
        fields={
            "btcpay_host":    FieldSpec(required=True, sensitive=True, description="..."),
            "btcpay_api_key": FieldSpec(required=True, sensitive=True, description="..."),
            "btcpay_store_id":FieldSpec(required=True, sensitive=True, description="..."),
            # add upstream API secrets here if your service needs them
        },
    ),
    operator_credential_greeting="Hi — I'm <Service>. You requested a credential channel.",
    service_name="<Service>",
    credential_validator=validate_btcpay_creds,
)

# 4. Register every STANDARD DPYC tool (check_balance, purchase_credits, Secure Courier,
#    Oracle, pricing, constraints, ...). Returns the @tool decorator for domain tools.
tool = register_standard_tools(mcp, "<slug>", runtime,
                               service_name="<slug>-mcp", service_version=__version__)

# 5. Domain tools = @tool + @runtime.paid_tool(<frozen tool_id>). Every paid tool
#    carries npub (billing identity) and dpop_token (proof) params. The decorators do the
#    debit/ACL/pricing; the body is pure domain logic. Reference the SAME frozen constant
#    you declared above. (The live template happens to write
#    capability_uuid("get_current_weather") here — that resolves to the same literal, but
#    referencing the constant keeps the identity in one place.)
@tool
@runtime.paid_tool(GET_CURRENT_WEATHER_UUID)
async def current(latitude: float, longitude: float,
                  npub: str = "", dpop_token: str = "") -> dict:
    """Get current weather conditions for a location."""
    return await weather.get_current(latitude, longitude)

# 6. Guarded entry point.
def main() -> None:
    from tollbooth import validate_operator_tools
    missing = validate_operator_tools(mcp, "<slug>")
    if missing:
        import sys
        print(f"⚠ Missing base-catalog tools: {', '.join(missing)}", file=sys.stderr)
    mcp.run()
```

## register_standard_tools vs. paid_tool — don't confuse them
- `register_standard_tools(...)` registers the **standard** DPYC tools (balance, purchase,
  courier, oracle, pricing, status) and returns the `@tool` decorator.
- `@runtime.paid_tool(<frozen tool_id>)` registers **your domain** tool and makes it
  billable. Both decorators stack on each domain function.

## DRY boundaries — the SDK owns these; never reimplement
| Concern | SDK module |
|---|---|
| Vault encryption (AES-256-GCM) | `tollbooth.vault_encryption` |
| Neon-backed credential vault | `tollbooth.vaults.neon.NeonVault` |
| Nostr identity proofs | `tollbooth.identity_proof` |
| Secure Courier (credential DMs) | `tollbooth.secure_courier` |
| ACL / debit | `OperatorRuntime.debit_or_deny` |
| Pricing constraints | `tollbooth.pricing*` |
| Authority client | `tollbooth.authority_client` |
| Lightning payments | `tollbooth.btcpay_client` |
| Audit trail | `tollbooth.nostr_audit` |
| Session caching | `tollbooth.session_cache` |

If you find yourself writing encryption, signing, proof, payment, or vault code, stop — import
it instead.

## Security NEVERs (apply to every tool you generate)
- Never log, print, echo, or return an nsec, API key, token, or BTCPay key. Redact in
  `__repr__` and pop secrets before returning (the `SecureCourier.receive()` pattern).
- Never hardcode npubs, nsecs, connection strings, or version numbers.
- Treat every tool argument as adversarial — it comes from an AI agent. Validate at the
  boundary.
- Every paid tool exposes `npub` and `dpop_token`. Don't drop them.
