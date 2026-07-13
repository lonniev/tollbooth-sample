---
name: bootstrap-dpyc-operator
description: Turn an existing REST API, stdio MCP, or HTTP MCP into a monetized DPYC Tollbooth Operator MCP — Bitcoin Lightning micropayments, Nostr identity, per-tool dynamic pricing. Use when someone wants to monetize their API or MCP with the DPYC ("Don't Pester Your Customer") protocol, or asks to "make my MCP paid", "add a tollbooth", "charge sats per call", or "become a DPYC operator".
license: Apache-2.0
---

# Bootstrap a DPYC Tollbooth Operator MCP

This skill scaffolds a new **DPYC Operator MCP server** that wraps a user's existing
service. The operator sells its tools for Bitcoin Lightning micropayments: patrons pre-fund a
satoshi balance (identified by a Nostr `npub`, no KYC), and each tool call debits credits at a
price the operator sets dynamically. All the payment, identity, vault, and audit machinery
comes from the `tollbooth-dpyc` SDK — the user only supplies domain logic.

The canonical template is the **tollbooth-sample** repo. This skill always fetches it live so
it never goes stale, then mirrors its structure into a new project.

## The one rule: the template is the source of truth

Do **not** invent structure, versions, or APIs from memory. Clone `tollbooth-sample` and copy
what is actually there. The SDK evolves; the live template reflects the current shape.

## Procedure

### 1. Confirm inputs
Gather (ask only for what the user did not already provide):
- **Service name / slug** — short, lowercase, e.g. `weather`, `polygon`, `wiki`. Becomes the
  tool prefix (`<slug>_check_balance`, `<slug>_<your_tool>`).
- **One-line description** of what the service does.
- **Path to the user's existing code** and its **shape**: a REST API, a stdio MCP, or an
  HTTP MCP. Detect the shape yourself if you can see the code (look for `FastMCP`, an MCP
  `Server`, stdio transport, or plain HTTP handlers vs. a REST client).

If the upstream service needs credentials (API key, OAuth), note that — it affects the
credential template and whether a per-call session module is warranted (see
`references/sessions-and-vaults.md`).

### 2. Fetch the live template
```bash
git clone --depth 1 https://github.com/lonniev/tollbooth-sample.git /tmp/tollbooth-sample-template
```
Then read, from the clone:
- `pyproject.toml` — the **live** wheel pin (e.g. `tollbooth-dpyc[nostr]==X.Y.Z`). Never
  hardcode a version; copy whatever the template pins today.
- `src/tollbooth_sample/server.py` — the bootstrap anatomy you will mirror.
- `src/tollbooth_sample/weather.py` — the domain-module exemplar (pure logic, no billing).
- `src/tollbooth_sample/config.py`, `fastmcp.json`, `.fastmcp.yaml`, `renovate.json`,
  `.github/workflows/ci.yml`, `tests/` — copy these with only names/slugs changed.

See `references/canonical-pattern.md` for the distilled anatomy and the DRY / security rules.

### 3. Plan the tool catalog
Enumerate the user's endpoints or existing MCP tools. For each, decide:
- **capability name** — stable, snake_case (e.g. `get_current_weather`). Choose deliberately;
  it's patron-facing and awkward to change later.
- **tool_id** — a frozen, opaque UUID minted **once** at tool birth (run
  `capability_uuid(name)` at a REPL, or `uuid.uuid4()`), then pasted as a literal constant and
  never changed. Freezing the literal is what lets you rename a capability later without
  orphaning its pricing rows. See `references/canonical-pattern.md`.
- **category** — `read`, `write`, or `heavy` (drives default pricing tier and ACL).
- **intent** — one line of human-readable purpose.

Not every upstream endpoint must become a paid tool. Prefer selling complete, useful answers
over raw data fragments.

### 4. Generate the new project
Create `<slug>-mcp/` as a **sibling** of the user's existing code — never modify their
original repo. Mirror the template, changing only what must change:
- **Package rename**: `tollbooth_sample` → `<package_name>`; slug `weather` → `<slug>`.
- **Domain module** (`src/<package>/<slug>.py`): wrap the user's service. Follow the recipe
  for their shape in `references/source-adapters.md`. This module is **pure domain logic** —
  no `npub`, no pricing, no SDK calls beyond the upstream client. If the upstream needs a
  per-patron authenticated client, see `references/sessions-and-vaults.md`.
- **server.py**: replace the `_DOMAIN_TOOLS` `ToolIdentity` list with the catalog from step 3;
  set the `CredentialTemplate` fields to the operator's real secrets (BTCPay is always
  present; add upstream API secrets if any); wrap each domain function with
  `@tool` + `@runtime.paid_tool(<frozen tool_id constant>)`; every paid tool signature carries
  `npub` and `dpop_token` params (copy the template's exactly).
- **config.py**: keep as-is — the only required env var is `TOLLBOOTH_NOSTR_OPERATOR_NSEC`.
- **pyproject.toml**: set name/description; keep the **exact** `==` pin from the template. Add
  the user's upstream dependency (e.g. their REST client). If the operator runs long tasks
  (durable async jobs), use the `[nostr,prefect]` extra instead of `[nostr]`.
- **renovate.json**, **fastmcp.json**, **.fastmcp.yaml**, **ci.yml**: copy; adjust only the
  server path/slug. Do not change the CI Python version or the "wait for wheel on PyPI" step.
- **tests/**: adapt `test_<slug>.py` from `test_weather.py` — cover happy paths **and
  adversarial inputs** (missing npub, out-of-range args, malformed upstream responses). Treat
  all tool arguments as adversarial.
- **README.md**, fresh **CHANGELOG.md** (start at `0.1.0`), **LICENSE**.

### 5. Verify
From inside `<slug>-mcp/`:
```bash
pip install -e ".[dev]"
ruff check .
pytest -v
python -m <package>.server   # runs the validate_operator_tools guard; prints a warning if a base tool is missing
```
The server needs `TOLLBOOTH_NOSTR_OPERATOR_NSEC` to fully run, but tests + the validate guard
confirm the wiring without any live infrastructure.

### 6. Hand off to onboarding
The code is only half the story — the operator must join the DPYC network to get paid. Walk
the user through `references/onboarding-checklist.md`, and point them at the cloned template's
`GETTING-STARTED.md` for the full narrative (Nostr keypair → sponsor Authority provisions Neon
+ BTCPay → deliver secrets via Secure Courier → set per-tool prices in Pricing Studio → deploy
on FastMCP Cloud / Horizon).

## What NOT to do
- Do not reimplement encryption, vaults, auth, pricing, payments, or audit — the SDK owns them
  (`references/canonical-pattern.md` lists the boundaries). If you're writing crypto, stop.
- Do not log, echo, or return secrets (nsec, API keys, tokens, BTCPay keys).
- Do not hardcode npubs, nsecs, connection strings, or versions.
- Do not set prices in code — prices live in Neon, edited via Pricing Studio.
