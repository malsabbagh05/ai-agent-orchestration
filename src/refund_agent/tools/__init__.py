"""Tool interfaces and deterministic implementations."""

from .interfaces import SupportRequestReader
from .mocks import MockSupportRequestReader

__all__ = ["MockSupportRequestReader", "SupportRequestReader"]
