"""The first small execution boundary around durable run state."""

from __future__ import annotations

import uuid
from typing import Any

from ..domain.records import RunRecord, StepRecord, utc_now
from ..domain.states import RunStatus, StepStatus
from ..persistence import RunStore

INITIAL_STEPS = ("collect_case_context",)


class Orchestrator:
    """Create and inspect a run without owning business tools yet."""

    def __init__(self, store: RunStore) -> None:
        self.store = store

    def start_run(self, request_id: str) -> dict[str, Any]:
        """Create a run and mark its first workflow step as running."""

        if not request_id.strip():
            raise ValueError("request_id cannot be empty")

        run_id = uuid.uuid4().hex
        self.store.create_run(
            run_id=run_id,
            request_id=request_id,
            step_names=INITIAL_STEPS,
            input_data={"request_id": request_id},
        )
        self.store.update_run(run_id, status=RunStatus.RUNNING)
        self.store.update_step(
            run_id,
            1,
            status=StepStatus.RUNNING,
            started_at=utc_now(),
        )
        return self.inspect_run(run_id)

    def inspect_run(self, run_id: str) -> dict[str, Any]:
        """Return the run and its ordered steps as JSON-ready dictionaries."""

        run = self.store.get_run(run_id)
        steps = self.store.get_steps(run_id)
        return {
            "run": self._run_to_dict(run),
            "steps": [self._step_to_dict(step) for step in steps],
        }

    @staticmethod
    def _run_to_dict(run: RunRecord) -> dict[str, Any]:
        return {
            "run_id": run.run_id,
            "request_id": run.request_id,
            "status": run.status.value,
            "input_data": run.input_data,
            "created_at": run.created_at,
            "updated_at": run.updated_at,
        }

    @staticmethod
    def _step_to_dict(step: StepRecord) -> dict[str, Any]:
        return {
            "run_id": step.run_id,
            "step_number": step.step_number,
            "name": step.name,
            "status": step.status.value,
            "result": step.result,
            "started_at": step.started_at,
            "completed_at": step.completed_at,
        }
