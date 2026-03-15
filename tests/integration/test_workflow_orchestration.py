"""
tests/integration/test_workflow_orchestration.py  (AM-106)

Integration tests for the multi-agent workflow orchestrator and
the creative intelligence loop.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.shared.exceptions import WorkflowError
from src.shared.schemas import AgentResult, AgentTask


class TestOrchestratorWorkflows:

    @pytest.mark.asyncio
    async def test_list_workflows_returns_registered_names(self) -> None:
        from src.core.orchestrator import list_workflows
        names = list_workflows()
        assert "creative_optimisation" in names
        assert "competitor_intelligence" in names

    @pytest.mark.asyncio
    async def test_get_workflow_returns_definition(self) -> None:
        from src.core.orchestrator import get_workflow
        wf = get_workflow("creative_optimisation")
        assert wf.name == "creative_optimisation"
        assert len(wf.steps) == 4
        assert wf.steps[0].agent_template == "engineer"

    @pytest.mark.asyncio
    async def test_get_unknown_workflow_raises(self) -> None:
        from src.core.orchestrator import get_workflow
        with pytest.raises(WorkflowError):
            get_workflow("nonexistent_workflow")

    @pytest.mark.asyncio
    async def test_run_workflow_unknown_name_raises(self) -> None:
        from src.core.orchestrator import run_workflow
        with pytest.raises(WorkflowError):
            await run_workflow("no_such_workflow", "aim")

    @pytest.mark.asyncio
    async def test_creative_optimisation_workflow_completes(self) -> None:
        """Full 4-step creative_optimisation workflow with all agents mocked."""
        from src.core.orchestrator import run_workflow, WorkflowStatus

        canned_result = AgentResult(success=True, output="step complete")

        with (
            patch("src.agents.registry.get_agent_instance") as mock_registry,
            patch("src.core.ticket_system.create_ticket", new_callable=AsyncMock, return_value="ticket-1"),
            patch("src.core.ticket_system.close_ticket", new_callable=AsyncMock),
        ):
            mock_agent = AsyncMock()
            mock_agent.run = AsyncMock(return_value=canned_result)
            mock_registry.return_value = mock_agent

            run = await run_workflow(
                "creative_optimisation",
                "aim",
                initial_context={"search_query": "health supplements India"},
            )

        assert run.status == WorkflowStatus.completed
        assert len(run.step_outputs) == 4
        assert run.step_outputs[0]["agent"] == "engineer"
        assert run.step_outputs[1]["agent"] == "data_scientist"
        assert run.step_outputs[2]["agent"] == "creative"
        assert run.step_outputs[3]["agent"] == "optimizer"
        assert run.parent_ticket_id == "ticket-1"

    @pytest.mark.asyncio
    async def test_prev_output_passed_to_next_step(self) -> None:
        """Each step receives the previous step's output as prev_output."""
        from src.core.orchestrator import run_workflow

        call_contexts: list[dict] = []

        async def capture_run(task: AgentTask) -> AgentResult:
            call_contexts.append(dict(task.context))
            return AgentResult(success=True, output=f"output_from_{task.context.get('prev_output', 'start')}")

        with (
            patch("src.agents.registry.get_agent_instance") as mock_registry,
            patch("src.core.ticket_system.create_ticket", new_callable=AsyncMock, return_value="t-1"),
            patch("src.core.ticket_system.close_ticket", new_callable=AsyncMock),
        ):
            mock_agent = AsyncMock()
            mock_agent.run = AsyncMock(side_effect=capture_run)
            mock_registry.return_value = mock_agent

            await run_workflow("creative_optimisation", "aim")

        # Step 2 should have received step 1's output
        assert call_contexts[1]["prev_output"] == "output_from_start"
        # Step 3 should have received step 2's output
        assert "output_from_" in call_contexts[2]["prev_output"]

    @pytest.mark.asyncio
    async def test_failed_step_raises_workflow_error(self) -> None:
        from src.core.orchestrator import run_workflow

        with (
            patch("src.agents.registry.get_agent_instance") as mock_registry,
            patch("src.core.ticket_system.create_ticket", new_callable=AsyncMock, return_value="t-1"),
            patch("src.core.ticket_system.close_ticket", new_callable=AsyncMock),
        ):
            mock_agent = AsyncMock()
            mock_agent.run = AsyncMock(
                return_value=AgentResult(success=False, output="Apify timeout")
            )
            mock_registry.return_value = mock_agent

            with pytest.raises(WorkflowError) as exc_info:
                await run_workflow("creative_optimisation", "aim")

        assert "engineer" in str(exc_info.value)
        assert "build_scraper" in str(exc_info.value)


