"""Tests for durable persistence and schema migration."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from refund_agent.domain.states import RunStatus, StepStatus
from refund_agent.persistence import RunStore


def test_run_and_step_checkpoints_survive_reopening_database(tmp_path) -> None:
    database = tmp_path / "runs.sqlite3"
    store = RunStore(database)
    created = store.create_run(
        run_id="run-1",
        request_id="REQ-1001",
        step_names=("collect_case_context",),
        input_data={"request_id": "REQ-1001"},
    )

    assert created.status is RunStatus.PENDING
    assert store.get_steps("run-1")[0].status is StepStatus.PENDING

    store.update_run("run-1", status=RunStatus.RUNNING)
    started_at = datetime.now(UTC).isoformat(timespec="seconds")
    store.update_step(
        "run-1",
        1,
        status=StepStatus.COMPLETED,
        result={"order_id": "ORD-1001"},
        started_at=started_at,
        completed_at=started_at,
    )
    store.close()

    reopened = RunStore(database)
    assert reopened.get_run("run-1").status is RunStatus.RUNNING
    step = reopened.get_steps("run-1")[0]
    assert step.status is StepStatus.COMPLETED
    assert step.result == {"order_id": "ORD-1001"}
    assert step.completed_at == started_at
    reopened.close()


def test_existing_first_slice_database_is_migrated(tmp_path) -> None:
    """A database created before trace and reliability fields remains readable."""

    database = tmp_path / "legacy.sqlite3"
    connection = sqlite3.connect(database)
    connection.executescript(
        """
        CREATE TABLE runs (
            run_id TEXT PRIMARY KEY,
            request_id TEXT NOT NULL,
            status TEXT NOT NULL,
            input_data TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE steps (
            run_id TEXT NOT NULL,
            step_number INTEGER NOT NULL,
            name TEXT NOT NULL,
            status TEXT NOT NULL,
            result TEXT,
            started_at TEXT,
            completed_at TEXT,
            PRIMARY KEY (run_id, step_number)
        );
        CREATE TABLE idempotency (
            idempotency_key TEXT PRIMARY KEY,
            action TEXT NOT NULL,
            result TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )
    connection.commit()
    connection.close()

    store = RunStore(database)

    columns = {row["name"] for row in store.connection.execute("PRAGMA table_info(runs)")}
    assert {"pause_data", "max_tool_calls", "error_message"} <= columns
    assert (
        store.connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'trace'"
        ).fetchone()
        is not None
    )
    store.close()
