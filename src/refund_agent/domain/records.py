"""Small immutable records returned by the persistence layer."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from .states import BusinessOutcome, PauseReason, RunStatus, StepStatus


def utc_now() -> str:
    """Return a sortable UTC timestamp."""

    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass(frozen=True)
class RunRecord:
    """Persisted state for one workflow run."""

    run_id: str
    request_id: str
    status: RunStatus
    business_outcome: BusinessOutcome | None
    pause_reason: PauseReason | None
    pause_data: dict[str, Any]
    input_data: dict[str, Any]
    error_type: str | None
    error_message: str | None
    tool_calls: int
    max_steps: int
    max_tool_calls: int
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class StepRecord:
    """Persisted state for one workflow step."""

    run_id: str
    step_number: int
    name: str
    status: StepStatus
    pause_reason: PauseReason | None
    result: dict[str, Any] | None
    attempt_count: int
    tool_name: str | None
    idempotency_key: str | None
    error_type: str | None
    error_message: str | None
    started_at: str | None
    completed_at: str | None


@dataclass(frozen=True)
class TraceRecord:
    """One structured execution event."""

    trace_id: int
    run_id: str
    step_number: int | None
    step_name: str | None
    event: str
    status: str
    timestamp: str
    tool_name: str | None
    pause_reason: PauseReason | None
    retry_attempt: int | None
    retry_limit: int | None
    error_type: str | None
    error_message: str | None
    details: dict[str, Any]
