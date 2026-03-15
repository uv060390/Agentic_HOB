"""
tests/conftest.py

Shared pytest fixtures for unit and integration tests.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import AsyncClient

from src.gateway.app import create_app
from src.shared.config import get_settings


# ── Event loop ────────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def event_loop_policy():
    return asyncio.DefaultEventLoopPolicy()


# ── Settings override ─────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def use_test_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Override settings for tests — always use development env, sandbox vault."""
    monkeypatch.setenv("BRANDOS_ENV", "development")
    monkeypatch.setenv("GATEWAY_API_KEY", "test-api-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
    monkeypatch.setenv("CEREBRAS_API_KEY", "test-cerebras-key")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# ── HTTP test client ──────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP test client for Gateway integration tests."""
    app = create_app()
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


# ── Mock database session ─────────────────────────────────────────────────────


@pytest.fixture
def mock_db_session() -> MagicMock:
    """Mock async DB session for unit tests that don't need a real DB."""
    session = MagicMock()
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


# ── Audit log mock ────────────────────────────────────────────────────────────


@pytest.fixture
def mock_audit_log(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    """Replace audit_log.write with a no-op mock."""
    from src.core import audit_log

    mock = AsyncMock(return_value="test-audit-id")
    monkeypatch.setattr(audit_log, "write", mock)
    return mock


# ── Budget enforcer mock ──────────────────────────────────────────────────────


@pytest.fixture
def mock_budget_enforcer(monkeypatch: pytest.MonkeyPatch) -> dict[str, AsyncMock]:
    """Replace budget_enforcer check/record with no-op mocks."""
    from src.core import budget_enforcer

    check_mock = AsyncMock(return_value=None)
    record_mock = AsyncMock(return_value=None)
    monkeypatch.setattr(budget_enforcer, "check", check_mock)
    monkeypatch.setattr(budget_enforcer, "record", record_mock)
    return {"check": check_mock, "record": record_mock}
