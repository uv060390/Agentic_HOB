"""
src/tools/custom_adapter.py  (AM-58)

Generic REST API adapter — config-driven, supports bearer/API key/basic/OAuth2 auth.
Any third-party REST API can be integrated without writing a new tool module.
Config is stored in the tool_config table per brand; credentials come from Infisical.

Example config (stored in tool_config.config_json):
    {
        "base_url": "https://api.somecrm.com/v1",
        "auth_type": "bearer",
        "secret_ref": "aim/crm_token",
        "endpoints": {
            "get_contacts": {"method": "GET", "path": "/contacts", "params": ["limit", "offset"]},
            "create_deal":  {"method": "POST", "path": "/deals"}
        }
    }
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.db import get_db
from src.shared.exceptions import ToolExecutionError, ToolNotRegisteredError
from src.shared.models import Company, ToolConfig
from src.tools.base_tool import BaseTool

logger = logging.getLogger(__name__)


def _get_credential(secret_ref: str, company_slug: str) -> str:
    """Fetch credential from vault (sandbox in dev)."""
    from src.shared.config import get_settings
    settings = get_settings()
    if settings.use_sandbox_vault:
        from src.vault.sandbox import get_secret
        return get_secret(f"/{secret_ref}")
    else:
        from src.vault.client import get_secret
        return get_secret(f"/{secret_ref}")


def _build_headers(auth_type: str, credential: str) -> dict[str, str]:
    """Build auth headers based on auth_type."""
    if auth_type == "bearer":
        return {"Authorization": f"Bearer {credential}"}
    elif auth_type == "api_key_header":
        return {"X-API-Key": credential}
    elif auth_type == "basic":
        import base64
        encoded = base64.b64encode(credential.encode()).decode()
        return {"Authorization": f"Basic {encoded}"}
    return {}


class CustomAdapterTool(BaseTool):
    """Config-driven REST API adapter."""

    slug = "custom_adapter"

    def __init__(self, company_slug: str, tool_slug: str, config: dict[str, Any]) -> None:
        super().__init__(company_slug)
        self.tool_slug = tool_slug
        self.config = config
        self.base_url: str = config.get("base_url", "")
        self.auth_type: str = config.get("auth_type", "bearer")
        self.secret_ref: str = config.get("secret_ref", "")
        self.endpoints: dict[str, dict[str, Any]] = config.get("endpoints", {})

    async def execute(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        self._log_call(action, params)

        endpoint = self.endpoints.get(action)
        if endpoint is None:
            raise ToolExecutionError(
                self.tool_slug,
                f"Unknown endpoint '{action}'. Available: {list(self.endpoints.keys())}",
            )

        method = endpoint.get("method", "GET").upper()
        path = endpoint.get("path", "/")
        url = f"{self.base_url.rstrip('/')}{path}"

        credential = ""
        if self.secret_ref:
            credential = _get_credential(self.secret_ref, self.company_slug)

        headers = _build_headers(self.auth_type, credential)
        headers["Content-Type"] = "application/json"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                if method == "GET":
                    response = await client.get(url, headers=headers, params=params)
                elif method == "POST":
                    response = await client.post(url, headers=headers, json=params)
                elif method == "PUT":
                    response = await client.put(url, headers=headers, json=params)
                elif method == "DELETE":
                    response = await client.delete(url, headers=headers, params=params)
                else:
                    raise ToolExecutionError(self.tool_slug, f"Unsupported HTTP method: {method}")

                response.raise_for_status()
                return {"ok": True, "data": response.json(), "status_code": response.status_code}

        except httpx.HTTPStatusError as exc:
            raise ToolExecutionError(
                self.tool_slug,
                f"{method} {url} returned {exc.response.status_code}: {exc.response.text[:300]}",
            ) from exc
        except Exception as exc:
            raise ToolExecutionError(self.tool_slug, str(exc)) from exc


async def get_custom_adapter(
    company_slug: str,
    tool_slug: str,
    db: AsyncSession | None = None,
) -> CustomAdapterTool:
    """Load a custom adapter from the tool_config table."""
    async def _run(session: AsyncSession) -> CustomAdapterTool:
        result = await session.execute(
            select(Company.id).where(Company.slug == company_slug)
        )
        company_id = result.scalar_one_or_none()
        if company_id is None:
            from src.shared.exceptions import CompanyNotFoundError
            raise CompanyNotFoundError(company_slug)

        result = await session.execute(
            select(ToolConfig).where(
                ToolConfig.company_id == company_id,
                ToolConfig.tool_slug == tool_slug,
            )
        )
        config_row = result.scalar_one_or_none()
        if config_row is None:
            raise ToolNotRegisteredError(tool_slug, company_slug)

        config = dict(config_row.config_json)
        if config_row.secret_ref:
            config["secret_ref"] = config_row.secret_ref

        return CustomAdapterTool(company_slug, tool_slug, config)

    if db is not None:
        return await _run(db)
    async with get_db() as session:
        return await _run(session)
