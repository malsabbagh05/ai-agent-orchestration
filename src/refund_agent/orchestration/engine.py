"""The first small execution boundary around durable run state."""

from __future__ import annotations

import uuid
from typing import Any

from ..domain.records import utc_now
from ..domain.states import BusinessOutcome, PauseReason, RunStatus, StepStatus
from ..eligibility import EligibilityAgent
from ..persistence import RunStore
from ..tools.interfaces import RefundWorkflowTools
from .refund_step import issue_refund
from .steps import WORKFLOW_STEPS
from .views import run_to_dict, step_to_dict


class Orchestrator:
    """Run the currently implemented workflow steps and persist their checkpoints."""

    def __init__(
        self,
        store: RunStore,
        tools: RefundWorkflowTools,
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
        assessment = self.store.get_steps(run_id)[1].result
        if assessment is None:
            raise ValueError("Eligibility result is missing.")
        if assessment["eligible"]:
            self._pause_for_approval(run_id)
        else:
            self._skip_refund_step(run_id)
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

    def _pause_for_approval(self, run_id: str) -> None:
        """Checkpoint the approval gate before the refund action exists."""

        self.store.update_step(
            run_id,
            3,
            status=StepStatus.RUNNING,
            started_at=utc_now(),
        )
        self.store.update_step(
            run_id,
            3,
            status=StepStatus.PAUSED,
            pause_reason=PauseReason.APPROVAL,
        )
        self.store.update_run(
            run_id,
            status=RunStatus.PAUSED,
            pause_reason=PauseReason.APPROVAL,
            pause_data={"required_step": 3},
        )

    def _skip_refund_step(self, run_id: str) -> None:
        """Complete an ineligible request without entering the approval gate."""

        self.store.update_step(
            run_id,
            3,
            status=StepStatus.SKIPPED,
            completed_at=utc_now(),
        )
        self.store.update_run(
            run_id,
            status=RunStatus.COMPLETED,
            business_outcome=BusinessOutcome.INELIGIBLE,
        )

    def approve(self, run_id: str, decision: str) -> dict[str, Any]:
        """Record an approval decision and leave approved work at its checkpoint."""

        if decision not in {"approve", "reject"}:
            raise ValueError("decision must be 'approve' or 'reject'")

        run = self.store.get_run(run_id)
        step = self.store.get_steps(run_id)[2]
        recorded = step.result.get("decision") if step.result else run.pause_data.get("approval")
        if recorded is not None:
            if recorded != decision:
                raise ValueError("A different approval decision was already recorded.")
            return self.inspect_run(run_id)
        if run.status != RunStatus.PAUSED or run.pause_reason != PauseReason.APPROVAL:
            raise ValueError("The run is not waiting for approval.")

        if decision == "reject":
            self.store.update_step(
                run_id,
                3,
                status=StepStatus.COMPLETED,
                result={"decision": "reject"},
                pause_reason=None,
                completed_at=utc_now(),
            )
            self.store.update_run(
                run_id,
                status=RunStatus.COMPLETED,
                business_outcome=BusinessOutcome.REJECTED,
            )
            return self.inspect_run(run_id)

        self.store.update_step(
            run_id,
            3,
            status=StepStatus.RUNNING,
            pause_reason=None,
        )
        self.store.update_run(
            run_id,
            status=RunStatus.RUNNING,
            pause_data={"approval": "approve"},
        )
        issue_refund(self.store, self.tools, run_id)
        return self.inspect_run(run_id)

    def inspect_run(self, run_id: str) -> dict[str, Any]:
        """Return the run and its ordered steps as JSON-ready dictionaries."""

        run = self.store.get_run(run_id)
        steps = self.store.get_steps(run_id)
        return {
            "run": run_to_dict(run),
            "steps": [step_to_dict(step) for step in steps],
        }
