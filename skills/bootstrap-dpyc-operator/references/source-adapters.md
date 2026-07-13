# Source adapters — mapping existing code into a domain module

The generated operator keeps **domain logic** in one module (`src/<package>/<slug>.py`) and
**monetization** in the decorators on `server.py`. Your job is to move the user's existing
logic into that domain module, unchanged in behavior, and then expose each capability as a
paid tool. Three starting shapes:

The exemplar for all three is `tollbooth-sample/src/tollbooth_sample/weather.py`: pure async
functions that return plain dicts, with no billing, no `npub`, no SDK imports.

---

## A. Existing REST API
The most direct case (this is what `weather.py` does with Open-Meteo).

1. Write async functions in the domain module that call the upstream with `httpx`:
   ```python
   import httpx
   _BASE = "https://api.example.com/v1"

   async def get_thing(thing_id: str) -> dict:
       async with httpx.AsyncClient(timeout=15.0) as client:
           resp = await client.get(f"{_BASE}/things/{thing_id}")
           resp.raise_for_status()
           return {"success": True, **resp.json()}
   ```
2. In `server.py`, wrap each with `@tool` + `@runtime.paid_tool(<frozen tool_id constant>)`,
   adding `npub`/`dpop_token` params, and call the domain function. (See
   `canonical-pattern.md` for how tool_id is minted once and frozen.)
3. If the REST API needs a **key**, decide whose key it is:
   - **Operator's own key** (one shared upstream account) → add it to the operator
     `CredentialTemplate` fields; read it from the vault at call time.
   - **Per-patron key** (each user brings their own upstream credential) → this is the case
     that warrants a session module; see `references/sessions-and-vaults.md`.

---

## B. Existing stdio MCP
The user already has MCP tools, just spoken over stdio (a `FastMCP` app run with the stdio
transport, or the low-level MCP `Server`).

1. **Drop the transport.** DPYC operators are SSE/HTTP on FastMCP Cloud (never stdio). You do
   not keep their `mcp.run(transport="stdio")` entry point.
2. **Lift each tool's body** into an async domain function in `src/<package>/<slug>.py`. Strip
   the MCP plumbing (the `@server.tool()` / `@mcp.tool` decorator, the `TextContent`
   wrapping); keep the actual work and return a plain dict.
3. **Re-expose** each as a paid tool in the generated `server.py` with the standard decorator
   stack. Preserve the tool's original name as the `capability` (users may already depend on
   it) unless there's a reason to rename.
4. Their existing input schema (pydantic models / JSON schema) maps to the generated tool's
   typed parameters.

---

## C. Existing vanilla HTTP MCP
An MCP served over plain HTTP without the DPYC runtime (e.g. a hand-rolled FastMCP HTTP app).

Same as (B), minus the transport swap: the tool bodies move into the domain module and get the
decorator stack. The generated project's `fastmcp.json` / `.fastmcp.yaml` replace their
deployment config. Anything they built for their own auth/billing is dropped — the DPYC
runtime supersedes it.

---

## Choosing `category` per tool
- `read` — cheap lookups, no side effects (default for most GETs).
- `write` — mutations or higher-value calls.
- `heavy` — expensive/slow operations (large compute, big upstream cost).

Category drives the default pricing tier and ACL. Final prices are set later in Pricing Studio,
not in code.

## Where upstream secrets go
| Whose credential? | Where it lives |
|---|---|
| Operator's own upstream account (shared) | operator `CredentialTemplate` field → vault |
| Each patron's own upstream credential | per-patron vault + a session module (see sessions-and-vaults.md) |
| No upstream credential (open API) | nothing — call it directly (like weather.py) |
