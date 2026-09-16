"""Persistence helpers mixed into the execution runner."""

from __future__ import annotations

from typing import Any

from ..domain.records import StepRecord, utc_now
from ..domain.states import BusinessOutcome, PauseReason, RunStatus, StepStatus


class RunnerPersistenceMixin:
    """Keep trace and terminal-state writes together and easy to review."""

    def record(
        self,
        run_id: str,
        step_number: int | None,
        event: str,
        status: str,
        *,
        error: Exception | None = None,
        **kwargs: Any,
    ) -> None:
        """Append a structured trace event."""

        step_name = None
        if step_number is not None:
            step_name = self.store.get_steps(run_id)[step_number - 1].name
        if error is not None:
            kwargs["error_type"] = type(error).__name__
            kwargs["error_message"] = str(error)
        self.store.trace.append(
            run_id=run_id,
            step_number=step_number,
            step_name=step_name,
            event=event,
            status=status,
            **kwargs,
        )

    def complete_run(self, run_id: str, outcome: BusinessOutcome) -> None:
        """Persist a successful terminal business outcome."""

        self.store.update_run(run_id, status=RunStatus.COMPLETED, business_outcome=outcome)
        self.record(
            run_id,
            None,
            "run_completed",
            RunStatus.COMPLETED.value,
            details={"business_outcome": outcome.value},
        )

    def pause(
        self, run_id: str, step: StepRecord, reason: PauseReason, data: dict[str, Any]
    ) -> None:
        """Persist both step and run pause checkpoints."""

        self.store.update_step(
            run_id, step.step_number, status=StepStatus.PAUSED, pause_reason=reason
        )
        self.store.update_run(run_id, status=RunStatus.PAUSED, pause_reason=reason, pause_data=data)
        self.record(
            run_id, step.step_number, "step_paused", StepStatus.PAUSED.value, pause_reason=reason
        )

    def skip_pending(self, run_id: str, start_at: int) -> None:
        """Mark steps after a business decision as not applicable."""

        for step in self.store.get_steps(run_id):
            if step.step_number >= start_at and step.status == StepStatus.PENDING:
                self.store.update_step(
                    run_id,
                    step.step_number,
                    status=StepStatus.SKIPPED,
                    completed_at=utc_now(),
                )
                self.record(run_id, step.step_number, "step_skipped", StepStatus.SKIPPED.value)

    def fail_run(self, run_id: str, step: StepRecord, error: Exception) -> None:
        """Persist a failed step and its terminal run error."""

        error_type, error_message = type(error).__name__, str(error)
        self.store.update_step(
            run_id,
            step.step_number,
            status=StepStatus.FAILED,
            error_type=error_type,
            error_message=error_message,
            completed_at=utc_now(),
        )
        self.record(run_id, step.step_number, "step_failed", StepStatus.FAILED.value, error=error)
        self.store.update_run(
            run_id,
            status=RunStatus.FAILED,
            error_type=error_type,
            error_message=error_message,
        )
        self.record(run_id, None, "run_failed", RunStatus.FAILED.value, error=error)