class TestBaseAgentDelegate:

    @pytest.mark.asyncio
    async def test_delegate_passes_company_id(self) -> None:
        """delegate() always uses the calling agent's company_id — brand isolation."""
        from src.agents.templates.ceo import CEOAgent

        ceo = CEOAgent(agent_id="aim-ceo", company_id="aim")
        canned = AgentResult(success=True, output="delegated result")

        with patch("src.agents.registry.get_agent_instance") as mock_get:
            mock_target = AsyncMock()
            mock_target.run = AsyncMock(return_value=canned)
            mock_get.return_value = mock_target

            result = await ceo.delegate("build_scraper", "engineer", {"tool": "apify"})

        mock_get.assert_called_once_with("engineer", "aim")
        assert result.output == "delegated result"

    @pytest.mark.asyncio
    async def test_delegate_returns_agent_result(self) -> None:
        from src.agents.templates.ceo import CEOAgent

        ceo = CEOAgent(agent_id="aim-ceo", company_id="aim")

        with patch("src.agents.registry.get_agent_instance") as mock_get:
            mock_target = AsyncMock()
            mock_target.run = AsyncMock(
                return_value=AgentResult(success=True, output="engineer output")
            )
            mock_get.return_value = mock_target

            result = await ceo.delegate("integrate_api", "engineer")

        assert isinstance(result, AgentResult)
        assert result.success is True


class TestCreativeLibrary:

    @pytest.mark.asyncio
    async def test_save_creative_returns_url(self) -> None:
        from src.tools.storage.google_drive import save_creative

        url = await save_creative(
            brand_slug="aim",
            file_name="hook_v1.md",
            content="Ad hook content here",
            metadata={"creative_type": "image", "source": "original"},
            created_by_agent="aim-creative",
        )
        assert "aim" in url
        assert url.startswith("https://")

    @pytest.mark.asyncio
    async def test_get_top_creatives_respects_brand_scope(self) -> None:
        from src.tools.storage.google_drive import get_top_creatives

        results = await get_top_creatives(brand_slug="aim", limit=3)
        assert len(results) <= 3
        for r in results:
            assert r["brand_slug"] == "aim"

    @pytest.mark.asyncio
    async def test_get_top_creatives_source_filter(self) -> None:
        from src.tools.storage.google_drive import get_top_creatives

        results = await get_top_creatives(brand_slug="aim", source="competitor")
        for r in results:
            assert r["source"] == "competitor"

    @pytest.mark.asyncio
    async def test_update_actual_ctr_does_not_raise(self) -> None:
        from src.tools.storage.google_drive import update_actual_ctr

        # Stub — should not raise
        await update_actual_ctr(
            creative_id="mock-creative-0",
            actual_ctr=0.042,
            updated_by_agent="aim-performance",
        )


class TestOptimizerAgent:

    @pytest.mark.asyncio
    async def test_set_objective_stores_values(self) -> None:
        from src.agents.specialists.optimizer import OptimizerAgent

        agent = OptimizerAgent(agent_id="aim-optimizer", company_id="aim")
        task = AgentTask(
            task_subtype="set_objective",
            context={
                "objective": "improve CTR to 4%",
                "success_criteria": "predicted_ctr >= 0.04 on 5 creatives",
            },
        )

        with (
            patch("src.core.audit_log.write", new_callable=AsyncMock),
        ):
            result = await agent.run(task)

        assert result.success is True
        assert agent._objective == "improve CTR to 4%"
        assert agent._success_criteria == "predicted_ctr >= 0.04 on 5 creatives"

    @pytest.mark.asyncio
    async def test_wound_down_raises_on_run(self) -> None:
        from datetime import datetime, timezone
        from src.agents.specialists.optimizer import OptimizerAgent
        from src.shared.exceptions import AgentWindDownError

        agent = OptimizerAgent(agent_id="aim-optimizer", company_id="aim")
        agent.wound_down_at = datetime.now(timezone.utc)

        task = AgentTask(task_subtype="set_objective", context={})
        with pytest.raises(AgentWindDownError):
            await agent.run(task)
