"""Public command boundary for durable refund workflow runs."""

from __future__ import annotations

import uuid
from typing import Any

from ..domain.records import utc_now
from ..domain.states import BusinessOutcome, PauseReason, RunStatus, StepStatus
from ..eligibility import EligibilityAgent
from ..errors import InvalidInputError, InvalidTransitionError
from ..persistence import RunStore
from ..tools.interfaces import RefundWorkflowTools
from .config import OrchestratorConfig
from .runner import TERMINAL_RUNS, TERMINAL_STEPS, ExecutionRunner
from .steps import WORKFLOW_STEPS
from .views import run_to_dict, step_to_dict, trace_to_dict


class Orchestrator:
    """Validate commands and delegate execution to the durable runner."""

    def __init__(
        self,
        store: RunStore,
        tools: RefundWorkflowTools,
        agent: EligibilityAgent | None = None,
        config: OrchestratorConfig | None = None,
    ) -> None:
        self.store = store
        self.tools = tools
        self.agent = agent or EligibilityAgent()
        self.config = config or OrchestratorConfig()
        self.runner = ExecutionRunner(store, tools, self.agent, self.config)

    def start_run(self, request_id: str) -> dict[str, Any]:
        """Create a run, execute until its first pause, and return its snapshot."""

        if not request_id.strip():
            raise InvalidInputError("request_id cannot be empty")
        run_id = uuid.uuid4().hex
        self.store.create_run(
            run_id=run_id,
            request_id=request_id,
            step_names=WORKFLOW_STEPS,
            input_data={"request_id": request_id},
            max_steps=self.config.max_steps,
            max_tool_calls=self.config.max_tool_calls,
        )
        self.runner.record(run_id, None, "run_created", RunStatus.PENDING.value)
        self._transition(run_id, RunStatus.RUNNING, "run_started")
        self.runner.run_until_pause(run_id)
        return self.inspect_run(run_id)

    def inspect_run(self, run_id: str) -> dict[str, Any]:
        """Return all persisted run and step fields in a JSON-ready shape."""

        return {
            "run": run_to_dict(self.store.get_run(run_id)),
            "steps": [step_to_dict(step) for step in self.store.get_steps(run_id)],
        }

    def approve(self, run_id: str, decision: str) -> dict[str, Any]:
        """Record an approval decision and continue approved work."""

        if decision not in {"approve", "reject"}:
            raise InvalidInputError("decision must be 'approve' or 'reject'")
        run = self.store.get_run(run_id)
        step = self.store.get_steps(run_id)[2]
        recorded = step.result.get("decision") if step.result else run.pause_data.get("approval")
        if recorded is not None:
            if recorded != decision:
                raise InvalidTransitionError("A different approval decision was already recorded.")
            return self.inspect_run(run_id)
        if run.status != RunStatus.PAUSED or run.pause_reason != PauseReason.APPROVAL:
            raise InvalidTransitionError("The run is not waiting for approval.")
        self.runner.record(
            run_id,
            3,
            "approval_recorded",
            RunStatus.RUNNING.value,
            details={"decision": decision},
        )
        if decision == "reject":
            # Rejection is a terminal business outcome, so later work is skipped.
            self.store.update_step(
                run_id,
                3,
                status=StepStatus.COMPLETED,
                pause_reason=None,
                result={"decision": decision},
                completed_at=utc_now(),
            )
            self._skip_pending(run_id, start_at=4)
            self.runner.complete_run(run_id, BusinessOutcome.REJECTED)
            return self.inspect_run(run_id)
        self.store.update_step(run_id, 3, status=StepStatus.RUNNING, pause_reason=None)
        self.store.update_run(
            run_id,
            status=RunStatus.RUNNING,
            pause_reason=None,
            pause_data={"approval": decision},
        )
        self.runner.run_until_pause(run_id)
        return self.inspect_run(run_id)

    def resume(self, run_id: str, event: str) -> dict[str, Any]:
        """Apply the expected provider event and continue the run."""

        if not event.strip():
            raise InvalidInputError("event cannot be empty")
        run = self.store.get_run(run_id)
        if run.status in TERMINAL_RUNS:
            return self.inspect_run(run_id)
        if run.status == RunStatus.RUNNING:
            self.runner.run_until_pause(run_id)
            return self.inspect_run(run_id)
        if run.status != RunStatus.PAUSED or run.pause_reason != PauseReason.PROVIDER_CONFIRMATION:
            raise InvalidTransitionError("The run is not waiting for provider confirmation.")
        expected = run.pause_data.get("expected_event", "refund.confirmed")
        if event != expected:
            raise InvalidInputError(f"unexpected event '{event}', expected '{expected}'")
        step = self.store.get_steps(run_id)[3]
        if step.status == StepStatus.PAUSED:
            self.store.update_step(
                run_id,
                4,
                status=StepStatus.COMPLETED,
                pause_reason=None,
                result={"event": event},
                completed_at=utc_now(),
            )
            self.runner.record(
                run_id,
                4,
                "provider_event_received",
                StepStatus.COMPLETED.value,
                details={"event": event},
            )
        self.store.update_run(
            run_id,
            status=RunStatus.RUNNING,
            pause_reason=None,
            pause_data={"provider_event": event},
        )
        self.runner.run_until_pause(run_id)
        return self.inspect_run(run_id)

    def cancel(self, run_id: str) -> dict[str, Any]:
        """Cancel a non-terminal run and mark all future steps cancelled."""

        run = self.store.get_run(run_id)
        if run.status in TERMINAL_RUNS:
            return self.inspect_run(run_id)
        for step in self.store.get_steps(run_id):
            if step.status not in TERMINAL_STEPS:
                self.store.update_step(
                    run_id,
                    step.step_number,
                    status=StepStatus.CANCELLED,
                    pause_reason=None,
                    completed_at=utc_now(),
                )
                self.runner.record(
                    run_id,
                    step.step_number,
                    "step_cancelled",
                    StepStatus.CANCELLED.value,
                )
        self._transition(run_id, RunStatus.CANCELLED, "run_cancelled")
        return self.inspect_run(run_id)

    def trace(self, run_id: str) -> list[dict[str, Any]]:
        """Return the append-only trace for a run."""

        self.store.get_run(run_id)
        return [trace_to_dict(item) for item in self.store.trace.get(run_id)]

    def _skip_pending(self, run_id: str, *, start_at: int) -> None:
        for step in self.store.get_steps(run_id):
            if step.step_number >= start_at and step.status == StepStatus.PENDING:
                self.store.update_step(
                    run_id,
                    step.step_number,
                    status=StepStatus.SKIPPED,
                    completed_at=utc_now(),
                )
                self.runner.record(
                    run_id,
                    step.step_number,
                    "step_skipped",
                    StepStatus.SKIPPED.value,
                )

    def _transition(self, run_id: str, status: RunStatus, event: str) -> None:
        self.store.update_run(run_id, status=status)
        self.runner.record(run_id, None, event, status.value)
