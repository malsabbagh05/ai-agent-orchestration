"""SQLite-backed storage for run and step checkpoints."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from ..domain.records import RunRecord, StepRecord, utc_now
from ..domain.states import BusinessOutcome, PauseReason, RunStatus, StepStatus
from .schema import SCHEMA


class RunStore:
    """Persist the smallest useful unit of orchestration state."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = str(database_path)
        if self.database_path != ":memory:":
            Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.database_path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.executescript(SCHEMA)
        self._migrate_schema()
        self.connection.commit()

    def _migrate_schema(self) -> None:
        """Add fields introduced by later slices to an existing local database."""

        tables = {
            "runs": {
                "business_outcome": "TEXT",
                "pause_reason": "TEXT",
                "pause_data": "TEXT NOT NULL DEFAULT '{}'",
            },
            "steps": {"pause_reason": "TEXT"},
        }
        for table, additions in tables.items():
            columns = {
                row["name"] for row in self.connection.execute(f"PRAGMA table_info({table})")
            }
            for name, definition in additions.items():
                if name not in columns:
                    self.connection.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")

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
    ) -> RunRecord:
        """Create one pending run and its pending steps."""

        now = utc_now()
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO runs (run_id, request_id, status, input_data, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (run_id, request_id, RunStatus.PENDING.value, json.dumps(input_data), now, now),
            )
            self.connection.executemany(
                "INSERT INTO steps (run_id, step_number, name, status) VALUES (?, ?, ?, ?)",
                [
                    (run_id, number, name, StepStatus.PENDING.value)
                    for number, name in enumerate(step_names, start=1)
                ],
            )
        return self.get_run(run_id)

    def get_run(self, run_id: str) -> RunRecord:
        """Load a run by ID."""

        row = self.connection.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        if row is None:
            raise KeyError(f"Run '{run_id}' was not found.")
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
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def get_steps(self, run_id: str) -> list[StepRecord]:
        """Load all steps for a run in workflow order."""

        self.get_run(run_id)
        rows = self.connection.execute(
            "SELECT * FROM steps WHERE run_id = ? ORDER BY step_number", (run_id,)
        ).fetchall()
        return [
            StepRecord(
                run_id=row["run_id"],
                step_number=row["step_number"],
                name=row["name"],
                status=StepStatus(row["status"]),
                pause_reason=PauseReason(row["pause_reason"]) if row["pause_reason"] else None,
                result=json.loads(row["result"]) if row["result"] else None,
                started_at=row["started_at"],
                completed_at=row["completed_at"],
            )
            for row in rows
        ]

    def update_run(
        self,
        run_id: str,
        *,
        status: RunStatus,
        business_outcome: BusinessOutcome | None = None,
        pause_reason: PauseReason | None = None,
        pause_data: dict[str, Any] | None = None,
    ) -> RunRecord:
        """Persist a run status transition and its waiting metadata."""

        with self.connection:
            cursor = self.connection.execute(
                """
                UPDATE runs
                SET status = ?, business_outcome = ?, pause_reason = ?, pause_data = ?,
                    updated_at = ?
                WHERE run_id = ?
                """,
                (
                    status.value,
                    business_outcome.value if business_outcome else None,
                    pause_reason.value if pause_reason else None,
                    json.dumps(pause_data or {}),
                    utc_now(),
                    run_id,
                ),
            )
        if cursor.rowcount != 1:
            raise KeyError(f"Run '{run_id}' was not found.")
        return self.get_run(run_id)

    def update_step(
        self,
        run_id: str,
        step_number: int,
        *,
        status: StepStatus,
        pause_reason: PauseReason | None = None,
        result: dict[str, Any] | None = None,
        started_at: str | None = None,
        completed_at: str | None = None,
    ) -> StepRecord:
        """Persist a step status and optional checkpoint data."""

        with self.connection:
            cursor = self.connection.execute(
                """
                UPDATE steps
                SET status = ?, pause_reason = ?, result = ?,
                    started_at = COALESCE(?, started_at),
                    completed_at = COALESCE(?, completed_at)
                WHERE run_id = ? AND step_number = ?
                """,
                (
                    status.value,
                    pause_reason.value if pause_reason else None,
                    json.dumps(result) if result is not None else None,
                    started_at,
                    completed_at,
                    run_id,
                    step_number,
                ),
            )
        if cursor.rowcount != 1:
            raise KeyError(f"Step {step_number} for run '{run_id}' was not found.")
        return self.get_steps(run_id)[step_number - 1]
