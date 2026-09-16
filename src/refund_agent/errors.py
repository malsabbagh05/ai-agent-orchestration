"""Expected orchestration and tool failures."""


class OrchestrationError(Exception):
    """Base class for expected workflow errors."""


class ExecutionLimitError(OrchestrationError):
    """The run reached a configured step or tool-call bound."""


class InvalidTransitionError(OrchestrationError):
    """A command does not match the run's current state."""


class InvalidInputError(OrchestrationError):
    """A command contains an invalid decision or event."""


class ToolError(Exception):
    """Base class for a tool failure."""


class RetryableToolError(ToolError):
    """A temporary tool failure that may be retried."""


class NonRetryableToolError(ToolError):
    """A permanent tool failure that should fail the run."""
