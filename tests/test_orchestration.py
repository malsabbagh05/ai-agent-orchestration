"""Tests for the first execution slice."""

from __future__ import annotations

from refund_agent.domain.states import RunStatus, StepStatus
from refund_agent.orchestration import Orchestrator
from refund_agent.persistence import RunStore
from refund_agent.tools import MockSupportRequestReader


def test_start_completes_the_first_context_step(tmp_path) -> None:
    store = RunStore(tmp_path / "runs.sqlite3")
    tools = MockSupportRequestReader()
    orchestrator = Orchestrator(store, tools)

    snapshot = orchestrator.start_run("REQ-1001")

    assert snapshot["run"]["status"] == RunStatus.RUNNING.value
    assert snapshot["run"]["request_id"] == "REQ-1001"
    assert snapshot["steps"][0]["status"] == StepStatus.COMPLETED.value
    assert snapshot["steps"][0]["result"] == {
        "support_request": {
            "request_id": "REQ-1001",
            "customer_id": "CUST-1001",
            "order_id": "ORD-1001",
            "reason": "Item arrived damaged",
        }
    }
    assert snapshot["steps"][0]["started_at"] is not None
    assert snapshot["steps"][0]["completed_at"] is not None
    assert tools.calls == ["REQ-1001"]
    store.close()


def test_inspect_reads_the_same_run_after_reopening(tmp_path) -> None:
    database = tmp_path / "runs.sqlite3"
    store = RunStore(database)
    run_id = Orchestrator(store, MockSupportRequestReader()).start_run("REQ-1001")["run"]["run_id"]
    store.close()

    reopened = RunStore(database)
    snapshot = Orchestrator(reopened, MockSupportRequestReader()).inspect_run(run_id)

    assert snapshot["run"]["run_id"] == run_id
    assert snapshot["steps"][0]["status"] == StepStatus.COMPLETED.value
    reopened.close()
