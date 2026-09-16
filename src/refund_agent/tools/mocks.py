"""Deterministic read tools for local runs and tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from ..errors import NonRetryableToolError, ToolError
from ..persistence import RunStore

DEFAULT_SUPPORT_REQUESTS = {
    "REQ-1001": {
        "request_id": "REQ-1001",
        "customer_id": "CUST-1001",
        "order_id": "ORD-1001",
        "reason": "Item arrived damaged",
    }
}


def default_orders() -> dict[str, dict[str, Any]]:
    """Return an order placed ten days ago for the happy-path request."""

    order_date = datetime.now(UTC).date() - timedelta(days=10)
    return {
        "ORD-1001": {
            "order_id": "ORD-1001",
            "customer_id": "CUST-1001",
            "order_date": order_date.isoformat(),
            "amount": 100.0,
            "currency": "USD",
        }
    }


class MockCaseContextTools:
    """Return fixed support, order, and refund-history data."""

    def __init__(
        self,
        *,
        support_requests: dict[str, dict[str, Any]] | None = None,
        orders: dict[str, dict[str, Any]] | None = None,
        refund_histories: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self.support_requests = (
            DEFAULT_SUPPORT_REQUESTS if support_requests is None else support_requests
        )
        self.orders = default_orders() if orders is None else orders
        self.refund_histories = (
            {"ORD-1001": {"refunds": []}} if refund_histories is None else refund_histories
        )
        self.calls: list[tuple[str, str]] = []

    def get_support_request(self, request_id: str) -> dict[str, Any]:
        """Return a support request copy."""

        self.calls.append(("get_support_request", request_id))
        return self._copy_for(self.support_requests, request_id, "Support request")

    def get_order(self, order_id: str) -> dict[str, Any]:
        """Return an order copy."""

        self.calls.append(("get_order", order_id))
        return self._copy_for(self.orders, order_id, "Order")

    def get_refund_history(self, order_id: str) -> dict[str, Any]:
        """Return refund history copy."""

        self.calls.append(("get_refund_history", order_id))
        return self._copy_for(self.refund_histories, order_id, "Refund history")

    @staticmethod
    def _copy_for(values: dict[str, dict[str, Any]], key: str, label: str) -> dict[str, Any]:
        try:
            return dict(values[key])
        except KeyError as exc:
            raise KeyError(f"{label} '{key}' was not found.") from exc


class MockRefundTools(MockCaseContextTools):
    """Add a durable, observable refund action to the read-tool mock."""

    def __init__(
        self,
        store: RunStore,
        *,
        failures: dict[str, list[ToolError]] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.store = store
        self.failures = {name: list(errors) for name, errors in (failures or {}).items()}
        self.invocations: dict[str, int] = {}
        self.refund_effects: list[dict[str, Any]] = []
        self.notification_effects: list[dict[str, Any]] = []

    def _before_action(self, name: str) -> None:
        self.invocations[name] = self.invocations.get(name, 0) + 1
        pending = self.failures.get(name, [])
        if pending:
            raise pending.pop(0)

    def get_support_request(self, request_id: str) -> dict[str, Any]:
        """Read a support request with optional failure injection."""

        self._before_action("get_support_request")
        return super().get_support_request(request_id)

    def get_order(self, order_id: str) -> dict[str, Any]:
        """Read an order with optional failure injection."""

        self._before_action("get_order")
        return super().get_order(order_id)

    def get_refund_history(self, order_id: str) -> dict[str, Any]:
        """Read refund history with optional failure injection."""

        self._before_action("get_refund_history")
        return super().get_refund_history(order_id)

    def issue_refund(
        self,
        *,
        order_id: str,
        amount: float,
        currency: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        """Record one refund effect and reuse its result for duplicate keys."""

        existing = self.store.idempotency.get(idempotency_key)
        if existing is not None:
            return {**existing, "deduplicated": True}
        self._before_action("issue_refund")
        if order_id not in self.orders:
            raise NonRetryableToolError(f"Order '{order_id}' was not found.")
        result = {
            "refund_id": f"REF-{order_id}",
            "order_id": order_id,
            "amount": amount,
            "currency": currency,
            "status": "submitted",
        }
        stored = self.store.idempotency.record(
            key=idempotency_key,
            action="issue_refund",
            result=result,
        )
        self.refund_effects.append(stored)
        return stored

    def send_customer_notification(
        self,
        *,
        customer_id: str,
        message: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        """Record one notification and reuse its result for duplicate keys."""

        existing = self.store.idempotency.get(idempotency_key)
        if existing is not None:
            return {**existing, "deduplicated": True}
        self._before_action("send_customer_notification")
        result = {"customer_id": customer_id, "message": message, "status": "sent"}
        stored = self.store.idempotency.record(
            key=idempotency_key,
            action="send_customer_notification",
            result=result,
        )
        self.notification_effects.append(stored)
        return stored
