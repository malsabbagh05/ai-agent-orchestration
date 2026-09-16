"""Tests for the first execution slice."""

from __future__ import annotations

from refund_agent.domain.states import RunStatus, StepStatus
from refund_agent.orchestration import Orchestrator
from refund_agent.persistence import RunStore


def test_start_marks_the_first_step_running(tmp_path) -> None:
    store = RunStore(tmp_path / "runs.sqlite3")
    orchestrator = Orchestrator(store)

    snapshot = orchestrator.start_run("REQ-1001")

    assert snapshot["run"]["status"] == RunStatus.RUNNING.value
    assert snapshot["run"]["request_id"] == "REQ-1001"
    assert snapshot["steps"] == [
        {
            "run_id": snapshot["run"]["run_id"],
            "step_number": 1,
            "name": "collect_case_context",
            "status": StepStatus.RUNNING.value,
            "result": None,
            "started_at": snapshot["steps"][0]["started_at"],
            "completed_at": None,
        }
    ]
    assert snapshot["steps"][0]["started_at"] is not None
    store.close()


def test_inspect_reads_the_same_run_after_reopening(tmp_path) -> None:
    database = tmp_path / "runs.sqlite3"
    store = RunStore(database)
    run_id = Orchestrator(store).start_run("REQ-1001")["run"]["run_id"]
    store.close()

    reopened = RunStore(database)
    snapshot = Orchestrator(reopened).inspect_run(run_id)

    assert snapshot["run"]["run_id"] == run_id
    assert snapshot["steps"][0]["status"] == StepStatus.RUNNING.value
    reopened.close()
