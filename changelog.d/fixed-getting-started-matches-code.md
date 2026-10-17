- GETTING-STARTED.md says what the code does, checked line by line against
  tollbooth-dpyc 0.97.0 and this repo's `server.py`:
  - BTCPay credentials: the operator delivers them to its **own** MCP
    (`request_credential_channel` → reply → `receive_credentials`). The guide said the
    Authority DMs them and that the channel is opened on the Authority.
  - Adoption: documents `request_adoption` / `adoption_status` and what approval
    provisions. The Neon connection arrives as an encrypted relay event, not a DM
    exchange and not an env var.
  - Patrons: prove an npub (`request_npub_proof` / `receive_npub_proof`) and buy
    credits. The guide said every patron couriers credentials and that the operator
    registers them; this sample has no patron credential template.
  - Certification fee: debited from the **operator's** balance at its Authority, which
    the operator must fund. The guide said the Authority paid it from its own balance.
  - Env vars: one. Removed the table of optional variables (`SEED_BALANCE_SATS`,
    `CREDIT_TTL_SECONDS`, `CONSTRAINTS_*`, `TOLLBOOTH_NOSTR_RELAYS`) — nothing reads them.
  - Removed the `[prefect]` extra (the SDK has none), the hardcoded `0.62.4` pin, and
    `weather_how_to_join` (the tool is `weather_oracle_how_to_join`).
  - BTCPay hosting: nothing in the protocol provisions a store; a hosted store is an
    arrangement outside it.
