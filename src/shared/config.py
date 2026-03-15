"""
src/shared/config.py  (AM-11)

Pydantic Settings — loads all BrandOS configuration from environment variables.
In production only INFISICAL_TOKEN, INFISICAL_HOST, BRANDOS_DB_URL, BRANDOS_ENV,
and LOG_LEVEL are set as system env vars. All other secrets come from Infisical.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Core ─────────────────────────────────────────────────────────────────
    brandos_env: Literal["development", "staging", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # ── Primary database ──────────────────────────────────────────────────────
    brandos_db_url: str = "postgresql+psycopg://brandos:brandos_dev@localhost:5432/brandos"
    brandos_supabase_url: str = ""
    brandos_supabase_key: str = ""

    # ── Secret vault ──────────────────────────────────────────────────────────
    infisical_token: str = ""
    infisical_host: str = "http://localhost:8080"

    # ── LLM providers (local dev only — use Infisical in production) ──────────
    anthropic_api_key: str = ""
    cerebras_api_key: str = ""

    # ── Gateway ───────────────────────────────────────────────────────────────
    gateway_api_key: str = "dev-insecure-key"

    # ── Messaging ─────────────────────────────────────────────────────────────
    whatsapp_verify_token: str = ""
    whatsapp_api_token: str = ""
    telegram_bot_token: str = ""

    @property
    def is_production(self) -> bool:
        return self.brandos_env == "production"

    @property
    def use_sandbox_vault(self) -> bool:
        return self.brandos_env == "development" and not self.infisical_token


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
