"""
src/vault/client.py  (AM-13)

Infisical SDK wrapper — fetches secrets with per-brand, per-agent scoping.
All secrets in production are retrieved here; only INFISICAL_TOKEN is a system env var.
"""

from __future__ import annotations

from functools import lru_cache

from infisical_client import ClientSettings, InfisicalClient  # type: ignore[import]

from src.shared.config import get_settings
from src.shared.exceptions import SecretNotFoundError, VaultUnavailableError


@lru_cache(maxsize=1)
def _get_infisical_client() -> InfisicalClient:
    settings = get_settings()
    return InfisicalClient(
        ClientSettings(
            client_id=settings.infisical_token,
            client_secret="",  # machine identity uses token only
            site_url=settings.infisical_host,
        )
    )


def get_secret(
    path: str,
    *,
    environment: str = "production",
    project_id: str = "",
) -> str:
    """
    Fetch a single secret from Infisical by path.

    Path convention:
      /<company_slug>/<agent_slug>/<key>   — agent-scoped
      /<company_slug>/<key>                — brand-scoped
      /shared/<key>                        — shared across all brands

    Raises:
        SecretNotFoundError: if the path does not exist in Infisical.
        VaultUnavailableError: if Infisical is unreachable.
    """
    settings = get_settings()
    try:
        client = _get_infisical_client()
        parts = path.strip("/").split("/")
        secret_name = parts[-1]
        secret_path = "/" + "/".join(parts[:-1]) if len(parts) > 1 else "/"

        secret = client.getSecret(
            secret_name=secret_name,
            environment=environment,
            project_id=project_id or settings.infisical_token,
            path=secret_path,
        )
        if secret is None:
            raise SecretNotFoundError(path)
        return str(secret.secretValue)
    except SecretNotFoundError:
        raise
    except Exception as exc:
        raise VaultUnavailableError(
            f"Infisical unreachable at {settings.infisical_host}: {exc}"
        ) from exc


def get_brand_secret(company_slug: str, key: str, **kwargs: str) -> str:
    """Convenience: fetch a brand-scoped secret."""
    return get_secret(f"/{company_slug}/{key}", **kwargs)


def set_brand_secret(
    company_slug: str,
    key: str,
    value: str,
    *,
    environment: str = "production",
    project_id: str = "",
) -> None:
    """
    Write a brand-scoped secret to Infisical at path /{company_slug}/{key}.

    Called ONLY during onboarding to persist API keys immediately after
    validation. In all other contexts the vault is read-only from agent code.

    Raises:
        VaultUnavailableError: if Infisical is unreachable.
    """
    settings = get_settings()
    try:
        client = _get_infisical_client()
        client.createSecret(
            secret_name=key,
            secret_value=value,
            environment=environment,
            project_id=project_id or settings.infisical_token,
            path=f"/{company_slug}",
        )
    except Exception as exc:
        raise VaultUnavailableError(
            f"Failed to write secret '{key}' for brand '{company_slug}': {exc}"
        ) from exc


def set_shared_secret(
    key: str,
    value: str,
    *,
    environment: str = "production",
    project_id: str = "",
) -> None:
    """
    Write a shared (cross-brand) secret to Infisical at path /shared/{key}.

    Used for provider-level keys (Anthropic, Cerebras) that are not brand-scoped.
    """
    settings = get_settings()
    try:
        client = _get_infisical_client()
        client.createSecret(
            secret_name=key,
            secret_value=value,
            environment=environment,
            project_id=project_id or settings.infisical_token,
            path="/shared",
        )
    except Exception as exc:
        raise VaultUnavailableError(
            f"Failed to write shared secret '{key}': {exc}"
        ) from exc


def get_agent_secret(company_slug: str, agent_slug: str, key: str, **kwargs: str) -> str:
    """Convenience: fetch an agent-scoped secret."""
    return get_secret(f"/{company_slug}/{agent_slug}/{key}", **kwargs)
