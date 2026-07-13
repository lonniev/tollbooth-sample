# Go-live checklist — joining the DPYC network

Scaffolding the code is half the job. To actually collect sats, the operator must join the
DPYC Social Contract. The cloned template's `GETTING-STARTED.md` has the full narrative; this
is the condensed checklist.

## 1. Generate a Nostr identity
The operator's Nostr keypair **is** their identity in DPYC (no email/username).
```bash
nak key generate    # or any Nostr client (Damus, Amethyst, ...)
```
- Keep the **npub** (public) for registration.
- Set the **nsec** (secret) as `TOLLBOOTH_NOSTR_OPERATOR_NSEC` — the only secret in env. It
  bootstraps identity, signs Secure Courier DMs, and derives the vault encryption key.

## 2. Find a sponsor Authority
Authorities are the certification backbone: they register operators, provision infrastructure,
and take a small ad-valorem fee (default 2%, min 10 sats) on each credit purchase. Ask the
Oracle how to join (via your service's `<slug>_oracle_how_to_join` tool, or the public
dpyc-oracle). Your sponsor Authority will:
- Register you in the `dpyc-community` registry (makes your service discoverable).
- **Provision your per-operator Neon schema** with its own LOGIN role — you get Neon
  automatically; you never set a `NEON_DATABASE_URL` yourself.
- Provision or help connect a BTCPay store for Lightning invoices.

## 3. Deliver operator secrets via Secure Courier
Your BTCPay credentials (and any operator-wide upstream API secret) go into the encrypted vault
through the Secure Courier DM flow — never into env or code:
1. Call `<slug>_request_credential_channel` to get a welcome DM with a session phrase.
2. Reply via your Nostr client with the secrets as JSON.
3. Call `<slug>_receive_credentials(sender_npub=..., service="<slug>-operator", dpop_token=<phrase>)`.

## 4. Set your prices in Pricing Studio
Tool prices live in Neon, edited via **Pricing Studio** (iOS) — never hardcoded. Newly
scaffolded tools start unpriced; set a price per tool (and any constraints / surge / discounts)
before patrons can call them. DPYC's differentiator is dynamic pricing — lean into it.

## 5. Deploy
Deploy on FastMCP Cloud / Horizon using the generated `fastmcp.json` + `.fastmcp.yaml`. The
only env var the deployment needs is `TOLLBOOTH_NOSTR_OPERATOR_NSEC`.

## 6. Smoke test the live service
- `<slug>_get_operator_onboarding_status` → confirms configuration readiness.
- `<slug>_service_status` → version + health.
- `<slug>_check_balance` (free) and `<slug>_check_price` → confirm pricing resolves.
- Call one paid tool end-to-end with a funded patron npub.

You do **not** need to run your own Lightning node — a Lightning address from any wallet
suffices for receiving.
