"""SQLite-backed storage for runs, steps, traces, and action keys."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from ..domain.records import RunRecord, StepRecord, utc_now
from ..domain.states import BusinessOutcome, PauseReason, RunStatus, StepStatus
from ..errors import ExecutionLimitError
from .idempotency import IdempotencyStore
from .mappers import run_from_row, step_from_row
from .migrations import migrate
from .schema import SCHEMA
from .trace import TraceStore


class RunStore:
    """Persist orchestration state in a local SQLite database."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = str(database_path)
        if self.database_path != ":memory:":
            Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.database_path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        # WAL keeps checkpoints readable across short-lived CLI processes.
        self.connection.execute(
            "PRAGMA journal_mode = WAL"
        ) if self.database_path != ":memory:" else None
        self.connection.executescript(SCHEMA)
        migrate(self.connection)
        self.connection.commit()
        self.idempotency = IdempotencyStore(self.connection)
        self.trace = TraceStore(self.connection)

    def close(self) -> None:
        """Close the database connection."""

        self.connection.close()

    def create_run(
        self,
        *,
        run_id: str,
        request_id: str,
        step_names: tuple[str, ...],
        input_data: dict[str, Any],
        max_steps: int = 10,
        max_tool_calls: int = 20,
    ) -> RunRecord:
        """Create a pending run and its pending steps."""

        now = utc_now()
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO runs (run_id, request_id, status, input_data, max_steps,
                    max_tool_calls, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    request_id,
                    RunStatus.PENDING.value,
                    json.dumps(input_data),
                    max_steps,
                    max_tool_calls,
                    now,
                    now,
                ),
            )
            self.connection.executemany(
                "INSERT INTO steps (run_id, step_number, name, status) VALUES (?, ?, ?, ?)",
                [
                    (run_id, n, name, StepStatus.PENDING.value)
                    for n, name in enumerate(step_names, 1)
                ],
            )
        return self.get_run(run_id)

    def get_run(self, run_id: str) -> RunRecord:
        """Load a run by ID."""

        row = self.connection.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        if row is None:
            raise KeyError(f"Run '{run_id}' was not found.")
        return run_from_row(row)

    def get_steps(self, run_id: str) -> list[StepRecord]:
        """Load a run's steps in workflow order."""

        self.get_run(run_id)
        rows = self.connection.execute(
            "SELECT * FROM steps WHERE run_id = ? ORDER BY step_number", (run_id,)
        ).fetchall()
        return [step_from_row(row) for row in rows]

    def update_run(
        self,
        run_id: str,
        *,
        status: RunStatus,
        business_outcome: BusinessOutcome | None = None,
        pause_reason: PauseReason | None = None,
        pause_data: dict[str, Any] | None = None,
        error_type: str | None = None,
        error_message: str | None = None,
    ) -> RunRecord:
        """Persist a run transition and metadata."""

        with self.connection:
            cursor = self.connection.execute(
                """
                UPDATE runs SET status = ?, business_outcome = ?, pause_reason = ?,
                    pause_data = ?, error_type = ?, error_message = ?, updated_at = ?
                WHERE run_id = ?
                """,
                (
                    status.value,
                    business_outcome.value if business_outcome else None,
                    pause_reason.value if pause_reason else None,
                    json.dumps(pause_data or {}),
                    error_type,
                    error_message,
                    utc_now(),
                    run_id,
                ),
            )
        if cursor.rowcount != 1:
            raise KeyError(f"Run '{run_id}' was not found.")
        return self.get_run(run_id)

    def update_step(self, run_id: str, step_number: int, **fields: Any) -> StepRecord:
        """Persist a step's mutable fields."""

        allowed = {
            "status",
            "pause_reason",
            "result",
            "attempt_count",
            "tool_name",
            "idempotency_key",
            "error_type",
            "error_message",
            "started_at",
            "completed_at",
        }
        unknown = set(fields) - allowed
        if unknown:
            raise ValueError(f"Unsupported step fields: {sorted(unknown)}")
        values = {
            name: (
                value.value
                if isinstance(value, (StepStatus, PauseReason))
                else json.dumps(value)
                if name == "result" and value is not None
                else value
            )
            for name, value in fields.items()
        }
        if not values:
            return self.get_steps(run_id)[step_number - 1]
        assignments = ", ".join(f"{name} = :{name}" for name in values)
        values.update(run_id=run_id, step_number=step_number)
        with self.connection:
            cursor = self.connection.execute(
                f"UPDATE steps SET {assignments} WHERE run_id = :run_id AND step_number = :step_number",
                values,
            )
        if cursor.rowcount != 1:
            raise KeyError(f"Step {step_number} for run '{run_id}' was not found.")
        return self.get_steps(run_id)[step_number - 1]

    def reserve_tool_call(self, run_id: str) -> None:
        """Reserve a call and enforce the configured per-run limit."""

        with self.connection:
            row = self.connection.execute(
                "SELECT tool_calls, max_tool_calls FROM runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            if row is None:
                raise KeyError(f"Run '{run_id}' was not found.")
            if row["tool_calls"] >= row["max_tool_calls"]:
                raise ExecutionLimitError(f"Run '{run_id}' exceeded its tool-call limit.")
            self.connection.execute(
                "UPDATE runs SET tool_calls = tool_calls + 1, updated_at = ? WHERE run_id = ?",
                (utc_now(), run_id),
            )
