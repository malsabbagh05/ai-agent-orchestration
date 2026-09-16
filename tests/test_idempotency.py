"""Tests for durable refund-action idempotency."""

from __future__ import annotations

from refund_agent.persistence import RunStore
from refund_agent.tools import MockRefundTools


def test_repeated_refund_key_returns_one_effect(tmp_path) -> None:
    database = tmp_path / "runs.sqlite3"
    store = RunStore(database)
    tools = MockRefundTools(store)

    first = tools.issue_refund(
        order_id="ORD-1001",
        amount=100.0,
        currency="USD",
        idempotency_key="refund:REQ-1001",
    )
    second = tools.issue_refund(
        order_id="ORD-1001",
        amount=100.0,
        currency="USD",
        idempotency_key="refund:REQ-1001",
    )

    assert first["refund_id"] == second["refund_id"]
    assert second["deduplicated"] is True
    assert len(tools.refund_effects) == 1
    store.close()
