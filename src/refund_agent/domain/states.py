"""Lifecycle states used by persisted runs and steps."""

from enum import Enum


class RunStatus(str, Enum):
    """Lifecycle of a complete workflow run."""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepStatus(str, Enum):
    """Lifecycle of one workflow step."""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class PauseReason(str, Enum):
    """Reason a run or step is waiting for an external decision."""

    APPROVAL = "approval"


class BusinessOutcome(str, Enum):
    """Business result recorded when a run reaches a decision."""

    INELIGIBLE = "ineligible"
    REJECTED = "rejected"
