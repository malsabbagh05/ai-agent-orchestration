"""JSON-ready views of persisted orchestration records."""

from __future__ import annotations

from typing import Any

from ..domain.records import RunRecord, StepRecord


def run_to_dict(run: RunRecord) -> dict[str, Any]:
    """Convert a run record to the public snapshot shape."""

    return {
        "run_id": run.run_id,
        "request_id": run.request_id,
        "status": run.status.value,
        "business_outcome": run.business_outcome.value if run.business_outcome else None,
        "pause_reason": run.pause_reason.value if run.pause_reason else None,
        "pause_data": run.pause_data,
        "input_data": run.input_data,
        "created_at": run.created_at,
        "updated_at": run.updated_at,
    }


def step_to_dict(step: StepRecord) -> dict[str, Any]:
    """Convert a step record to the public snapshot shape."""

    return {
        "run_id": step.run_id,
        "step_number": step.step_number,
        "name": step.name,
        "status": step.status.value,
        "pause_reason": step.pause_reason.value if step.pause_reason else None,
        "result": step.result,
        "started_at": step.started_at,
        "completed_at": step.completed_at,
    }
