"""Execution of the approved refund action."""

from __future__ import annotations

from ..domain.records import utc_now
from ..domain.states import StepStatus
from ..persistence import RunStore
from ..tools.interfaces import RefundWorkflowTools


def issue_refund(store: RunStore, tools: RefundWorkflowTools, run_id: str) -> None:
    """Issue the full approved refund and checkpoint its result."""

    run = store.get_run(run_id)
    steps = store.get_steps(run_id)
    context = steps[0].result
    assessment = steps[1].result
    if context is None or assessment is None:
        raise ValueError("Refund context or eligibility result is missing.")

    order = context["order"]
    idempotency_key = f"refund:{run.request_id}"
    refund = tools.issue_refund(
        order_id=order["order_id"],
        amount=float(assessment["amount"]),
        currency=assessment["currency"],
        idempotency_key=idempotency_key,
    )
    store.update_step(
        run_id,
        3,
        status=StepStatus.COMPLETED,
        result={
            "decision": "approve",
            "idempotency_key": idempotency_key,
            "refund": refund,
        },
        completed_at=utc_now(),
    )
