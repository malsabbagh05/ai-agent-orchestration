"""Reliability checks for retries, restart recovery, bounds, and trace output."""

from __future__ import annotations

import pytest

from refund_agent.domain.states import RunStatus, StepStatus
from refund_agent.errors import InvalidTransitionError, NonRetryableToolError, RetryableToolError
from refund_agent.orchestration import Orchestrator
from refund_agent.orchestration.config import OrchestratorConfig
from refund_agent.persistence import RunStore
from refund_agent.tools import MockRefundTools


def test_transient_tool_failure_is_retried_and_traced(tmp_path) -> None:
    store = RunStore(tmp_path / "runs.sqlite3")
    tools = MockRefundTools(
        store,
        failures={"get_order": [RetryableToolError("temporary provider timeout")]},
    )
    orchestrator = Orchestrator(store, tools, config=OrchestratorConfig(retry_delay_seconds=0))

    snapshot = orchestrator.start_run("REQ-1001")

    assert snapshot["run"]["status"] == "paused"
    assert tools.invocations["get_order"] == 2
    assert any(
        event["event"] == "tool_retryable_failure"
        for event in orchestrator.trace(snapshot["run"]["run_id"])
    )
    store.close()


def test_non_retryable_tool_failure_fails_run(tmp_path) -> None:
    store = RunStore(tmp_path / "runs.sqlite3")
    tools = MockRefundTools(
        store,
        failures={"get_order": [NonRetryableToolError("order service rejected request")]},
    )

    snapshot = Orchestrator(store, tools).start_run("REQ-1001")

    assert snapshot["run"]["status"] == RunStatus.FAILED.value
    assert snapshot["run"]["error_type"] == "NonRetryableToolError"
    assert snapshot["steps"][0]["status"] == "failed"
    store.close()


def test_approved_run_resumes_after_database_restart(tmp_path) -> None:
    database = tmp_path / "runs.sqlite3"
    first_store = RunStore(database)
    first = Orchestrator(first_store, MockRefundTools(first_store))
    run_id = first.start_run("REQ-1001")["run"]["run_id"]
    first_store.close()

    second_store = RunStore(database)
    second_tools = MockRefundTools(second_store)
    approved = Orchestrator(second_store, second_tools).approve(run_id, "approve")
    assert approved["run"]["pause_reason"] == "provider_confirmation"
    second_store.close()

    third_store = RunStore(database)
    third_tools = MockRefundTools(third_store)
    completed = Orchestrator(third_store, third_tools).resume(run_id, "refund.confirmed")

    assert completed["run"]["business_outcome"] == "refunded"
    assert completed["steps"][4]["status"] == "completed"
    refund_row = third_store.connection.execute(
        "SELECT COUNT(*) AS count FROM idempotency WHERE action = 'issue_refund'"
    ).fetchone()
    assert refund_row["count"] == 1
    assert len(third_tools.notification_effects) == 1
    third_store.close()


def test_recovery_deduplicates_effect_before_step_checkpoint(tmp_path) -> None:
    """A replay after a successful action cannot create a second refund."""

    database = tmp_path / "runs.sqlite3"
    first_store = RunStore(database)
    first_tools = MockRefundTools(first_store)
    orchestrator = Orchestrator(first_store, first_tools)
    run_id = orchestrator.start_run("REQ-1001")["run"]["run_id"]
    first_store.update_step(run_id, 3, status=StepStatus.RUNNING)
    first_store.update_run(run_id, status=RunStatus.RUNNING, pause_data={"approval": "approve"})
    first_tools.issue_refund(
        order_id="ORD-1001",
        amount=100.0,
        currency="USD",
        idempotency_key="refund:REQ-1001",
    )
    first_store.close()

    recovered_store = RunStore(database)
    recovered_tools = MockRefundTools(recovered_store)
    recovered = Orchestrator(recovered_store, recovered_tools)
    paused = recovered.resume(run_id, "ignored while recovering")

    assert paused["run"]["pause_reason"] == "provider_confirmation"
    assert recovered_tools.invocations.get("issue_refund", 0) == 0
    assert (
        recovered_store.connection.execute(
            "SELECT COUNT(*) AS count FROM idempotency WHERE action = 'issue_refund'"
        ).fetchone()["count"]
        == 1
    )
    recovered_store.close()


def test_repeated_resume_is_a_no_op(tmp_path) -> None:
    store = RunStore(tmp_path / "runs.sqlite3")
    tools = MockRefundTools(store)
    orchestrator = Orchestrator(store, tools)
    run_id = orchestrator.start_run("REQ-1001")["run"]["run_id"]
    orchestrator.approve(run_id, "approve")

    completed = orchestrator.resume(run_id, "refund.confirmed")
    repeated = orchestrator.resume(run_id, "refund.confirmed")

    assert repeated == completed
    assert len(tools.refund_effects) == 1
    assert len(tools.notification_effects) == 1
    store.close()


def test_tool_call_bound_fails_before_unbounded_execution(tmp_path) -> None:
    store = RunStore(tmp_path / "runs.sqlite3")
    config = OrchestratorConfig(max_tool_calls=2, retry_delay_seconds=0)

    snapshot = Orchestrator(store, MockRefundTools(store), config=config).start_run("REQ-1001")

    assert snapshot["run"]["status"] == "failed"
    assert snapshot["run"]["error_type"] == "ExecutionLimitError"
    assert snapshot["run"]["tool_calls"] == 2
    store.close()


def test_cancel_prevents_future_side_effects(tmp_path) -> None:
    store = RunStore(tmp_path / "runs.sqlite3")
    tools = MockRefundTools(store)
    orchestrator = Orchestrator(store, tools)
    run_id = orchestrator.start_run("REQ-1001")["run"]["run_id"]

    cancelled = orchestrator.cancel(run_id)

    assert cancelled["run"]["status"] == "cancelled"
    assert all(step["status"] != "pending" for step in cancelled["steps"])
    assert tools.refund_effects == []
    with pytest.raises(InvalidTransitionError):
        orchestrator.approve(run_id, "approve")
    store.close()
