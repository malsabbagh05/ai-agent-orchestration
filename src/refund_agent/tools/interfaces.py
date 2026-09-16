"""Interfaces for tools used by workflow steps."""

from typing import Any, Protocol


class SupportRequestReader(Protocol):
    """Read the support request that starts a refund workflow."""

    def get_support_request(self, request_id: str) -> dict[str, Any]: ...


class OrderReader(Protocol):
    """Read order details referenced by a support request."""

    def get_order(self, order_id: str) -> dict[str, Any]: ...


class RefundHistoryReader(Protocol):
    """Read previous refunds for an order."""

    def get_refund_history(self, order_id: str) -> dict[str, Any]: ...


class CaseContextTools(SupportRequestReader, OrderReader, RefundHistoryReader, Protocol):
    """Read-only tools needed to assemble the refund case context."""
