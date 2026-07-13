# Sessions and vaults — two different things

New operators often conflate these. They are separate layers.

## The vault is the SDK's — you don't build one
The encrypted, persistent **credential vault** is `tollbooth.vaults.neon.NeonVault`:
AES-256-GCM (`VaultCipher` keyed by the operator's nsec), Neon-backed. Every operator gets it
for free through `OperatorRuntime` + Secure Courier. Secrets patrons and operators deliver via
Secure Courier land there, encrypted at rest.

You do **not** write encryption or persistence code. When you need a stored credential back,
you ask the runtime — e.g. `runtime.restore_oauth_session(npub)` (loads, refreshes, and
re-persists an OAuth token) or `runtime.store_patron_session(...)`. That is the whole story for
most operators, including the stateless template (`weather.py` stores nothing per patron).

## The optional per-call "session" — only when the upstream needs a per-patron client
Some operators sell access to an upstream API that requires **each patron's own
credential** to make a call. For those, the tool handler needs a *live authenticated upstream
client* built from that patron's (already-vaulted, already-decrypted) credential, used for the
duration of the call. That assembly is a **session** concern, not a vault concern — it holds
no secrets at rest and does no crypto.

This is a design choice, not a required step. If your upstream needs no per-patron credential,
you need none of this.

### What this looks like in the wild (examples, not a mandate)
Two production operators do this today. They happen to name the file `vault.py`, which is a bit
of a misnomer — the real vault is the SDK's; these modules only assemble a client:

- **OAuth per patron** — `schwab-mcp`: each patron authorizes via Schwab OAuth. A per-call
  helper routes through `runtime.restore_oauth_session(npub)` and bundles the token,
  account, and a live client together for that one call. Refreshed tokens persist back to the
  SDK vault; the bundle is discarded after the call.
- **API key per patron** — `thebrain-mcp`: each patron brings their own API key. A helper
  caches a live client per user via the SDK's `tollbooth.session_cache.SessionCache` (TTL), so
  repeated calls in a window reuse it. Its own docstring notes that credential *persistence* is
  delegated to the SDK vault, not stored in the session.

Treat these as illustrations of the shape, not as a template to copy line-for-line. A given
operator may need much less; build the smallest thing that assembles the client you need.

### If you do add one
- Name it for what it is (a session/client assembler), keep it tiny, and let the SDK own
  persistence and refresh.
- Redact secrets in `__repr__`; never return the client's credentials from a tool.
- Get the credential from the runtime/vault at call time — don't cache raw secrets yourself.

## Rule of thumb
| Your upstream... | You need |
|---|---|
| needs no credential (open API) | nothing — call it directly |
| uses one operator-wide credential | an operator `CredentialTemplate` field; read from vault |
| needs each patron's own credential per call | a small per-call session/client assembler |
