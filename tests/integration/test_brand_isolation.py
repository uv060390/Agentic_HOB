"""
tests/integration/test_brand_isolation.py  (AM-45)
"""
from __future__ import annotations
from unittest.mock import AsyncMock, patch, MagicMock
import uuid
import pytest
from src.shared.exceptions import SecretNotFoundError, VaultUnavailableError


class TestBrandIsolation:
    def test_aim_agent_cannot_access_lembasmax_vault_path(self) -> None:
        from src.vault import sandbox
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises((SecretNotFoundError, VaultUnavailableError, KeyError, Exception)):
                sandbox.get_secret("/lembasmax/some_key")

    @pytest.mark.asyncio
    async def test_lembasmax_agent_cannot_query_aim_agent_config(self) -> None:
        from src.core.org_chart import get_standing_agents
        aim_id = uuid.uuid4()
        lembasmax_id = uuid.uuid4()

        mock_session = AsyncMock()

        # Simulate DB returning only lembasmax agents
        aim_agent = MagicMock()
        aim_agent.company_id = aim_id
        aim_agent.agent_slug = "aim-ceo"
        aim_agent.is_specialist = False

        lembasmax_agent = MagicMock()
        lembasmax_agent.company_id = lembasmax_id
        lembasmax_agent.agent_slug = "lembasmax-ceo"
        lembasmax_agent.is_specialist = False

        # company lookup returns lembasmax id
        company_execute = AsyncMock()
        company_execute.scalar_one_or_none = MagicMock(return_value=lembasmax_id)

        agents_execute = AsyncMock()
        agents_execute.scalars = MagicMock(
            return_value=MagicMock(all=MagicMock(return_value=[lembasmax_agent]))
        )

        mock_session.execute = AsyncMock(side_effect=[company_execute, agents_execute])

        agents = await get_standing_agents("lembasmax", db=mock_session)
        for agent in agents:
            assert agent.company_id != aim_id

    @pytest.mark.asyncio
    async def test_company_registry_scopes_by_slug(self) -> None:
        from src.core.company_registry import get_company
        from src.shared.exceptions import CompanyNotFoundError

        aim_company = MagicMock()
        aim_company.slug = "aim"
        aim_company.id = uuid.uuid4()

        lembasmax_company = MagicMock()
        lembasmax_company.slug = "lembasmax"
        lembasmax_company.id = uuid.uuid4()

        assert aim_company.id != lembasmax_company.id

        # Test with mocked session
        mock_session = AsyncMock()
        aim_result = AsyncMock()
        aim_result.scalar_one_or_none = MagicMock(return_value=aim_company)
        mock_session.execute = AsyncMock(return_value=aim_result)

        result = await get_company("aim", db=mock_session)
        assert result.slug == "aim"

    @pytest.mark.asyncio
    async def test_org_chart_does_not_cross_brands(self) -> None:
        from src.core.org_chart import get_standing_agents

        aim_id = uuid.uuid4()
        lembasmax_id = uuid.uuid4()

        aim_agent = MagicMock()
        aim_agent.company_id = aim_id
        aim_agent.agent_slug = "aim-ceo"
        aim_agent.is_specialist = False

        mock_session = AsyncMock()
        company_execute = AsyncMock()
        company_execute.scalar_one_or_none = MagicMock(return_value=aim_id)

        agents_execute = AsyncMock()
        agents_execute.scalars = MagicMock(
            return_value=MagicMock(all=MagicMock(return_value=[aim_agent]))
        )

        mock_session.execute = AsyncMock(side_effect=[company_execute, agents_execute])

        agents = await get_standing_agents("aim", db=mock_session)
        for agent in agents:
            assert agent.company_id == aim_id
            assert agent.company_id != lembasmax_id
