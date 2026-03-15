"""
src/gateway/auth.py  (AM-22)

API key validation middleware for the BrandOS Gateway.
All endpoints (except /health) require a valid X-API-Key header.
The key is compared to GATEWAY_API_KEY from settings using a constant-time
comparison to prevent timing attacks.
"""

from __future__ import annotations

import hmac

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from src.shared.config import get_settings

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(
    api_key: str | None = Security(_api_key_header),
) -> str:
    """
    FastAPI dependency — validates the X-API-Key header.

    Returns the key on success.
    Raises HTTP 401 on missing or invalid key.
    """
    settings = get_settings()
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header.",
        )

    expected = settings.gateway_api_key
    # Constant-time comparison prevents timing oracle attacks
    if not hmac.compare_digest(api_key.encode(), expected.encode()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key.",
        )

    return api_key
