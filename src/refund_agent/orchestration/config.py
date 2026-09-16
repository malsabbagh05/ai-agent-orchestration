"""Execution limits and retry settings."""

from dataclasses import dataclass


@dataclass(frozen=True)
class OrchestratorConfig:
    """Keep every run finite and retries predictable."""

    max_steps: int = 10
    max_tool_calls: int = 20
    max_attempts: int = 3
    retry_delay_seconds: float = 0.05

    def __post_init__(self) -> None:
        if self.max_steps < 1 or self.max_tool_calls < 1 or self.max_attempts < 1:
            raise ValueError("execution limits must be at least 1")
        if self.retry_delay_seconds < 0:
            raise ValueError("retry delay cannot be negative")
