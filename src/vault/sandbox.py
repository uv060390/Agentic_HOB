"""
src/vault/sandbox.py  (AM-14)

Mock credential provider for local development and testing.
When BRANDOS_ENV=development and INFISICAL_TOKEN is not set,
the system falls back to reading secrets from environment variables.

Mapping convention: the Infisical path is flattened to an env var name.
  /aim/meta_ads_token  →  AIM_META_ADS_TOKEN
  /shared/anthropic_api_key  →  SHARED_ANTHROPIC_API_KEY (or just ANTHROPIC_API_KEY)
"""

from __future__ import annotations

import os

from src.shared.exceptions import SecretNotFoundError


# Explicit env var overrides for well-known paths used in local dev.
_PATH_TO_ENV: dict[str, str] = {
    "/shared/anthropic_api_key": "ANTHROPIC_API_KEY",
    "/shared/cerebras_api_key": "CEREBRAS_API_KEY",
    "/shared/openai_api_key": "OPENAI_API_KEY",
    "/shared/perplexity_api_key": "PERPLEXITY_API_KEY",
}


def _path_to_env_key(path: str) -> str:
    """Convert /company/agent/key → COMPANY_AGENT_KEY."""
    return path.strip("/").replace("/", "_").upper()


def get_secret(path: str) -> str:
    """
    Retrieve a secret from environment variables (sandbox mode only).

    Lookup order:
    1. Explicit mapping in _PATH_TO_ENV
    2. Derived env var: /aim/meta_token → AIM_META_TOKEN
    3. SecretNotFoundError if neither is set
    """
    # Check explicit mapping first
    env_key = _PATH_TO_ENV.get(path) or _path_to_env_key(path)
    value = os.environ.get(env_key)
    if value:
        return value
    raise SecretNotFoundError(path)


def get_brand_secret(company_slug: str, key: str) -> str:
    return get_secret(f"/{company_slug}/{key}")


def get_agent_secret(company_slug: str, agent_slug: str, key: str) -> str:
    return get_secret(f"/{company_slug}/{agent_slug}/{key}")
