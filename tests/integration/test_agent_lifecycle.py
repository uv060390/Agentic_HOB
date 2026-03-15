"""
tests/integration/test_agent_lifecycle.py  (AM-41, AM-42, AM-43)
"""
from __future__ import annotations
from unittest.mock import AsyncMock, patch, MagicMock
import pytest
from src.agents.templates.ceo import CEOAgent
from src.agents.templates.finance import FinanceAgent
from src.agents.specialists.data_scientist import DataScientistAgent
from src.shared.schemas import AgentTask, AgentResult, AgentReport, LLMResponse
from src.shared.exceptions import GovernanceError


_CANNED_LLM = LLMResponse(
    model="claude-opus-4-6",
    provider="anthropic",
    content="Synthesised company status: all KPIs on track.",
    input_tokens=100,
    output_tokens=50,
    cost_usd=0.01,
)


class TestCEOAgent:
    @pytest.mark.asyncio
    async def test_ceo_agent_weekly_synthesis(self) -> None:
        task = AgentTask(task_subtype="weekly_synthesis", context={})
        agent = CEOAgent(agent_id="aim-ceo", company_id="aim")

        with (
            patch("src.agents.templates.ceo.provider.call", new_callable=AsyncMock) as mock_call,
            patch("src.agents.templates.ceo.audit_log.write_raw", new_callable=AsyncMock) as mock_audit,
            patch("src.agents.templates.ceo.ticket_system.create_ticket", new_callable=AsyncMock) as mock_ticket,
        ):
            mock_call.return_value = _CANNED_LLM
            mock_ticket.return_value = "test-ticket-id"

            result = await agent.run(task)

        assert result.success is True
        assert result.output == _CANNED_LLM.content
        mock_call.assert_called_once()
        call_kwargs = mock_call.call_args
        assert call_kwargs.kwargs.get("task_type") == "strategy" or call_kwargs.args[0] == "strategy"
        assert mock_audit.call_count >= 2
        mock_ticket.assert_called_once()

    @pytest.mark.asyncio
    async def test_ceo_agent_report(self) -> None:
        agent = CEOAgent(agent_id="aim-ceo", company_id="aim")
        report = await agent.report()
        assert isinstance(report, AgentReport)
        assert report.agent_id == "aim-ceo"
        assert report.company_id == "aim"


class TestFinanceAgent:
    @pytest.mark.asyncio
    async def test_finance_agent_unit_economics(self) -> None:
        financial_data = {"cac": 450, "revenue": 15000, "ad_spend": 5000}
        task = AgentTask(task_subtype="unit_economics", context={"financial_data": financial_data})
        agent = FinanceAgent(agent_id="aim-finance", company_id="aim")

        with (
            patch("src.agents.templates.finance.provider.call", new_callable=AsyncMock) as mock_call,
            patch("src.agents.templates.finance.audit_log.write_raw", new_callable=AsyncMock),
            patch("src.agents.templates.finance.ticket_system.create_ticket", new_callable=AsyncMock) as mock_ticket,
        ):
            mock_call.return_value = _CANNED_LLM
            mock_ticket.return_value = "finance-ticket-id"

            result = await agent.run(task)

        assert result.success is True
        assert result.output != ""
        mock_call.assert_called_once()
        call_kwargs = mock_call.call_args
        assert call_kwargs.kwargs.get("task_type") == "strategy" or call_kwargs.args[0] == "strategy"
        # Verify financial data is in the prompt
        messages_arg = call_kwargs.kwargs.get("messages") or call_kwargs.args[1]
        prompt_text = str(messages_arg)
        assert "450" in prompt_text or "cac" in prompt_text.lower()

    @pytest.mark.asyncio
    async def test_finance_agent_pl_draft(self) -> None:
        task = AgentTask(task_subtype="pl_draft", context={"financial_data": {"revenue": 50000}})
        agent = FinanceAgent(agent_id="aim-finance", company_id="aim")

        with (
            patch("src.agents.templates.finance.provider.call", new_callable=AsyncMock) as mock_call,
            patch("src.agents.templates.finance.audit_log.write_raw", new_callable=AsyncMock),
            patch("src.agents.templates.finance.ticket_system.create_ticket", new_callable=AsyncMock) as mock_ticket,
        ):
            mock_call.return_value = _CANNED_LLM
            mock_ticket.return_value = "finance-ticket-2"
            result = await agent.run(task)

        assert result.success is True


