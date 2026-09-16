"""Tests for the human approval gate."""

from __future__ import annotations

import pytest

from refund_agent.domain.states import BusinessOutcome, PauseReason, RunStatus, StepStatus
from refund_agent.errors import InvalidTransitionError
from refund_agent.orchestration import Orchestrator
from refund_agent.persistence import RunStore
from refund_agent.tools import MockRefundTools


def test_approval_pause_happens_before_refund_step(tmp_path) -> None:
    database_path = tmp_path / "runs.sqlite3"
    store = RunStore(database_path)
    tools = MockRefundTools(store)
    orchestrator = Orchestrator(store, tools)

    paused = orchestrator.start_run("REQ-1001")
    run_id = paused["run"]["run_id"]

    assert paused["run"]["status"] == RunStatus.PAUSED.value
    assert paused["run"]["pause_reason"] == PauseReason.APPROVAL.value
    assert paused["steps"][2]["status"] == StepStatus.PAUSED.value
    assert paused["steps"][2]["result"] is None

    approved = orchestrator.approve(run_id, "approve")
    assert approved["run"]["status"] == RunStatus.PAUSED.value
    assert approved["run"]["pause_reason"] == PauseReason.PROVIDER_CONFIRMATION.value
    assert approved["run"]["pause_data"]["expected_event"] == "refund.confirmed"
    assert approved["steps"][2]["status"] == StepStatus.COMPLETED.value
    assert approved["steps"][2]["result"]["idempotency_key"] == "refund:REQ-1001"
    assert len(tools.refund_effects) == 1
    assert orchestrator.approve(run_id, "approve")["run"]["status"] == "paused"
    assert len(tools.refund_effects) == 1
    with pytest.raises(InvalidTransitionError):
        orchestrator.approve(run_id, "reject")
    store.close()


def test_rejection_completes_without_entering_refund_action(tmp_path) -> None:
    database_path = tmp_path / "runs.sqlite3"
    store = RunStore(database_path)
    orchestrator = Orchestrator(store, MockRefundTools(store))
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
        MockRefundTools(store, orders={"ORD-1001": old_order}),
    )

    completed = orchestrator.start_run("REQ-1001")

    assert completed["run"]["status"] == RunStatus.COMPLETED.value
    assert completed["run"]["business_outcome"] == BusinessOutcome.INELIGIBLE.value
    assert completed["steps"][2]["status"] == StepStatus.SKIPPED.value
    store.close()
