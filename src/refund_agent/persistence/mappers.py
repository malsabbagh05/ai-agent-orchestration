"""Convert SQLite rows into domain records."""

from __future__ import annotations

import json
import sqlite3

from ..domain.records import RunRecord, StepRecord, TraceRecord
from ..domain.states import BusinessOutcome, PauseReason, RunStatus, StepStatus


def run_from_row(row: sqlite3.Row) -> RunRecord:
    return RunRecord(
        run_id=row["run_id"],
        request_id=row["request_id"],
        status=RunStatus(row["status"]),
        business_outcome=(
            BusinessOutcome(row["business_outcome"]) if row["business_outcome"] else None
        ),
        pause_reason=PauseReason(row["pause_reason"]) if row["pause_reason"] else None,
        pause_data=json.loads(row["pause_data"] or "{}"),
        input_data=json.loads(row["input_data"]),
        error_type=row["error_type"],
        error_message=row["error_message"],
        tool_calls=row["tool_calls"],
        max_steps=row["max_steps"],
        max_tool_calls=row["max_tool_calls"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def step_from_row(row: sqlite3.Row) -> StepRecord:
    return StepRecord(
        run_id=row["run_id"],
        step_number=row["step_number"],
        name=row["name"],
        status=StepStatus(row["status"]),
        pause_reason=PauseReason(row["pause_reason"]) if row["pause_reason"] else None,
        result=json.loads(row["result"]) if row["result"] else None,
        attempt_count=row["attempt_count"],
        tool_name=row["tool_name"],
        idempotency_key=row["idempotency_key"],
        error_type=row["error_type"],
        error_message=row["error_message"],
        started_at=row["started_at"],
        completed_at=row["completed_at"],
    )


def trace_from_row(row: sqlite3.Row) -> TraceRecord:
    return TraceRecord(
        trace_id=row["trace_id"],
        run_id=row["run_id"],
        step_number=row["step_number"],
        step_name=row["step_name"],
        event=row["event"],
        status=row["status"],
        timestamp=row["timestamp"],
        tool_name=row["tool_name"],
        pause_reason=PauseReason(row["pause_reason"]) if row["pause_reason"] else None,
        retry_attempt=row["retry_attempt"],
        retry_limit=row["retry_limit"],
        error_type=row["error_type"],
        error_message=row["error_message"],
        details=json.loads(row["details"] or "{}"),
    )
