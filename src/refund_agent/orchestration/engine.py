"""The first small execution boundary around durable run state."""

from __future__ import annotations

import uuid
from typing import Any

from ..domain.records import RunRecord, StepRecord, utc_now
from ..domain.states import RunStatus, StepStatus
from ..eligibility import EligibilityAgent
from ..persistence import RunStore
from ..tools.interfaces import CaseContextTools

WORKFLOW_STEPS = ("collect_case_context", "assess_eligibility")


class Orchestrator:
    """Run the currently implemented workflow steps and persist their checkpoints."""

    def __init__(
        self,
        store: RunStore,
        tools: CaseContextTools,
        agent: EligibilityAgent | None = None,
    ) -> None:
        self.store = store
        self.tools = tools
        self.agent = agent or EligibilityAgent()

    def start_run(self, request_id: str) -> dict[str, Any]:
        """Create a run and execute its first workflow step."""

        if not request_id.strip():
            raise ValueError("request_id cannot be empty")

        run_id = uuid.uuid4().hex
        self.store.create_run(
            run_id=run_id,
            request_id=request_id,
            step_names=WORKFLOW_STEPS,
            input_data={"request_id": request_id},
        )
        self.store.update_run(run_id, status=RunStatus.RUNNING)
        self.store.update_step(
            run_id,
            1,
            status=StepStatus.RUNNING,
            started_at=utc_now(),
        )
        self._collect_case_context(run_id)
        self._assess_eligibility(run_id)
        return self.inspect_run(run_id)

    def _collect_case_context(self, run_id: str) -> None:
        """Read and checkpoint all read-only inputs for the current run."""

        request_id = self.store.get_run(run_id).request_id
        support_request = self.tools.get_support_request(request_id)
        order_id = support_request["order_id"]
        order = self.tools.get_order(order_id)
        refund_history = self.tools.get_refund_history(order_id)
        self.store.update_step(
            run_id,
            1,
            status=StepStatus.COMPLETED,
            result={
                "support_request": support_request,
                "order": order,
                "refund_history": refund_history,
            },
            completed_at=utc_now(),
        )

    def _assess_eligibility(self, run_id: str) -> None:
        """Assess the saved context and checkpoint the recommendation."""

        self.store.update_step(
            run_id,
            2,
            status=StepStatus.RUNNING,
            started_at=utc_now(),
        )
        context = self.store.get_steps(run_id)[0].result
        if context is None:
            raise ValueError("Case context is missing.")
        assessment = self.agent.assess(context)
        self.store.update_step(
            run_id,
            2,
            status=StepStatus.COMPLETED,
            result={
                "eligible": assessment.eligible,
                "reason": assessment.reason,
                "amount": assessment.amount,
                "currency": assessment.currency,
            },
            completed_at=utc_now(),
        )

    def inspect_run(self, run_id: str) -> dict[str, Any]:
        """Return the run and its ordered steps as JSON-ready dictionaries."""

        run = self.store.get_run(run_id)
        steps = self.store.get_steps(run_id)
        return {
            "run": self._run_to_dict(run),
            "steps": [self._step_to_dict(step) for step in steps],
        }

    @staticmethod
    def _run_to_dict(run: RunRecord) -> dict[str, Any]:
        return {
            "run_id": run.run_id,
            "request_id": run.request_id,
            "status": run.status.value,
            "input_data": run.input_data,
            "created_at": run.created_at,
            "updated_at": run.updated_at,
        }

    @staticmethod
    def _step_to_dict(step: StepRecord) -> dict[str, Any]:
        return {
            "run_id": step.run_id,
            "step_number": step.step_number,
            "name": step.name,
            "status": step.status.value,
            "result": step.result,
            "started_at": step.started_at,
            "completed_at": step.completed_at,
        }
