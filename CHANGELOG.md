# Changelog

All notable changes to this project will be documented in this file.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.2.0] — 2026-04-13

- security: add proof parameter to all tools with npub

## [0.1.13] — 2026-04-12

- chore: pin tollbooth-dpyc>=0.5.0 — Horizon OAuth removed from wheel

## [0.1.12] — 2026-04-11

- chore: pin tollbooth-dpyc>=0.4.9 — credential validator fix

## [0.1.11] — 2026-04-11

- chore: pin tollbooth-dpyc>=0.4.8 — ncred fix, courier diagnostics

## [0.1.10] — 2026-04-11

- chore: pin tollbooth-dpyc>=0.4.6
- Add credential_validator: validates btcpay creds at receive time

## [0.1.9] — 2026-04-11

- chore: pin tollbooth-dpyc>=0.4.0
- chore: pin tollbooth-dpyc>=0.3.3
- chore: pin tollbooth-dpyc>=0.3.2 — lazy MCP name resolution
- chore: pin tollbooth-dpyc>=0.3.1 — function name MCP stamping
- chore: pin tollbooth-dpyc>=0.3.0 — single tool identity model
- chore: pin tollbooth-dpyc>=0.2.17 for slug namespace filtering
- chore: pin tollbooth-dpyc>=0.2.14
- chore: pin tollbooth-dpyc>=0.2.13
- feat: UUID-keyed internals — paid_tool and registry use UUID, not short names
- chore: pin tollbooth-dpyc>=0.2.11
- chore: pin tollbooth-dpyc>=0.2.10
- fix: remove hardcoded cost claims from tool docstrings
- chore: pin tollbooth-dpyc>=0.2.9
- chore: pin tollbooth-dpyc>=0.2.8
- chore: pin tollbooth-dpyc>=0.2.7
- chore: pin tollbooth-dpyc>=0.2.6 for reset_pricing_model
- chore: pin tollbooth-dpyc>=0.2.5
- chore: pin tollbooth-dpyc>=0.2.4 for security fix + legacy UUID fallback
- chore: pin tollbooth-dpyc>=0.2.3 for pricing cache invalidation
- feat: UUID-based tool identity — TOOL_COSTS → TOOL_REGISTRY
- chore: gitignore uv.lock
- chore: update uv.lock for tollbooth-dpyc>=0.2.0
- chore: pin tollbooth-dpyc>=0.2.0 — clean Neon schema isolation
- chore: pin tollbooth-dpyc>=0.1.173 for onboarding late-attach fix
- chore: pin tollbooth-dpyc>=0.1.171 — don't cache empty ledgers on cold start
- chore: pin tollbooth-dpyc>=0.1.170 for cold start fixes
- chore: pin tollbooth-dpyc>=0.1.169 for session_status lifecycle
- chore: pin tollbooth-dpyc>=0.1.165 for demurrage constraint rename
- chore: pin tollbooth-dpyc>=0.1.164 for tranche_expiration constraint
- chore: pin tollbooth-dpyc>=0.1.163 for authority_client npub fix
- chore: pin tollbooth-dpyc>=0.1.162 for patron onboarding status
- fix: pin tollbooth-dpyc>=0.1.161
- chore: pin tollbooth-dpyc>=0.1.160

## [0.1.7] — 2026-03-29

