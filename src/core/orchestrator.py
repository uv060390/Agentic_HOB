"""
src/core/orchestrator.py  (AM-98)

Multi-agent workflow engine.
Defines named workflows as directed sequences of agent steps where each
step's output is passed as context["prev_output"] to the next step.
All inter-agent coordination routes through here — agents never call
each other directly.
"""

from __future__ import annotations

import logging
import uuid as _uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from src.shared.exceptions import WorkflowError

logger = logging.getLogger(__name__)


class WorkflowStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


@dataclass
class WorkflowStep:
    agent_template: str  # e.g. "engineer", "data_scientist"
    task_subtype: str    # e.g. "build_scraper", "rank_creatives"
    context: dict[str, Any] = field(default_factory=dict)  # static inputs


@dataclass
class Workflow:
    name: str
    steps: list[WorkflowStep]
    description: str = ""


@dataclass
class WorkflowRun:
    run_id: str
    workflow_name: str
    company_slug: str
    status: WorkflowStatus
    parent_ticket_id: str | None
    step_outputs: list[dict[str, Any]]
    started_at: str
    completed_at: str | None = None
    error: str | None = None


# ── Workflow registry ──────────────────────────────────────────────────────────
# All known multi-agent workflows. Add new workflows here.
WORKFLOW_REGISTRY: dict[str, Workflow] = {
    "creative_optimisation": Workflow(
        name="creative_optimisation",
        description=(
            "Scrape competitor ads via Apify → rank by predicted CTR → "
            "replicate top performers with brand assets → evaluate quality"
        ),
        steps=[
            WorkflowStep("engineer", "build_scraper", {"target": "meta_ads_library"}),
            WorkflowStep("data_scientist", "rank_creatives", {}),
            WorkflowStep("creative", "replicate_top_ads", {}),
            WorkflowStep("optimizer", "evaluate_quality", {}),
        ],
    ),
    "competitor_intelligence": Workflow(
        name="competitor_intelligence",
        description=(
            "Scan competitor ads and market benchmarks → analyse spend patterns "
            "→ generate informed campaign brief for CMO"
        ),
        steps=[
            WorkflowStep("scout", "competitor_scan", {}),
            WorkflowStep("data_analyst", "attribution_analysis", {}),
            WorkflowStep("cmo", "campaign_brief", {}),
        ],
    ),
}


async def run_workflow(
    workflow_name: str,
    company_slug: str,
    initial_context: dict[str, Any] | None = None,
    *,
    db: Any = None,
) -> WorkflowRun:
    """
    Execute a named workflow for a brand.

    Each step receives the previous step's AgentResult.output as
    context["prev_output"]. The first step additionally receives
    initial_context merged in.

    A parent ticket is created for the whole run and closed on completion.
    Raises WorkflowError if the workflow is unknown or any step fails.
    """
    from src.agents.registry import get_agent_instance
    from src.core import ticket_system
    from src.shared.schemas import AgentTask

    if workflow_name not in WORKFLOW_REGISTRY:
        raise WorkflowError(f"Unknown workflow: '{workflow_name}'")

    workflow = WORKFLOW_REGISTRY[workflow_name]
    run_id = str(_uuid.uuid4())
    started_at = datetime.now(timezone.utc).isoformat()

    logger.info(
        "Workflow '%s' starting run %s for company '%s'",
        workflow_name, run_id, company_slug,
    )

    # Create parent ticket for the whole workflow run
    parent_ticket_id: str | None = None
    try:
        parent_ticket_id = await ticket_system.create_ticket(
            company_slug=company_slug,
            agent_slug="orchestrator",
            summary=f"Workflow: {workflow_name}",
            description=workflow.description,
            task_type="workflow",
            db=db,
        )
    except Exception as exc:
        logger.warning("Could not create parent ticket for workflow %s: %s", workflow_name, exc)

    step_outputs: list[dict[str, Any]] = []
    prev_output: str = ""

    for i, step in enumerate(workflow.steps):
        logger.info(
            "Workflow '%s' step %d/%d: %s.%s",
            workflow_name, i + 1, len(workflow.steps),
            step.agent_template, step.task_subtype,
        )

        step_context: dict[str, Any] = {
            **step.context,
            "prev_output": prev_output,
            "workflow_run_id": run_id,
        }
        if initial_context and i == 0:
            step_context.update(initial_context)

        try:
            agent = await get_agent_instance(step.agent_template, company_slug, db=db)
            task = AgentTask(
                task_subtype=step.task_subtype,
                context=step_context,
                ticket_id=parent_ticket_id,
            )
            result = await agent.run(task)
            prev_output = result.output
            step_outputs.append({
                "step": i,
                "agent": step.agent_template,
                "task_subtype": step.task_subtype,
                "success": result.success,
                "output": result.output,
            })

            if not result.success:
                raise WorkflowError(
                    f"Step {i} ({step.agent_template}.{step.task_subtype}) failed: {result.output}"
                )

        except WorkflowError:
            raise
        except Exception as exc:
            raise WorkflowError(
                f"Step {i} ({step.agent_template}.{step.task_subtype}) raised: {exc}"
            ) from exc

    completed_at = datetime.now(timezone.utc).isoformat()

    if parent_ticket_id:
        try:
            await ticket_system.close_ticket(
                parent_ticket_id,
                resolution=f"Workflow '{workflow_name}' completed — {len(workflow.steps)} steps.",
                db=db,
            )
        except Exception as exc:
            logger.warning("Could not close parent ticket %s: %s", parent_ticket_id, exc)

    logger.info("Workflow '%s' run %s completed", workflow_name, run_id)

    return WorkflowRun(
        run_id=run_id,
        workflow_name=workflow_name,
        company_slug=company_slug,
        status=WorkflowStatus.completed,
        parent_ticket_id=parent_ticket_id,
        step_outputs=step_outputs,
        started_at=started_at,
        completed_at=completed_at,
    )


def list_workflows() -> list[str]:
    """Return names of all registered workflows."""
    return list(WORKFLOW_REGISTRY.keys())


def get_workflow(name: str) -> Workflow:
    """Return workflow definition by name. Raises WorkflowError if unknown."""
    if name not in WORKFLOW_REGISTRY:
        raise WorkflowError(f"Unknown workflow: '{name}'")
    return WORKFLOW_REGISTRY[name]
