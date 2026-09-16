"""Tests for the deterministic refund-policy assessment."""

from datetime import date

from refund_agent.eligibility import EligibilityAgent


def make_context(*, order_date: str = "2026-09-06", customer_id: str = "CUST-1001", refunds=None):
    return {
        "support_request": {"customer_id": "CUST-1001", "order_id": "ORD-1001"},
        "order": {
            "order_id": "ORD-1001",
            "customer_id": customer_id,
            "order_date": order_date,
            "amount": 100.0,
            "currency": "USD",
        },
        "refund_history": {"refunds": [] if refunds is None else refunds},
    }


def test_recent_order_without_refund_is_eligible() -> None:
    assessment = EligibilityAgent(today=date(2026, 9, 16)).assess(make_context())

    assert assessment.eligible is True
    assert assessment.amount == 100.0
    assert "within 30 days" in assessment.reason


def test_old_order_is_ineligible() -> None:
    assessment = EligibilityAgent(today=date(2026, 9, 16)).assess(
        make_context(order_date="2026-07-01")
    )

    assert assessment.eligible is False
    assert "outside" in assessment.reason


def test_existing_refund_is_ineligible() -> None:
    assessment = EligibilityAgent(today=date(2026, 9, 16)).assess(
        make_context(refunds=[{"refund_id": "REF-1"}])
    )

    assert assessment.eligible is False
    assert "already has a refund" in assessment.reason
