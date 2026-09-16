"""Small immutable records returned by the persistence layer."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from .states import RunStatus, StepStatus


def utc_now() -> str:
    """Return a sortable UTC timestamp."""

    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass(frozen=True)
class RunRecord:
    """Persisted state for one workflow run."""

    run_id: str
    request_id: str
    status: RunStatus
    input_data: dict[str, Any]
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class StepRecord:
    """Persisted state for one workflow step."""

    run_id: str
    step_number: int
    name: str
    status: StepStatus
    result: dict[str, Any] | None
    started_at: str | None
    completed_at: str | None
