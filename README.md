# Gaia Assignment: Durable Refund Support Agent

This project implements a durable orchestration layer for a customer-support refund workflow.
The agent retrieves case information, evaluates refund eligibility, pauses for human approval,
issues a refund, waits for provider confirmation, and notifies the customer.

The first implementation is intentionally small and uses mocked tools so the reliability behavior
can be tested without external services.

## Documentation

- [Workflow specification](docs/workflow-spec.md)
- [Initial acceptance scenario](docs/scenarios.md)
- [Run and step state model](docs/state-model.md)
- [Architecture and design decisions](docs/architecture.md)

## Development setup

Create a virtual environment and install the development tools:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

The CLI scaffold can be checked with:

```bash
python -m refund_agent --help
pytest
```

The workflow commands are being implemented on the `feat/orchestrator-core` branch.
