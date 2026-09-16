"""Durable execution trace storage."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from ..domain.records import TraceRecord, utc_now
from ..domain.states import PauseReason
from .mappers import trace_from_row


class TraceStore:
    """Append and read structured events for one run."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def append(
        self,
        *,
        run_id: str,
        step_number: int | None,
        step_name: str | None,
        event: str,
        status: str,
        tool_name: str | None = None,
        pause_reason: PauseReason | None = None,
        retry_attempt: int | None = None,
        retry_limit: int | None = None,
        error_type: str | None = None,
        error_message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Append one event without storing tool payloads or secrets."""

        with self.connection:
            self.connection.execute(
                """
                INSERT INTO trace (run_id, step_number, step_name, event, status, timestamp,
                    tool_name, pause_reason, retry_attempt, retry_limit, error_type,
                    error_message, details)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    step_number,
                    step_name,
                    event,
                    status,
                    utc_now(),
                    tool_name,
                    pause_reason.value if pause_reason else None,
                    retry_attempt,
                    retry_limit,
                    error_type,
                    error_message,
                    json.dumps(details or {}, sort_keys=True),
                ),
            )

    def get(self, run_id: str) -> list[TraceRecord]:
        """Return events in append order."""

        rows = self.connection.execute(
            "SELECT * FROM trace WHERE run_id = ? ORDER BY trace_id", (run_id,)
        ).fetchall()
        return [trace_from_row(row) for row in rows]
