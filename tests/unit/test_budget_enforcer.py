"""
tests/unit/test_budget_enforcer.py  (AM-25)

Unit tests for src/core/budget_enforcer.py
Tests use mocked DB sessions — no real database required.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.shared.exceptions import BudgetExceededError


class TestCheck:
    @pytest.mark.asyncio
    async def test_allows_when_no_cap_configured(self) -> None:
        """If no agent config found, budget check passes."""
        with patch("src.core.budget_enforcer._resolve_ids", new_callable=AsyncMock) as mock_resolve:
            import uuid
            mock_resolve.return_value = (uuid.uuid4(), uuid.uuid4(), None)
            from src.core.budget_enforcer import check
            # Should not raise
            await check(agent_id="aim-ceo", company_id="aim")

    @pytest.mark.asyncio
    async def test_allows_when_under_cap(self) -> None:
        """Agent with $5 spent against $10 cap passes."""
        import uuid
        agent_uuid = uuid.uuid4()
        company_uuid = uuid.uuid4()

        with (
            patch("src.core.budget_enforcer._resolve_ids", new_callable=AsyncMock) as mock_resolve,
            patch("src.core.budget_enforcer._get_monthly_spent", new_callable=AsyncMock) as mock_spent,
        ):
            mock_resolve.return_value = (agent_uuid, company_uuid, 10.0)
            mock_spent.return_value = 5.0

            from src.core.budget_enforcer import check
            await check(agent_id="aim-ceo", company_id="aim")

    @pytest.mark.asyncio
    async def test_raises_when_at_cap(self) -> None:
        """Agent at exactly the cap raises BudgetExceededError."""
        import uuid
        agent_uuid = uuid.uuid4()
        company_uuid = uuid.uuid4()

        with (
            patch("src.core.budget_enforcer._resolve_ids", new_callable=AsyncMock) as mock_resolve,
            patch("src.core.budget_enforcer._get_monthly_spent", new_callable=AsyncMock) as mock_spent,
        ):
            mock_resolve.return_value = (agent_uuid, company_uuid, 10.0)
            mock_spent.return_value = 10.0

            from src.core.budget_enforcer import check
            with pytest.raises(BudgetExceededError) as exc_info:
                await check(agent_id="aim-ceo", company_id="aim")

            err = exc_info.value
            assert err.agent_slug == "aim-ceo"
            assert err.company_slug == "aim"
            assert err.cap_usd == 10.0

    @pytest.mark.asyncio
    async def test_raises_when_over_cap(self) -> None:
        """Spending over the cap also raises BudgetExceededError."""
        import uuid
        agent_uuid = uuid.uuid4()
        company_uuid = uuid.uuid4()

        with (
            patch("src.core.budget_enforcer._resolve_ids", new_callable=AsyncMock) as mock_resolve,
            patch("src.core.budget_enforcer._get_monthly_spent", new_callable=AsyncMock) as mock_spent,
        ):
            mock_resolve.return_value = (agent_uuid, company_uuid, 10.0)
            mock_spent.return_value = 12.50

            from src.core.budget_enforcer import check
            with pytest.raises(BudgetExceededError):
                await check(agent_id="aim-ceo", company_id="aim")

    @pytest.mark.asyncio
    async def test_logs_warning_at_80_percent(self, caplog: pytest.LogCaptureFixture) -> None:
        """Warning is logged when spending hits 80% of cap."""
        import logging
        import uuid

        agent_uuid = uuid.uuid4()
        company_uuid = uuid.uuid4()

        with (
            patch("src.core.budget_enforcer._resolve_ids", new_callable=AsyncMock) as mock_resolve,
            patch("src.core.budget_enforcer._get_monthly_spent", new_callable=AsyncMock) as mock_spent,
        ):
            mock_resolve.return_value = (agent_uuid, company_uuid, 10.0)
            mock_spent.return_value = 8.5  # 85% — above 80% threshold

            from src.core.budget_enforcer import check
            with caplog.at_level(logging.WARNING, logger="src.core.budget_enforcer"):
                await check(agent_id="aim-ceo", company_id="aim")

            assert any("Budget alert" in record.message for record in caplog.records)


class TestBudgetExceededError:
    def test_error_message_format(self) -> None:
        err = BudgetExceededError(agent_slug="aim-ceo", company_slug="aim", cap_usd=10.0)
        assert "aim-ceo" in str(err)
        assert "aim" in str(err)
        assert "10.00" in str(err)

    def test_attributes_set(self) -> None:
        err = BudgetExceededError(agent_slug="aim-ceo", company_slug="aim", cap_usd=25.50)
        assert err.agent_slug == "aim-ceo"
        assert err.company_slug == "aim"
        assert err.cap_usd == 25.50
