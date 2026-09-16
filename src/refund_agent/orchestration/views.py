"""JSON-ready views of persisted orchestration records."""

from __future__ import annotations

from typing import Any

from ..domain.records import RunRecord, StepRecord, TraceRecord


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
        "error_type": run.error_type,
        "error_message": run.error_message,
        "tool_calls": run.tool_calls,
        "max_steps": run.max_steps,
        "max_tool_calls": run.max_tool_calls,
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
        "attempt_count": step.attempt_count,
        "tool_name": step.tool_name,
        "idempotency_key": step.idempotency_key,
        "error_type": step.error_type,
        "error_message": step.error_message,
        "started_at": step.started_at,
        "completed_at": step.completed_at,
    }


def trace_to_dict(trace: TraceRecord) -> dict[str, Any]:
    """Convert a trace record to a JSON-ready event."""

    return {
        "trace_id": trace.trace_id,
        "run_id": trace.run_id,
        "step_number": trace.step_number,
        "step_name": trace.step_name,
        "event": trace.event,
        "status": trace.status,
        "timestamp": trace.timestamp,
        "tool_name": trace.tool_name,
        "pause_reason": trace.pause_reason.value if trace.pause_reason else None,
        "retry_attempt": trace.retry_attempt,
        "retry_limit": trace.retry_limit,
        "error_type": trace.error_type,
        "error_message": trace.error_message,
        "details": trace.details,
    }
