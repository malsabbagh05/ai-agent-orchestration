"""Tests for the first durable persistence slice."""

from __future__ import annotations

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