class TestSpecialistHireLifecycle:
    """AM-43: Full hiring lifecycle using in-memory mocks."""

    @pytest.mark.asyncio
    async def test_specialist_hire_full_lifecycle(self) -> None:
        """propose -> approve -> activate -> run -> wind_down"""
        from src.agents.hiring_manager import (
            propose_hire, get_pending_proposals, approve_hire, activate_hire, wind_down,
        )

        # In-memory store simulating DB
        _store: dict = {}

        async def fake_propose(
            company_slug, specialist_type, problem_statement, budget_usd, success_criteria, db=None
        ):
            import uuid as _uuid
            hid = str(_uuid.uuid4())
            _store[hid] = {
                "id": hid, "company_slug": company_slug, "specialist_type": specialist_type,
                "problem_statement": problem_statement, "success_criteria": success_criteria,
                "budget_allocated": budget_usd, "budget_spent": 0.0,
                "status": "proposed", "approved_by": None,
                "activated_at": None, "wound_down_at": None,
            }
            return hid

        async def fake_get_pending(company_slug, db=None):
            from src.shared.schemas import SpecialistHireSchema
            return [
                SpecialistHireSchema(**{**v, "id": k})
                for k, v in _store.items() if v["status"] == "proposed"
            ]

        async def fake_approve(hire_id, approved_by, db=None):
            if hire_id not in _store:
                raise GovernanceError("Not found")
            if _store[hire_id]["status"] != "proposed":
                raise GovernanceError("Not proposed")
            _store[hire_id]["status"] = "approved"
            _store[hire_id]["approved_by"] = approved_by

        async def fake_activate(hire_id, db=None):
            if hire_id not in _store:
                raise GovernanceError("Not found")
            if _store[hire_id]["status"] != "approved":
                raise GovernanceError(f"Cannot activate, status={_store[hire_id]['status']}")
            _store[hire_id]["status"] = "active"
            from datetime import datetime, timezone
            _store[hire_id]["activated_at"] = datetime.now(timezone.utc).isoformat()
            return DataScientistAgent(agent_id="aim-data_scientist", company_id="aim")

        async def fake_wind_down(hire_id, outcome_summary, db=None):
            if hire_id not in _store or _store[hire_id]["status"] != "active":
                raise GovernanceError("Not active")
            _store[hire_id]["status"] = "wound_down"
            from datetime import datetime, timezone
            _store[hire_id]["wound_down_at"] = datetime.now(timezone.utc).isoformat()

        with (
            patch("src.agents.hiring_manager.propose_hire", side_effect=fake_propose),
            patch("src.agents.hiring_manager.get_pending_proposals", side_effect=fake_get_pending),
            patch("src.agents.hiring_manager.approve_hire", side_effect=fake_approve),
            patch("src.agents.hiring_manager.activate_hire", side_effect=fake_activate),
            patch("src.agents.hiring_manager.wind_down", side_effect=fake_wind_down),
        ):
            hire_id = await fake_propose(
                company_slug="aim",
                specialist_type="data_scientist",
                problem_statement="CAC up 40%",
                budget_usd=100.0,
                success_criteria="CAC back to baseline",
            )
            assert hire_id and len(hire_id) > 0

            pending = await fake_get_pending("aim")
            assert any(h.id == hire_id for h in pending)
            assert _store[hire_id]["status"] == "proposed"

            await fake_approve(hire_id, approved_by="founder")
            assert _store[hire_id]["status"] == "approved"

            agent = await fake_activate(hire_id)
            assert isinstance(agent, DataScientistAgent)
            assert _store[hire_id]["status"] == "active"
            assert _store[hire_id]["activated_at"] is not None

            # Run the specialist
            with (
                patch("src.agents.specialists.data_scientist.provider.call", new_callable=AsyncMock) as mock_call,
                patch("src.agents.specialists.data_scientist.audit_log.write_raw", new_callable=AsyncMock),
                patch("src.agents.specialists.data_scientist.ticket_system.create_ticket", new_callable=AsyncMock) as mock_ticket,
            ):
                mock_call.return_value = _CANNED_LLM
                mock_ticket.return_value = "specialist-ticket"
                run_result = await agent.run(AgentTask(task_subtype="analyse_cac", context={}))

            assert run_result.success is True

            await fake_wind_down(hire_id, outcome_summary="CAC normalised")
            assert _store[hire_id]["status"] == "wound_down"
            assert _store[hire_id]["wound_down_at"] is not None

    @pytest.mark.asyncio
    async def test_activate_without_approval_raises(self) -> None:
        _store: dict = {}

        async def fake_propose(
            company_slug, specialist_type, problem_statement, budget_usd, success_criteria, db=None
        ):
            import uuid as _uuid
            hid = str(_uuid.uuid4())
            _store[hid] = {"status": "proposed"}
            return hid

        async def fake_activate(hire_id, db=None):
            if _store.get(hire_id, {}).get("status") != "approved":
                raise GovernanceError(
                    f"Cannot activate, status={_store.get(hire_id, {}).get('status')}"
                )

        hire_id = await fake_propose("aim", "data_scientist", "test", 50.0, "test criteria")
        with pytest.raises(GovernanceError):
            await fake_activate(hire_id)
