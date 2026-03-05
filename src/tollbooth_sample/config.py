"""Settings for the tollbooth-sample weather service."""

from __future__ import annotations

from pydantic_settings import BaseSettings

from tollbooth.config import TollboothConfig


class Settings(BaseSettings):
    """Environment-driven configuration.

    All fields are optional so the server boots in local-dev mode
    (no gating) when env vars are absent.  Set the BTCPay / Neon
    vars to enable real monetization.
    """

    # ── Persistence (NeonVault for credit ledgers) ─────────────────
    neon_database_url: str | None = None

    # ── BTCPay Server (Lightning invoices) ─────────────────────────
    btcpay_host: str | None = None
    btcpay_api_key: str | None = None
    btcpay_store_id: str | None = None

    # ── Credit economics ───────────────────────────────────────────
    seed_balance_sats: int = 25
    credit_ttl_seconds: int = 604800  # 7 days

    # ── Constraint Engine (opt-in) ─────────────────────────────────
    constraints_enabled: bool = False
    constraints_config: str | None = None  # JSON string

    # ── Nostr identity (Secure Courier + Oracle delegation) ────────
    tollbooth_nostr_operator_nsec: str | None = None

    model_config = {"env_prefix": "", "env_file": ".env"}

    def to_tollbooth_config(self) -> TollboothConfig:
        """Build a TollboothConfig for passing to tollbooth library tools."""
        return TollboothConfig(
            btcpay_host=self.btcpay_host,
            btcpay_store_id=self.btcpay_store_id,
            btcpay_api_key=self.btcpay_api_key,
            seed_balance_sats=self.seed_balance_sats,
            credit_ttl_seconds=self.credit_ttl_seconds,
            constraints_enabled=self.constraints_enabled,
            constraints_config=self.constraints_config,
        )


# Lazy singleton — avoids loading env vars at import time.
_settings: Settings | None = None


def get_settings() -> Settings:
    """Return the cached Settings singleton."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
