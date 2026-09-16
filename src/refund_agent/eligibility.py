"""Deterministic refund-policy assessment for the refund workflow."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any


@dataclass(frozen=True)
class EligibilityAssessment:
    """Policy recommendation recorded for a refund request."""

    eligible: bool
    reason: str
    amount: float
    currency: str


class EligibilityAgent:
    """Evaluate the documented refund policy without performing side effects."""

    def __init__(self, *, today: date | None = None) -> None:
        self.today = today or datetime.now(UTC).date()

    def assess(self, context: dict[str, Any]) -> EligibilityAssessment:
        """Return a recommendation based on customer ownership, age, and refund history."""

        request = context["support_request"]
        order = context["order"]
        history = context["refund_history"]
        amount = float(order["amount"])
        currency = order["currency"]

        if request["customer_id"] != order["customer_id"]:
            return self._ineligible(
                "The order does not belong to the requesting customer.", amount, currency
            )

        age_days = (self.today - date.fromisoformat(order["order_date"])).days
        if age_days > 30:
            return self._ineligible(
                "The order is outside the 30-day refund window.", amount, currency
            )

        if history.get("refunds"):
            return self._ineligible("The order already has a refund.", amount, currency)

        return EligibilityAssessment(
            eligible=True,
            reason="The order is within 30 days and has no previous refund.",
            amount=amount,
            currency=currency,
        )

    @staticmethod
    def _ineligible(reason: str, amount: float, currency: str) -> EligibilityAssessment:
        return EligibilityAssessment(False, reason, amount, currency)
