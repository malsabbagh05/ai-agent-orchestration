"""Execution loop, retries, traces, and failure checkpoints."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ..domain.records import StepRecord, utc_now
from ..domain.states import BusinessOutcome, RunStatus, StepStatus
from ..eligibility import EligibilityAgent
from ..errors import ExecutionLimitError, RetryableToolError, ToolError
from ..persistence import RunStore
from ..tools.interfaces import RefundWorkflowTools
from .config import OrchestratorConfig
from .runner_support import RunnerPersistenceMixin
from .steps import WORKFLOW_STEPS

TERMINAL_RUNS = {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED}
TERMINAL_STEPS = {
    StepStatus.COMPLETED,
    StepStatus.FAILED,
    StepStatus.SKIPPED,
    StepStatus.CANCELLED,
}


@dataclass
class ExecutionRunner(RunnerPersistenceMixin):
    """Execute steps using injected durable services."""

    store: RunStore
    tools: RefundWorkflowTools
    agent: EligibilityAgent
    config: OrchestratorConfig
    sleep: Callable[[float], None] = time.sleep

    def run_until_pause(self, run_id: str) -> None:
        """Continue from the first unfinished step until pause or terminal state."""

        while True:
            run = self.store.get_run(run_id)
            if run.status in TERMINAL_RUNS or run.status == RunStatus.PAUSED:
                return
            steps = self.store.get_steps(run_id)
            current = next((step for step in steps if step.status not in TERMINAL_STEPS), None)
            if current is None:
                self.complete_run(run_id, BusinessOutcome.REFUNDED)
                return
            if current.step_number > run.max_steps:
                self.fail_run(run_id, current, ExecutionLimitError("maximum step limit exceeded"))
                return
            try:
                self._execute_step(run_id, current)
            except Exception as exc:  # noqa: BLE001 - persist unexpected step failures
                self.fail_run(run_id, current, exc)
                return

    def _execute_step(self, run_id: str, step: StepRecord) -> None:
        from . import workflow

        handlers = {
            WORKFLOW_STEPS[0]: workflow.collect_case_context,
            WORKFLOW_STEPS[1]: workflow.assess_eligibility,
            WORKFLOW_STEPS[2]: workflow.approve_and_issue_refund,
            WORKFLOW_STEPS[3]: workflow.await_provider_confirmation,
            WORKFLOW_STEPS[4]: workflow.notify_customer,
        }
        try:
            handler = handlers[step.name]
        except KeyError as exc:
            raise ValueError(f"Unknown workflow step '{step.name}'.") from exc
        handler(self, run_id)

    def start_step(self, run_id: str, number: int) -> StepRecord:
        """Move a pending step to running, preserving running state on recovery."""

        step = self.store.get_steps(run_id)[number - 1]
        if step.status == StepStatus.PENDING:
            step = self.store.update_step(
                run_id, number, status=StepStatus.RUNNING, started_at=utc_now()
            )
            self.record(run_id, number, "step_started", StepStatus.RUNNING.value)
        return step

    def call_tool(
        self,
        run_id: str,
        step: StepRecord,
        tool_name: str,
        operation: Callable[[], dict[str, Any]],
        *,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Call an allowlisted tool with bounded exponential retry."""

        allowed = {
            "get_support_request",
            "get_order",
            "get_refund_history",
            "issue_refund",
            "send_customer_notification",
        }
        if tool_name not in allowed:
            raise ValueError(f"Tool '{tool_name}' is not allowed.")
        if idempotency_key:
            # A replay can finish from the stored result without calling the tool again.
            existing = self.store.idempotency.get(idempotency_key)
            if existing is not None:
                self.record(
                    run_id,
                    step.step_number,
                    "tool_call_deduplicated",
                    StepStatus.RUNNING.value,
                    tool_name=tool_name,
                    details={"idempotency_key": idempotency_key},
                )
                return existing
        for attempt in range(1, self.config.max_attempts + 1):
            # Count retries before invoking the tool so every attempt is bounded.
            self.store.reserve_tool_call(run_id)
            self.store.update_step(
                run_id,
                step.step_number,
                attempt_count=attempt,
                tool_name=tool_name,
                idempotency_key=idempotency_key,
            )
            self.record(
                run_id,
                step.step_number,
                "tool_call_started",
                StepStatus.RUNNING.value,
                tool_name=tool_name,
                retry_attempt=attempt,
                retry_limit=self.config.max_attempts,
                details={"idempotency_key": idempotency_key} if idempotency_key else {},
            )
            try:
                result = operation()
            except RetryableToolError as exc:
                self.record(
                    run_id,
                    step.step_number,
                    "tool_retryable_failure",
                    "retrying" if attempt < self.config.max_attempts else "failed",
                    tool_name=tool_name,
                    retry_attempt=attempt,
                    retry_limit=self.config.max_attempts,
                    error=exc,
                )
                if attempt == self.config.max_attempts:
                    raise
                self.sleep(self.config.retry_delay_seconds * (2 ** (attempt - 1)))
            except ToolError as exc:
                self.record(
                    run_id,
                    step.step_number,
                    "tool_non_retryable_failure",
                    "failed",
                    tool_name=tool_name,
                    retry_attempt=attempt,
                    retry_limit=self.config.max_attempts,
                    error=exc,
                )
                raise
            except Exception as exc:
                self.record(
                    run_id,
                    step.step_number,
                    "tool_non_retryable_failure",
                    "failed",
                    tool_name=tool_name,
                    retry_attempt=attempt,
                    retry_limit=self.config.max_attempts,
                    error=exc,
                )
                raise
            else:
                self.record(
                    run_id,
                    step.step_number,
                    "tool_call_succeeded",
                    StepStatus.RUNNING.value,
                    tool_name=tool_name,
                    retry_attempt=attempt,
                    retry_limit=self.config.max_attempts,
                    details={"idempotency_key": idempotency_key} if idempotency_key else {},
                )
                return result
        raise AssertionError("retry loop did not return or raise")
