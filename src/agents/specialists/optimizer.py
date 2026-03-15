"""
src/agents/specialists/optimizer.py  (AM-100)

Optimizer — meta-specialist for closed-loop creative optimisation.

Sets a measurable objective, triggers multi-agent workflows via the
orchestrator, evaluates quality against success criteria, and iterates
until the objective is met or the budget is exhausted.

The Optimizer does not execute creative work itself — it coordinates
Engineer, Data Scientist, and Creative agents through the orchestrator.

Hire trigger: Performance agent raises anomaly_alert(type=creative_underperformance)
              or CMO brand_audit finds CTR below D2C benchmark.
Reports to:   Brand CEO agent during engagement.
"""

from __future__ import annotations

from datetime import datetime, timezone

from src.agents.base_agent import BaseAgent
from src.shared.exceptions import AgentPausedError, AgentWindDownError
from src.shared.schemas import AgentReport, AgentResult, AgentTask

_SYSTEM_PROMPT = """\
You are the Optimisation Director for an Indian D2C brand.

Your role is to drive closed-loop improvement cycles:
1. Set a precise, measurable objective (e.g. "creative CTR ≥ 3.5% on 5 new ads")
2. Coordinate specialist teams to execute the improvement workflow
3. Evaluate whether the outcome meets the stated success criteria
4. Iterate if criteria are not met; wind down cleanly when they are

You are rigorous — "looks good" is not a pass. You require data.
All creative outputs must be saved to the Creative Library before you
evaluate them. Your evaluation uses predicted CTR from the Data Scientist
model, not subjective judgment.
"""


class OptimizerAgent(BaseAgent):
    """
    Meta-specialist that orchestrates multi-agent creative improvement loops.

    Coordinates Engineer (Apify scraping), Data Scientist (creative ranking),
    and Creative (brand-adapted replication) agents through the orchestrator.
    """

    def __init__(self, agent_id: str, company_id: str) -> None:
        super().__init__(agent_id, company_id, task_type="strategy")
        self._iterations_completed: int = 0
        self._objective: str = ""
        self._success_criteria: str = ""

    def get_tools(self) -> list[str]:
        return ["ticket_system", "audit_log", "google_drive", "supabase_client"]

    async def run(self, task: AgentTask) -> AgentResult:
        from src.core import audit_log, orchestrator
        from src.llm import provider

        if self.wound_down_at is not None:
            raise AgentWindDownError(self.agent_id)
        if self.is_paused:
            raise AgentPausedError(self.agent_id)

        await audit_log.write(
            agent_slug=self.agent_id,
            company_slug=self.company_id,
            action=f"optimizer.{task.task_subtype}.start",
            detail=str(task.context)[:300],
        )
        self._mark_run()

        subtype = task.task_subtype
        output: str

        if subtype == "set_objective":
            self._objective = task.context.get("objective", "improve creative CTR by 20%")
            self._success_criteria = task.context.get("success_criteria", "")
            output = (
                f"Objective set: '{self._objective}'. "
                f"Success criteria: '{self._success_criteria}'."
            )

        elif subtype == "trigger_workflow":
            workflow_name = task.context.get("workflow_name", "creative_optimisation")
            workflow_run = await orchestrator.run_workflow(
                workflow_name=workflow_name,
                company_slug=self.company_id,
                initial_context={
                    "objective": self._objective,
                    "success_criteria": self._success_criteria,
                    **{k: v for k, v in task.context.items() if k != "workflow_name"},
                },
            )
            self._iterations_completed += 1
            output = (
                f"Workflow '{workflow_name}' completed. "
                f"Run ID: {workflow_run.run_id}. "
                f"Steps executed: {len(workflow_run.step_outputs)}. "
                f"Iteration #{self._iterations_completed}."
            )

        elif subtype == "evaluate_quality":
            prev_output = task.context.get("prev_output", "No output provided.")
            messages = [
                {
                    "role": "user",
                    "content": (
                        f"{_SYSTEM_PROMPT}\n\n"
                        f"Objective: {self._objective}\n"
                        f"Success criteria: {self._success_criteria}\n\n"
                        f"Latest workflow output:\n{prev_output}\n\n"
                        "Does this output meet the success criteria? "
                        "Answer YES or NO followed by a concise 2-sentence rationale."
                    ),
                }
            ]
            response = await provider.call(
                task_type=self.task_type,
                messages=messages,
                agent_id=self.agent_id,
                company_id=self.company_id,
            )
            output = response.content

        elif subtype == "iterate_or_complete":
            evaluation = task.context.get("evaluation", "")
            if "YES" in evaluation.upper():
                self.wound_down_at = datetime.now(timezone.utc)
                output = (
                    f"Objective met after {self._iterations_completed} iteration(s). "
                    "Winding down. All outputs saved to Creative Library."
                )
            else:
                output = (
                    f"Objective not yet met. "
                    f"Triggering iteration #{self._iterations_completed + 1}. "
                    f"Evaluation: {evaluation[:200]}"
                )

        else:
            output = f"Unknown task subtype for Optimizer: '{subtype}'"

        await audit_log.write(
            agent_slug=self.agent_id,
            company_slug=self.company_id,
            action=f"optimizer.{subtype}.complete",
            detail=output[:500],
        )

        return AgentResult(success=True, output=output)

    async def report(self) -> AgentReport:
        if self.wound_down_at:
            status = f"wound_down after {self._iterations_completed} iteration(s)"
        elif self.is_paused:
            status = "paused"
        else:
            status = f"active — iteration {self._iterations_completed} — objective: {self._objective[:80]}"

        return AgentReport(
            agent_id=self.agent_id,
            company_id=self.company_id,
            last_run_at=self._last_run_at,
            open_tickets_count=0,
            status=status,
        )
