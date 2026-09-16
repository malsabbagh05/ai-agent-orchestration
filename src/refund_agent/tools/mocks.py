"""Deterministic support-request tool for local runs and tests."""

from __future__ import annotations

from typing import Any

DEFAULT_SUPPORT_REQUESTS = {
    "REQ-1001": {
        "request_id": "REQ-1001",
        "customer_id": "CUST-1001",
        "order_id": "ORD-1001",
        "reason": "Item arrived damaged",
    }
}


class MockSupportRequestReader:
    """Return fixed support data without contacting an external service."""

    def __init__(self, support_requests: dict[str, dict[str, Any]] | None = None) -> None:
        self.support_requests = (
            DEFAULT_SUPPORT_REQUESTS if support_requests is None else support_requests
        )
        self.calls: list[str] = []

    def get_support_request(self, request_id: str) -> dict[str, Any]:
        """Return a copy so a workflow cannot mutate the tool's fixture."""

        self.calls.append(request_id)
        try:
            return dict(self.support_requests[request_id])
        except KeyError as exc:
            raise KeyError(f"Support request '{request_id}' was not found.") from exc
