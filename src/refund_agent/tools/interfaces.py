"""Interfaces for tools used by workflow steps."""

from typing import Any, Protocol


class SupportRequestReader(Protocol):
    """Read the support request that starts a refund workflow."""

    def get_support_request(self, request_id: str) -> dict[str, Any]: ...
