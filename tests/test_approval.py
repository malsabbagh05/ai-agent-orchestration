"""Tests for the human approval gate."""

from __future__ import annotations

import pytest

from refund_agent.domain.states import BusinessOutcome, PauseReason, RunStatus, StepStatus
from refund_agent.orchestration import Orchestrator
from refund_agent.persistence import RunStore
from refund_agent.tools import MockCaseContextTools


def test_approval_pause_happens_before_refund_step(tmp_path) -> None:
    database_path = tmp_path / "runs.sqlite3"
    store = RunStore(database_path)
    orchestrator = Orchestrator(store, MockCaseContextTools())

    paused = orchestrator.start_run("REQ-1001")
    run_id = paused["run"]["run_id"]

    assert paused["run"]["status"] == RunStatus.PAUSED.value
    assert paused["run"]["pause_reason"] == PauseReason.APPROVAL.value
    assert paused["steps"][2]["status"] == StepStatus.PAUSED.value
    assert paused["steps"][2]["result"] is None

    approved = orchestrator.approve(run_id, "approve")
    assert approved["run"]["status"] == RunStatus.RUNNING.value
    assert approved["run"]["pause_data"] == {"approval": "approve"}
    assert approved["steps"][2]["status"] == StepStatus.RUNNING.value
    assert orchestrator.approve(run_id, "approve")["run"]["status"] == "running"
    with pytest.raises(ValueError):
        orchestrator.approve(run_id, "reject")
    store.close()


def test_rejection_completes_without_entering_refund_action(tmp_path) -> None:
    database_path = tmp_path / "runs.sqlite3"
    store = RunStore(database_path)
    orchestrator = Orchestrator(store, MockCaseContextTools())
    run_id = orchestrator.start_run("REQ-1001")["run"]["run_id"]

    rejected = orchestrator.approve(run_id, "reject")

    assert rejected["run"]["status"] == RunStatus.COMPLETED.value
    assert rejected["run"]["business_outcome"] == BusinessOutcome.REJECTED.value
    assert rejected["steps"][2]["status"] == StepStatus.COMPLETED.value
    assert rejected["steps"][2]["result"] == {"decision": "reject"}
    store.close()


def test_ineligible_request_skips_approval(tmp_path) -> None:
    old_order = {
        "order_id": "ORD-1001",
        "customer_id": "CUST-1001",
        "order_date": "2020-01-01",
        "amount": 100.0,
        "currency": "USD",
    }
    database_path = tmp_path / "runs.sqlite3"
    store = RunStore(database_path)
    orchestrator = Orchestrator(
        store,
        MockCaseContextTools(orders={"ORD-1001": old_order}),
    )

    completed = orchestrator.start_run("REQ-1001")

    assert completed["run"]["status"] == RunStatus.COMPLETED.value
    assert completed["run"]["business_outcome"] == BusinessOutcome.INELIGIBLE.value
    assert completed["steps"][2]["status"] == StepStatus.SKIPPED.value
    store.close()