- chore: pin tollbooth-dpyc>=0.1.159, bump to v0.1.7, update README
- refactor: adopt @runtime.paid_tool() decorator, annotate npub params
- chore: bump tollbooth-dpyc to >=0.1.155
- chore: bump tollbooth-dpyc to >=0.1.152
- chore: require Python >=3.12 (matches Horizon)
- chore: bump tollbooth-dpyc to >=0.1.150
- chore: bump tollbooth-dpyc to >=0.1.147
- chore: bump tollbooth-dpyc to >=0.1.144
- chore: bump tollbooth-dpyc to >=0.1.143
- chore: bump tollbooth-dpyc to >=0.1.138
- chore: bump tollbooth-dpyc to >=0.1.137
- chore: bump tollbooth-dpyc to >=0.1.136
- chore: bump tollbooth-dpyc to >=0.1.135
- chore: bump tollbooth-dpyc to >=0.1.134
- chore: bump tollbooth-dpyc to >=0.1.132
- chore: bump tollbooth-dpyc to >=0.1.131
- chore: bump tollbooth-dpyc to >=0.1.128
- chore: bump tollbooth-dpyc to >=0.1.127
- refactor: remove boilerplate now in OperatorRuntime
- refactor: nsec-only Settings, dual credential template
- chore: update uv.lock
- fix: credential template service must match CREDENTIAL_SERVICE
- feat: BTCPay credential field descriptions
- feat: pass service_name to OperatorRuntime
- chore: bump to 0.1.121 (nsec hex fix)
- chore: bump to 0.1.120
- chore: bump to 0.1.119
- chore: force cold start for v0.1.118 bootstrap
- chore: bump to 0.1.118
- chore: bump to 0.1.117 (decrypt fix)
- chore: bump to 0.1.116
- chore: bump to 0.1.115 for relay diagnostics
- chore: bump to 0.1.114 for bootstrap diagnostics
- chore: force Horizon redeploy for fresh bootstrap
- chore: bump tollbooth-dpyc to >=0.1.113 (relay bootstrap)
- chore: bump tollbooth-dpyc to >=0.1.112
- fix: pin >=0.1.111 to force Horizon to fetch vault bootstrap fix
- fix: remove 3 unused imports (ruff F401)
- fix: loose pin tollbooth-dpyc>=0.1.100 to avoid PyPI race
- ci: add ruff lint step to CI workflow
- chore: retrigger CI (PyPI propagation delay)
- chore: bump tollbooth-dpyc to >=0.1.111
- chore: retrigger CI (PyPI race)
- chore: bump tollbooth-dpyc to >=0.1.110 (bootstrap diagnostics)
- feat: restore Secure Courier greeting + bump to 0.1.109
- fix: delete test_credit_gating — standard tool costs in wheel now
- fix: delete test_operator_protocol — SampleOperator and DOMAIN_CATALOG deleted
- chore: trigger CI re-run (PyPI race condition)
- chore: bump tollbooth-dpyc to >=0.1.108 (infographic restored)
- chore: bump tollbooth-dpyc to >=0.1.107
- refactor: tollbooth-sample is now ~250 lines — register_standard_tools
- refactor: tollbooth-sample uses OperatorRuntime — thin operator
- fix: all ledger operations use async bootstrap path
- refactor: npub is required on all credit tools — no session cache
- feat: check_balance accepts explicit npub parameter
- refactor: _ensure_dpyc_session accepts explicit npub override
- chore: bump tollbooth-dpyc to >=0.1.104 for bootstrap Schnorr proof
- feat: process lifecycle telemetry in service_status
- fix: courier vault backed by bootstrapped Neon — credentials persist
- chore: bump tollbooth-dpyc to >=0.1.103 for generic vault helpers
- refactor: use generic vault helpers from tollbooth-dpyc wheel
- feat: BTCPay credentials loaded from vault, not env vars
- feat: expose Secure Courier tools as MCP @tool endpoints
- feat: add BTCPay credential template for operator onboarding
- chore: bump tollbooth-dpyc to >=0.1.102 for onboarding tool
- feat: get_onboarding_status tool + onboarding instructions in metadata
- feat: bootstrap-aware vault — discovers Neon URL from Authority
- feat: nsec-only deployment — strip all env vars except NSEC

## [0.1.5] — 2026-03-22

- chore: bump tollbooth-dpyc to >=0.1.96 for pricing model bridge
- chore: bump tollbooth-dpyc to >=0.1.95 for certify_credits rename
- refactor: rename certifier.certify() to certify_credits()
- chore: bump tollbooth-dpyc to >=0.1.94 for rollback tranche expiry
- chore: nudge deploy for tollbooth-dpyc v0.1.93 PyPI release
- chore: bump tollbooth-dpyc to >=0.1.93
- chore: add fastmcp.json for Horizon deployment config
- Merge pull request #3 from lonniev/feat/getting-started-guide
- chore: resolve merge conflict, keep nostr extra from main
- fix: extract operator_proof from model_json instead of separate tool arg (#8)
- feat: wire catalog conformance check at startup, bump to 0.1.5
- docs: add Getting Started guide for Lightning Node entrepreneurs

## [0.1.4] — 2026-03-14

- chore: bump tollbooth-dpyc to >=0.1.91
- feat: gate set_pricing_model to operator-only (Step 0C)
- feat: wire pricing CRUD tools for operator self-service (#7)

## [0.1.3] — 2026-03-07

- chore: bump version to 0.1.3
- chore: bump version to 0.1.1
- docs: clarify lookup_member accepts any role's npub (#6)

## [0.1.2] — 2026-03-07

- Merge pull request #5 from lonniev/feat/courier-construction
- feat: construct minimal SecureCourierService for invoice DM delivery

## [0.1.1] — 2026-03-07

- Merge pull request #4 from lonniev/feat/invoice-dm-delivery
- feat: wire invoice DM delivery via Secure Courier
- chore: trigger FastMCP Cloud redeploy for tollbooth-dpyc 0.1.75
- feat: wire surge pricing + fix example constraint configs (#2)
- Merge pull request #1 from lonniev/chore/ecosystem-links
- chore: pin tollbooth-dpyc>=0.1.74 for ECOSYSTEM_LINKS
- chore: add ecosystem_links to service_status response
- feat: initial tollbooth-sample weather MCP service
- Initial commit

