"""Step handlers for the refund workflow."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..domain.records import utc_now
from ..domain.states import BusinessOutcome, PauseReason, StepStatus

if TYPE_CHECKING:
    from .runner import ExecutionRunner


def collect_case_context(runner: ExecutionRunner, run_id: str) -> None:
    """Read and checkpoint the support request, order, and refund history."""

    step = runner.start_step(run_id, 1)
    request_id = runner.store.get_run(run_id).request_id
    support_request = runner.call_tool(
        run_id, step, "get_support_request", lambda: runner.tools.get_support_request(request_id)
    )
    order_id = support_request["order_id"]
    order = runner.call_tool(run_id, step, "get_order", lambda: runner.tools.get_order(order_id))
    history = runner.call_tool(
        run_id, step, "get_refund_history", lambda: runner.tools.get_refund_history(order_id)
    )
    result = {"support_request": support_request, "order": order, "refund_history": history}
    runner.store.update_step(
        run_id, 1, status=StepStatus.COMPLETED, result=result, completed_at=utc_now()
    )
    runner.record(run_id, 1, "step_completed", StepStatus.COMPLETED.value)


def assess_eligibility(runner: ExecutionRunner, run_id: str) -> None:
    """Assess the persisted case context."""

    runner.start_step(run_id, 2)
    context = runner.store.get_steps(run_id)[0].result
    if context is None:
        raise ValueError("Case context is missing.")
    assessment = runner.agent.assess(context)
    result = {
        "eligible": assessment.eligible,
        "reason": assessment.reason,
        "amount": assessment.amount,
        "currency": assessment.currency,
    }
    runner.store.update_step(
        run_id, 2, status=StepStatus.COMPLETED, result=result, completed_at=utc_now()
    )
    runner.record(run_id, 2, "step_completed", StepStatus.COMPLETED.value)


def approve_and_issue_refund(runner: ExecutionRunner, run_id: str) -> None:
    """Pause for approval or issue the approved refund."""

    step = runner.start_step(run_id, 3)
    assessment = runner.store.get_steps(run_id)[1].result
    if assessment is None:
        raise ValueError("Eligibility result is missing.")
    if not assessment["eligible"]:
        runner.store.update_step(run_id, 3, status=StepStatus.SKIPPED, completed_at=utc_now())
        runner.record(run_id, 3, "step_skipped", StepStatus.SKIPPED.value)
        runner.skip_pending(run_id, 4)
        runner.complete_run(run_id, BusinessOutcome.INELIGIBLE)
        return

    approval = runner.store.get_run(run_id).pause_data.get("approval")
    if approval != "approve":
        # The approval pause is persisted before any financial side effect.
        runner.pause(run_id, step, PauseReason.APPROVAL, {"required_step": 3})
        return

    context = runner.store.get_steps(run_id)[0].result
    if context is None:
        raise ValueError("Refund context is missing.")
    order = context["order"]
    key = f"refund:{runner.store.get_run(run_id).request_id}"
    refund = runner.call_tool(
        run_id,
        step,
        "issue_refund",
        lambda: runner.tools.issue_refund(
            order_id=order["order_id"],
            amount=float(assessment["amount"]),
            currency=assessment["currency"],
            idempotency_key=key,
        ),
        idempotency_key=key,
    )
    runner.store.update_step(
        run_id,
        3,
        status=StepStatus.COMPLETED,
        result={"decision": "approve", "idempotency_key": key, "refund": refund},
        completed_at=utc_now(),
    )
    runner.record(run_id, 3, "step_completed", StepStatus.COMPLETED.value, tool_name="issue_refund")
    # The refund result is checkpointed before waiting for the provider event.
    runner.pause(
        run_id,
        runner.start_step(run_id, 4),
        PauseReason.PROVIDER_CONFIRMATION,
        {
            "required_step": 4,
            "expected_event": "refund.confirmed",
            "refund_id": refund["refund_id"],
        },
    )


def await_provider_confirmation(runner: ExecutionRunner, run_id: str) -> None:
    """Create the provider wait if recovery reaches this step directly."""

    refund_result = runner.store.get_steps(run_id)[2].result or {}
    refund = refund_result.get("refund", {})
    runner.pause(
        run_id,
        runner.start_step(run_id, 4),
        PauseReason.PROVIDER_CONFIRMATION,
        {
            "required_step": 4,
            "expected_event": "refund.confirmed",
            "refund_id": refund.get("refund_id"),
        },
    )


def notify_customer(runner: ExecutionRunner, run_id: str) -> None:
    """Send the confirmed refund notification exactly once."""

    step = runner.start_step(run_id, 5)
    run = runner.store.get_run(run_id)
    context = runner.store.get_steps(run_id)[0].result
    refund_step = runner.store.get_steps(run_id)[2].result
    if context is None or refund_step is None:
        raise ValueError("Notification context is missing.")
    refund = refund_step["refund"]
    key = f"notification:{run.request_id}"
    message = (
        f"Your refund of {refund['amount']:.2f} {refund['currency']} for order "
        f"{refund['order_id']} has been confirmed."
    )
    notification = runner.call_tool(
        run_id,
        step,
        "send_customer_notification",
        lambda: runner.tools.send_customer_notification(
            customer_id=context["support_request"]["customer_id"],
            message=message,
            idempotency_key=key,
        ),
        idempotency_key=key,
    )
    runner.store.update_step(
        run_id,
        5,
        status=StepStatus.COMPLETED,
        result={"message": message, "idempotency_key": key, "notification": notification},
        completed_at=utc_now(),
    )
    runner.record(
        run_id,
        5,
        "step_completed",
        StepStatus.COMPLETED.value,
        tool_name="send_customer_notification",
    )
    runner.complete_run(run_id, BusinessOutcome.REFUNDED)
