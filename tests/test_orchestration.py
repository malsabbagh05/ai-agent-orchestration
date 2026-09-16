"""Tests for the first execution slice."""

from __future__ import annotations

from refund_agent.domain.states import RunStatus, StepStatus
from refund_agent.orchestration import Orchestrator
from refund_agent.persistence import RunStore
from refund_agent.tools import MockCaseContextTools


def test_start_completes_the_first_context_step(tmp_path) -> None:
    store = RunStore(tmp_path / "runs.sqlite3")
    tools = MockCaseContextTools()
    orchestrator = Orchestrator(store, tools)

    snapshot = orchestrator.start_run("REQ-1001")

    assert snapshot["run"]["status"] == RunStatus.PAUSED.value
    assert snapshot["run"]["pause_reason"] == "approval"
    assert snapshot["run"]["request_id"] == "REQ-1001"
    assert snapshot["steps"][0]["status"] == StepStatus.COMPLETED.value
    context = snapshot["steps"][0]["result"]
    assert context["support_request"]["order_id"] == "ORD-1001"
    assert context["order"]["customer_id"] == "CUST-1001"
    assert context["refund_history"] == {"refunds": []}
    assert snapshot["steps"][1]["name"] == "assess_eligibility"
    assert snapshot["steps"][1]["status"] == StepStatus.COMPLETED.value
    assert snapshot["steps"][1]["result"]["eligible"] is True
    assert snapshot["steps"][2]["name"] == "approve_and_issue_refund"
    assert snapshot["steps"][2]["status"] == StepStatus.PAUSED.value
    assert snapshot["steps"][2]["pause_reason"] == "approval"
    assert snapshot["steps"][0]["started_at"] is not None
    assert snapshot["steps"][0]["completed_at"] is not None
    assert tools.calls == [
        ("get_support_request", "REQ-1001"),
        ("get_order", "ORD-1001"),
        ("get_refund_history", "ORD-1001"),
    ]
    store.close()


def test_inspect_reads_the_same_run_after_reopening(tmp_path) -> None:
    database = tmp_path / "runs.sqlite3"
    store = RunStore(database)
    run_id = Orchestrator(store, MockCaseContextTools()).start_run("REQ-1001")["run"]["run_id"]
    store.close()

    reopened = RunStore(database)
    snapshot = Orchestrator(reopened, MockCaseContextTools()).inspect_run(run_id)

    assert snapshot["run"]["run_id"] == run_id
    assert snapshot["steps"][0]["status"] == StepStatus.COMPLETED.value
    assert snapshot["steps"][1]["status"] == StepStatus.COMPLETED.value
    assert snapshot["steps"][2]["status"] == StepStatus.PAUSED.value
    reopened.close()
